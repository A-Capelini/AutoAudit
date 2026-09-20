"""
Baixa o catálogo de controles do NIST SP 800-53 Rev. 5 em formato OSCAL (JSON).

Fonte oficial: repositório GitHub usnistgov/oscal-content (mantido pelo NIST).
Não requer cadastro nem chave de API.

Uso:
    python scripts/download_nist_oscal.py
"""

import json
import sys
from pathlib import Path

import requests

CATALOG_URL = (
    "https://raw.githubusercontent.com/usnistgov/oscal-content/main/"
    "nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
)

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_FILE = OUT_DIR / "nist_sp800-53_rev5_catalog.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Baixando catálogo NIST SP 800-53 Rev. 5 de:\n  {CATALOG_URL}")
    resp = requests.get(CATALOG_URL, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    catalog = data["catalog"]
    families = catalog.get("groups", [])
    total_controls = sum(len(g.get("controls", [])) for g in families)

    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK — {len(families)} famílias de controle, {total_controls} controles.")
    print(f"Versão do catálogo: {catalog['metadata'].get('version')}")
    print(f"Salvo em: {OUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Falha ao baixar o catálogo: {exc}", file=sys.stderr)
        sys.exit(1)
