"""
Baixa o texto compilado da LGPD (Lei nº 13.709/2018) direto do Planalto
e estrutura em uma lista de artigos (JSON), pronta para ingestão/RAG.

Fonte oficial: planalto.gov.br (Presidência da República).
Não requer cadastro.

O site do Planalto às vezes demora a responder. O script tenta de novo algumas vezes,
com tempo de leitura maior. Se mesmo assim falhar, use o plano B: abra a URL no navegador,
salve a página (Ctrl+S, "Página da Web, somente HTML") e aponte o script para o arquivo.

Cuidados com a página compilada (todos tratados aqui):
  - Codificação: a página é Windows-1252. NÃO se usa detecção automática (errava e corrompia os acentos).
  - Histórico: um artigo alterado aparece em várias redações, em ordem cronológica. Fica a ÚLTIMA (vigente).
  - Texto riscado (revogado) é descartado, junto com a anotação que sobra dele.
  - Títulos de capítulo/seção e o rodapé "Este texto não substitui…" são retirados do fim dos artigos.

Uso:
    python scripts/download_lgpd.py                         # baixa do Planalto
    python scripts/download_lgpd.py --html caminho/lei.htm  # plano B: usa uma página já salva
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

LGPD_URL = "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm"

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_RAW_HTML = OUT_DIR / "lgpd_raw.html"
OUT_JSON = OUT_DIR / "lgpd_artigos.json"

# Início de artigo, SÓ no começo de uma linha: "Art. 1º", "Art. 12.", "Art. 55-A.", "Art. 5 7." (número partido por tag).
# Citações no meio da frase ("... conforme o Art. 7º") não cortam o texto.
ARTICLE_RE = re.compile(r"^(Art\.\s*\d+(?:\s\d+)?[ºo°]?(?:-[A-Z]{1,2})?)\.?", re.MULTILINE)
CABECALHO_RE = re.compile(r"^(CAP[ÍI]TULO|T[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\b", re.IGNORECASE)
RODAPE_RE = re.compile(r"\s*Este texto n[ãa]o substitui.*\Z", re.DOTALL | re.IGNORECASE)
REVOGADO_FINAL_RE = re.compile(r"\(Revogad[oa][^)]*\)\.?\s*\Z", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
TENTATIVAS = 4
ESPERA_ENTRE_TENTATIVAS = (5, 15, 30)  # segundos
TIMEOUT = (15, 180)  # (conexão, leitura) — o padrão anterior de 60 s era curto para o Planalto


def baixar_html() -> bytes:
    print(f"Baixando LGPD (texto compilado) de:\n  {LGPD_URL}")
    for n in range(1, TENTATIVAS + 1):
        try:
            print(f"Tentativa {n}/{TENTATIVAS}…")
            resp = requests.get(LGPD_URL, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.content  # bytes originais: quem decide a codificação é decodificar()
        except requests.RequestException as exc:
            print(f"  falhou: {exc}")
            if n == TENTATIVAS:
                raise
            espera = ESPERA_ENTRE_TENTATIVAS[n - 1]
            print(f"  nova tentativa em {espera}s")
            time.sleep(espera)
    raise RuntimeError("inalcançável")


def decodificar(dados: bytes) -> str:
    """UTF-8 se for válido; senão Windows-1252 (a codificação das páginas do Planalto)."""
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("cp1252", errors="replace")


def _acentos_corrompidos(html: str) -> bool:
    """Detecta o HTML gravado pela versão antiga do script (Windows-1252 lido como Windows-1250)."""
    ruins = len(re.findall(r"[şăŕę]", html))
    bons = len(re.findall(r"[ºãà]", html))
    return ruins > 20 and bons == 0


def _identificador(bruto: str) -> str:
    return re.sub(r"(?<=\d)\s+(?=\d)", "", bruto).strip()  # "Art. 5 7" -> "Art. 57"


def _limpar_fim(texto: str) -> str:
    """Tira o rodapé e os títulos de capítulo/seção que vazam para o fim do último artigo de cada bloco."""
    texto = RODAPE_RE.sub("", texto)
    linhas = texto.split("\n")
    # Cabeçalho (CAPÍTULO/Seção/TÍTULO) nunca aparece dentro de um artigo: do primeiro em diante é título
    # do bloco seguinte (inclusive a linha com o nome da seção, que vem logo depois).
    for i, linha in enumerate(linhas[1:], start=1):
        if CABECALHO_RE.match(linha.strip()):
            linhas = linhas[:i]
            break
    return "\n".join(linhas).strip()


def extrair_artigos(html: str) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "lxml")

    paragrafos, riscados, residuos = [], 0, 0
    for p in soup.find_all("p"):
        # Texto riscado = redação antiga/revogada. Sai antes de ler o parágrafo.
        tachados = p.find_all(["strike", "s", "del"])
        for tag in tachados:
            tag.decompose()
        riscados += len(tachados)
        texto = " ".join(p.get_text(" ", strip=True).split())  # junta quebras de linha/tabs/nbsp do HTML
        if not texto:
            continue
        if tachados and texto.startswith("("):  # sobrou só a anotação "(Revogado pela Lei…)" de um trecho riscado
            residuos += 1
            continue
        paragrafos.append(texto)
    full_text = "\n".join(paragrafos)

    marcas = list(ARTICLE_RE.finditer(full_text))
    brutos = []
    for atual, proxima in zip(marcas, marcas[1:] + [None]):
        fim = proxima.start() if proxima else len(full_text)
        ident = _identificador(atual.group(1))
        texto = ident + full_text[atual.start() + len(atual.group(1)) : fim]
        brutos.append({"artigo": ident, "texto": _limpar_fim(texto.strip())})

    # Um artigo alterado aparece em várias redações, em ordem cronológica: fica a última (vigente).
    por_id: dict[str, list[dict]] = {}
    for a in brutos:
        por_id.setdefault(a["artigo"], []).append(a)
    artigos, substituidos, revogados = [], {}, []
    for ident, versoes in por_id.items():
        escolhida = versoes[-1]
        artigos.append(escolhida)
        if len(versoes) > 1:
            substituidos[ident] = (len(versoes), escolhida["texto"])
        if REVOGADO_FINAL_RE.search(escolhida["texto"]):
            revogados.append(ident)

    info = {"riscados": riscados, "residuos": residuos, "brutos": len(brutos),
            "substituidos": substituidos, "revogados": revogados}
    return artigos, info


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa e estrutura a LGPD em artigos (JSON).")
    parser.add_argument("--html", help="Plano B: caminho de uma página da lei já salva no navegador.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.html:
        print(f"Usando a página salva em: {args.html}")
        dados = Path(args.html).read_bytes()
    else:
        dados = baixar_html()
        OUT_RAW_HTML.write_bytes(dados)  # bytes originais, sem reinterpretar a codificação

    html = decodificar(dados)
    if _acentos_corrompidos(html):
        sys.exit(
            "Este HTML está com os acentos corrompidos (gravado pela versão antiga do script).\n"
            "Baixe de novo, SEM --html:  python scripts/download_lgpd.py"
        )

    artigos, info = extrair_artigos(html)
    OUT_JSON.write_text(json.dumps(artigos, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK — {len(artigos)} artigos (de {info['brutos']} trechos lidos na página).")
    print(f"     {info['riscados']} trechos riscados removidos; {info['residuos']} anotações órfãs descartadas.")
    if info["substituidos"]:
        print(f"Artigos com várias redações na página (mantida a ÚLTIMA, a mais recente): {len(info['substituidos'])}")
        for ident, (n, texto) in info["substituidos"].items():
            print(f"  {ident}: {n} redações; mantida com {len(texto)} car. — {texto[:95]!r}…")
    if info["revogados"]:
        print(f"ATENÇÃO — a redação mantida termina com nota de REVOGAÇÃO (confira): {info['revogados']}")
    print(f"Artigos estruturados salvos em: {OUT_JSON}")
    if not args.html:
        print(f"HTML bruto salvo em: {OUT_RAW_HTML}")
    print("\nAtenção: confira uma amostra manualmente — páginas de leis mudam de")
    print("formatação com o tempo, e o parser acima é heurístico (regex), não oficial.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        print(f"Arquivo não encontrado: {exc.filename}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Falha ao baixar a LGPD: {exc}", file=sys.stderr)
        print("\nPlano B: abra a URL abaixo no navegador, salve como 'Página da Web, somente HTML'", file=sys.stderr)
        print(f"e rode:  python scripts/download_lgpd.py --html caminho/do/arquivo.htm\n  {LGPD_URL}", file=sys.stderr)
        sys.exit(1)
