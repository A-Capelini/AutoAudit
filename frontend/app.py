"""AutoAudit — frontend (Streamlit). Rodar, a partir da raiz do repositório: streamlit run frontend/app.py"""
import html

import pandas as pd
import streamlit as st

from api_client import ErroApi, analisar, estado_api, listar_historico, url_api

st.set_page_config(page_title="AutoAudit", page_icon="🛡️", layout="wide")

CORES_SEV = {"alta": "#B42318", "média": "#B45309", "baixa": "#475467"}

st.markdown(
    """
    <style>
    .nota-grande {font-size: 4rem; font-weight: 700; line-height: 1; color: #14213D;}
    .nota-escala {font-size: 1.4rem; color: #667085;}
    .selo {display:inline-block; padding:2px 10px; border-radius:4px; color:#fff;
           font-size:.8rem; font-weight:600;}
    .trecho {border-left: 3px solid #CBD5E1; padding-left: .8rem; margin-bottom: .8rem; color:#475467;}
    </style>
    """,
    unsafe_allow_html=True,
)

if "historico" not in st.session_state:
    st.session_state.historico = []
if "relatorio" not in st.session_state:
    st.session_state.relatorio = None


def faixa(nota: float) -> str:
    if nota >= 4:
        return "Boa conformidade"
    if nota >= 3:
        return "Conformidade parcial"
    if nota >= 2:
        return "Conformidade baixa"
    return "Conformidade crítica"


def rotulo_lacuna(l: dict) -> str:
    """Título do item: severidade, cláusula e o começo do trecho (várias lacunas caem na mesma cláusula)."""
    trecho = " ".join(l["trecho"].split())
    for c in "*_`[]#<>$~":          # o título do expander aceita markdown: evita formatar por acaso
        trecho = trecho.replace(c, "")
    trecho = trecho[:70].rstrip() + ("…" if len(l["trecho"]) > 70 else "")
    return f'{l["severidade"].upper()} · {l["clausula"]} — “{trecho}”'


def selo(sev: str) -> str:
    return f'<span class="selo" style="background:{CORES_SEV.get(sev, "#475467")}">{html.escape(sev)}</span>'


# ---------------------------------------------------------------- páginas
def pagina_nova():
    st.title("Nova auditoria")
    st.write("Envie a política de segurança da empresa para avaliar clareza, abrangência e rigor técnico.")

    arquivo = st.file_uploader("Política de segurança (PDF ou DOCX)", type=["pdf", "docx"])
    com_verif = st.toggle(
        "Incluir Verificação Prática",
        value=True,
        help="Testa em ambiente de laboratório isolado se os controles descritos existem de fato.",
    )
    if com_verif and estado_api(url_api()):
        st.caption("Nesta versão do backend a Verificação Prática ainda não é executada: "
                   "o relatório virá com essa parte marcada como não executada.")
    elif com_verif:
        st.caption("Os testes rodam apenas contra o laboratório isolado (DVWA, Juice Shop, Metasploitable).")

    if st.button("Analisar política", type="primary", disabled=arquivo is None):
        try:
            with st.spinner("Lendo cláusulas e comparando com a base normativa…"):
                rel, origem = analisar(arquivo.name, arquivo.getvalue(), com_verif)
        except ErroApi as erro:
            st.error(f"Não foi possível analisar o documento: {erro}")
            return
        rel["origem"] = origem  # só do frontend: "api" (backend real) ou "simulado"
        listar_historico.clear()  # a auditoria nova já está no banco: o histórico precisa reler
        st.session_state.relatorio = rel
        st.session_state.historico.insert(0, rel)
        st.session_state.ir_para = "Resultado"
        st.rerun()


