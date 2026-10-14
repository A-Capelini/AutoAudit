"""
Carrega a base normativa (grounding) na coleção `normas` do MongoDB.

Fontes lidas de data/raw/ (baixadas pelos scripts em scripts/):
    nist  -> nist_sp800-53_rev5_catalog.json   (scripts/download_nist_oscal.py)
    lgpd  -> lgpd_artigos.json                 (scripts/download_lgpd.py)

Uma "unidade curta" por controle (NIST) ou artigo (LGPD), no formato do schema de `normas`.
Idempotente: usa upsert por (fonte, identificador), então pode rodar de novo sem duplicar.
Não mexe em faiss_id / embedding_modelo / mapeamentos de normas que já existem
(esses campos são preenchidos depois, na etapa de embeddings).

Uso:
    python db/seed_normas.py                   # NIST + LGPD
    python db/seed_normas.py --fonte nist
    python db/seed_normas.py --dry-run         # só lê e mostra o que seria gravado (não usa o Mongo)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

RAIZ = Path(__file__).resolve().parent.parent
ARQ_NIST = RAIZ / "data" / "raw" / "nist_sp800-53_rev5_catalog.json"
ARQ_LGPD = RAIZ / "data" / "raw" / "lgpd_artigos.json"

LINK_RE = re.compile(r"\[([^\]]+)\]\(#[^)]*\)")  # [texto](#id)  ->  texto
INSERT_RE = re.compile(r"\{\{\s*insert:\s*param,\s*([^\s}]+)\s*\}\}")  # {{ insert: param, ac-02_odp.01 }}


# ------------------------------------------------------------------ NIST (OSCAL)
def _limpar_prosa(texto: str, params: dict) -> str:
    """Troca os marcadores de parâmetro pelo rótulo legível e remove links internos."""

    def troca(m: re.Match) -> str:
        p = params.get(m.group(1))
        if p and p.get("label"):
            rotulo = LINK_RE.sub(r"\1", p["label"])  # o próprio rótulo pode conter links (ex.: AU-2)
            return "[" + rotulo + "]"
        return "[definido pela organização]"

    return INSERT_RE.sub(troca, LINK_RE.sub(r"\1", texto)).strip()


def _rotulo(item: dict) -> str:
    """Valor da propriedade 'label' sem classe (ex.: 'AC-2', 'a.', '1.')."""
    return next(
        (p["value"] for p in item.get("props", []) if p["name"] == "label" and not p.get("class")), ""
    )


def _texto_parte(parte: dict, params: dict, nivel: int = 0) -> list[str]:
    """Achata uma 'part' (statement/guidance) em linhas, mantendo os rótulos a., b., 1.…"""
    linhas = []
    rotulo = _rotulo(parte)
    prosa = parte.get("prose")
    if prosa:
        linhas.append("  " * nivel + (f"{rotulo} " if rotulo else "") + _limpar_prosa(prosa, params))
    for sub in parte.get("parts", []):
        linhas.extend(_texto_parte(sub, params, nivel + (1 if prosa or rotulo else 0)))
    return linhas


def _docs_nist_controle(ctrl: dict, familia: str, versao: str, params_pai: dict, saida: list) -> None:
    params = {**params_pai, **{p["id"]: p for p in ctrl.get("params", [])}}

    retirado = any(p["name"] == "status" and p["value"] == "withdrawn" for p in ctrl.get("props", []))
    if not retirado:
        partes = {p["name"]: p for p in ctrl.get("parts", [])}
        blocos = []
        if "statement" in partes:
            blocos.append("\n".join(_texto_parte(partes["statement"], params)))
        if "guidance" in partes:
            blocos.append("Guidance: " + "\n".join(_texto_parte(partes["guidance"], params)))
        texto = "\n\n".join(b for b in blocos if b.strip())
        if texto:
            saida.append(
                {
                    "fonte": "NIST_800_53",
                    "identificador": _rotulo(ctrl) or ctrl["id"].upper(),
                    "titulo": ctrl["title"],
                    "texto": texto,
                    "idioma": "en",
                    "familia": familia,
                    "grupo_implementacao": None,
                    "versao_fonte": versao,
                }
            )

    for melhoria in ctrl.get("controls", []):  # melhorias (ex.: AC-2(1)) ficam aninhadas
        _docs_nist_controle(melhoria, familia, versao, params, saida)


def carregar_nist(caminho: Path) -> tuple[list[dict], dict]:
    catalogo = json.loads(caminho.read_text(encoding="utf-8"))["catalog"]
    versao = f"Rev. 5 (OSCAL {catalogo['metadata'].get('version', '?')})"
    docs: list[dict] = []
    for grupo in catalogo.get("groups", []):
        for ctrl in grupo.get("controls", []):
            _docs_nist_controle(ctrl, grupo["id"].upper(), versao, {}, docs)
    return docs, {}


# ------------------------------------------------------------------ LGPD
def carregar_lgpd(caminho: Path) -> tuple[list[dict], dict]:
    artigos = json.loads(caminho.read_text(encoding="utf-8"))
    por_id: dict[str, dict] = {}
    duplicados = 0
    for a in artigos:
        ident = a["artigo"].strip().rstrip(".")  # "Art. 12." -> "Art. 12"
        if ident in por_id:  # o download já deixa só a redação vigente; se sobrar repetido, a última vence
            duplicados += 1
        por_id[ident] = a
    docs, curtos, revogados, sem_conteudo = [], 0, [], []
    for ident, a in por_id.items():
        texto = a["texto"].strip()
        corpo = re.sub(r"^Art\.\s*\S+\s*", "", texto).strip()
        if re.fullmatch(r"\(\s*(VETADO|Revogad[oa][^)]*)\)\.?", corpo, re.IGNORECASE):
            sem_conteudo.append(ident)  # só "(VETADO)" ou "(Revogado…)": não há norma para buscar
            continue
        if len(texto) < 40:
            curtos += 1  # normal para artigos vetados: "Art. 56. (VETADO)."
        if re.search(r"\(Revogad[oa][^)]*\)\.?\s*$", texto, re.IGNORECASE):
            revogados.append(ident)
        docs.append(
            {
                "fonte": "LGPD",
                "identificador": ident,
                "titulo": f"LGPD {ident}",
                "texto": texto,
                "idioma": "pt",
                "familia": None,
                "grupo_implementacao": None,
                "versao_fonte": "Lei nº 13.709/2018 (texto compilado)",
            }
        )
    avisos = {"repetidos (a última vence)": duplicados, "pulados por serem só vetado/revogado": sem_conteudo,
              "textos curtos restantes (<40 car.)": curtos}
    if revogados:
        avisos["terminam com nota de revogação (confira)"] = revogados
    return docs, avisos


# ------------------------------------------------------------------ gravação
CAMPOS_SET = ("titulo", "texto", "idioma", "familia", "grupo_implementacao", "versao_fonte")


def gravar(db, docs: list[dict]) -> dict:
    agora = datetime.now(timezone.utc)
    ops = [
        UpdateOne(
            {"fonte": d["fonte"], "identificador": d["identificador"]},
            {
                "$set": {k: d[k] for k in CAMPOS_SET},
                "$setOnInsert": {"faiss_id": None, "embedding_modelo": None, "mapeamentos": [], "criado_em": agora},
            },
            upsert=True,
        )
        for d in docs
    ]
    novas = atualizadas = 0
    for i in range(0, len(ops), 500):
        r = db.normas.bulk_write(ops[i : i + 500], ordered=False)
        novas += r.upserted_count
        atualizadas += r.modified_count
    return {"novas": novas, "atualizadas": atualizadas, "inalteradas": len(ops) - novas - atualizadas}


# ------------------------------------------------------------------ main
FONTES = {
    "nist": ("NIST SP 800-53 Rev. 5", ARQ_NIST, carregar_nist, "python scripts/download_nist_oscal.py"),
    "lgpd": ("LGPD", ARQ_LGPD, carregar_lgpd, "python scripts/download_lgpd.py"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Carrega NIST e LGPD na coleção `normas`.")
    parser.add_argument("--fonte", choices=["nist", "lgpd", "todas"], default="todas")
    parser.add_argument("--dry-run", action="store_true", help="Só lê e resume; não grava no Mongo.")
    args = parser.parse_args()

    escolhidas = list(FONTES) if args.fonte == "todas" else [args.fonte]
    db = None
    if not args.dry_run:
        load_dotenv(RAIZ / ".env")
        uri = os.getenv("MONGO_URI")
        if not uri:
            sys.exit("MONGO_URI não definida. Copie .env.example para .env e preencha.")
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[os.getenv("MONGO_DB_NAME", "autoaudit")]

    faltando = 0
    for chave in escolhidas:
        nome, caminho, carregar, comando = FONTES[chave]
        if not caminho.exists():
            print(f"[pulado] {nome}: arquivo não encontrado ({caminho.relative_to(RAIZ)}). Rode: {comando}")
            faltando += 1
            continue
        docs, avisos = carregar(caminho)
        print(f"[lido]   {nome}: {len(docs)} unidades")
        for k, v in avisos.items():
            print(f"         aviso — {k}: {v}")
        if args.dry_run:
            for d in docs[:2]:
                print(f"         ex.: {d['identificador']} — {d['titulo']}: {d['texto'][:110]!r}…")
        else:
            print(f"[gravado] {nome}: {gravar(db, docs)}")

    if db is not None:
        print("Total na coleção normas:", db.normas.count_documents({}))
    return 1 if faltando == len(escolhidas) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PyMongoError as exc:
        sys.exit(f"Falha no MongoDB: {exc}")
