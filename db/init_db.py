"""
Cria (ou atualiza) as coleções do AutoAudit no MongoDB: validação $jsonSchema
e índices. Idempotente — pode rodar quantas vezes quiser.

Os nomes de campo de `relatorios` seguem EXATAMENTE o dicionário devolvido por
`analisar_documento()` em frontend/mock_data.py (o contrato com o frontend).

Uso (Mongo do docker-compose no ar, .env preenchido):
    python db/init_db.py            # cria/atualiza coleções e índices
    python db/init_db.py --reset    # APAGA as 3 coleções e recria (só em dev!)
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

FONTES = ["NIST_800_53", "CIS_V8", "LGPD", "ISO27001_ANEXO_A", "SANS"]
SEVERIDADES = ["alta", "média", "baixa"]  # mesmos valores do frontend (com acento)
NOTA = {"bsonType": ["double", "int"], "minimum": 0, "maximum": 5}
NOTA_OU_NULL = {"bsonType": ["double", "int", "null"], "minimum": 0, "maximum": 5}

# --------------------------------------------------------------------------
# normas — uma "unidade curta" por controle/artigo da base normativa (grounding).
# Os vetores ficam no índice FAISS; aqui guardamos só o faiss_id (posição).
# --------------------------------------------------------------------------
NORMAS_SCHEMA = {
    "bsonType": "object",
    "required": ["fonte", "identificador", "titulo", "texto", "idioma"],
    "properties": {
        "fonte": {"enum": FONTES},
        "identificador": {"bsonType": "string"},  # "AC-2", "Art. 46", "5.2"
        "titulo": {"bsonType": "string"},
        "texto": {"bsonType": "string"},
        "idioma": {"enum": ["pt", "en"]},
        "familia": {"bsonType": ["string", "null"]},
        "grupo_implementacao": {"enum": ["IG1", "IG2", "IG3", None]},  # só CIS
        "versao_fonte": {"bsonType": ["string", "null"]},
        "faiss_id": {"bsonType": ["int", "long", "null"]},
        "embedding_modelo": {"bsonType": ["string", "null"]},
        "mapeamentos": {"bsonType": "array", "items": {"bsonType": "string"}},
        "criado_em": {"bsonType": "date"},
    },
}

# --------------------------------------------------------------------------
# auditorias — a EXECUÇÃO: qual arquivo, quando, em que estado.
# O resultado da análise fica em `relatorios`.
# --------------------------------------------------------------------------
AUDITORIAS_SCHEMA = {
    "bsonType": "object",
    "required": ["arquivo", "sha256", "com_verificacao", "status", "criada_em"],
    "properties": {
        "arquivo": {"bsonType": "string"},
        "sha256": {"bsonType": "string"},
        "formato": {"enum": ["pdf", "docx", None]},
        "tamanho_bytes": {"bsonType": ["int", "long", "null"]},
        "com_verificacao": {"bsonType": "bool"},
        "status": {"enum": ["pendente", "processando", "concluida", "erro"]},
        "modelo_llm": {"bsonType": ["string", "null"]},
        "erro": {"bsonType": ["string", "null"]},
        "criada_em": {"bsonType": "date"},
        "concluida_em": {"bsonType": ["date", "null"]},
    },
}

# --------------------------------------------------------------------------
# relatorios — o RESULTADO. Campos idênticos ao dict de analisar_documento().
# --------------------------------------------------------------------------
RELATORIOS_SCHEMA = {
    "bsonType": "object",
    "required": ["auditoria_id", "arquivo", "criado_em", "nota_documental",
                 "saude_compliance", "lacunas"],
    "properties": {
        "auditoria_id": {"bsonType": "objectId"},
        "arquivo": {"bsonType": "string"},
        "criado_em": {"bsonType": "date"},  # o frontend formata como "dd/mm/YYYY HH:MM"
        "nota_documental": NOTA,
        "nota_pratica": NOTA_OU_NULL,  # null = Verificação Prática não executada (FCS)
        "saude_compliance": NOTA,
        "lacunas": {
            "bsonType": "array",
            "items": {
                "bsonType": "object",
                "required": ["clausula", "trecho", "severidade", "referencia", "problema", "sugestao"],
                "properties": {
                    "clausula": {"bsonType": "string"},
                    "trecho": {"bsonType": "string"},
                    "severidade": {"enum": SEVERIDADES},
                    "referencia": {"bsonType": "string"},  # texto exibido ao usuário
                    "problema": {"bsonType": "string"},
                    "sugestao": {"bsonType": "string"},
                    "mitre": {"bsonType": ["string", "null"]},
                    # extra (rastreabilidade do grounding); o frontend ignora
                    "normas_ref": {"bsonType": "array", "items": {"bsonType": "objectId"}},
                },
            },
        },
        # null quando a Verificação Prática não rodou; senão, lista de checagens
        "verificacoes": {
            "bsonType": ["array", "null"],
            "items": {
                "bsonType": "object",
                "required": ["controle", "acao", "alvo", "esperado", "observado", "status"],
                "properties": {
                    "controle": {"bsonType": "string"},
                    "acao": {"bsonType": "string"},  # ex.: check_port
                    "alvo": {"bsonType": "string"},
                    "esperado": {"bsonType": "string"},
                    "observado": {"bsonType": "string"},
                    "status": {"enum": ["passou", "falhou"]},
                },
            },
        },
        # HITL / melhoria contínua (opcional)
        "feedback_analista": {
            "bsonType": ["object", "null"],
            "properties": {
                "avaliacao": {"enum": ["util", "parcial", "inutil", None]},
                "comentario": {"bsonType": ["string", "null"]},
            },
        },
    },
}

COLECOES = {
    "normas": NORMAS_SCHEMA,
    "auditorias": AUDITORIAS_SCHEMA,
    "relatorios": RELATORIOS_SCHEMA,
}

INDICES = {
    "normas": [
        ([("fonte", ASCENDING), ("identificador", ASCENDING)],
         {"unique": True, "name": "uq_fonte_identificador"}),
        ([("faiss_id", ASCENDING)], {"name": "ix_faiss_id", "sparse": True}),
    ],
    "auditorias": [
        ([("criada_em", DESCENDING)], {"name": "ix_criada_em"}),
        ([("sha256", ASCENDING)], {"name": "ix_sha256"}),
        ([("status", ASCENDING)], {"name": "ix_status"}),
    ],
    "relatorios": [
        ([("auditoria_id", ASCENDING)], {"unique": True, "name": "uq_auditoria_id"}),
        ([("criado_em", DESCENDING)], {"name": "ix_criado_em"}),
    ],
}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Cria coleções e índices do AutoAudit.")
    parser.add_argument("--reset", action="store_true",
                        help="Apaga e recria as coleções (dev). Pede confirmação.")
    args = parser.parse_args()

    uri = os.getenv("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI não definida. Copie .env.example para .env e preencha.")

    db_name = os.getenv("MONGO_DB_NAME", "autoaudit")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # falha rápido se o Mongo não está no ar
    db = client[db_name]

    if args.reset:
        resp = input(f"--reset apaga {list(COLECOES)} do banco '{db_name}'. "
                     f"Digite o nome do banco para confirmar: ")
        if resp.strip() != db_name:
            sys.exit("Cancelado.")

    existentes = set(db.list_collection_names())
    for nome, schema in COLECOES.items():
        validator = {"$jsonSchema": schema}
        if args.reset and nome in existentes:
            db.drop_collection(nome)
            existentes.discard(nome)
            print(f"[reset] {nome} apagada")
        if nome in existentes:
            db.command("collMod", nome, validator=validator, validationLevel="moderate")
            print(f"[ok] {nome}: validador atualizado")
        else:
            db.create_collection(nome, validator=validator, validationLevel="moderate")
            print(f"[ok] {nome}: criada")
        for keys, opts in INDICES[nome]:
            db[nome].create_index(keys, **opts)
        print(f"     índices: {[o['name'] for _, o in INDICES[nome]]}")

    print("Pronto.")


if __name__ == "__main__":
    try:
        main()
    except PyMongoError as exc:
        sys.exit(f"Falha no MongoDB: {exc}")
