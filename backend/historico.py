"""
Histórico por política: agrupa as auditorias de versões do mesmo documento e compara versões.

Funções puras (sem banco, sem FastAPI), para testar sem dependências. A API só as chama.

Como duas auditorias são "a mesma política": o nome do arquivo, normalizado por `chave_politica`
(minúsculas, sem extensão, acentos, marcas de versão como v2/final/(1)/datas). É uma heurística:
o relatório não guarda o conteúdo do documento, então não há como provar identidade por conteúdo.
Nomes muito diferentes entre versões criam políticas separadas (limitação assumida).

Como se compara: uma lacuna da versão anterior é a MESMA da versão nova quando têm o mesmo
`problema` e trechos parecidos (difflib >= LIMIAR_TRECHO), o que tolera pequenas edições de redação.
Lacuna sem par na nova = resolvida; sem par na anterior = nova; com par = persistente.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

LIMIAR_TRECHO = 0.8

_EXTENSAO = re.compile(r"\.(pdf|docx)$", re.I)
_DATA = re.compile(r"\d{4}[-_.]\d{2}[-_.]\d{2}|\d{2}[-_.]\d{2}[-_.]\d{4}")
_MARCAS = re.compile(
    r"\(\d+\)"                      # "(1)" de download repetido
    r"|\b(?:v|vers[aã]o|rev|r)\s*\.?\s*\d+(?:[._]\d+)*\b"
    r"|\b(?:final|revisad[ao]|rascunho|draft|copia|c[óo]pia|novo|nova|atualizad[ao])\b"
    , re.I)


def chave_politica(arquivo: str) -> str:
    """Nome do arquivo -> chave estável da política ('Politica_Seguranca_v2 (1).pdf' -> 'politica seguranca')."""
    nome = _EXTENSAO.sub("", arquivo.strip())
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    nome = re.sub(r"[_\-]+", " ", _DATA.sub(" ", nome.lower()))   # "_" é caractere de palavra e esconderia o \b das marcas
    nome = _MARCAS.sub(" ", nome)
    nome = re.sub(r"[^a-z0-9]+", " ", nome)
    return nome.strip() or "sem nome"


def _trecho(l: dict) -> str:
    return " ".join((l.get("trecho") or "").lower().split())


def comparar_lacunas(anteriores: list[dict], novas: list[dict]) -> dict:
    """Pareia lacunas das duas versões. Devolve {resolvidas, novas, persistentes} (listas de lacunas)."""
    livres = list(novas)
    resolvidas, persistentes = [], []
    for ant in anteriores:
        achada = None
        for cand in livres:
            if cand.get("problema") != ant.get("problema"):
                continue
            if SequenceMatcher(None, _trecho(ant), _trecho(cand)).ratio() >= LIMIAR_TRECHO:
                achada = cand
                break
        if achada is None:
            resolvidas.append(ant)
        else:
            livres.remove(achada)
            persistentes.append(achada)
    return {"resolvidas": resolvidas, "novas": livres, "persistentes": persistentes}


def agrupar_por_politica(relatorios: list[dict]) -> dict[str, list[dict]]:
    """Relatórios (formato do contrato, qualquer ordem) -> {chave: versões do mais antigo ao mais novo}.
    A ordem vem da posição na lista (mais recentes primeiro, como o repositório devolve)."""
    grupos: dict[str, list[dict]] = {}
    for rel in reversed(relatorios):
        grupos.setdefault(chave_politica(rel["arquivo"]), []).append(rel)
    return grupos


def _resumo(rel: dict) -> dict:
    return {"id": rel["id"], "arquivo": rel["arquivo"], "data": rel["data"],
            "nota_documental": rel["nota_documental"], "nota_pratica": rel.get("nota_pratica"),
            "saude_compliance": rel["saude_compliance"], "total_lacunas": len(rel["lacunas"])}


def resumo_das_politicas(relatorios: list[dict]) -> list[dict]:
    """Uma linha por política: quantas versões, a última nota e a variação em relação à primeira."""
    linhas = []
    for chave, versoes in agrupar_por_politica(relatorios).items():
        ultima, primeira = versoes[-1], versoes[0]
        linhas.append({"chave": chave, "arquivo": ultima["arquivo"], "versoes": len(versoes),
                       "ultima_data": ultima["data"], "ultima_saude": ultima["saude_compliance"],
                       "variacao": round(ultima["saude_compliance"] - primeira["saude_compliance"], 2)})
    return sorted(linhas, key=lambda l: l["arquivo"].lower())


def historico_da_politica(relatorios: list[dict], chave: str) -> dict | None:
    """Versões da política em ordem cronológica; cada uma (menos a 1ª) traz a comparação com a anterior."""
    versoes = agrupar_por_politica(relatorios).get(chave)
    if not versoes:
        return None
    saida = []
    for i, rel in enumerate(versoes):
        item = _resumo(rel)
        if i == 0:
            item["comparacao"] = None
        else:
            ant = versoes[i - 1]
            cmp = comparar_lacunas(ant["lacunas"], rel["lacunas"])
            item["comparacao"] = {
                "variacao_saude": round(rel["saude_compliance"] - ant["saude_compliance"], 2),
                **cmp,
            }
        saida.append(item)
    return {"chave": chave, "arquivo": versoes[-1]["arquivo"], "versoes": saida}