def pagina_resultado():
    rel = st.session_state.relatorio
    if rel is None:
        st.title("Resultado")
        st.info("Nenhuma auditoria aberta. Envie uma política em **Nova auditoria** ou abra uma do **Histórico**.")
        return

    st.title("Resultado da auditoria")
    st.caption(f"{rel['arquivo']} — analisado em {rel['data']}")
    if rel.get("origem") == "simulado":
        st.warning("Resultado SIMULADO: a API do backend não estava disponível quando esta auditoria "
                   "foi feita, então os dados abaixo são de demonstração e não vêm da análise do documento.")

    c1, c2, c3 = st.columns([1.3, 1, 1])
    with c1:
        st.markdown("**Saúde de Compliance**")
        st.markdown(
            f'<span class="nota-grande">{rel["saude_compliance"]}</span>'
            f'<span class="nota-escala"> / 5</span>',
            unsafe_allow_html=True,
        )
        st.progress(rel["saude_compliance"] / 5)
        st.caption(faixa(rel["saude_compliance"]))
    with c2:
        st.metric("Conformidade documental", f'{rel["nota_documental"]} / 5',
                  help="A política é clara e completa?")
    with c3:
        if rel["nota_pratica"] is None:
            st.metric("Conformidade prática", "—", help="Verificação Prática não executada.")
        else:
            st.metric("Conformidade prática", f'{rel["nota_pratica"]} / 5',
                      help="Os controles estão de fato implementados?")

    aba_lac, aba_ver = st.tabs(["Lacunas e sugestões", "Verificação prática"])

    with aba_lac:
        sev_sel = st.multiselect("Filtrar por severidade", ["alta", "média", "baixa"],
                                 default=["alta", "média", "baixa"])
        lacunas = [l for l in rel["lacunas"] if l["severidade"] in sev_sel]
        if not lacunas:
            st.info("Nenhuma lacuna com os filtros escolhidos.")
        for l in lacunas:
            with st.expander(rotulo_lacuna(l)):
                st.markdown(selo(l["severidade"]), unsafe_allow_html=True)
                st.markdown("**Trecho original**")
                st.markdown(f'<div class="trecho">{html.escape(l["trecho"])}</div>', unsafe_allow_html=True)
                st.markdown(f'**Problema:** {l["problema"]}')
                st.markdown(f'**Referência normativa:** {l["referencia"]}')
                if l["mitre"]:
                    st.markdown(f'**MITRE ATT&CK:** {l["mitre"]}')
                st.markdown("**Sugestão de nova redação**")
                st.code(l["sugestao"], language=None, wrap_lines=True)

    with aba_ver:
        if rel["verificacoes"] is None:
            st.info("A Verificação Prática não foi executada nesta auditoria. "
                    "A nota de Saúde de Compliance considera apenas a avaliação documental.")
        else:
            df = pd.DataFrame(rel["verificacoes"])
            falhas = (df["status"] == "falhou").sum()
            st.write(f"**{falhas} de {len(df)} verificações falharam** — o ambiente diverge do que a política declara.")
            st.dataframe(
                df.rename(columns={"controle": "Controle", "acao": "Ação (contrato JSON)", "alvo": "Alvo",
                                   "esperado": "Esperado", "observado": "Observado", "status": "Status"}),
                width="stretch", hide_index=True,
            )
            st.caption("Resultados de scanners automatizados podem conter falsos positivos. "
                       "Use como apoio à decisão e valide com um analista.")

    st.divider()
    st.caption("O AutoAudit é um assistente de produtividade: revise as sugestões antes de publicar qualquer política.")


def pagina_historico():
    st.title("Histórico")
    do_banco = listar_historico(url_api()) if estado_api(url_api()) else None
    hist = do_banco if do_banco is not None else st.session_state.historico
    if do_banco is not None:
        st.caption(f"Histórico salvo no MongoDB ({len(hist)} auditorias).")
    else:
        st.caption("Backend fora do ar: mostrando só as auditorias feitas nesta sessão do navegador.")
    if not hist:
        st.info("Nenhuma auditoria salva ainda." if do_banco is not None else
                "Nenhuma auditoria nesta sessão. Com o backend no ar, o histórico fica salvo no MongoDB.")
        return
    politicas = sorted({r["arquivo"] for r in hist})
    filtro = st.selectbox("Política", ["Todas"] + politicas) if len(politicas) > 1 else "Todas"
    if filtro != "Todas":
        hist = [r for r in hist if r["arquivo"] == filtro]
    def fmt(x):
        return "—" if x is None else f"{x:.1f}"

    df = pd.DataFrame(
        [{"Data": r["data"], "Arquivo": r["arquivo"], "Documental": fmt(r["nota_documental"]),
          "Prática": fmt(r["nota_pratica"]), "Saúde de Compliance": fmt(r["saude_compliance"])} for r in hist]
    )
    st.dataframe(df, width="stretch", hide_index=True)
    if len(hist) > 1 and (filtro != "Todas" or len(politicas) == 1):
        st.markdown("**Evolução da Saúde de Compliance**")
        # O rótulo leva o número da auditoria: duas auditorias no mesmo minuto têm a mesma
        # data, e um índice repetido faz o gráfico de linha colapsar em um traço vertical.
        cronologico = list(reversed(hist))
        evolucao = pd.DataFrame(
            {"Saúde de Compliance": [r["saude_compliance"] for r in cronologico]},
            index=[f'{i:02d} · {r["data"][:5]} {r["data"][-5:]}' for i, r in enumerate(cronologico, start=1)],
        )
        st.line_chart(evolucao)
    elif len(hist) > 1:
        st.caption("Escolha uma política acima para ver a evolução da nota dela.")
    escolha = st.selectbox("Abrir auditoria", range(len(hist)),
                           format_func=lambda i: f'{hist[i]["data"]} — {hist[i]["arquivo"]}')
    if st.button("Abrir resultado"):
        st.session_state.relatorio = hist[escolha]
        st.session_state.ir_para = "Resultado"
        st.rerun()


# ---------------------------------------------------------------- navegação
PAGINAS = {"Nova auditoria": pagina_nova, "Resultado": pagina_resultado, "Histórico": pagina_historico}

# Troca de página pedida por um botão: precisa ser aplicada antes do st.radio ser criado,
# porque o Streamlit não permite alterar o valor de um widget depois de ele ser desenhado.
if "ir_para" in st.session_state:
    st.session_state.pagina = st.session_state.pop("ir_para")
if "pagina" not in st.session_state:
    st.session_state.pagina = "Nova auditoria"

with st.sidebar:
    st.header("AutoAudit")
    st.caption("Auditoria de políticas de segurança com PLN")
    st.radio("Navegação", list(PAGINAS), key="pagina", label_visibility="collapsed")
    st.divider()
    saude = estado_api(url_api())
    if saude:
        banco = "MongoDB ok" if saude.get("mongo") == "ok" else "MongoDB indisponível"
        st.caption(f"Backend conectado ({banco}; busca semântica: {saude.get('busca_semantica', '—')}).")
    else:
        st.caption("Backend fora do ar: as análises usam dados simulados (modo demonstração).")

PAGINAS[st.session_state.pagina]()
