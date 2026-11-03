"""
Regras de detecção de lacunas em políticas de segurança da informação.

Abordagem desta versão: regras explícitas (expressões regulares + critérios de ausência),
sem LLM. Vantagem para a apresentação: cada lacuna é explicável ("disparou a regra X porque
a frase tem Y e não tem Z"). Limitação: só acha o que as regras conhecem; a busca semântica
(FAISS) entra depois para ligar cada trecho às normas mais próximas.

Cada lacuna sai no formato do contrato com o frontend:
    {clausula, trecho, severidade ("alta"|"média"|"baixa"), referencia, problema, sugestao, mitre}

Duas famílias de regra:
  * ESPECÍFICAS (senha, MFA, incidente, dados pessoais, dispositivos pessoais, encarregado):
    um tema com referência e sugestão próprias;
  * GENÉRICA (termos vagos): "sempre que possível", "periodicamente", "em tempo hábil"...
    Só dispara numa frase que nenhuma regra específica já apontou.
"""

from __future__ import annotations

import re

from .extracao import Secao

ORDEM_SEVERIDADE = {"alta": 0, "média": 1, "baixa": 2}


def _tem(padrao: str, texto: str) -> bool:
    return re.search(padrao, texto, re.IGNORECASE) is not None


def _lacuna(secao: Secao, trecho: str, severidade: str, referencia: str, problema: str,
            sugestao: str, mitre: str | None = None) -> dict:
    return {"clausula": secao.rotulo, "trecho": trecho[:400], "severidade": severidade,
            "referencia": referencia, "problema": problema, "sugestao": sugestao, "mitre": mitre}


# --------------------------------------------------------------------------- termos vagos

TERMOS_VAGOS: list[tuple[str, str]] = [  # (expressão, severidade)
    (r"\bsempre que poss[ií]vel\b", "média"),
    (r"\bna medida do poss[ií]vel\b", "média"),
    (r"\bassim que poss[ií]vel\b", "média"),
    (r"\bquando (?:for )?necess[aá]ri[oa]\b", "média"),
    (r"\bquando houver necessidade\b", "média"),
    (r"\bse (?:for )?necess[aá]ri[oa]\b", "média"),
    (r"\bconforme necess[aá]rio\b", "média"),
    (r"\bquando aplic[aá]vel\b", "média"),
    (r"\bem tempo h[aá]bil\b", "média"),
    (r"\bde tempos em tempos\b", "média"),
    (r"\bperiodicamente\b", "média"),
    (r"\bperi[oó]dic[oa]s?\b", "média"),
    (r"\bregularmente\b", "média"),
    (r"\badequad[oa]s?\b", "baixa"),
    (r"\brazo[aá]ve(?:l|is)\b", "baixa"),
]

# Tema da frase -> referência exibida (ordem importa: o primeiro tema que casar vale).
TEMAS: list[tuple[str, str]] = [
    (r"criptograf|cifr", "NIST SP 800-53 SC-28, SC-13; CIS Controls v8 3.11"),
    (r"\bservi[çc]os?\b|\bportas?\b", "NIST SP 800-53 CM-7; CIS Controls v8 4.8"),
    (r"\bbackups?\b|c[óo]pias? de seguran[çc]a", "NIST SP 800-53 CP-9; CIS Controls v8 11.2"),
    (r"vulnerabilid|corre[çc][õo]es|\bpatch|atualiza[çc]", "NIST SP 800-53 RA-5, SI-2; CIS Controls v8 7.5"),
    (r"treinament|conscientiza|orienta[çc]|capacita", "NIST SP 800-53 AT-2; CIS Controls v8 14.1"),
    (r"\bsenhas?\b|credenciais|autentica", "NIST SP 800-53 IA-5; CIS Controls v8 5.2"),
    (r"\bacessos?\b|\bcontas?\b|desativad|revog", "NIST SP 800-53 AC-2; CIS Controls v8 6.2"),
    (r"\bincidentes?\b", "LGPD Art. 48; NIST SP 800-53 IR-6"),
]
REFERENCIA_PADRAO = "NIST SP 800-53 PL-1 (políticas e procedimentos)"


def _termo_vago(frase: str) -> tuple[str, str] | None:
    for padrao, severidade in TERMOS_VAGOS:
        achou = re.search(padrao, frase, re.IGNORECASE)
        if achou:
            return achou.group(0), severidade
    return None


