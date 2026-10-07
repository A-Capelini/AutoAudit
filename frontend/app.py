"""AutoAudit — frontend (Streamlit). Rodar com: streamlit run app.py"""
import pandas as pd
import streamlit as st

from mock_data import analisar_documento

st.set_page_config(page_title="AutoAudit", page_icon="🛡️", layout="wide")

CORES_SEV = {"alta": "#B42318", "média": "#B45309", "baixa": "#475467"}

st.markdown(
    """
    <style>
    .nota-grande {font-size: 4rem; font-weight: 700; line-height: 1; color: #14213D;}
    .nota-escala {font-size: 1.4rem; color: #667085;}
    .selo {display:inline-block; padding:2px 10px; border-radius:4px; color:#fff;
           font-size:.8rem; font-weight:600;}
    .trecho {border-left: 3px solid #CBD5E1; padding-left: .8rem; color:#475467;}
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


def selo(sev: str) -> str:
    return f'<span class="selo" style="background:{CORES_SEV[sev]}">{sev}</span>'


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
    if com_verif:
        st.caption("Os testes rodam apenas contra o laboratório isolado (DVWA, Juice Shop, Metasploitable).")

    if st.button("Analisar política", type="primary", disabled=arquivo is None):
        with st.spinner("Lendo cláusulas e comparando com a base normativa…"):
            rel = analisar_documento(arquivo.name, arquivo.getvalue(), com_verif)
        st.session_state.relatorio = rel
        st.session_state.historico.insert(0, rel)
        st.session_state.pagina = "Resultado"
        st.rerun()


def pagina_resultado():
    rel = st.session_state.relatorio
    if rel is None:
        st.title("Resultado")
        st.info("Nenhuma auditoria aberta. Envie uma política em **Nova auditoria** ou abra uma do **Histórico**.")
        return

    st.title("Resultado da auditoria")
    st.caption(f"{rel['arquivo']} — analisado em {rel['data']}")

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
            with st.expander(f'{l["clausula"]}  ·  severidade {l["severidade"]}'):
                st.markdown(selo(l["severidade"]), unsafe_allow_html=True)
                st.markdown("**Trecho original**")
                st.markdown(f'<div class="trecho">{l["trecho"]}</div>', unsafe_allow_html=True)
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
    hist = st.session_state.historico
    if not hist:
        st.info("Nenhuma auditoria nesta sessão. Quando o banco estiver conectado, o histórico ficará salvo no MongoDB.")
        return
    df = pd.DataFrame(
        [{"Data": r["data"], "Arquivo": r["arquivo"], "Documental": r["nota_documental"],
          "Prática": r["nota_pratica"], "Saúde de Compliance": r["saude_compliance"]} for r in hist]
    )
    st.dataframe(df, width="stretch", hide_index=True)
    if len(hist) > 1:
        st.markdown("**Evolução da Saúde de Compliance**")
        st.line_chart(df.iloc[::-1].set_index("Data")["Saúde de Compliance"])
    escolha = st.selectbox("Abrir auditoria", range(len(hist)),
                           format_func=lambda i: f'{hist[i]["data"]} — {hist[i]["arquivo"]}')
    if st.button("Abrir resultado"):
        st.session_state.relatorio = hist[escolha]
        st.session_state.pagina = "Resultado"
        st.rerun()


# ---------------------------------------------------------------- navegação
PAGINAS = {"Nova auditoria": pagina_nova, "Resultado": pagina_resultado, "Histórico": pagina_historico}

with st.sidebar:
    st.header("AutoAudit")
    st.caption("Auditoria de políticas de segurança com PLN")
    st.radio("Navegação", list(PAGINAS), key="pagina", label_visibility="collapsed")
    st.divider()
    st.caption("Versão de demonstração: dados simulados até a integração com o backend.")

PAGINAS[st.session_state.pagina]()
