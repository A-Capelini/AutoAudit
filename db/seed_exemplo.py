"""
Dados de exemplo para `auditorias` e `relatorios` (entrega do banco, 20/10).

Cria 6 auditorias que cobrem todos os estados do ciclo de vida, e 3 relatórios:
  - Nimbus Logística : concluída, COM Verificação Prática (nota documental, prática e saúde)
  - Alfa Saúde       : concluída, SEM Verificação Prática (nota_pratica e verificacoes nulas)
  - Orion Tech       : concluída, com Verificação Prática e nota alta
  - Vega             : erro        (sem relatório)
  - Zeta             : processando (sem relatório)
  - Kappa            : pendente    (sem relatório)

As lacunas apontam (`normas_ref`) para normas REAIS já carregadas em `normas` (NIST e LGPD),
buscadas por (fonte, identificador). Uma norma que não exista na base é avisada e ignorada.

Tudo aqui é fictício: empresas, documentos, hashes e notas inventados só para demonstração
(os valores de `saude_compliance` são exemplos; a regra de cálculo é do backend, Sprint 3).
As datas são retroativas, para o histórico parecer real.

Idempotente: cada auditoria de exemplo tem um sha256 fixo (derivado do nome do arquivo); se já
existe, é pulada. Use --recriar para apagar as de exemplo (relatório antes da auditoria) e criar
de novo. Nada além dos registros de exemplo é alterado.

Uso (Mongo do docker-compose no ar, .env preenchido):
    python db/seed_exemplo.py
    python db/seed_exemplo.py --recriar
"""

import argparse
import hashlib
import sys
from collections import Counter
from datetime import timedelta

from pymongo.errors import PyMongoError

try:
    from repositorio import Repositorio, agora
except ModuleNotFoundError:  # executado como módulo: python -m db.seed_exemplo
    from db.repositorio import Repositorio, agora

NIST = "NIST_800_53"
LGPD = "LGPD"

