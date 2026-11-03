"""
Remove do MongoDB as auditorias criadas por TESTES (uploads reais), preservando os 6 exemplos
do seed (db/seed_exemplo.py), que têm hash fictício.

    python db/limpar_testes.py             # só LISTA o que seria apagado (não apaga nada)
    python db/limpar_testes.py --apagar    # apaga de verdade (relatório primeiro, depois a auditoria)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.repositorio import Repositorio  # noqa: E402
from db.seed_exemplo import sha_exemplo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apagar", action="store_true", help="apaga de verdade (sem isso é só simulação)")
    args = ap.parse_args()

    repo = Repositorio.from_env()
    try:
        todas = repo.listar_auditorias(limite=10_000)
        testes = [a for a in todas if a.get("sha256") != sha_exemplo(a["arquivo"])]
        print(f"{len(todas)} auditorias no banco; {len(todas) - len(testes)} de exemplo (mantidas); "
              f"{len(testes)} de teste.")
        for a in testes:
            print(f"  - {a['arquivo']}  [{a['status']}]  {a['criada_em']:%d/%m/%Y %H:%M}")
        if not testes:
            return 0
        if not args.apagar:
            print("\nSimulação: nada foi apagado. Rode com --apagar para remover.")
            return 0
        for a in testes:
            repo.remover_auditoria(a["_id"])
        print(f"\nApagadas {len(testes)} auditorias de teste (e seus relatórios).")
        return 0
    finally:
        repo.fechar()


if __name__ == "__main__":
    sys.exit(main())
