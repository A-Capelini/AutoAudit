"""
Camada de dados do frontend.

Enquanto o backend (Sprint 3) não existe, `analisar_documento` devolve um
relatório simulado. O formato do dicionário É o contrato com a futura API
FastAPI: quando o backend ficar pronto, só esta função muda (troca por um
requests.post para /auditorias) e o resto da interface continua igual.
"""
from datetime import datetime
import hashlib

SEVERIDADES = ["alta", "média", "baixa"]


def _nota_geral(documental: float, pratica: float | None) -> float:
    # Regra provisória: média simples. Se a verificação prática não rodou
    # (cenário FCS), a nota depende só da avaliação documental.
    if pratica is None:
        return round(documental, 1)
    return round((documental + pratica) / 2, 1)


def analisar_documento(nome_arquivo: str, conteudo: bytes, com_verificacao: bool) -> dict:
    """Simula a resposta do backend. Determinística por arquivo (hash)."""
    h = int(hashlib.sha256(conteudo).hexdigest(), 16)
    documental = round(2.2 + (h % 20) / 10, 1)          # 2.2 a 4.1
    pratica = round(1.5 + ((h >> 8) % 20) / 10, 1) if com_verificacao else None

    lacunas = [
        {
            "clausula": "Seção 4.2 — Senhas",
            "trecho": "Os usuários devem utilizar senhas seguras.",
            "severidade": "alta",
            "referencia": "NIST SP 800-53 IA-5; CIS Controls v8 5.2",
            "problema": "Termo 'seguras' não é mensurável: não define tamanho mínimo, complexidade nem rotação.",
            "sugestao": "Senhas devem ter no mínimo 12 caracteres, combinando letras, números e símbolos, "
                        "e ser bloqueadas após 5 tentativas inválidas consecutivas.",
            "mitre": "T1110 — Brute Force",
        },
        {
            "clausula": "Seção 6.1 — Acesso remoto",
            "trecho": "O acesso remoto é permitido mediante autorização.",
            "severidade": "alta",
            "referencia": "NIST SP 800-53 IA-2(1); CIS Controls v8 6.5",
            "problema": "Não exige autenticação multifator (MFA) para acessos remotos.",
            "sugestao": "Todo acesso remoto à rede corporativa deve exigir autenticação multifator.",
            "mitre": "T1133 — External Remote Services",
        },
        {
            "clausula": "Seção 8 — Incidentes",
            "trecho": "Incidentes serão tratados pela equipe de TI.",
            "severidade": "média",
            "referencia": "LGPD Art. 48; NIST SP 800-53 IR-6",
            "problema": "Não define prazo nem responsável pela comunicação à ANPD e aos titulares.",
            "sugestao": "O encarregado (DPO) deve comunicar incidentes com risco relevante à ANPD e aos titulares "
                        "em prazo razoável, conforme o art. 48 da LGPD.",
            "mitre": None,
        },
        {
            "clausula": "Seção 2 — Responsabilidades",
            "trecho": "A diretoria é responsável pela segurança.",
            "severidade": "baixa",
            "referencia": "LGPD Art. 41",
            "problema": "Não nomeia o encarregado de dados (DPO).",
            "sugestao": "A organização deve designar formalmente um encarregado pelo tratamento de dados pessoais.",
            "mitre": None,
        },
    ]

    verificacoes = None
    if com_verificacao:
        verificacoes = [
            {"controle": "Portas não utilizadas fechadas", "acao": "check_port", "alvo": "ssh (22)",
             "esperado": "closed", "observado": "open", "status": "falhou"},
            {"controle": "Portas não utilizadas fechadas", "acao": "check_port", "alvo": "telnet (23)",
             "esperado": "closed", "observado": "closed", "status": "passou"},
            {"controle": "Uso de HTTPS", "acao": "check_https", "alvo": "app web de laboratório",
             "esperado": "enforced", "observado": "optional", "status": "falhou"},
            {"controle": "Política de senhas", "acao": "check_password_policy", "alvo": "app web de laboratório",
             "esperado": "min_length>=12", "observado": "min_length=6", "status": "falhou"},
        ]

    return {
        "id": h % 10**6,
        "arquivo": nome_arquivo,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nota_documental": documental,
        "nota_pratica": pratica,
        "saude_compliance": _nota_geral(documental, pratica),
        "lacunas": lacunas,
        "verificacoes": verificacoes,
    }
