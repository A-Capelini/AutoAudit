"""
Mede o motor de regras em uma pasta de políticas (PDF/DOCX) e imprime uma tabela comparável.

Serve para acompanhar a calibração: rode ANTES e DEPOIS de mexer nas regras e compare. Não usa
MongoDB nem o modelo de embeddings.

    python backend/avaliar_politicas.py                         # data/raw/politicas_reais
    python backend/avaliar_politicas.py outra/pasta
    python backend/avaliar_politicas.py --salvar antes.json     # guarda o resultado
    python backend/avaliar_politicas.py --comparar antes.json   # mostra o que mudou

Atenção: sem especialista rotulando os documentos, a tabela mostra o COMPORTAMENTO do motor
(quantas lacunas, de que tipo, que nota), não sua acurácia. A única verdade conhecida é o
gabarito da Nimbus (`python backend/validar_gabarito.py`).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.pln.analisador import analisar_texto  # noqa: E402
from backend.pln.extracao import ErroExtracao, extrair_texto  # noqa: E402

PASTA_PADRAO = RAIZ / "data" / "raw" / "politicas_reais"
FORMATOS = {".pdf", ".docx"}

# Tipo da lacuna, reconhecido pelo texto do problema (o contrato com o frontend não tem campo de regra).
TIPOS = [
    ("vago", "sem critério verificável"),
    ("incidente", "tratamento de incidentes"),
    ("senha", "senha"),
    ("mfa", "multifator"),
    ("legislacao", "declaração genérica"),
    ("dpo", "encarregado"),
    ("dispositivo", "dispositivos pessoais"),
    ("backup", "backup"),
    ("logs", "registros (logs)"),
    ("criptografia", "criptografia"),
    ("treinamento", "treinamento"),
]


def tipo_da_lacuna(lacuna: dict) -> str:
    texto = lacuna["problema"].lower()
    return next((nome for nome, chave in TIPOS if chave in texto), "outro")


def avaliar(pasta: Path) -> dict:
    resultado = {}
    for arquivo in sorted(pasta.iterdir()):
        if arquivo.suffix.lower() not in FORMATOS:
            continue
        try:
            r = analisar_texto(extrair_texto(arquivo.name, arquivo.read_bytes()))
        except ErroExtracao as exc:
            resultado[arquivo.name] = {"erro": str(exc)}
            continue
        lacunas = r["lacunas"]
        resultado[arquivo.name] = {
            "secoes": r["secoes_analisadas"],
            "nota": r["nota_documental"],
            "lacunas": len(lacunas),
            "por_severidade": dict(Counter(l["severidade"] for l in lacunas)),
            "por_tipo": dict(Counter(tipo_da_lacuna(l) for l in lacunas)),
        }
    return resultado


def imprimir(resultado: dict, antes: dict | None = None) -> None:
    print(f"{'arquivo':46} {'seç':>3} {'nota':>9} {'lac':>7}  por tipo")
    for nome, d in resultado.items():
        if "erro" in d:
            print(f"{nome[:46]:46} ERRO: {d['erro']}")
            continue
        a = (antes or {}).get(nome)
        nota = f"{d['nota']:.1f}" + (f" ({a['nota']:.1f})" if a and "nota" in a else "")
        lac = f"{d['lacunas']}" + (f" ({a['lacunas']})" if a and "lacunas" in a else "")
        tipos = ", ".join(f"{t}={n}" for t, n in sorted(d["por_tipo"].items()))
        print(f"{nome[:46]:46} {d['secoes']:>3} {nota:>9} {lac:>7}  {tipos}")
    if antes:
        print("\n(valores entre parênteses = antes)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta", nargs="?", type=Path, default=PASTA_PADRAO)
    ap.add_argument("--salvar", type=Path, help="grava o resultado em JSON")
    ap.add_argument("--comparar", type=Path, help="compara com um JSON salvo antes")
    args = ap.parse_args()
    if not args.pasta.is_dir():
        print(f"Pasta não encontrada: {args.pasta}")
        return 1
    resultado = avaliar(args.pasta)
    antes = json.loads(args.comparar.read_text(encoding="utf-8")) if args.comparar else None
    imprimir(resultado, antes)
    if args.salvar:
        args.salvar.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSalvo em {args.salvar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
