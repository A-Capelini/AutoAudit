# Fontes normativas: origem, licença e o que vai para o Git

O AutoAudit ancora a análise em uma base normativa (grounding). Este documento registra de onde
vem cada fonte, em que condições pode ser usada e o que pode ou não ser versionado. O repositório
é **público**, então a licença de cada fonte decide o que entra nele.

| Fonte | Origem | Licença / condição | Versionado no Git? |
|---|---|---|---|
| NIST SP 800-53 Rev. 5 | catálogo OSCAL (`usnistgov/oscal-content`) | publicação do governo dos EUA, uso livre com crédito | Não (`data/raw/` é ignorado); o dump tem a base derivada |
| LGPD (Lei nº 13.709/2018) | portal do Planalto | texto legal público | Não (`data/raw/` é ignorado); o dump tem a base derivada |
| CIS Controls v8.1.2 | planilha Excel oficial, baixada em cisecurity.org (cadastro gratuito) | **CC BY-NC-ND 4.0**: uso não comercial, com crédito à CIS e link da licença; **não se distribui material modificado** | **Não.** Nem a planilha, nem o texto carregado, nem o índice |
| SANS (templates de política) | sans.org | a conferir antes do uso; ver a página de cada template | a definir |

## CIS Controls: regras do projeto

- A planilha fica em `data/raw/cis/` (pasta ignorada pelo Git).
- A carga (`python db/seed_normas.py --fonte cis`) grava as normas no MongoDB **local** de cada integrante.
- O índice FAISS (`data/processed/`) também é ignorado pelo Git e copiado entre as máquinas da dupla.
- **O dump versionado (`db/dump/autoaudit.archive.gz`) não pode conter CIS.** O dump atual foi gerado antes
  da carga do CIS e tem só NIST e LGPD. **Não regenere o dump depois de carregar o CIS** no mesmo banco. Se um
  dump novo for necessário, gere-o a partir de um banco que não tenha o CIS (por exemplo, um MongoDB de teste
  restaurado do dump atual) e confira antes do commit: `gunzip -c db/dump/autoaudit.archive.gz | grep -a -c CIS_V8`
  deve imprimir `1`: a única ocorrência é o `enum` de fontes do validador do schema, que já aceita `CIS_V8`. Mais
  de uma indica que há normas do CIS no dump.
- No artigo e na apresentação: citar "CIS Controls v8.1.2, Center for Internet Security", com o link da licença
  (https://creativecommons.org/licenses/by-nc-nd/4.0/). O uso no AutoAudit é acadêmico e não comercial; um uso
  comercial futuro exigiria aprovação prévia da CIS.
- O AutoAudit **não redistribui** o texto do CIS: ele aponta o controle (ex.: "CIS Controls v8 5.2") no relatório
  e usa o catálogo localmente para a busca semântica.
