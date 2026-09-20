# Fontes de dados — guia de aquisição

Os três scripts em `scripts/` baixam automaticamente o que dá pra baixar sem
cadastro. As fontes abaixo exigem passo manual — não dá pra scriptar porque
ficam atrás de formulário/paywall.

## ✅ Automatizado (rode os scripts)

| Fonte | Script | Formato |
|---|---|---|
| NIST SP 800-53 Rev. 5 (catálogo de controles) | `download_nist_oscal.py` | JSON (OSCAL) |
| LGPD — Lei nº 13.709/2018 (texto compilado) | `download_lgpd.py` | HTML + JSON estruturado por artigo |
| NVD — amostra de CVEs | `download_nvd_sample.py` | JSON |

## ✋ Manual — exige cadastro gratuito

### CIS Controls v8
1. Acesse: https://learn.cisecurity.org/cis-controls-download-v8
2. Preencha o formulário (nome, e-mail institucional — pode usar o e-mail da Fatec).
3. Você recebe PDF + **planilha Excel** com todos os Safeguards.
4. Salve a planilha em `data/raw/cis_controls_v8.xlsx`.
5. Para converter em JSON: `pandas.read_excel(...).to_dict(orient="records")`
   (a coluna de Implementation Group já vem pronta pra filtrar por IG1/IG2/IG3).

### SANS Institute — templates de política de segurança
1. Acesse: https://www.sans.org/information-security-policy/
2. A página lista os templates por categoria (Acceptable Use, Incident
   Response, Password Protection, etc.) — download direto em .doc, sem
   formulário na maioria dos casos (alguns exigem e-mail).
3. Salve os `.doc`/`.docx` baixados em `data/raw/sans_templates/`.
4. Esses arquivos servem duplo papel no projeto: (a) corpus de referência
   para grounding, e (b) documentos de teste/demo — dá pra rodar o AutoAudit
   "neles mesmos" pra demonstrar o sistema funcionando sem expor dados de
   uma empresa real.

## ⚠️ NÃO baixar — ISO/IEC 27001 (texto integral)

O texto completo da norma ISO/IEC 27001 é **pago e protegido por direitos
autorais** (vendido pela ISO e, no Brasil, pela ABNT). Não existe versão
oficial gratuita para redistribuir.

O que é seguro usar como "resumo público do Anexo A":
- **Títulos e numeração dos controles do Anexo A** (ex.: "A.5.1 — Políticas
  de segurança da informação") — isso é amplamente republicado por
  fornecedores de GRC e não é o texto normativo em si.
- Tabelas de mapeamento cruzado ISO 27001 ↔ CIS Controls ↔ NIST 800-53,
  publicadas por terceiros (CIS e outros mantêm mapeamentos públicos).

Se quiser citar a norma formalmente no artigo/relatório, use a referência
bibliográfica (já está no documento da proposta) sem reproduzir o texto.

## Próximo passo depois de baixar tudo

Estruturar cada fonte em documentos curtos (por cláusula/artigo/controle) e
gerar os embeddings pra indexar no FAISS — isso é o restante da Sprint 1
(`ingestão, limpeza e estruturação... geração dos embeddings iniciais`).
