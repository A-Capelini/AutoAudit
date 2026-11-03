"""
API do AutoAudit (Sprint 3).

Rodar a partir da RAIZ do repositório, com o MongoDB no ar e o .env configurado (MONGO_URI):

    uvicorn backend.main:app --reload

Documentação interativa gerada automaticamente: http://localhost:8000/docs

Rotas:
    POST /auditorias        envia PDF/DOCX, analisa e grava auditoria + relatório no MongoDB
    GET  /auditorias        histórico (mais recentes primeiro)
    GET  /relatorios/{id}   relatório completo, no formato do contrato com o frontend
    GET  /saude             a API e o MongoDB estão de pé?

Todo acesso ao banco passa por db/repositorio.py. Ciclo de uma auditoria:
    pendente -> processando -> concluida  (ou erro, e nesse caso não existe relatório)

Esta versão NÃO executa a Verificação Prática: `nota_pratica` e `verificacoes` voltam None
(o frontend já trata esse estado) mesmo que `com_verificacao` seja true.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from pymongo.errors import PyMongoError

from backend.pln.analisador import analisar_texto, enriquecer_lacunas
from backend.pln.busca_normas import BuscadorNormas
from backend.pln.extracao import ErroExtracao, detectar_formato, extrair_texto
from db.repositorio import Repositorio

log = logging.getLogger("autoaudit")

FUSO = ZoneInfo("America/Sao_Paulo")
TAMANHO_MAXIMO = 10 * 1024 * 1024  # 10 MB por documento

# Busca semântica (FAISS). AUTOAUDIT_BUSCA=0 desliga (a API segue com as referências das regras).
buscador: BuscadorNormas | None = BuscadorNormas() if os.getenv("AUTOAUDIT_BUSCA", "1") != "0" else None


def _aquecer_busca() -> None:
    try:
        buscador.carregar()
    except Exception as exc:  # sem índice/modelo a API continua; a rota /saude mostra o estado
        log.warning("Busca semântica não carregou: %s", exc)


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Carrega o modelo de embeddings em segundo plano para a 1ª auditoria não esperar."""
    if buscador is not None and buscador.arquivos_existem:
        threading.Thread(target=_aquecer_busca, daemon=True).start()
    yield


app = FastAPI(
    title="AutoAudit API",
    version="0.3.0",
    description="Auditoria de políticas de segurança da informação com PLN. "
                "Sprint 3: extração de texto, regras de detecção de lacunas, busca semântica nas "
                "normas (FAISS) e gravação no MongoDB.",
    lifespan=ciclo_de_vida,
)


# --------------------------------------------------------------------------- modelos (contrato)

class Lacuna(BaseModel):
    clausula: str
    trecho: str
    severidade: Literal["alta", "média", "baixa"]
    referencia: str
    problema: str
    sugestao: str
    mitre: str | None = None


class Verificacao(BaseModel):
    controle: str
    acao: str
    alvo: str
    esperado: str
    observado: str
    status: Literal["passou", "falhou"]


class Relatorio(BaseModel):
    id: str
    arquivo: str
    data: str                       # "dd/mm/YYYY HH:MM", fuso America/Sao_Paulo
    nota_documental: float
    nota_pratica: float | None = None
    saude_compliance: float
    lacunas: list[Lacuna]
    verificacoes: list[Verificacao] | None = None


class ItemAuditoria(BaseModel):
    id: str
    arquivo: str
    status: Literal["pendente", "processando", "concluida", "erro"]
    com_verificacao: bool
    criada_em: str
    concluida_em: str | None = None
    relatorio_id: str | None = None
    saude_compliance: float | None = None
    erro: str | None = None


# --------------------------------------------------------------------------- infraestrutura

_repo: Repositorio | None = None


def get_repo() -> Repositorio:
    """Uma conexão por processo, criada no primeiro uso (a API sobe mesmo com o Mongo fora)."""
    global _repo
    if _repo is None:
        try:
            _repo = Repositorio.from_env()
        except (RuntimeError, PyMongoError) as exc:
            raise HTTPException(503, f"MongoDB indisponível: {exc}") from exc
    return _repo


@app.exception_handler(PyMongoError)
async def erro_mongo(_request: Request, exc: PyMongoError) -> JSONResponse:
    log.exception("Erro no MongoDB")
    return JSONResponse(status_code=503, content={"detail": f"Erro no MongoDB: {exc.__class__.__name__}"})