AMOSTRAS = [
    {
        "arquivo": "Politica_Seguranca_Nimbus_Logistica.pdf",
        "formato": "pdf", "tamanho_bytes": 184233, "com_verificacao": True,
        "status": "concluida", "ha": timedelta(days=6, hours=3),
        "relatorio": {
            "nota_documental": 3.4, "nota_pratica": 2.1, "saude_compliance": 2.8,
            "lacunas": [
                {
                    "clausula": "Seção 4.2 — Senhas",
                    "trecho": "Os usuários devem utilizar senhas seguras.",
                    "severidade": "alta",
                    "referencia": "NIST SP 800-53 IA-5; CIS Controls v8 5.2",
                    "problema": "O termo 'seguras' não é mensurável: não define tamanho mínimo, "
                                "complexidade, prazo de troca nem bloqueio após tentativas.",
                    "sugestao": "Exigir senhas com no mínimo 12 caracteres, verificação contra listas "
                                "de senhas vazadas e bloqueio temporário após 5 tentativas falhas; "
                                "adotar MFA para acessos privilegiados.",
                    "mitre": "T1110 — Brute Force",
                    "normas": [(NIST, "IA-5")],
                },
                {
                    "clausula": "Seção 7.1 — Incidentes",
                    "trecho": "Incidentes de segurança serão comunicados em prazo razoável.",
                    "severidade": "média",
                    "referencia": "LGPD Art. 48; NIST SP 800-53 IR-6",
                    "problema": "'Prazo razoável' é impreciso e não indica quem comunica, a quem nem "
                                "por qual canal; a LGPD prevê a comunicação à ANPD e ao titular quando "
                                "o incidente puder causar risco ou dano relevante.",
                    "sugestao": "Definir um prazo interno máximo para acionar a resposta a incidentes "
                                "(por exemplo, 24 horas) e o responsável pela comunicação à ANPD e aos "
                                "titulares, com modelo de notificação.",
                    "mitre": None,
                    "normas": [(LGPD, "Art. 48"), (NIST, "IR-6")],
                },
                {
                    "clausula": "Seção 9.3 — Cópias de segurança",
                    "trecho": "Os backups são realizados regularmente.",
                    "severidade": "média",
                    "referencia": "NIST SP 800-53 CP-9",
                    "problema": "'Regularmente' não define frequência, retenção, local de "
                                "armazenamento nem testes de restauração.",
                    "sugestao": "Definir a frequência por criticidade do sistema, a retenção mínima, "
                                "uma cópia fora do ambiente de produção e teste de restauração trimestral.",
                    "mitre": "T1486 — Data Encrypted for Impact",
                    "normas": [(NIST, "CP-9")],
                },
                {
                    "clausula": "Seção 3.1 — Responsabilidades",
                    "trecho": "A área de TI cuida da proteção dos dados pessoais.",
                    "severidade": "baixa",
                    "referencia": "LGPD Art. 41",
                    "problema": "Não designa o encarregado pelo tratamento de dados pessoais nem "
                                "divulga sua identidade e contato.",
                    "sugestao": "Designar formalmente o encarregado (DPO) e publicar nome e canal de contato.",
                    "mitre": None,
                    "normas": [(LGPD, "Art. 41")],
                },
            ],
            "verificacoes": [
                {"controle": "Portas não utilizadas fechadas", "acao": "check_port",
                 "alvo": "ssh (22)", "esperado": "closed", "observado": "open", "status": "falhou"},
                {"controle": "Portas não utilizadas fechadas", "acao": "check_port",
                 "alvo": "telnet (23)", "esperado": "closed", "observado": "closed", "status": "passou"},
                {"controle": "Política de senha mínima aplicada", "acao": "check_password_policy",
                 "alvo": "servidor de autenticação (laboratório)", "esperado": "mínimo de 12 caracteres",
                 "observado": "mínimo de 8 caracteres", "status": "falhou"},
                {"controle": "Cabeçalhos de segurança HTTP", "acao": "check_http_headers",
                 "alvo": "portal interno (laboratório)", "esperado": "HSTS ativo",
                 "observado": "HSTS ativo", "status": "passou"},
            ],
            "feedback": ("util", "Lacunas claras; a de senhas foi confirmada na verificação prática."),
        },
    },
    {
        "arquivo": "Politica_Privacidade_Alfa_Saude.docx",
        "formato": "docx", "tamanho_bytes": 96512, "com_verificacao": False,
        "status": "concluida", "ha": timedelta(days=4, hours=1),
        "relatorio": {
            # Sem Verificação Prática: nota_pratica e verificacoes ficam nulas.
            "nota_documental": 2.6, "nota_pratica": None, "saude_compliance": 2.6,
            "lacunas": [
                {
                    "clausula": "Seção 2.4 — Bases legais",
                    "trecho": "Coletamos dados pessoais sempre que necessário para o atendimento.",
                    "severidade": "alta",
                    "referencia": "LGPD Art. 7º e Art. 11",
                    "problema": "Não indica a base legal de cada tratamento; para dados de saúde "
                                "(sensíveis), o Art. 11 restringe as hipóteses possíveis.",
                    "sugestao": "Associar cada finalidade a uma base legal e, para dados de saúde, "
                                "às hipóteses do Art. 11 (por exemplo, tutela da saúde ou "
                                "consentimento específico e destacado).",
                    "mitre": None,
                    "normas": [(LGPD, "Art. 11")],
                },
                {
                    "clausula": "Seção 5.2 — Retenção",
                    "trecho": "Os dados são mantidos pelo tempo que a empresa julgar necessário.",
                    "severidade": "média",
                    "referencia": "LGPD Art. 15 e Art. 16",
                    "problema": "Não define prazo de retenção nem critério de eliminação ao fim do tratamento.",
                    "sugestao": "Criar uma tabela de temporalidade por categoria de dado e um "
                                "procedimento de eliminação ou anonimização.",
                    "mitre": None,
                    "normas": [(LGPD, "Art. 15"), (LGPD, "Art. 16")],
                },
                {
                    "clausula": "Seção 6.1 — Segurança",
                    "trecho": "Adotamos medidas de segurança adequadas.",
                    "severidade": "média",
                    "referencia": "LGPD Art. 46; NIST SP 800-53 SC-28",
                    "problema": "'Adequadas' não especifica as medidas técnicas, como criptografia "
                                "de dados em repouso e controle de acesso.",
                    "sugestao": "Listar as medidas mínimas: criptografia em repouso e em trânsito, "
                                "controle de acesso por perfil e registro de acessos aos prontuários.",
                    "mitre": "T1005 — Data from Local System",
                    "normas": [(LGPD, "Art. 46"), (NIST, "SC-28")],
                },
            ],
            "verificacoes": None,
            "feedback": None,
        },
    },
    {
        "arquivo": "Plano_Continuidade_Orion_Tech.pdf",
        "formato": "pdf", "tamanho_bytes": 312904, "com_verificacao": True,
        "status": "concluida", "ha": timedelta(days=2, hours=5),
        "relatorio": {
            "nota_documental": 4.2, "nota_pratica": 3.8, "saude_compliance": 4.0,
            "lacunas": [
                {
                    "clausula": "Seção 8.4 — Testes do plano",
                    "trecho": "O plano será revisado quando necessário.",
                    "severidade": "baixa",
                    "referencia": "NIST SP 800-53 CP-4",
                    "problema": "Não define a periodicidade de revisão nem exercícios de teste do plano "
                                "de contingência.",
                    "sugestao": "Revisar o plano pelo menos uma vez por ano e após mudanças relevantes, "
                                "com exercício de simulação documentado.",
                    "mitre": None,
                    "normas": [(NIST, "CP-4")],
                },
            ],
            "verificacoes": [
                {"controle": "Portas não utilizadas fechadas", "acao": "check_port",
                 "alvo": "rdp (3389)", "esperado": "closed", "observado": "closed", "status": "passou"},
                {"controle": "Protocolos TLS obsoletos desativados", "acao": "check_tls",
                 "alvo": "portal (laboratório), porta 443", "esperado": "TLS 1.2 ou superior",
                 "observado": "TLS 1.2 ou superior", "status": "passou"},
                {"controle": "Cabeçalhos de segurança HTTP", "acao": "check_http_headers",
                 "alvo": "portal (laboratório)", "esperado": "HSTS ativo",
                 "observado": "HSTS ativo", "status": "passou"},
            ],
            "feedback": ("parcial", "Faltou citar o teste de restauração dos backups."),
        },
    },
    {
        "arquivo": "Politica_Acesso_Remoto_Vega.pdf",
        "formato": "pdf", "tamanho_bytes": 58311, "com_verificacao": True,
        "status": "erro", "ha": timedelta(days=3, hours=2),
        "erro": "Falha ao extrair o texto: o PDF está protegido por senha.",
    },
    {
        "arquivo": "Norma_Backup_Zeta_Industrial.docx",
        "formato": "docx", "tamanho_bytes": 77204, "com_verificacao": False,
        "status": "processando", "ha": timedelta(minutes=3),
    },
    {
        "arquivo": "Politica_Uso_Aceitavel_Kappa.pdf",
        "formato": "pdf", "tamanho_bytes": 143007, "com_verificacao": True,
        "status": "pendente", "ha": timedelta(minutes=1),
    },
]

