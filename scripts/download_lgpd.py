"""
Baixa o texto compilado da LGPD (Lei nº 13.709/2018) direto do Planalto
e estrutura em uma lista de artigos (JSON), pronta para ingestão/RAG.

Fonte oficial: planalto.gov.br (Presidência da República).
Não requer cadastro.

Uso:
    python scripts/download_lgpd.py
"""

import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

LGPD_URL = "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm"

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_RAW_HTML = OUT_DIR / "lgpd_raw.html"
OUT_JSON = OUT_DIR / "lgpd_artigos.json"

# Identifica o início de cada artigo: "Art. 1º", "Art. 12.", "Art. 5º-A" etc.
ARTICLE_RE = re.compile(r"(Art\.\s*\d+[ºo°]?[\-A-Z]?\.?)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Baixando LGPD (texto compilado) de:\n  {LGPD_URL}")
    resp = requests.get(LGPD_URL, timeout=60)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    OUT_RAW_HTML.write_text(resp.text, encoding="utf-8")

    soup = BeautifulSoup(resp.text, "lxml")
    # O corpo da lei no Planalto fica em parágrafos <p> soltos na página.
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    full_text = "\n".join(p for p in paragraphs if p)

    # Quebra o texto em artigos usando o marcador "Art. N".
    pieces = ARTICLE_RE.split(full_text)
    articles = []
    for i in range(1, len(pieces) - 1, 2):
        header = pieces[i].strip()
        body = pieces[i + 1].strip()
        if body:
            articles.append({"artigo": header, "texto": f"{header} {body}"})

    OUT_JSON.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK — {len(articles)} artigos identificados.")
    print(f"HTML bruto salvo em: {OUT_RAW_HTML}")
    print(f"Artigos estruturados salvos em: {OUT_JSON}")
    print("\nAtenção: confira uma amostra manualmente — páginas de leis mudam de")
    print("formatação com o tempo, e o parser acima é heurístico (regex), não oficial.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Falha ao baixar a LGPD: {exc}", file=sys.stderr)
        sys.exit(1)
