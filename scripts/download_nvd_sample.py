"""
Baixa uma amostra de CVEs recentes da API 2.0 da NVD (NIST).

Sem chave de API: limite de 5 requisições/30s (suficiente para uma amostra).
Com chave gratuita (NVD_API_KEY no .env): limite sobe para 50/30s — necessário
se for baixar o feed inteiro ou rodar isso com frequência.
Registro gratuito: https://nvd.nist.gov/developers/request-an-api-key

Uso:
    python scripts/download_nvd_sample.py [--keyword ssh] [--results 50]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Baixa uma amostra de CVEs da NVD.")
    parser.add_argument("--keyword", default=None, help="Filtra por palavra-chave (ex.: 'mongodb').")
    parser.add_argument("--results", type=int, default=50, help="Quantidade de CVEs a buscar (máx. 2000/página).")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    headers = {"Accept": "application/json"}
    api_key = os.getenv("NVD_API_KEY")
    if api_key:
        headers["apiKey"] = api_key
    else:
        print("Aviso: NVD_API_KEY não definida no .env — usando limite público (5 req/30s).")

    params = {"resultsPerPage": args.results}
    if args.keyword:
        params["keywordSearch"] = args.keyword

    print(f"Consultando NVD API: {API_URL}  params={params}")
    resp = requests.get(API_URL, headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    vulns = data.get("vulnerabilities", [])
    out_name = f"nvd_sample_{args.keyword or 'geral'}.json".replace(" ", "_")
    out_file = OUT_DIR / out_name
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK — {len(vulns)} CVEs recebidos (de um total de {data.get('totalResults')} disponíveis).")
    print(f"Salvo em: {out_file}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Falha ao consultar a NVD: {exc}", file=sys.stderr)
        sys.exit(1)
