"""
Repositório do AutoAudit: CRUD (Create, Read, Update, Delete) das três coleções do
MongoDB — `normas`, `auditorias` e `relatorios`. É a única camada que fala com o banco:
o backend (Sprint 3) e o script de demonstração só chamam os métodos daqui.

O schema está descrito em docs/modelagem_mongodb.md e docs/dicionario_dados.md.

Regras de integridade mantidas AQUI (o MongoDB não tem chave estrangeira e este projeto
não usa transações):

  * Criar: a auditoria vem antes do relatório. O relatório só é criado se a auditoria
    existe e se toda norma citada em `lacunas[].normas_ref` existe.
  * Apagar: o relatório (filho) é apagado ANTES da auditoria (pai). Sem transações, se o
    processo cair entre os dois passos sobra uma auditoria sem relatório, que é um estado
    válido (relação 1 : 0..1). Na ordem inversa sobraria um relatório órfão.
  * Uma norma citada por algum relatório não pode ser apagada.
  * As verificações acima não são atômicas: sem transações, outra escrita simultânea pode
    passar entre a checagem e a gravação. Para este projeto (um usuário por instância) é
    um risco aceito e documentado.

A validação de tipos e domínios (status, severidade, notas de 0 a 5 etc.) é feita pelo
próprio MongoDB ($jsonSchema criado por db/init_db.py): dado inválido levanta
pymongo.errors.WriteError (código 121). Este módulo não duplica essas regras.

Convenções:
  * `obter_*` devolve None quando não acha; `atualizar_*` e `remover_*` levantam NaoEncontrado.
  * Os ids podem ser ObjectId ou texto (como chegam de uma API).
  * Datas são gravadas em UTC e lidas com fuso (tz_aware) quando a conexão vem de `from_env`.

Uso:
    from repositorio import Repositorio          # ou: from db.repositorio import Repositorio

    with Repositorio.from_env() as repo:
        auditoria_id = repo.criar_auditoria("politica.pdf", sha256, com_verificacao=True)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

Id = ObjectId | str

STATUS_FINAIS = ("concluida", "erro")  # estados em que a auditoria terminou

# Campos que o chamador pode informar/alterar (o resto é controlado pelo repositório).
CAMPOS_NORMA_OPCIONAIS = ("familia", "grupo_implementacao", "versao_fonte", "faiss_id",
                          "faiss_ids", "embedding_modelo", "mapeamentos")
CAMPOS_NORMA_EDITAVEIS = ("titulo", "texto", "idioma") + CAMPOS_NORMA_OPCIONAIS
CAMPOS_AUDITORIA_EDITAVEIS = ("formato", "tamanho_bytes", "com_verificacao", "status",
                              "modelo_llm", "erro", "concluida_em")
CAMPOS_RELATORIO_EDITAVEIS = ("nota_documental", "nota_pratica", "saude_compliance",
                              "lacunas", "verificacoes", "feedback_analista")


class RepositorioError(Exception):
    """Base dos erros deste módulo."""


class NaoEncontrado(RepositorioError, LookupError):
    """O documento (ou o pai/a referência que ele exige) não existe."""


class IntegridadeError(RepositorioError):
    """A operação deixaria o banco inconsistente (duplicidade, referência em uso...)."""


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _oid(valor: Id) -> ObjectId:
    """Aceita ObjectId ou texto e devolve ObjectId."""
    if isinstance(valor, ObjectId):
        return valor
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError) as exc:
        raise ValueError(f"id inválido: {valor!r}") from exc


def _checar_campos(campos: dict[str, Any], permitidos: tuple[str, ...], entidade: str,
                   *, vazio_ok: bool = False) -> None:
    proibidos = sorted(set(campos) - set(permitidos))
    if proibidos:
        raise ValueError(f"{entidade}: campos que não podem ser informados/alterados: {proibidos}")
    if not campos and not vazio_ok:
        raise ValueError(f"{entidade}: nenhum campo para atualizar")


class Repositorio:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.normas = db["normas"]
        self.auditorias = db["auditorias"]
        self.relatorios = db["relatorios"]
        self._client: MongoClient | None = None

    # ------------------------------------------------------------ conexão
    @classmethod
    def from_env(cls) -> Repositorio:
        """Conecta usando MONGO_URI e MONGO_DB_NAME do .env (mesmo padrão do init_db.py)."""
        load_dotenv()
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI não definida. Copie .env.example para .env e preencha.")
        client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")  # falha rápido se o Mongo não está no ar
        repo = cls(client[os.getenv("MONGO_DB_NAME", "autoaudit")])
        repo._client = client
        return repo

    def fechar(self) -> None:
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> Repositorio:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fechar()

    # ======================================================================
    # NORMAS
    # ======================================================================
    def criar_norma(self, fonte: str, identificador: str, titulo: str, texto: str,
                    idioma: str, **opcionais: Any) -> ObjectId:
        """Cria uma norma. (fonte, identificador) é único: repetir levanta IntegridadeError."""
        _checar_campos(opcionais, CAMPOS_NORMA_OPCIONAIS, "norma", vazio_ok=True)
        doc = {"fonte": fonte, "identificador": identificador, "titulo": titulo,
               "texto": texto, "idioma": idioma, **opcionais, "criado_em": agora()}
        try:
            return self.normas.insert_one(doc).inserted_id
        except DuplicateKeyError as exc:
            raise IntegridadeError(f"A norma {fonte}:{identificador} já existe.") from exc

    def obter_norma(self, fonte: str, identificador: str) -> dict | None:
        return self.normas.find_one({"fonte": fonte, "identificador": identificador})

    def listar_normas(self, fonte: str | None = None, familia: str | None = None,
                      limite: int = 50, pular: int = 0) -> list[dict]:
        """Lista normas ordenadas por (fonte, identificador), com paginação."""
        filtro: dict[str, Any] = {}
        if fonte:
            filtro["fonte"] = fonte
        if familia:
            filtro["familia"] = familia
        cursor = (self.normas.find(filtro)
                  .sort([("fonte", ASCENDING), ("identificador", ASCENDING)])
                  .skip(pular).limit(limite))
        return list(cursor)

    def contar_normas_por_fonte(self) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$fonte", "total": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
        return {d["_id"]: d["total"] for d in self.normas.aggregate(pipeline)}

    def atualizar_norma(self, fonte: str, identificador: str, /, **campos: Any) -> None:
        """Altera campos da norma. `fonte`, `identificador` e `criado_em` não mudam
        (tentar mudá-los levanta ValueError)."""
        _checar_campos(campos, CAMPOS_NORMA_EDITAVEIS, "norma")
        res = self.normas.update_one({"fonte": fonte, "identificador": identificador},
                                     {"$set": campos})
        if res.matched_count == 0:
            raise NaoEncontrado(f"Norma {fonte}:{identificador} não encontrada.")

    def remover_norma(self, fonte: str, identificador: str) -> None:
        """Apaga a norma, desde que nenhum relatório a cite em `lacunas[].normas_ref`."""
        norma = self.obter_norma(fonte, identificador)
        if norma is None:
            raise NaoEncontrado(f"Norma {fonte}:{identificador} não encontrada.")
        em_uso = self.relatorios.find_one({"lacunas.normas_ref": norma["_id"]}, {"_id": 1})
        if em_uso is not None:
            raise IntegridadeError(
                f"A norma {fonte}:{identificador} é citada por relatórios "
                "(lacunas[].normas_ref); apague ou atualize esses relatórios antes.")
        self.normas.delete_one({"_id": norma["_id"]})

    # ======================================================================
    # AUDITORIAS
    # ======================================================================
    def criar_auditoria(self, arquivo: str, sha256: str, com_verificacao: bool, *,
                        formato: str | None = None, tamanho_bytes: int | None = None,
                        modelo_llm: str | None = None) -> ObjectId:
        """Registra uma execução nova, sempre no estado `pendente`."""
        doc = {"arquivo": arquivo, "sha256": sha256, "formato": formato,
               "tamanho_bytes": tamanho_bytes, "com_verificacao": com_verificacao,
               "status": "pendente", "modelo_llm": modelo_llm, "erro": None,
               "criada_em": agora(), "concluida_em": None}
        return self.auditorias.insert_one(doc).inserted_id

    def obter_auditoria(self, auditoria_id: Id) -> dict | None:
        return self.auditorias.find_one({"_id": _oid(auditoria_id)})

    def listar_auditorias(self, status: str | None = None, limite: int = 50,
                          pular: int = 0) -> list[dict]:
        """Mais recentes primeiro (índice ix_criada_em)."""
        filtro = {"status": status} if status else {}
        cursor = self.auditorias.find(filtro).sort("criada_em", DESCENDING).skip(pular).limit(limite)
        return list(cursor)

    def buscar_auditorias_por_sha256(self, sha256: str) -> list[dict]:
        """Detecta documento já auditado (índice ix_sha256)."""
        return list(self.auditorias.find({"sha256": sha256}).sort("criada_em", DESCENDING))

    def atualizar_auditoria(self, auditoria_id: Id, /, **campos: Any) -> None:
        """Altera campos da auditoria. Ao passar para `concluida` ou `erro`, preenche
        `concluida_em` automaticamente (a menos que seja informado)."""
        _checar_campos(campos, CAMPOS_AUDITORIA_EDITAVEIS, "auditoria")
        if campos.get("status") in STATUS_FINAIS and "concluida_em" not in campos:
            campos["concluida_em"] = agora()
        res = self.auditorias.update_one({"_id": _oid(auditoria_id)}, {"$set": campos})
        if res.matched_count == 0:
            raise NaoEncontrado(f"Auditoria {auditoria_id} não encontrada.")

    def remover_auditoria(self, auditoria_id: Id) -> dict[str, int]:
        """Apaga o relatório da auditoria (se houver) e DEPOIS a auditoria.

        Devolve quantos documentos saíram de cada coleção.
        """
        oid = _oid(auditoria_id)
        if self.obter_auditoria(oid) is None:
            raise NaoEncontrado(f"Auditoria {auditoria_id} não encontrada.")
        # 1º o filho (relatório), 2º o pai (auditoria): ver docstring do módulo.
        n_relatorios = self.relatorios.delete_many({"auditoria_id": oid}).deleted_count
        self.auditorias.delete_one({"_id": oid})
        return {"relatorios": n_relatorios, "auditorias": 1}

    # ======================================================================
    # RELATÓRIOS
    # ======================================================================
    def criar_relatorio(self, auditoria_id: Id, nota_documental: float, saude_compliance: float,
                        lacunas: list[dict], *, nota_pratica: float | None = None,
                        verificacoes: list[dict] | None = None,
                        feedback_analista: dict | None = None) -> ObjectId:
        """Cria o relatório de uma auditoria existente (no máximo um por auditoria).

        `arquivo` é copiado da auditoria (desnormalização intencional, para o histórico).
        `nota_pratica` e `verificacoes` ficam None quando a Verificação Prática não rodou.
        Esta função NÃO muda o status da auditoria: quem orquestra faz isso com
        `atualizar_auditoria(..., status="concluida")`.
        """
        oid = _oid(auditoria_id)
        auditoria = self.obter_auditoria(oid)
        if auditoria is None:
            raise NaoEncontrado(
                f"Auditoria {auditoria_id} não existe; crie a auditoria antes do relatório.")
        self._checar_normas_ref(lacunas)
        doc = {"auditoria_id": oid, "arquivo": auditoria["arquivo"], "criado_em": agora(),
               "nota_documental": nota_documental, "nota_pratica": nota_pratica,
               "saude_compliance": saude_compliance, "lacunas": lacunas,
               "verificacoes": verificacoes, "feedback_analista": feedback_analista}
        try:
            return self.relatorios.insert_one(doc).inserted_id
        except DuplicateKeyError as exc:
            raise IntegridadeError(f"A auditoria {auditoria_id} já tem relatório.") from exc

    def obter_relatorio(self, relatorio_id: Id) -> dict | None:
        return self.relatorios.find_one({"_id": _oid(relatorio_id)})

    def obter_relatorio_por_auditoria(self, auditoria_id: Id) -> dict | None:
        return self.relatorios.find_one({"auditoria_id": _oid(auditoria_id)})

    def listar_relatorios(self, limite: int = 50, pular: int = 0) -> list[dict]:
        """Histórico: mais recentes primeiro (índice ix_criado_em)."""
        cursor = self.relatorios.find({}).sort("criado_em", DESCENDING).skip(pular).limit(limite)
        return list(cursor)

    def atualizar_relatorio(self, relatorio_id: Id, /, **campos: Any) -> None:
        """Altera notas, lacunas, verificações ou feedback. `auditoria_id`, `arquivo` e
        `criado_em` não mudam. Se `saude_compliance` precisa mudar junto com as notas, o
        chamador informa o valor novo (a regra de cálculo é do backend)."""
        _checar_campos(campos, CAMPOS_RELATORIO_EDITAVEIS, "relatório")
        if campos.get("lacunas") is not None:
            self._checar_normas_ref(campos["lacunas"])
        res = self.relatorios.update_one({"_id": _oid(relatorio_id)}, {"$set": campos})
        if res.matched_count == 0:
            raise NaoEncontrado(f"Relatório {relatorio_id} não encontrado.")

    def registrar_feedback(self, relatorio_id: Id, avaliacao: str,
                           comentario: str | None = None) -> None:
        """Grava o feedback do analista (`avaliacao`: util, parcial ou inutil)."""
        self.atualizar_relatorio(relatorio_id, feedback_analista={
            "avaliacao": avaliacao, "comentario": comentario})

    def remover_relatorio(self, relatorio_id: Id) -> None:
        res = self.relatorios.delete_one({"_id": _oid(relatorio_id)})
        if res.deleted_count == 0:
            raise NaoEncontrado(f"Relatório {relatorio_id} não encontrado.")

    # ------------------------------------------------------------ interno
    def _checar_normas_ref(self, lacunas: list[dict]) -> None:
        """Toda norma citada em `lacunas[].normas_ref` precisa existir em `normas`."""
        ids = {i for lacuna in lacunas for i in lacuna.get("normas_ref", [])}
        if not ids:
            return
        existentes = self.normas.count_documents({"_id": {"$in": list(ids)}})
        if existentes != len(ids):
            raise NaoEncontrado("Alguma norma citada em lacunas[].normas_ref não existe em `normas`.")
