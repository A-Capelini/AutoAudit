"""
Testes de regressão das regras de detecção (calibração da Sprint 4).

Cada teste guarda um caso que errou em política real (falso positivo ou falso negativo) para que a
correção não volte atrás. Rodar na raiz do repositório, sem dependências extras:

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.pln.extracao import Secao  # noqa: E402
from backend.pln.regras import detectar_lacunas  # noqa: E402


def secao(titulo: str, *frases: str, numero: str | None = "1") -> Secao:
    return Secao(numero, titulo, list(frases))


def tipos(lacunas: list[dict]) -> list[str]:
    return [l["problema"] for l in lacunas]


class TestTermosVagos(unittest.TestCase):
    def test_termo_vago_em_diretriz_gera_lacuna(self):
        r = detectar_lacunas([secao("Diretrizes", "Os backups devem ser testados sempre que possível.")])
        self.assertEqual(len([l for l in r if "sempre que possível" in l["problema"]]), 1)

    def test_adequado_no_objetivo_nao_gera_lacuna(self):
        r = detectar_lacunas([secao("Objetivo", "Esta política assegura o uso adequado da informação.")])
        self.assertFalse([l for l in r if "adequado" in l["problema"]])

    def test_adequado_em_diretriz_continua_gerando(self):
        r = detectar_lacunas([secao("Diretrizes", "Os dados devem receber proteção adequada.")])
        self.assertTrue([l for l in r if "adequada" in l["problema"]])

    def test_aviso_de_modelo_e_ignorado(self):
        r = detectar_lacunas([secao("Diretrizes",
                                    "IMPORTANTE: este modelo deve ser adaptado de forma adequada pelo órgão.")])
        self.assertFalse([l for l in r if "adequada" in l["problema"]])


class TestIncidente(unittest.TestCase):
    SEM_NADA = "Os incidentes de segurança devem ser tratados pela equipe de TI."

    def test_incidente_sem_prazo_e_anpd_gera_lacuna_alta(self):
        r = [l for l in detectar_lacunas([secao("Incidentes", self.SEM_NADA)]) if "incidentes" in l["problema"]]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["severidade"], "alta")

    def test_cabecalho_de_secao_nao_gera_lacuna(self):
        r = detectar_lacunas([secao("Diretrizes", "Seção II Do Tratamento de Incidentes em Segurança da Informação")])
        self.assertFalse([l for l in r if "incidentes" in l["problema"]])

    def test_nome_de_equipe_sem_verbo_nao_gera_lacuna(self):
        r = detectar_lacunas([secao("Competências",
                                    "Equipe de Tratamento de Incidentes em Segurança da Informação (ETISI).")])
        self.assertFalse([l for l in r if "incidentes" in l["problema"]])

    def test_pdf_com_palavra_quebrada_ainda_e_analisado(self):
        # "dever á" vem assim da extração de alguns PDFs
        r = detectar_lacunas([secao("Diretrizes", "Todo incidente de segurança dever á ser comunicado ao gestor.")])
        self.assertTrue([l for l in r if "incidentes" in l["problema"]])

    def test_prazo_e_anpd_em_outra_secao_valem(self):
        r = detectar_lacunas([
            secao("Diretrizes", self.SEM_NADA),
            secao("Anexo", "Todo incidente com dados pessoais deve ser comunicado pelo comitê de resposta à ANPD "
                           "e aos titulares dos dados em até 72 horas.", numero="2"),
        ])
        self.assertFalse([l for l in r if "incidentes" in l["problema"]])

    def test_prazo_solto_em_frase_sem_relacao_nao_vale(self):
        # "imediatamente" e "titulares de unidade" não tratam de incidente: não podem esconder a lacuna
        r = detectar_lacunas([
            secao("Diretrizes", self.SEM_NADA),
            secao("Usuários", "Os usuários devem comunicar imediatamente a perda de crachá aos titulares de unidade.",
                  numero="2"),
        ])
        self.assertTrue([l for l in r if "incidentes" in l["problema"]])

    def test_achado_de_incidente_aparece_uma_vez_no_documento(self):
        r = detectar_lacunas([
            secao("Diretrizes", self.SEM_NADA),
            secao("Competências", "Compete ao gestor tratar os incidentes de segurança reportados.", numero="2"),
            secao("Anexo", "Os incidentes devem ser registrados e comunicados à equipe.", numero="3"),
        ])
        self.assertEqual(len([l for l in r if "incidentes" in l["problema"]]), 1)


class TestLegislacao(unittest.TestCase):
    def test_declaracao_generica_gera_lacuna(self):
        r = detectar_lacunas([secao("Escopo", "A empresa respeita a legislação vigente de proteção de dados.")])
        self.assertTrue([l for l in r if "genérica" in l["problema"]])

    def test_lista_de_competencias_nao_gera_lacuna(self):
        r = detectar_lacunas([secao(
            "Competências",
            "O comitê tem as seguintes competências: I – assessorar a diretoria; II – observar a legislação vigente.")])
        self.assertFalse([l for l in r if "genérica" in l["problema"]])


if __name__ == "__main__":
    unittest.main()