def _regra_termo_vago(secao: Secao, frase: str) -> dict | None:
    vago = _termo_vago(frase)
    if vago is None:
        return None
    termo, severidade = vago
    referencia = next((ref for padrao, ref in TEMAS if _tem(padrao, frase)), REFERENCIA_PADRAO)
    return _lacuna(
        secao, frase, severidade, referencia,
        problema=f"A expressão '{termo}' deixa a regra sem critério verificável: não dá para "
                 "auditar quando ela foi ou não cumprida.",
        sugestao=f"Trocar '{termo}' por prazo, frequência ou responsável explícitos "
                 "(ex.: 'a cada 90 dias', 'em até 24 horas', 'pelo gestor de TI').")


# --------------------------------------------------------------------------- regras específicas

def _regra_senha(secao: Secao, frase: str) -> dict | None:
    if not _tem(r"\bsenhas?\b", frase):
        return None
    if _tem(r"\d+\s*(?:caracteres|d[ií]gitos)|m[ií]nimo de \d+|bloqueio|tentativas|gerenciador", frase):
        return None  # já traz requisito mensurável
    if not _tem(r"\bsegur[ao]s?\b|\bfortes?\b|\bcomplex[ao]s?\b|dif[ií]ce(?:l|is) de adivinhar"
                r"|\bboas senhas\b|\brobust[ao]s?\b|\badequad[ao]s?\b", frase):
        return None
    return _lacuna(
        secao, frase, "alta", "NIST SP 800-53 IA-5; CIS Controls v8 5.2",
        problema="O adjetivo que qualifica a senha não é mensurável: a política não define tamanho "
                 "mínimo, complexidade nem bloqueio por tentativas inválidas.",
        sugestao="Definir requisitos objetivos: mínimo de 12 caracteres combinando letras, números e "
                 "símbolos, bloqueio após 5 tentativas inválidas consecutivas e proibição de reutilizar "
                 "senhas anteriores.",
        mitre="T1110 — Brute Force")


def _regra_mfa(secao: Secao, frase: str, contexto: str) -> dict | None:
    if not _tem(r"\bacessos? remotos?\b|\bVPN\b|\bacessos? externos?\b|\btrabalho remoto\b|\bteletrabalho\b",
                frase):
        return None
    if _tem(r"multifator|multi-fator|m[úu]ltiplos fatores|dois fatores|duplo fator|\bMFA\b|\b2FA\b", contexto):
        return None  # a seção já exige MFA
    return _lacuna(
        secao, frase, "alta", "NIST SP 800-53 IA-2(1); CIS Controls v8 6.5",
        problema="O acesso remoto não exige autenticação multifator (MFA): só a senha protege a entrada "
                 "pela internet.",
        sugestao="Exigir MFA em todo acesso remoto à rede e aos sistemas corporativos, inclusive VPN.",
        mitre="T1133 — External Remote Services")


def _regra_incidente(secao: Secao, frase: str, contexto: str) -> dict | None:
    if not _tem(r"\bincidentes?\b", frase):
        return None
    faltas = []
    if not _tem(r"\b\d+\s*(?:horas?|h|dias?)\b|imediat|no mesmo dia", contexto):
        faltas.append("prazo")
    if not _tem(r"encarregad|\bDPO\b|comit[êe]|CSIRT|ETIR|\bCISO\b|gestor de seguran|equipe de resposta|\bSOC\b",
                contexto):
        faltas.append("responsável designado")
    if not _tem(r"\bANPD\b|autoridade nacional|titulares?", contexto):
        faltas.append("comunicação à ANPD e aos titulares")
    if not faltas:
        return None
    lista = faltas[0] if len(faltas) == 1 else ", ".join(faltas[:-1]) + " e " + faltas[-1]
    return _lacuna(
        secao, frase, "alta" if len(faltas) >= 2 else "média", "LGPD Art. 48; NIST SP 800-53 IR-6",
        problema=f"O tratamento de incidentes não define {lista}.",
        sugestao="Definir quem responde pelo incidente (ex.: encarregado/DPO ou comitê de resposta), "
                 "o prazo máximo de comunicação e o fluxo de aviso à ANPD e aos titulares quando houver "
                 "risco relevante (confirme o prazo vigente no regulamento da ANPD).")


def _regra_legislacao_generica(secao: Secao, frase: str) -> dict | None:
    if not _tem(r"legisla[çc][ãa]o|\bLGPD\b|lei geral de prote", frase):
        return None
    if not _tem(r"\brespeita\b|\bcumpre\b|\bobserva\b|\batende\b|em conformidade|\bsegue\b", frase):
        return None
    if _tem(r"\d|prazo|controles?|encarregad|\bDPO\b|base legal|relat[óo]rio de impacto", frase):
        return None  # a frase traz algo concreto
    return _lacuna(
        secao, frase, "média", "LGPD Art. 46",
        problema="Declaração genérica de conformidade: não cita controles, responsáveis nem prazos "
                 "que a tornem verificável.",
        sugestao="Descrever as medidas adotadas (ex.: medidas técnicas e administrativas do art. 46, "
                 "registro das operações, atendimento a titulares em prazo definido) e quem responde "
                 "por cada uma.")


