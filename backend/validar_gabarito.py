"""
Valida o motor de regras contra o gabarito da política da Nimbus
(data/samples/Gabarito_Politica_Nimbus.docx): 6 falhas plantadas e 5 trechos adequados.

  * falha plantada não encontrada  = falso negativo
  * trecho adequado apontado       = falso positivo

Não precisa de MongoDB nem do modelo de embeddings. Rodar na raiz do repositório:

    python backend/validar_gabarito.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.pln.analisador import analisar_texto  # noqa: E402
from backend.pln.extracao import extrair_texto  # noqa: E402

AMOSTRAS = RAIZ / "data" / "samples"
ARQUIVOS = ["Politica_Seguranca_Nimbus_Logistica.pdf", "Politica_Seguranca_Nimbus_Logistica.docx"]

# (id, seção, trecho que identifica a falha, descrição do gabarito)
FALHAS = [
    ("F1", "2", "diretoria é responsável", "não designa encarregado de dados (DPO)"),
    ("F2", "2", "respeita a legislação", "declaração vaga de conformidade com a LGPD"),
    ("F3", "4", "senhas seguras", "'seguras' não é mensurável"),
    ("F4", "5", "acesso remoto", "não exige MFA"),
    ("F5", "6", "sempre que possível", "'sempre que possível' enfraquece a regra"),
    ("F6", "8", "Incidentes de segurança serão", "sem prazo, responsável nem comunicação à ANPD"),
]


def validar(arquivo: str) -> bool:
    texto = extrair_texto(arquivo, (AMOSTRAS / arquivo).read_bytes())
    lacunas = analisar_texto(texto)["lacunas"]
    print(f"\n=== {arquivo}: {len(lacunas)} lacunas")

    usadas, achadas = set(), 0
    for fid, secao, chave, descricao in FALHAS:
        indice = next((i for i, l in enumerate(lacunas)
                       if l["clausula"].startswith(f"Seção {secao} ")
                       and chave.lower() in l["trecho"].lower()), None)
        if indice is None:
            print(f"  {fid}  NÃO ACHOU  (seção {secao}: {descricao})")
        else:
            usadas.add(indice)
            achadas += 1
            print(f"  {fid}  achou      {lacunas[indice]['severidade']:5} | {lacunas[indice]['referencia']}")

    extras = [l for i, l in enumerate(lacunas) if i not in usadas]
    # Lacunas do "Documento inteiro" são achados de AUSÊNCIA (backup, logs, criptografia…): o gabarito
    # rotula trechos, não temas ausentes, então elas não entram na conta de falso positivo. Ficam à vista.
    ausencias = [l for l in extras if l["clausula"] == "Documento inteiro"]
    falsos = [l for l in extras if l["clausula"] != "Documento inteiro"]
    for l in falsos:
        print(f"  FALSO POSITIVO: {l['clausula']} | {l['trecho'][:70]}")
    for l in ausencias:
        print(f"  ausência (sem rótulo no gabarito): {l['trecho']}")
    print(f"  -> achadas {achadas}/{len(FALHAS)}; falsos positivos: {len(falsos)}"
          f"; achados de ausência não rotulados: {len(ausencias)}")
    return achadas == len(FALHAS) and not falsos


if __name__ == "__main__":
    resultados = [validar(a) for a in ARQUIVOS]
    print("\nRESULTADO:", "OK, bate com o gabarito" if all(resultados) else "DIVERGE do gabarito")
    sys.exit(0 if all(resultados) else 1)