DURACAO_FICTICIA = timedelta(minutes=4)


def sha_exemplo(arquivo: str) -> str:
    """Hash fixo e fictício (não é o hash de nenhum arquivo real)."""
    return hashlib.sha256(f"exemplo-autoaudit:{arquivo}".encode("utf-8")).hexdigest()


def resolver_normas(repo: Repositorio, pares: list, stats: dict) -> list:
    """Converte [(fonte, identificador)] em _ids da coleção `normas`; ignora as ausentes."""
    ids = []
    for fonte, identificador in pares:
        norma = repo.obter_norma(fonte, identificador)
        if norma is None:
            stats["refs_faltando"].append(f"{fonte}:{identificador}")
        else:
            ids.append(norma["_id"])
            stats["refs_ok"] += 1
    return ids


def criar_amostra(repo: Repositorio, amostra: dict, stats: dict) -> bool:
    """Cria a auditoria (e o relatório, se houver). Devolve True se criou relatório."""
    criada = agora() - amostra["ha"]
    fim = criada + DURACAO_FICTICIA
    status = amostra["status"]

    auditoria_id = repo.criar_auditoria(
        amostra["arquivo"], sha_exemplo(amostra["arquivo"]), amostra["com_verificacao"],
        formato=amostra["formato"], tamanho_bytes=amostra["tamanho_bytes"])

    relatorio_id = None
    if status in ("processando", "concluida"):
        repo.atualizar_auditoria(auditoria_id, status="processando")
    if status == "erro":
        repo.atualizar_auditoria(auditoria_id, status="erro", erro=amostra["erro"], concluida_em=fim)
    if status == "concluida":
        rel = amostra["relatorio"]
        lacunas = []
        for lac in rel["lacunas"]:
            lacuna = {k: v for k, v in lac.items() if k != "normas"}
            lacuna["normas_ref"] = resolver_normas(repo, lac["normas"], stats)
            lacunas.append(lacuna)
        feedback = None
        if rel["feedback"] is not None:
            feedback = {"avaliacao": rel["feedback"][0], "comentario": rel["feedback"][1]}
        relatorio_id = repo.criar_relatorio(
            auditoria_id, rel["nota_documental"], rel["saude_compliance"], lacunas,
            nota_pratica=rel["nota_pratica"], verificacoes=rel["verificacoes"],
            feedback_analista=feedback)
        repo.atualizar_auditoria(auditoria_id, status="concluida", concluida_em=fim)
        # Datas retroativas (só nos dados de exemplo): o repositório sempre grava "agora".
        repo.relatorios.update_one({"_id": relatorio_id}, {"$set": {"criado_em": fim}})
    repo.auditorias.update_one({"_id": auditoria_id}, {"$set": {"criada_em": criada}})
    return relatorio_id is not None