def _regra_dispositivo_pessoal(secao: Secao, frase: str, contexto: str) -> dict | None:
    if not _tem(r"\b(?:celulares?|notebooks?|smartphones?|aparelhos?|equipamentos?) pr[óo]prios?\b"
                r"|dispositivos? (?:pessoais|particulares)|\bBYOD\b", frase):
        return None
    if _tem(r"\bMDM\b|gest[ãa]o de dispositivos|criptograf|bloqueio de tela|antiv[íi]rus|apagamento remoto"
            r"|\bsenha|autoriza", contexto):
        return None
    return _lacuna(
        secao, frase, "média", "NIST SP 800-53 AC-19",
        problema="Permite dispositivos pessoais acessarem dados da organização sem exigir controles mínimos "
                 "(bloqueio de tela, criptografia, gestão do aparelho).",
        sugestao="Condicionar o uso a bloqueio de tela, criptografia do aparelho, registro/gestão do "
                 "dispositivo (MDM) e possibilidade de apagamento remoto dos dados corporativos.")


# Regras por frase, na ordem de prioridade. `uma_vez_por_secao` evita repetir o mesmo achado
# quando a seção tem várias frases sobre o mesmo tema.
REGRAS_POR_FRASE = [
    ("legislacao", _regra_legislacao_generica, False, False),
    ("senha", _regra_senha, False, False),
    ("mfa", _regra_mfa, True, True),
    ("incidente", _regra_incidente, True, True),
    ("dispositivo", _regra_dispositivo_pessoal, True, True),
]  # (id, função, usa o contexto da seção, dispara no máximo uma vez por seção)


def _regra_sem_encarregado(secoes: list[Secao]) -> dict | None:
    """Regra de AUSÊNCIA: nenhuma menção a encarregado de dados (DPO) no documento inteiro."""
    todo = " ".join(f for s in secoes for f in s.sentencas)
    if _tem(r"encarregad|\bDPO\b|data protection officer", todo):
        return None
    alvo_secao, alvo_frase = None, None
    for secao in secoes:  # ancora o achado na seção de responsabilidades
        if secao.sentencas and _tem(r"responsabilidad|pap[ée]is|atribui", secao.titulo):
            alvo_secao = secao
            alvo_frase = next((f for f in secao.sentencas
                               if _tem(r"respons|supervision|compete|cabe", f)), secao.sentencas[0])
            break
    if alvo_secao is None:
        alvo_secao = Secao(None, "Documento inteiro")
        alvo_frase = "(o documento não menciona o encarregado pelo tratamento de dados pessoais)"
    return _lacuna(
        alvo_secao, alvo_frase, "média", "LGPD Art. 41",
        problema="A política não designa o encarregado pelo tratamento de dados pessoais (DPO): "
                 "ninguém é apontado como canal com os titulares e com a ANPD.",
        sugestao="Designar formalmente o encarregado e divulgar sua identidade e contato (LGPD, art. 41).")


# --------------------------------------------------------------------------- orquestração

def detectar_lacunas(secoes: list[Secao]) -> list[dict]:
    """Aplica todas as regras e devolve as lacunas, da mais grave para a menos grave."""
    achados: list[dict] = []
    for indice, secao in enumerate(secoes):
        contexto = " ".join(secao.sentencas)
        usadas: set[str] = set()
        for frase in secao.sentencas:
            lacuna = None
            for nome, regra, usa_contexto, so_uma_vez in REGRAS_POR_FRASE:
                if so_uma_vez and nome in usadas:
                    continue
                lacuna = regra(secao, frase, contexto) if usa_contexto else regra(secao, frase)
                if lacuna:
                    usadas.add(nome)
                    vago = _termo_vago(frase)  # frase com achado específico E termo vago
                    if vago and vago[0].lower() not in lacuna["problema"].lower():
                        lacuna["problema"] += f" Além disso, '{vago[0]}' torna a exigência subjetiva."
                    break
            if lacuna is None:
                lacuna = _regra_termo_vago(secao, frase)
            if lacuna:
                achados.append(lacuna)

    ausencia = _regra_sem_encarregado(secoes)
    if ausencia:
        achados.append(ausencia)

    achados.sort(key=lambda l: ORDEM_SEVERIDADE[l["severidade"]])  # estável: mantém a ordem do documento
    return achados
