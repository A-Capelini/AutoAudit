"""
Teste de regressão com política sintética INDEPENDENTE (NexusPay, escrita por outra IA, fora do ciclo
de calibração do motor). Em 15/11/2026 ela revelou dois falsos positivos (BYOD com controles em outra
seção e "grau de proteção de dados adequado" do art. 33 da LGPD), corrigidos em regras.py.

Resultado esperado hoje: nota 4,8 e uma única lacuna (o "se necessário" da Seção 9). Se o motor
mudar de propósito, atualize os valores abaixo e o registro no estado do projeto.

Rodar na raiz do repositório (precisa de pypdf, que já está no ambiente do projeto):

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQUIVO = RAIZ / "data" / "samples" / "Politica_Seguranca_NexusPay.pdf"

try:
    from backend.pln.analisador import analisar_texto  # noqa: E402
    from backend.pln.extracao import extrair_texto  # noqa: E402
    DEPENDENCIAS_OK = True
except ImportError:  # sem pypdf/python-docx o teste é pulado, não falha
    DEPENDENCIAS_OK = False


@unittest.skipUnless(DEPENDENCIAS_OK and ARQUIVO.is_file(), "amostra NexusPay ou dependências ausentes")
class TestNexusPay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.relatorio = analisar_texto(extrair_texto(ARQUIVO.name, ARQUIVO.read_bytes()))
        cls.lacunas = cls.relatorio["lacunas"]

    def test_so_o_se_necessario_e_apontado(self):
        self.assertEqual(len(self.lacunas), 1)
        self.assertIn("se necessário", self.lacunas[0]["problema"])
        self.assertEqual(self.lacunas[0]["clausula"][:8], "Seção 9 ")

    def test_byod_nao_vira_lacuna(self):
        self.assertFalse([l for l in self.lacunas if "dispositivos pessoais" in l["problema"]])

    def test_adequado_do_art_33_nao_vira_lacuna(self):
        self.assertFalse([l for l in self.lacunas if "adequado" in l["problema"]])

    def test_nota(self):
        self.assertAlmostEqual(self.relatorio["nota_documental"], 4.8, places=1)


if __name__ == "__main__":
    unittest.main()
