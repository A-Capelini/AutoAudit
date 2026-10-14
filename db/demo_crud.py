"""
Demonstração ao vivo do CRUD do AutoAudit (entrega do banco, 20/10).

O que faz, em ordem:
  0. Conecta e mostra o estado do banco (contagem por coleção e por fonte de norma).
  1. CREATE  - cria 1 norma, 1 auditoria e 1 relatório de demonstração.
  2. READ    - lê o que foi criado e algumas normas reais (NIST) já carregadas.
  3. UPDATE  - muda o status da auditoria, preenche a Verificação Prática do relatório,
               registra o feedback do analista e edita a norma.
  4. REGRAS  - tenta 4 operações que DEVEM ser recusadas (integridade e validação).
  5. DELETE  - apaga na ordem certa (relatório, auditoria, norma) e confere que o banco
               voltou ao estado inicial.

Só toca nos registros de demonstração (norma SANS:DEMO-CRUD-001 e o arquivo
demo_crud_politica_seguranca.pdf). Os dados reais (NIST, LGPD) não são alterados, e tudo
o que a demonstração cria é removido ao final, mesmo se algo falhar no meio.

Uso (Mongo do docker-compose no ar, .env preenchido):
    python db/demo_crud.py               # pausa a cada passo: Enter para continuar
    python db/demo_crud.py --sem-pausa   # roda direto, sem pausas
"""

import argparse
import sys
from datetime import timezone

from bson import ObjectId
from pymongo.errors import PyMongoError, WriteError

try:
    from repositorio import IntegridadeError, NaoEncontrado, Repositorio
except ModuleNotFoundError:  # executado como módulo: python -m db.demo_crud
    from db.repositorio import IntegridadeError, NaoEncontrado, Repositorio

FONTE_DEMO = "SANS"
ID_DEMO = "DEMO-CRUD-001"
ARQUIVO_DEMO = "demo_crud_politica_seguranca.pdf"
SHA_DEMO = "d" * 64  # hash fictício

_PAUSAR = True


# ---------------------------------------------------------------- apresentação
def pausar() -> None:
    if _PAUSAR and sys.stdin.isatty():
        input("   [Enter para executar este passo] ")


def passo(titulo: str) -> None:
    print(f"\n{'=' * 72}\n{titulo}\n{'=' * 72}")
    pausar()


def info(msg: str) -> None:
    print(f"   {msg}")


def fmt_data(dt) -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d/%m/%Y %H:%M:%S")


def esperar_falha(descricao: str, funcao, *excecoes) -> bool:
    """Executa `funcao` esperando que o banco/repositório RECUSE. Devolve True se recusou."""
    try:
        funcao()
    except excecoes as exc:
        detalhe = f"código {exc.code} (validação do schema)" if isinstance(exc, WriteError) else str(exc)
        info(f"[recusado, como esperado] {descricao}")
        info(f"    -> {type(exc).__name__}: {detalhe}")
        return True
    info(f"[ATENÇÃO] {descricao}: o banco ACEITOU, mas deveria recusar.")
    return False


def contagens(repo: Repositorio) -> dict[str, int]:
    return {nome: repo.db[nome].count_documents({}) for nome in ("normas", "auditorias", "relatorios")}


# ---------------------------------------------------------------- dados da demo
def lacuna_demo(norma_id: ObjectId) -> dict:
    return {
        "clausula": "Seção 4.2 — Senhas",
        "trecho": "Os usuários devem utilizar senhas seguras.",
        "severidade": "alta",
        "referencia": "NIST SP 800-53 IA-5",
        "problema": "O termo 'seguras' não é mensurável.",
        "sugestao": "Senhas devem ter no mínimo 12 caracteres.",
        "mitre": "T1110 — Brute Force",
        "normas_ref": [norma_id],
    }


VERIFICACOES_DEMO = [{
    "controle": "Portas não utilizadas fechadas",
    "acao": "check_port",
    "alvo": "ssh (22)",
    "esperado": "closed",
    "observado": "open",
    "status": "falhou",
}]


