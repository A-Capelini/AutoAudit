"""Testes do histórico por política (backend/historico.py): agrupamento de versões e comparação de lacunas."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.historico import (chave_politica, comparar_lacunas, historico_da_politica,  # noqa: E402
                               resumo_das_politicas)


def lac(problema, trecho="Os backups devem ser testados sempre que possível."):
    return {"problema": problema, "trecho": trecho, "clausula": "4", "severidade": "média"}


def rel(i, arquivo, saude, lacunas, data="01/11/2026 10:00"):
    return {"id": str(i), "arquivo": arquivo, "data": data, "nota_documental": saude,
            "nota_pratica": None, "saude_compliance": saude, "lacunas": lacunas}


class TestChave(unittest.TestCase):
    def test_versoes_do_mesmo_arquivo_compartilham_a_chave(self):
        nomes = ["Politica_Seguranca.pdf", "Politica_Seguranca_v2.pdf", "politica seguranca (1).PDF",
                 "Política-Segurança_final.docx", "Politica_Seguranca_2026-11-03.pdf"]
        self.assertEqual({chave_politica(n) for n in nomes}, {"politica seguranca"})

    def test_politicas_diferentes_tem_chaves_diferentes(self):
        self.assertNotEqual(chave_politica("PoSIC IFB.pdf"), chave_politica("PoSIC UFPE.pdf"))

    def test_nome_so_de_marcas_nao_gera_chave_vazia(self):
        self.assertEqual(chave_politica("final.pdf"), "sem nome")


class TestComparar(unittest.TestCase):
    def test_resolvida_nova_e_persistente(self):
        a = [lac("vago"), lac("sem MFA", "Acesso por senha."), lac("sem prazo", "Incidentes são tratados.")]
        b = [lac("vago"), lac("sem logs", "Documento inteiro")]
        r = comparar_lacunas(a, b)
        self.assertEqual([l["problema"] for l in r["persistentes"]], ["vago"])
        self.assertEqual([l["problema"] for l in r["resolvidas"]], ["sem MFA", "sem prazo"])
        self.assertEqual([l["problema"] for l in r["novas"]], ["sem logs"])

    def test_pequena_edicao_de_redacao_continua_sendo_a_mesma_lacuna(self):
        a = [lac("vago", "Os backups devem ser testados sempre que possível.")]
        b = [lac("vago", "Os backups devem ser testados sempre que possivel!")]
        r = comparar_lacunas(a, b)
        self.assertEqual((len(r["persistentes"]), len(r["resolvidas"]), len(r["novas"])), (1, 0, 0))

    def test_mesmo_problema_em_trecho_diferente_nao_pareia(self):
        r = comparar_lacunas([lac("vago", "Texto A totalmente distinto sobre senhas.")],
                             [lac("vago", "Outro trecho qualquer sobre backup noturno.")])
        self.assertEqual((len(r["resolvidas"]), len(r["novas"])), (1, 1))

    def test_cada_lacuna_nova_pareia_no_maximo_uma_vez(self):
        r = comparar_lacunas([lac("vago"), lac("vago")], [lac("vago")])
        self.assertEqual((len(r["persistentes"]), len(r["resolvidas"])), (1, 1))


class TestHistorico(unittest.TestCase):
    # a lista chega com os mais recentes primeiro, como o repositório devolve
    RELS = [rel(3, "Pol_v3.pdf", 4.2, [lac("vago")], "09/11/2026 10:00"),
            rel(2, "Pol_v2.pdf", 3.5, [lac("vago"), lac("sem MFA", "Acesso por senha.")], "05/11/2026 10:00"),
            rel(1, "Pol.pdf", 2.8, [lac("vago"), lac("sem MFA", "Acesso por senha."), lac("sem logs", "Documento inteiro")],
                "01/11/2026 10:00"),
            rel(9, "Outra.pdf", 3.0, [])]

    def test_resumo_agrupa_e_calcula_variacao(self):
        linhas = {l["chave"]: l for l in resumo_das_politicas(self.RELS)}
        self.assertEqual(linhas["pol"]["versoes"], 3)
        self.assertEqual(linhas["pol"]["variacao"], 1.4)
        self.assertEqual(linhas["outra"]["versoes"], 1)

    def test_historico_em_ordem_cronologica_com_comparacao(self):
        h = historico_da_politica(self.RELS, "pol")
        self.assertEqual([v["id"] for v in h["versoes"]], ["1", "2", "3"])
        self.assertIsNone(h["versoes"][0]["comparacao"])
        c2, c3 = h["versoes"][1]["comparacao"], h["versoes"][2]["comparacao"]
        self.assertEqual([l["problema"] for l in c2["resolvidas"]], ["sem logs"])
        self.assertEqual([l["problema"] for l in c3["resolvidas"]], ["sem MFA"])
        self.assertEqual(c3["variacao_saude"], 0.7)

    def test_politica_inexistente(self):
        self.assertIsNone(historico_da_politica(self.RELS, "nao existe"))


if __name__ == "__main__":
    unittest.main()
