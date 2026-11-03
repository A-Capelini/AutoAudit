"""
Mostra o que a busca semântica (FAISS) devolve para cada lacuna encontrada nas políticas de
teste. Serve para conferir se as normas "próximas" fazem sentido antes de apresentar.

Precisa do índice (python db/build_faiss.py). NÃO precisa do MongoDB. Rodar na raiz:

    python backend/testar_busca.py                 # só a Nimbus (6 lacunas)
    python backend/testar_busca.py --todas         # as quatro políticas de data/samples/
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.pln.analisador import TOP_CANDIDATAS, analisar_texto, selecionar_proximas  # noqa: E402
from backend.pln.busca_normas import BuscadorNormas  # noqa: E402
from backend.pln.extracao import extrair_texto  # noqa: E402

AMOSTRAS = RAIZ / "data" / "samples"
NIMBUS = ["Politica_Seguranca_Nimbus_Logistica.pdf"]
TODAS = NIMBUS + ["Politica_Seguranca_Alfa_Saude.pdf", "Politica_Seguranca_Orion_Pagamentos.pdf"]


def linha(r: dict, aceitas: list[dict]) -> str:
    marca = "+" if r in aceitas else " "  # + = entra na referência do relatório
    return f"{marca} {r['nota']:.2f} {r['fonte']} {r['identificador']}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--todas", action="store_true")
    args = parser.parse_args()

    buscador = BuscadorNormas()
    inicio = time.time()
    try:
        buscador.carregar()
    except Exception as exc:
        print(f"Busca indisponível: {exc}")
        return 1
    print(f"Modelo e índice carregados em {time.time() - inicio:.1f}s. (+ = norma que entra no relatório)\n")

    for nome in (TODAS if args.todas else NIMBUS):
        lacunas = analisar_texto(extrair_texto(nome, (AMOSTRAS / nome).read_bytes()))["lacunas"]
        print(f"=== {nome}")
        for l in lacunas:
            t0 = time.time()
            achados = buscador.buscar(f"{l['trecho']} {l['problema']}", TOP_CANDIDATAS)
            aceitas = selecionar_proximas(l["referencia"], achados)
            print(f"\n{l['clausula']}  [{l['severidade']}]  curada: {l['referencia']}")
            print(f"  trecho: {l['trecho'][:90]}  ({time.time() - t0:.2f}s)")
            for r in achados:
                print("     ", linha(r, aceitas))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