def _formatar(data: datetime | None) -> str | None:
    if data is None:
        return None
    if data.tzinfo is None:  # o Mongo devolve naive quando a conexão não é tz_aware
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def relatorio_para_contrato(doc: dict) -> dict:
    """Documento do MongoDB -> dicionário do contrato com o frontend."""
    return {
        "id": str(doc["_id"]),
        "arquivo": doc["arquivo"],
        "data": _formatar(doc["criado_em"]),
        "nota_documental": doc["nota_documental"],
        "nota_pratica": doc.get("nota_pratica"),
        "saude_compliance": doc["saude_compliance"],
        "lacunas": [{k: l.get(k) for k in ("clausula", "trecho", "severidade", "referencia",
                                           "problema", "sugestao", "mitre")}
                    for l in doc["lacunas"]],
        "verificacoes": doc.get("verificacoes"),
    }


# --------------------------------------------------------------------------- rotas

@app.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/saude", summary="A API e o MongoDB estão de pé?")
def saude() -> dict:
    busca = "desativada" if buscador is None else buscador.estado
    try:
        get_repo().db.client.admin.command("ping")
        return {"api": "ok", "mongo": "ok", "busca_semantica": busca}
    except (HTTPException, PyMongoError):
        return {"api": "ok", "mongo": "indisponível", "busca_semantica": busca}


@app.post("/auditorias", response_model=Relatorio, status_code=201,
          summary="Audita uma política (PDF ou DOCX)")
def criar_auditoria(
    arquivo: UploadFile = File(..., description="Política de segurança em PDF ou DOCX (até 10 MB)"),
    com_verificacao: bool = Form(False, description="Incluir a Verificação Prática (ainda não executada nesta versão)"),
    repo: Repositorio = Depends(get_repo),
) -> dict:
    nome = arquivo.filename or "documento"
    formato = detectar_formato(nome)
    if formato is None:
        raise HTTPException(415, "Formato não suportado: envie um arquivo .pdf ou .docx.")
    conteudo = arquivo.file.read()
    if not conteudo:
        raise HTTPException(400, "O arquivo enviado está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise HTTPException(413, "Arquivo maior que 10 MB.")

    sha256 = hashlib.sha256(conteudo).hexdigest()
    auditoria_id = repo.criar_auditoria(nome, sha256, com_verificacao,
                                        formato=formato, tamanho_bytes=len(conteudo))
    repo.atualizar_auditoria(auditoria_id, status="processando")
    try:
        texto = extrair_texto(nome, conteudo)
        resultado = analisar_texto(texto)
        lacunas = enriquecer_lacunas(
            resultado["lacunas"], buscador,
            lambda fonte, ident: (repo.obter_norma(fonte, ident) or {}).get("_id"))
        relatorio_id = repo.criar_relatorio(
            auditoria_id, resultado["nota_documental"], resultado["saude_compliance"],
            lacunas, nota_pratica=None, verificacoes=None)
        repo.atualizar_auditoria(auditoria_id, status="concluida")
    except ErroExtracao as exc:
        repo.atualizar_auditoria(auditoria_id, status="erro", erro=str(exc)[:500])
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        log.exception("Falha ao analisar %s", nome)
        repo.atualizar_auditoria(auditoria_id, status="erro", erro=f"{exc.__class__.__name__}: {exc}"[:500])
        raise HTTPException(500, "Falha interna ao analisar o documento (veja o log da API).") from exc

    return relatorio_para_contrato(repo.obter_relatorio(relatorio_id))


@app.get("/auditorias", response_model=list[ItemAuditoria], summary="Histórico de auditorias")
def listar_auditorias(
    limite: int = Query(50, ge=1, le=200),
    status: Literal["pendente", "processando", "concluida", "erro"] | None = None,
    repo: Repositorio = Depends(get_repo),
) -> list[dict]:
    itens = []
    for aud in repo.listar_auditorias(status=status, limite=limite):
        rel = repo.obter_relatorio_por_auditoria(aud["_id"]) if aud["status"] == "concluida" else None
        itens.append({
            "id": str(aud["_id"]), "arquivo": aud["arquivo"], "status": aud["status"],
            "com_verificacao": aud["com_verificacao"], "criada_em": _formatar(aud["criada_em"]),
            "concluida_em": _formatar(aud.get("concluida_em")),
            "relatorio_id": str(rel["_id"]) if rel else None,
            "saude_compliance": rel["saude_compliance"] if rel else None,
            "erro": aud.get("erro"),
        })
    return itens


@app.get("/relatorios/{relatorio_id}", response_model=Relatorio, summary="Relatório completo")
def obter_relatorio(relatorio_id: str, repo: Repositorio = Depends(get_repo)) -> dict:
    try:
        doc = repo.obter_relatorio(relatorio_id)
    except ValueError:  # id que não é um ObjectId válido
        doc = None
    if doc is None:
        raise HTTPException(404, "Relatório não encontrado.")
    return relatorio_para_contrato(doc)
