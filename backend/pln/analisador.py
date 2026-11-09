"""
Orquestra o pipeline de PLN: texto -> seções -> lacunas -> notas.

Nota documental (0 a 5), fórmula simples e explicável:

    peso da lacuna:  alta = 3, média = 2, baixa = 1
    peso máximo:     3 x "unidades" do documento (todas com lacuna alta); unidades = o maior entre
                     o nº de seções, MIN_SECOES e 1 por FRASES_POR_UNIDADE frases (para um documento
                     longo, com poucos capítulos enormes, não ser punido só pelo tamanho)
    nota_documental = 5 x (1 - peso_total / peso_máximo)      (mínimo 0, 1 casa decimal)

A fórmula é provisória (heurística da Sprint 3) e será calibrada com as políticas de teste.
A Saúde de Compliance segue a regra do frontend: média simples de documental e prática;
sem Verificação Prática, vale só a documental.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Callable

from .extracao import dividir_secoes
from .regras import detectar_lacunas

log = logging.getLogger("autoaudit")

PESOS = {"alta": 3, "média": 2, "baixa": 1}
MIN_SECOES = 5  # evita que um documento curtíssimo dê nota extrema com uma única lacuna
FRASES_POR_UNIDADE = 10


def calcular_nota_documental(lacunas: list[dict], n_secoes: int) -> float:
    peso_total = sum(PESOS[l["severidade"]] for l in lacunas)
    peso_maximo = 3 * max(n_secoes, MIN_SECOES)
    return round(max(0.0, 5 * (1 - peso_total / peso_maximo)), 1)


def calcular_saude_compliance(documental: float, pratica: float | None) -> float:
    if pratica is None:
        return round(documental, 1)
    return round((documental + pratica) / 2, 1)


def faixa_compliance(nota: float) -> str:
    if nota >= 4:
        return "boa conformidade"
    if nota >= 3:
        return "conformidade parcial"
    if nota >= 2:
        return "baixa conformidade"
    return "crítica"


def analisar_texto(texto: str) -> dict:
    """Devolve os campos do relatório que o PLN calcula (o resto — id, data — vem do banco).

    `nota_pratica` e `verificacoes` ficam None: a Verificação Prática é a etapa seguinte.
    """
    secoes = dividir_secoes(texto)
    lacunas = detectar_lacunas(secoes)
    numeradas = [s for s in secoes if s.numero is not None]
    n_secoes = len(numeradas) or len(secoes)
    total_frases = sum(len(s.sentencas) for s in secoes)
    unidades = max(n_secoes, round(total_frases / FRASES_POR_UNIDADE))
    documental = calcular_nota_documental(lacunas, unidades)
    return {
        "nota_documental": documental,
        "nota_pratica": None,
        "saude_compliance": calcular_saude_compliance(documental, None),
        "lacunas": lacunas,
        "verificacoes": None,
        "secoes_analisadas": n_secoes,
    }


# --------------------------------------------------------------------------- busca semântica

# Similaridade mínima (cosseno) para aceitar uma norma "próxima". As notas do modelo ficam
# entre 0,5 e 0,7 até para resultados irrelevantes, então o filtro precisa ser seletivo
# (calibrado com a saída real de backend/testar_busca.py nas políticas de teste):
NOTA_MIN_FAMILIA = float(os.getenv("AUTOAUDIT_NOTA_FAMILIA", "0.45"))  # NIST, mesma família do controle da regra
NOTA_MIN_OUTRA = float(os.getenv("AUTOAUDIT_NOTA_OUTRA", "0.62"))      # NIST, outra família
NOTA_MIN_LGPD = float(os.getenv("AUTOAUDIT_NOTA_LGPD", "0.66"))        # LGPD (notas inflam: todos os artigos são parecidos)
NOTA_MIN_CIS = float(os.getenv("AUTOAUDIT_NOTA_CIS", "0.62"))          # CIS Controls v8.1.2 (a calibrar com testar_busca.py)
MAX_PROXIMAS = 2   # quantas normas "próximas" acrescentar além da referência curada
TOP_CANDIDATAS = 6  # quantos resultados do FAISS são considerados antes de filtrar


def _pares_curados(referencia: str) -> list[tuple[str, str]]:
    """Extrai (fonte, identificador) do texto da referência escrita nas regras."""
    pares: list[tuple[str, str]] = []
    for grupo in re.findall(r"NIST SP 800-53 ((?:[A-Z]{2}-\d+(?:\(\d+\))?(?:,\s*)?)+)", referencia):
        pares += [("NIST_800_53", ident) for ident in re.findall(r"[A-Z]{2}-\d+(?:\(\d+\))?", grupo)]
    pares += [("LGPD", f"Art. {n}") for n in re.findall(r"LGPD Art\. (\d+)", referencia)]
    pares += [("CIS_V8", n) for n in re.findall(r"CIS Controls v8 (\d{1,2}\.\d{1,2})", referencia)]
    return pares


def _familia_nist(identificador: str) -> str:
    return identificador.split("-")[0]  # "IA-5(18)" -> "IA"


def selecionar_proximas(referencia: str, achados: list[dict]) -> list[dict]:
    """Escolhe, entre os resultados do FAISS, as normas próximas que valem ser acrescentadas.

    Não repete as normas da referência curada. Limiar por tipo (ver NOTA_MIN_*): controle da
    MESMA família NIST de um controle citado pela regra (ex.: IA-5(1) para IA-5) aceita nota
    menor; LGPD exige nota maior.
    """
    curados = _pares_curados(referencia)
    familias = {_familia_nist(i) for f, i in curados if f == "NIST_800_53"}
    aceitas = []
    for r in achados:
        par = (r["fonte"], r["identificador"])
        if par in curados:
            continue
        if r["fonte"] == "LGPD":
            minimo = NOTA_MIN_LGPD
        elif r["fonte"] == "CIS_V8":
            minimo = NOTA_MIN_CIS
        elif _familia_nist(r["identificador"]) in familias:
            minimo = NOTA_MIN_FAMILIA
        else:
            minimo = NOTA_MIN_OUTRA
        if r["nota"] >= minimo:
            aceitas.append(r)
        if len(aceitas) == MAX_PROXIMAS:
            break
    return aceitas


def _rotulo_norma(fonte: str, identificador: str) -> str:
    return {"NIST_800_53": f"NIST SP 800-53 {identificador}", "LGPD": f"LGPD {identificador}",
            "CIS_V8": f"CIS Controls v8 {identificador}"}.get(fonte, f"{fonte} {identificador}")


def enriquecer_lacunas(lacunas: list[dict], buscador, resolver: Callable[[str, str], object | None]) -> list[dict]:
    """Liga cada lacuna às normas da base (`normas_ref`) e acrescenta as mais próximas na busca.

      * as normas da referência curada pelas regras (ex.: NIST IA-5) viram `normas_ref`;
      * a busca FAISS (texto da lacuna -> normas) acrescenta até MAX_PROXIMAS normas que passam
        no filtro de `selecionar_proximas` e ainda não estão na referência; elas entram em
        `normas_ref` e são listadas no fim de `referencia`, rotuladas como busca semântica.

    `resolver(fonte, identificador)` devolve o _id da norma no MongoDB (ou None se não existir).
    Sem `buscador`, ou se a busca falhar, só valem as normas curadas: a API segue funcionando.
    """
    consultas = [f"{l['trecho']} {l['problema']}" for l in lacunas]
    try:
        resultados = (buscador.buscar_varias(consultas, top=TOP_CANDIDATAS)
                      if buscador is not None else [[] for _ in lacunas])
    except Exception as exc:
        log.warning("Busca semântica indisponível, seguindo só com as referências das regras: %s", exc)
        resultados = [[] for _ in lacunas]

    cache: dict[tuple[str, str], object | None] = {}

    def achar(par: tuple[str, str]):
        if par not in cache:
            cache[par] = resolver(*par)
        return cache[par]

    for lacuna, achados in zip(lacunas, resultados):
        curados = _pares_curados(lacuna["referencia"])
        ids = [achar(par) for par in curados]
        proximas = [(r["fonte"], r["identificador"])
                    for r in selecionar_proximas(lacuna["referencia"], achados)
                    if achar((r["fonte"], r["identificador"])) is not None]
        ids += [achar(par) for par in proximas]
        lacuna["normas_ref"] = [i for n, i in enumerate(ids) if i is not None and i not in ids[:n]]
        if proximas:
            lacuna["referencia"] += " | Normas próximas (busca semântica): " + "; ".join(
                _rotulo_norma(*par) for par in proximas)
    return lacunas
