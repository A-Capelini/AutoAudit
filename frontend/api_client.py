"""
Cliente da API do AutoAudit (backend FastAPI) para o frontend Streamlit.

`analisar()` tenta a API; se ela estiver fora do ar, cai no modo simulado (mock_data.py).
Assim a demonstração local usa o backend de verdade e o app publicado no Streamlit Cloud
(que não alcança a API nem o MongoDB do seu computador) continua funcionando.

URL da API, em ordem: variável de ambiente AUTOAUDIT_API_URL, st.secrets["AUTOAUDIT_API_URL"],
padrão http://localhost:8000.
"""
import os

import requests
import streamlit as st

from mock_data import analisar_documento

PADRAO = "http://localhost:8000"


class ErroApi(Exception):
    """A API está no ar mas recusou ou falhou (ex.: formato inválido, PDF escaneado)."""


def url_api() -> str:
    url = os.getenv("AUTOAUDIT_API_URL")
    if not url:
        try:
            url = st.secrets.get("AUTOAUDIT_API_URL")
        except Exception:  # sem arquivo de secrets (caso normal no uso local)
            url = None
    return (url or PADRAO).rstrip("/")


@st.cache_data(ttl=5, show_spinner=False)
def estado_api(url: str) -> dict | None:
    """Resposta de GET /saude, ou None se a API não responde. Em cache por 5 s (o Streamlit
    reexecuta o script a cada clique)."""
    try:
        r = requests.get(f"{url}/saude", timeout=2)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


@st.cache_data(ttl=3, show_spinner=False)
def listar_historico(url: str, limite: int = 50) -> list[dict] | None:
    """Relatórios salvos no MongoDB (mais recentes primeiro), ou None se a API não responde."""
    try:
        r = requests.get(f"{url}/relatorios", params={"limite": limite}, timeout=10)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def _detalhe(resposta: requests.Response) -> str:
    try:
        detalhe = resposta.json().get("detail")
        return detalhe if isinstance(detalhe, str) else str(detalhe)
    except ValueError:
        return resposta.text[:200]


def analisar(nome: str, conteudo: bytes, com_verificacao: bool) -> tuple[dict, str]:
    """Devolve (relatório no formato do contrato, origem), com origem "api" ou "simulado"."""
    try:
        resposta = requests.post(
            f"{url_api()}/auditorias",
            files={"arquivo": (nome, conteudo)},
            data={"com_verificacao": "true" if com_verificacao else "false"},
            timeout=(3, 120),  # conectar: 3 s; a 1ª análise pode esperar o modelo carregar
        )
    except requests.ConnectionError:  # API fora do ar -> modo simulado
        return analisar_documento(nome, conteudo, com_verificacao), "simulado"
    except requests.Timeout as exc:
        raise ErroApi("A API demorou demais para responder. Tente de novo em instantes.") from exc

    if resposta.status_code == 201:
        return resposta.json(), "api"
    if resposta.status_code == 503:  # API no ar, mas sem o MongoDB -> modo simulado
        return analisar_documento(nome, conteudo, com_verificacao), "simulado"
    raise ErroApi(f"{_detalhe(resposta)} (erro {resposta.status_code})")
