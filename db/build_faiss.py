"""
Gera os embeddings da base normativa e monta o índice FAISS (busca semântica).

Fluxo:
  1. lê todas as normas da coleção `normas` (MongoDB);
  2. divide em "trechos" as normas que não cabem no limite do modelo (256 tokens): artigos longos da LGPD
     (ex.: Art. 7º, Art. 5º) e controles longos do NIST. Cada trecho repete o título e a primeira linha da norma
     (o "caput") como contexto, para não perder do que se trata;
  3. transforma cada trecho em vetor com o modelo multilíngue (NIST em inglês e LGPD em português
     ficam no mesmo espaço, então uma cláusula em português encontra um controle em inglês);
  4. grava o índice em data/processed/normas.index, o texto de cada trecho em normas_trechos.json
     e os metadados em normas_index.json;
  5. grava em cada norma `faiss_ids` (todos os seus vetores), `faiss_id` (o primeiro) e `embedding_modelo`.

O FAISS guarda só os vetores; o texto e os metadados continuam no Mongo. O elo entre os dois é o faiss_id.
A execução refaz tudo (são ~1.100 normas): os ids são sempre consistentes com o arquivo do índice.

Uso (Mongo no ar, normas carregadas com db/seed_normas.py e `python db/init_db.py` rodado após a última atualização):
    python db/build_faiss.py                      # monta o índice e atualiza o Mongo
    python db/build_faiss.py --consulta "política de senhas e controle de acesso"   # só pesquisa (top 5)
    python db/build_faiss.py --consulta "retenção de logs" --top 8
A primeira execução baixa o modelo (~1,1 GB) do Hugging Face; as seguintes usam o cache local.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "data" / "processed"
ARQ_INDICE = PASTA / "normas.index"
ARQ_TRECHOS = PASTA / "normas_trechos.json"
ARQ_META = PASTA / "normas_index.json"

MODELO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
MAX_TOKENS = 256     # o modelo foi treinado com 128; acima de 256 a qualidade cai, então dividimos em trechos
CORPO_TOKENS = 150   # tamanho do corpo de cada trecho
CONTEXTO_TOKENS = 50 # espaço para repetir o caput; título (~30) + contexto + corpo ficam abaixo de MAX_TOKENS


# ------------------------------------------------------------------ divisão em trechos
def texto_para_vetor(n: dict) -> str:
    """Norma inteira: identificador + título + texto (o título ajuda quando o texto é longo)."""
    return f"{n['identificador']} — {n['titulo']}\n{n['texto']}"


def _cortar(texto: str, contar, limite: int) -> str:
    if contar(texto) <= limite:
        return texto
    palavras = []
    for palavra in texto.split():
        if contar(" ".join(palavras + [palavra, "…"])) > limite:
            break
        palavras.append(palavra)
    return " ".join(palavras) + " …"


def _quebrar(linha: str, contar, limite: int) -> list[str]:
    """Linha maior que o limite: quebra por frase e, se preciso, por palavra."""
    if contar(linha) <= limite:
        return [linha]
    pedacos = []
    for frase in re.split(r"(?<=[.;:])\s+", linha):
        if contar(frase) <= limite:
            pedacos.append(frase)
            continue
        atual: list[str] = []
        for palavra in frase.split():
            if atual and contar(" ".join(atual + [palavra])) > limite:
                pedacos.append(" ".join(atual))
                atual = []
            atual.append(palavra)
        if atual:
            pedacos.append(" ".join(atual))
    return pedacos


def dividir(n: dict, contar) -> list[str]:
    """Textos a vetorizar para uma norma: 1 se cabe no modelo; senão vários trechos com contexto."""
    completo = texto_para_vetor(n)
    if contar(completo) <= MAX_TOKENS:
        return [completo]

    prefixo = f"{n['identificador']} — {n['titulo']}\n"
    linhas = [l.strip() for l in n["texto"].split("\n") if l.strip()]
    contexto = _cortar(linhas[0], contar, CONTEXTO_TOKENS)  # o caput: "…nas seguintes hipóteses:"
    pecas = [p for l in linhas for p in _quebrar(l, contar, CORPO_TOKENS)]

    grupos, atual, total = [], [], 0
    for p in pecas:
        t = contar(p)
        if atual and total + t > CORPO_TOKENS:
            grupos.append(atual)
            atual, total = [], 0
        atual.append(p)
        total += t
    if atual:
        grupos.append(atual)

    trechos = []
    for i, g in enumerate(grupos):
        corpo = "\n".join(g)
        if i > 0 and not corpo.startswith(contexto):
            corpo = contexto + "\n" + corpo
        trechos.append(prefixo + corpo)
    return trechos


# ------------------------------------------------------------------ modelo e índice
def carregar_modelo():
    from sentence_transformers import SentenceTransformer  # import tardio: só quem usa o modelo paga o custo

    modelo = SentenceTransformer(MODELO)
    modelo.max_seq_length = MAX_TOKENS
    return modelo


def contador(modelo):
    tok = modelo.tokenizer
    return lambda texto: len(tok(texto, add_special_tokens=False, verbose=False)["input_ids"])


def codificar(modelo, textos: list[str]) -> np.ndarray:
    # normalizados: o produto interno vira similaridade de cosseno
    vetores = modelo.encode(textos, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
    return np.asarray(vetores, dtype="float32")


def montar_indice(vetores: np.ndarray):
    import faiss

    indice = faiss.IndexFlatIP(vetores.shape[1])  # busca exata; com ~3.000 vetores é instantânea
    indice.add(vetores)
    return indice


def _salvar_indice(indice, caminho: Path) -> None:
    import faiss

    faiss.write_index(indice, str(caminho))


def conectar():
    load_dotenv(RAIZ / ".env")
    uri = os.getenv("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI não definida. Copie .env.example para .env e preencha.")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client[os.getenv("MONGO_DB_NAME", "autoaudit")]


# ------------------------------------------------------------------ montagem
def construir(db, modelo=None, contar_fn=None, codificar_fn=codificar, montar_fn=montar_indice,
              salvar_fn=_salvar_indice) -> dict:
    normas = list(db.normas.find({}, {"fonte": 1, "identificador": 1, "titulo": 1, "texto": 1}).sort(
        [("fonte", 1), ("identificador", 1)]))
    if not normas:
        sys.exit("A coleção `normas` está vazia. Rode antes: python db/seed_normas.py")

    modelo = modelo if modelo is not None else carregar_modelo()
    contar = contar_fn or contador(modelo)

    textos, trechos, ids_por_norma = [], [], []
    for n in normas:
        partes = dividir(n, contar)
        ids_por_norma.append(list(range(len(textos), len(textos) + len(partes))))
        for p in partes:
            trechos.append({"faiss_id": len(textos), "fonte": n["fonte"], "identificador": n["identificador"],
                            "texto": p})
            textos.append(p)
    divididas = sum(len(ids) > 1 for ids in ids_por_norma)
    print(f"{len(normas)} normas lidas; {divididas} divididas em trechos -> {len(textos)} vetores a gerar "
          f"({MODELO})…")

    vetores = codificar_fn(modelo, textos)
    indice = montar_fn(vetores)

    PASTA.mkdir(parents=True, exist_ok=True)
    salvar_fn(indice, ARQ_INDICE)
    ARQ_TRECHOS.write_text(json.dumps(trechos, ensure_ascii=False), encoding="utf-8")
    ops = [
        UpdateOne({"_id": n["_id"]},
                  {"$set": {"faiss_id": ids[0], "faiss_ids": ids, "embedding_modelo": MODELO}})
        for n, ids in zip(normas, ids_por_norma)
    ]
    for k in range(0, len(ops), 500):
        db.normas.bulk_write(ops[k : k + 500], ordered=False)

    meta = {"modelo": MODELO, "dimensao": int(vetores.shape[1]), "normas": len(normas),
            "normas_divididas": divididas, "vetores": len(textos), "max_tokens": MAX_TOKENS,
            "corpo_tokens": CORPO_TOKENS, "criado_em": datetime.now(timezone.utc).isoformat()}
    ARQ_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


# ------------------------------------------------------------------ consulta
def agrupar_resultados(notas, ids, trechos: dict, top: int) -> list[dict]:
    """Vários trechos da mesma norma viram um resultado só (o de maior nota)."""
    vistos, saida = set(), []
    for nota, fid in zip(notas, ids):
        t = trechos.get(int(fid))
        if t is None:
            continue
        chave = (t["fonte"], t["identificador"])
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append({"nota": float(nota), **t})
        if len(saida) == top:
            break
    return saida


def pesquisar(consulta: str, top: int) -> None:
    import faiss

    if not ARQ_INDICE.exists() or not ARQ_TRECHOS.exists():
        sys.exit("Índice não encontrado. Monte primeiro:  python db/build_faiss.py")
    indice = faiss.read_index(str(ARQ_INDICE))
    trechos = {t["faiss_id"]: t for t in json.loads(ARQ_TRECHOS.read_text(encoding="utf-8"))}
    vetor = codificar(carregar_modelo(), [consulta])
    notas, ids = indice.search(vetor, min(top * 6, indice.ntotal))  # folga: vários trechos da mesma norma
    print(f"\nConsulta: {consulta!r}\n")
    for r in agrupar_resultados(notas[0], ids[0], trechos, top):
        corpo = r["texto"].split("\n", 1)[1] if "\n" in r["texto"] else r["texto"]
        print(f"  {r['nota']:.3f}  [{r['fonte']}] {r['identificador']}\n         {' '.join(corpo.split())[:120]}…")


def main() -> int:
    parser = argparse.ArgumentParser(description="Monta o índice FAISS das normas ou faz uma consulta de teste.")
    parser.add_argument("--consulta", help="Só pesquisa no índice já montado (não altera nada).")
    parser.add_argument("--top", type=int, default=5, help="Quantas normas mostrar na consulta.")
    args = parser.parse_args()

    if args.consulta:
        pesquisar(args.consulta, args.top)
        return 0

    db = conectar()
    meta = construir(db)
    sem_id = db.normas.count_documents({"faiss_ids": {"$exists": False}})
    print(f"\nÍndice salvo em {ARQ_INDICE.relative_to(RAIZ)} — {meta['vetores']} vetores de "
          f"{meta['dimensao']} dimensões ({meta['normas']} normas, {meta['normas_divididas']} divididas em trechos).")
    print(f"Normas sem faiss_ids: {sem_id} (esperado: 0)")
    return 0 if sem_id == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PyMongoError as exc:
        sys.exit(f"Falha no MongoDB: {exc}")