def remover_exemplos(repo: Repositorio) -> int:
    """Apaga só as auditorias de exemplo (identificadas pelo sha256 fixo), relatório primeiro."""
    removidas = 0
    for amostra in AMOSTRAS:
        for aud in repo.buscar_auditorias_por_sha256(sha_exemplo(amostra["arquivo"])):
            repo.remover_auditoria(aud["_id"])  # apaga o relatório e depois a auditoria
            removidas += 1
    return removidas


def executar(repo: Repositorio, recriar: bool = False) -> dict:
    stats = {"criadas": 0, "puladas": 0, "removidas": 0, "relatorios": 0,
             "refs_ok": 0, "refs_faltando": []}
    if recriar:
        stats["removidas"] = remover_exemplos(repo)
        print(f"[recriar] {stats['removidas']} auditoria(s) de exemplo removida(s)")

    for amostra in AMOSTRAS:
        if repo.buscar_auditorias_por_sha256(sha_exemplo(amostra["arquivo"])):
            print(f"[pulada ] {amostra['arquivo']} (já existe)")
            stats["puladas"] += 1
            continue
        com_relatorio = criar_amostra(repo, amostra, stats)
        stats["criadas"] += 1
        stats["relatorios"] += int(com_relatorio)
        print(f"[criada ] {amostra['arquivo']:<42} {amostra['status']:<12} "
              f"{'com relatório' if com_relatorio else 'sem relatório'}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Dados de exemplo para auditorias e relatórios.")
    parser.add_argument("--recriar", action="store_true",
                        help="Apaga as auditorias de exemplo (e seus relatórios) e cria de novo.")
    args = parser.parse_args()

    try:
        with Repositorio.from_env() as repo:
            stats = executar(repo, recriar=args.recriar)
            por_status = Counter(a["status"] for a in repo.listar_auditorias(limite=1000))
            total_rel = repo.relatorios.count_documents({})
    except RuntimeError as exc:  # MONGO_URI ausente
        sys.exit(str(exc))
    except PyMongoError as exc:
        sys.exit(f"Falha no MongoDB: {exc}")

    print(f"\nCriadas: {stats['criadas']} | puladas: {stats['puladas']} | "
          f"relatórios criados: {stats['relatorios']}")
    print(f"normas_ref resolvidas: {stats['refs_ok']}")
    if stats["refs_faltando"]:
        faltando = sorted(set(stats["refs_faltando"]))
        print(f"ATENÇÃO: {len(faltando)} norma(s) não encontrada(s) em `normas` (ignoradas): "
              f"{', '.join(faltando)}")
    print(f"No banco agora: auditorias por status = {dict(sorted(por_status.items()))}; "
          f"relatórios = {total_rel}")


if __name__ == "__main__":
    main()
