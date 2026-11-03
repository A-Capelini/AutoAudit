"""
Teste de ponta a ponta da API no ar: envia as políticas de data/samples/, confere a resposta
e lê o histórico e o relatório de volta. Os registros FICAM no MongoDB (útil para mostrar no
mongo-express, http://localhost:8081).

    # terminal 1 (raiz do repositório):  uvicorn backend.main:app --reload
    # terminal 2:                        python backend/testar_api.py
"""

import os
import sys
from pathlib import Path

import requests

BASE = os.getenv("AUTOAUDIT_API", "http://localhost:8000")
AMOSTRAS = Path(__file__).resolve().parent.parent / "data" / "samples"
ARQUIVOS = ["Politica_Seguranca_Nimbus_Logistica.pdf", "Politica_Seguranca_Nimbus_Logistica.docx",
            "Politica_Seguranca_Alfa_Saude.pdf", "Politica_Seguranca_Orion_Pagamentos.pdf"]
CHAVES = {"id", "arquivo", "data", "nota_documental", "nota_pratica", "saude_compliance",
          "lacunas", "verificacoes"}

erros = 0


def checar(nome: str, ok: bool, detalhe: str = "") -> None:
    global erros
    erros += 0 if ok else 1
    print(f"  [{'OK' if ok else 'FALHOU'}] {nome} {detalhe}")


def main() -> int:
    try:
        saude = requests.get(f"{BASE}/saude", timeout=5).json()
    except requests.RequestException as exc:
        print(f"API fora do ar em {BASE}: {exc}")
        return 1
    print("Saúde:", saude)
    if saude.get("mongo") != "ok":
        print("MongoDB indisponível: confira `docker compose ps` e o .env (MONGO_URI).")
        return 1

    ultimo_id = None
    for nome in ARQUIVOS:
        print(f"\nPOST /auditorias  {nome}")
        r = requests.post(f"{BASE}/auditorias", timeout=60,
                          files={"arquivo": (nome, (AMOSTRAS / nome).read_bytes())},
                          data={"com_verificacao": "false"})
        checar("status 201", r.status_code == 201, f"(veio {r.status_code})")
        if r.status_code != 201:
            print("   ", r.text[:300])
            continue
        rel = r.json()
        ultimo_id = rel["id"]
        checar("contrato com os campos esperados", set(rel) == CHAVES)
        checar("severidades válidas", all(l["severidade"] in ("alta", "média", "baixa") for l in rel["lacunas"]))
        checar("notas entre 0 e 5", 0 <= rel["nota_documental"] <= 5 and 0 <= rel["saude_compliance"] <= 5)
        checar("sem Verificação Prática (None)", rel["nota_pratica"] is None and rel["verificacoes"] is None)
        print(f"    nota documental {rel['nota_documental']} | {len(rel['lacunas'])} lacunas | {rel['data']}")

    print("\nGET /auditorias")
    historico = requests.get(f"{BASE}/auditorias", params={"limite": 10}, timeout=10).json()
    checar("histórico devolve lista", isinstance(historico, list) and len(historico) >= 1,
           f"({len(historico)} itens)")
    r = requests.get(f"{BASE}/relatorios", params={"limite": 5}, timeout=10)
    lista = r.json() if r.status_code == 200 else []
    checar("GET /relatorios devolve relatórios no contrato",
           r.status_code == 200 and len(lista) >= 1 and all(set(x) == CHAVES for x in lista),
           f"({len(lista)} itens)")
    if ultimo_id:
        print(f"GET /relatorios/{ultimo_id}")
        r = requests.get(f"{BASE}/relatorios/{ultimo_id}", timeout=10)
        checar("relatório lido de volta", r.status_code == 200 and r.json()["id"] == ultimo_id)

    print("\nCasos de erro")
    r = requests.post(f"{BASE}/auditorias", files={"arquivo": ("nota.txt", b"texto")}, timeout=10)
    checar("formato inválido -> 415", r.status_code == 415, f"(veio {r.status_code})")
    r = requests.get(f"{BASE}/relatorios/nao-e-um-id", timeout=10)
    checar("id inválido -> 404", r.status_code == 404, f"(veio {r.status_code})")

    print("\nRESULTADO:", "tudo certo" if erros == 0 else f"{erros} verificação(ões) falharam")
    return 0 if erros == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
