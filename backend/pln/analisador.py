"""
Orquestra o pipeline de PLN: texto -> seções -> lacunas -> notas.

Nota documental (0 a 5), fórmula simples e explicável:

    peso da lacuna:  alta = 3, média = 2, baixa = 1
    peso máximo:     3 x número de seções do documento (todas as seções com lacuna alta)
    nota_documental = 5 x (1 - peso_total / peso_máximo)      (mínimo 0, 1 casa decimal)

A fórmula é provisória (heurística da Sprint 3) e será calibrada com as políticas de teste.
A Saúde de Compliance segue a regra do frontend: média simples de documental e prática;
sem Verificação Prática, vale só a documental.
"""

from __future__ import annotations

from .extracao import dividir_secoes
from .regras import detectar_lacunas

PESOS = {"alta": 3, "média": 2, "baixa": 1}
MIN_SECOES = 5  # evita que um documento curtíssimo dê nota extrema com uma única lacuna


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
    documental = calcular_nota_documental(lacunas, n_secoes)
    return {
        "nota_documental": documental,
        "nota_pratica": None,
        "saude_compliance": calcular_saude_compliance(documental, None),
        "lacunas": lacunas,
        "verificacoes": None,
        "secoes_analisadas": n_secoes,
    }
