"""
Testes da carga do CIS Controls (db/seed_normas.py) e da ligação das referências às normas
(backend/pln/analisador.py). A planilha usada é SINTÉTICA, criada na hora: o conteúdo do CIS tem
licença CC BY-NC-ND e não vai para o repositório. Rodar na raiz:

    python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "db"))

import seed_normas  # noqa: E402
from backend.pln.analisador import _pares_curados, _rotulo_norma, selecionar_proximas  # noqa: E402

CABECALHO = ["CIS Control", "CIS Safeguard", "Asset Class", "Security Function", "Title", "Description",
             "IG1", "IG2", "IG3"]


def planilha(linhas: list[list], titulo_aba: str = "Controls v8.1.2") -> Path:
    wb = openpyxl.Workbook()
    wb.active.title = "Introduction"           # a aba certa não é a primeira
    ws = wb.create_sheet(titulo_aba)
    ws.append(CABECALHO)
    for l in linhas:
        ws.append(l)
    destino = Path(tempfile.mkdtemp()) / "cis_teste.xlsx"
    wb.save(destino)
    return destino


LINHAS = [
    ["5\xa0", None, None, None, "Account Management", "Use processes and tools…", None, None, None],
    ["5", "5.2", "Users", "Protect", "Use Unique Passwords", "Use unique passwords for all assets.", "x", "x", "x"],
    ["5", "5.3", "Users", "Respond", "Disable Dormant Accounts", "Delete or disable dormant accounts.", None, "x", "x"],
    ["5", "5.9", "Users", "Protect", "Exemplo só IG3", "Texto.", None, None, "x"],
]


class TestCarregarCis(unittest.TestCase):
    def setUp(self):
        self.docs, self.avisos = seed_normas.carregar_cis(planilha(LINHAS))
        self.por_id = {d["identificador"]: d for d in self.docs}

    def test_uma_norma_por_salvaguarda_e_controle_vira_familia(self):
        self.assertEqual(sorted(self.por_id), ["5.2", "5.3", "5.9"])
        self.assertEqual(self.por_id["5.2"]["familia"], "5 — Account Management")  # nbsp do "5\xa0" tratado
        self.assertEqual(self.avisos["controles"], 1)

    def test_campos_do_schema(self):
        d = self.por_id["5.2"]
        self.assertEqual((d["fonte"], d["idioma"], d["titulo"]), ("CIS_V8", "en", "Use Unique Passwords"))
        self.assertEqual(d["versao_fonte"], "CIS Controls v8.1.2")

    def test_grupo_e_o_menor_que_inclui_a_salvaguarda(self):
        self.assertEqual([self.por_id[i]["grupo_implementacao"] for i in ("5.2", "5.3", "5.9")],
                         ["IG1", "IG2", "IG3"])

    def test_avisa_quando_o_total_nao_bate_com_o_catalogo(self):
        self.assertIn("salvaguardas lidas (esperado 153)", self.avisos)

    def test_identificador_fora_do_padrao_e_ignorado_com_aviso(self):
        # um "5.10" salvo como número viraria 5.1: se o id não for texto N.N, não grava e avisa
        docs, avisos = seed_normas.carregar_cis(planilha(LINHAS + [["5", "cinco", "Users", "Protect", "X", "Y", "x", "x", "x"]]))
        self.assertEqual(len(docs), 3)
        self.assertEqual(avisos["identificadores fora do padrão N.N (ignorados)"], ["cinco"])

    def test_planilha_sem_cabecalho_esperado_falha_com_mensagem_clara(self):
        wb = openpyxl.Workbook()
        wb.active.append(["a", "b"])
        destino = Path(tempfile.mkdtemp()) / "ruim.xlsx"
        wb.save(destino)
        with self.assertRaises(ValueError):
            seed_normas.carregar_cis(destino)


class TestIdsNumericos(unittest.TestCase):
    """A planilha real guarda o ID como número: 3.10 vira o decimal 3.1 (igual ao 3.1). Já aconteceu."""

    @staticmethod
    def controle3(valores: list) -> list[list]:
        linhas = [["3", None, None, None, "Data Protection", "Desc.", None, None, None]]
        for k, v in enumerate(valores, start=1):
            linhas.append(["3", v, "Data", "Protect", f"Titulo {k}", f"Texto {k}", "x", "x", "x"])
        return linhas

    def test_id_numerico_x10_nao_colide_com_x1(self):
        valores = [3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.1, 3.11]   # o 10º é o 3.10 salvo como 3.1
        docs, avisos = seed_normas.carregar_cis(planilha(self.controle3(valores)))
        ids = [d["identificador"] for d in docs]
        self.assertEqual(ids, [f"3.{k}" for k in range(1, 12)])
        self.assertEqual(len(set(ids)), 11)
        por_id = {d["identificador"]: d for d in docs}
        self.assertEqual(por_id["3.1"]["titulo"], "Titulo 1")      # a 3.1 NÃO foi sobrescrita pela 3.10
        self.assertEqual(por_id["3.10"]["titulo"], "Titulo 10")
        self.assertNotIn("IDs da planilha que não conferem com a sequência do controle", avisos)

    def test_id_numerico_fora_da_sequencia_gera_aviso(self):
        docs, avisos = seed_normas.carregar_cis(planilha(self.controle3([3.1, 3.5, 3.3])))   # 2ª linha deveria ser 3.2
        self.assertEqual([d["identificador"] for d in docs], ["3.1", "3.2", "3.3"])
        self.assertIn("IDs da planilha que não conferem com a sequência do controle", avisos)

    def test_id_repetido_como_texto_aborta_em_vez_de_sobrescrever(self):
        with self.assertRaises(ValueError):
            seed_normas.carregar_cis(planilha(self.controle3(["3.1", "3.1"])))


class TestReferencias(unittest.TestCase):
    def test_referencia_com_nist_lgpd_e_cis(self):
        pares = _pares_curados("NIST SP 800-53 IA-5; CIS Controls v8 5.2")
        self.assertEqual(pares, [("NIST_800_53", "IA-5"), ("CIS_V8", "5.2")])
        self.assertEqual(_pares_curados("LGPD Art. 48; NIST SP 800-53 IR-6"),
                         [("NIST_800_53", "IR-6"), ("LGPD", "Art. 48")])

    def test_cis_com_dois_digitos(self):
        self.assertIn(("CIS_V8", "11.2"), _pares_curados("NIST SP 800-53 CP-9; CIS Controls v8 11.2"))
        self.assertIn(("CIS_V8", "3.11"), _pares_curados("NIST SP 800-53 SC-28; CIS Controls v8 3.11"))

    def test_rotulo_do_cis(self):
        self.assertEqual(_rotulo_norma("CIS_V8", "5.2"), "CIS Controls v8 5.2")

    def test_cis_ja_citado_pela_regra_nao_vira_norma_proxima(self):
        achados = [{"fonte": "CIS_V8", "identificador": "5.2", "nota": 0.9},
                   {"fonte": "CIS_V8", "identificador": "5.3", "nota": 0.9},
                   {"fonte": "CIS_V8", "identificador": "5.4", "nota": 0.3}]
        aceitas = selecionar_proximas("NIST SP 800-53 IA-5; CIS Controls v8 5.2", achados)
        self.assertEqual([a["identificador"] for a in aceitas], ["5.3"])   # 5.2 já citado; 5.4 abaixo do limiar


if __name__ == "__main__":
    unittest.main()
