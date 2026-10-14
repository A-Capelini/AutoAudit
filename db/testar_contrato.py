"""
Teste de ida e volta: o banco aceita e devolve igual o que o frontend produz?

Para cada caso (com e sem Verificação Prática):
  1. gera um relatório com analisar_documento() (frontend/mock_data.py);
  2. grava em `auditorias` e `relatorios` do Mongo;
  3. lê de volta e reconstrói o dicionário do contrato;
  4. compara campo a campo com o original.
Também confere duas regras do banco: auditoria_id único e validação do schema.

Os documentos de teste usam o arquivo "__teste_contrato__.pdf" e são APAGADOS no final.

Uso (Mongo no ar, coleções criadas com db/init_db.py):
    python db/testar_contrato.py
"""

import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError, WriteError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "frontend"))
from mock_data import analisar_documento  # noqa: E402  (o contrato com o frontend)

MARCA = "__teste_contrato__.pdf"
CAMPOS = ("arquivo", "nota_documental", "nota_pratica", "saude_compliance", "lacunas", "verificacoes")
FORMATO_DATA = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")

resultados: list[bool] = []


def checar(nome: str, ok: bool, detalhe: str = "") -> None:
    resultados.append(ok)
    print(f"{'OK   ' if ok else 'FALHA'} {nome}" + (f" — {detalhe}" if detalhe and not ok else ""))


def relatorio_para_contrato(doc: dict) -> dict:
    """Mongo -> dicionário do contrato (é a conversão que o backend fará na borda da API)."""
    criado = doc["criado_em"]
    if criado.tzinfo is None:  # o pymongo devolve datas em UTC sem fuso
        criado = criado.replace(tzinfo=timezone.utc)
    return {
        "id": str(doc["_id"]),
        "data": criado.astimezone().strftime("%d/%m/%Y %H:%M"),
        **{k: doc[k] for k in CAMPOS},
    }


def caso(db, com_verificacao: bool) -> None:
    rotulo = "com Verificação Prática" if com_verificacao else "sem Verificação Prática (FCS)"
    conteudo = f"conteudo-de-teste-{com_verificacao}".encode()
    original = analisar_documento(MARCA, conteudo, com_verificacao)
    agora = datetime.now(timezone.utc)

    aud_id = db.auditorias.insert_one(
        {
            "arquivo": MARCA,
            "sha256": hashlib.sha256(conteudo).hexdigest(),
            "formato": "pdf",
            "tamanho_bytes": len(conteudo),
            "com_verificacao": com_verificacao,
            "status": "concluida",
            "modelo_llm": None,
            "erro": None,
            "criada_em": agora,
            "concluida_em": agora,
        }
    ).inserted_id

    rel_doc = {k: original[k] for k in CAMPOS}
    rel_doc.update(auditoria_id=aud_id, criado_em=agora)
    rel_id = db.relatorios.insert_one(rel_doc).inserted_id

    volta = relatorio_para_contrato(db.relatorios.find_one({"_id": rel_id}))
    iguais = [k for k in CAMPOS if volta[k] == original[k]]
    checar(f"[{rotulo}] campos idênticos após ida e volta", len(iguais) == len(CAMPOS),
           f"divergem: {sorted(set(CAMPOS) - set(iguais))}")
    checar(f"[{rotulo}] mesmas chaves do contrato do frontend", set(volta) == set(original),
           f"diferença: {set(volta) ^ set(original)}")
    checar(f"[{rotulo}] data no formato dd/mm/aaaa hh:mm", bool(FORMATO_DATA.match(volta["data"])), volta["data"])


def main() -> int:
    load_dotenv(RAIZ / ".env")
    client = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[os.getenv("MONGO_DB_NAME", "autoaudit")]

    def limpar():
        db.relatorios.delete_many({"arquivo": MARCA})
        db.auditorias.delete_many({"arquivo": MARCA})

    limpar()
    try:
        caso(db, True)
        caso(db, False)

        # regra 1: um único relatório por auditoria (índice uq_auditoria_id)
        rel = db.relatorios.find_one({"arquivo": MARCA})
        copia = {k: v for k, v in rel.items() if k != "_id"}  # insert_one muda o dict; usa cópia limpa
        try:
            db.relatorios.insert_one(copia)  # sem _id: a única chave única que pode colidir é auditoria_id
            checar("auditoria_id duplicado é recusado", False, "o banco aceitou")
        except DuplicateKeyError:
            restantes = db.relatorios.count_documents({"auditoria_id": rel["auditoria_id"]})
            checar("auditoria_id duplicado é recusado", restantes == 1, f"{restantes} relatórios para a mesma auditoria")

        # regra 2: o validador recusa severidade fora do padrão (sem acento)
        invalido = {k: v for k, v in rel.items() if k != "_id"}
        invalido["auditoria_id"] = ObjectId()
        invalido["lacunas"] = [{**invalido["lacunas"][0], "severidade": "media"}]
        try:
            db.relatorios.insert_one(invalido)
            checar("severidade 'media' (sem acento) é recusada pelo validador", False, "o banco aceitou")
        except WriteError as e:
            checar("severidade 'media' (sem acento) é recusada pelo validador", e.code == 121, f"código {e.code}")
    finally:
        limpar()
        print("(documentos de teste apagados)")

    ok = all(resultados)
    print("\nTUDO OK" if ok else "\nHÁ FALHAS")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PyMongoError as exc:
        sys.exit(f"Falha no MongoDB: {exc}")
