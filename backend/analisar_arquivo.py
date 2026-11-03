"""
Analisa um PDF/DOCX direto no terminal, SEM API e SEM MongoDB. Serve para testar qualquer
documento de empresa em segundos antes de mostrá-lo na aplicação.

    python backend/analisar_arquivo.py caminho/politica.pdf
    python backend/analisar_arquivo.py caminho/politica.docx --busca   # inclui normas próximas (FAISS)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.pln.analisador import analisar_texto, enriquecer_lacunas, faixa_compliance  # noqa: E402
from backend.pln.extracao import ErroExtracao, dividir_secoes, extrair_texto  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", type=Path)
    ap.add_argument("--busca", action="store_true", help="acrescenta normas próximas via FAISS (mais lento)")
    args = ap.parse_args()

    if not args.arquivo.is_file():
        print(f"Arquivo não encontrado: {args.arquivo}")
        return 1
    try:
        texto = extrair_texto(args.arquivo.name, args.arquivo.read_bytes())
    except ErroExtracao as exc:
        print("ERRO:", exc)
        return 1

    secoes = dividir_secoes(texto)
    print(f"\nSeções detectadas ({len(secoes)}):")
    for s in secoes:
        print(f"  - {s.rotulo}  ({len(s.sentencas)} frases)")
    sem_titulo = len(secoes) == 1 and secoes[0].numero is None
    if sem_titulo:
        print("  ATENÇÃO: nenhum título reconhecido; o texto foi analisado como um bloco só.")

    r = analisar_texto(texto)
    lacunas = r["lacunas"]
    if args.busca:
        from backend.pln.busca_normas import BuscadorNormas
        lacunas = enriquecer_lacunas(lacunas, BuscadorNormas(), lambda fonte, ident: ident)

    print(f"\nNota documental: {r['nota_documental']} / 5  ({faixa_compliance(r['saude_compliance'])})")
    print(f"Lacunas: {len(lacunas)}")
    for i, l in enumerate(lacunas, 1):
        print(f"\n{i}. [{l['severidade'].upper()}] {l['clausula']}")
        print(f"   trecho:     {l['trecho'][:160]}")
        print(f"   problema:   {l['problema']}")
        print(f"   referência: {l['referencia']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