def limpar_demo(repo: Repositorio, silencioso: bool = False) -> None:
    """Remove qualquer resíduo da demonstração (execução anterior interrompida, por exemplo)."""
    removidos = []
    for aud in repo.auditorias.find({"arquivo": ARQUIVO_DEMO}, {"_id": 1}):
        repo.remover_auditoria(aud["_id"])  # apaga o relatório e depois a auditoria
        removidos.append("auditoria")
    orfaos = repo.relatorios.delete_many({"arquivo": ARQUIVO_DEMO}).deleted_count
    if orfaos:
        removidos.append(f"{orfaos} relatório(s) órfão(s)")
    if repo.obter_norma(FONTE_DEMO, ID_DEMO) is not None:
        repo.remover_norma(FONTE_DEMO, ID_DEMO)
        removidos.append("norma")
    if removidos and not silencioso:
        print(f"\nLimpeza de segurança: removidos {', '.join(removidos)} da demonstração.")


# ---------------------------------------------------------------- a demonstração
def executar(repo: Repositorio, antes: dict[str, int]) -> bool:
    passo("0. Estado inicial do banco")
    info(f"banco: {repo.db.name}")
    for nome, total in antes.items():
        info(f"{nome}: {total} documentos")
    info(f"normas por fonte: {repo.contar_normas_por_fonte()}")

    # ------------------------------------------------------------------ CREATE
    passo("1. CREATE - criar norma, auditoria e relatório")
    norma_id = repo.criar_norma(
        FONTE_DEMO, ID_DEMO, "Política de senhas (demonstração)",
        "As senhas devem ter no mínimo 12 caracteres e ser trocadas após suspeita de "
        "comprometimento.", "pt", familia="DEMO")
    info(f"normas     : criada {FONTE_DEMO}:{ID_DEMO}  (_id {norma_id})")

    auditoria_id = repo.criar_auditoria(
        ARQUIVO_DEMO, SHA_DEMO, True, formato="pdf", tamanho_bytes=184233)
    info(f"auditorias : criada {ARQUIVO_DEMO}, status 'pendente'  (_id {auditoria_id})")

    # Verificação Prática ainda não executada: nota_pratica e verificacoes ficam nulas.
    relatorio_id = repo.criar_relatorio(
        auditoria_id, nota_documental=3.4, saude_compliance=3.4,
        lacunas=[lacuna_demo(norma_id)])
    info(f"relatorios : criado para a auditoria, com 1 lacuna ligada à norma  (_id {relatorio_id})")
    info("o campo `arquivo` do relatório foi copiado da auditoria pelo repositório")

    # ------------------------------------------------------------------ READ
    passo("2. READ - consultar")
    norma = repo.obter_norma(FONTE_DEMO, ID_DEMO)
    info(f"obter_norma      : {norma['fonte']}:{norma['identificador']} - {norma['titulo']}")
    info(f"                   criada em {fmt_data(norma['criado_em'])}")

    nist = repo.listar_normas(fonte="NIST_800_53", limite=3)
    if nist:
        info("listar_normas    : 3 primeiras normas reais do NIST (ordem por identificador)")
        for n in nist:
            info(f"                   {n['identificador']:8} {n['titulo']}")
    else:
        info("listar_normas    : nenhuma norma NIST carregada (rode db/seed_normas.py)")

    aud = repo.obter_auditoria(auditoria_id)
    info(f"obter_auditoria  : status '{aud['status']}', concluída em {fmt_data(aud['concluida_em'])}")
    repetidas = repo.buscar_auditorias_por_sha256(SHA_DEMO)
    info(f"por sha256       : {len(repetidas)} auditoria(s) com este hash (detecta documento repetido)")

    rel = repo.obter_relatorio_por_auditoria(auditoria_id)
    info(f"relatório        : arquivo '{rel['arquivo']}', {len(rel['lacunas'])} lacuna(s), "
         f"nota documental {rel['nota_documental']}")
    pratica = "não executada (nulo)" if rel["nota_pratica"] is None else rel["nota_pratica"]
    info(f"                   Verificação Prática: {pratica}")
    recentes = repo.listar_relatorios(limite=1)
    info(f"histórico        : relatório mais recente é de '{recentes[0]['arquivo']}'")

    # ------------------------------------------------------------------ UPDATE
    passo("3. UPDATE - atualizar")
    repo.atualizar_auditoria(auditoria_id, status="processando")
    aud = repo.obter_auditoria(auditoria_id)
    info(f"auditoria        : status -> '{aud['status']}'")
    repo.atualizar_auditoria(auditoria_id, status="concluida")
    aud = repo.obter_auditoria(auditoria_id)
    info(f"auditoria        : status -> '{aud['status']}', concluida_em preenchida "
         f"automaticamente: {fmt_data(aud['concluida_em'])}")

    # saude_compliance 2.8 é só um valor de exemplo; a regra de cálculo é do backend (Sprint 3).
    repo.atualizar_relatorio(relatorio_id, nota_pratica=2.1, saude_compliance=2.8,
                             verificacoes=VERIFICACOES_DEMO)
    rel = repo.obter_relatorio(relatorio_id)
    info(f"relatório        : Verificação Prática executada -> nota_pratica {rel['nota_pratica']}, "
         f"{len(rel['verificacoes'])} verificação(ões), saúde de compliance {rel['saude_compliance']}")

    repo.registrar_feedback(relatorio_id, "util", "Lacunas claras e acionáveis.")
    rel = repo.obter_relatorio(relatorio_id)
    info(f"relatório        : feedback do analista -> {rel['feedback_analista']}")

    repo.atualizar_norma(FONTE_DEMO, ID_DEMO, titulo="Política de senhas (demonstração, editada)")
    info(f"norma            : título -> '{repo.obter_norma(FONTE_DEMO, ID_DEMO)['titulo']}'")

    # ------------------------------------------------------------------ REGRAS
    passo("4. REGRAS - o que o banco/repositório deve RECUSAR")
    recusas = [
        esperar_falha("apagar a norma enquanto um relatório a cita",
                      lambda: repo.remover_norma(FONTE_DEMO, ID_DEMO), IntegridadeError),
        esperar_falha("segundo relatório para a mesma auditoria (índice único)",
                      lambda: repo.criar_relatorio(auditoria_id, 1.0, 1.0, []), IntegridadeError),
        esperar_falha("relatório para uma auditoria que não existe",
                      lambda: repo.criar_relatorio(ObjectId(), 1.0, 1.0, []), NaoEncontrado),
        esperar_falha("lacuna com severidade sem acento ('media') - validador do schema",
                      lambda: repo.atualizar_relatorio(
                          relatorio_id,
                          lacunas=[{**lacuna_demo(norma["_id"]), "severidade": "media"}]),
                      WriteError),
    ]
    if not recusas[3]:
        info("    -> o validador $jsonSchema não está ativo: rode `python db/init_db.py`.")

    # ------------------------------------------------------------------ DELETE
    passo("5. DELETE - apagar na ordem certa")
    repo.remover_relatorio(relatorio_id)
    info("relatorios     : relatório apagado PRIMEIRO (é o filho)")
    resultado = repo.remover_auditoria(auditoria_id)
    info(f"auditorias     : auditoria apagada DEPOIS (pai); removido junto: {resultado}")
    repo.remover_norma(FONTE_DEMO, ID_DEMO)
    info("normas         : norma apagada (já sem relatório que a cite)")
    info("sem transações: se o processo caísse entre o 1º e o 2º passo, restaria uma auditoria")
    info("sem relatório (estado válido, 1 : 0..1). Na ordem inversa restaria um relatório órfão.")

    depois = contagens(repo)
    voltou = depois == antes
    info(f"contagens depois : {depois}")
    info("banco voltou ao estado inicial: " + ("SIM" if voltou else "NÃO - confira os dados!"))

    print("\nDemonstração concluída.")
    return voltou and all(recusas)


def main() -> None:
    global _PAUSAR
    parser = argparse.ArgumentParser(description="Demonstração ao vivo do CRUD do AutoAudit.")
    parser.add_argument("--sem-pausa", action="store_true",
                        help="Não espera Enter entre os passos.")
    args = parser.parse_args()
    _PAUSAR = not args.sem_pausa

    ok = False
    try:
        with Repositorio.from_env() as repo:
            limpar_demo(repo, silencioso=True)  # resíduo de uma execução interrompida
            antes = contagens(repo)
            try:
                ok = executar(repo, antes)
            finally:
                limpar_demo(repo)  # garante que nada da demonstração sobra
    except RuntimeError as exc:  # MONGO_URI ausente
        sys.exit(str(exc))
    except PyMongoError as exc:
        sys.exit(f"Falha no MongoDB: {exc}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
