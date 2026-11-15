# AutoAudit

**Auditoria Automatizada de Políticas de Segurança com PLN e Verificação Prática de Conformidade**

Projeto da disciplina de Processamento de Linguagem Natural (PLN) — Ciência de Dados, Fatec Cotia.
Professor: Braz Izaias da Silva Junior.

Equipe: Anderson Capelini Andrade (RA 2701352423046) · Moisés Germano Leite (RA 2701352423043)

## O que é

O AutoAudit lê uma política de segurança da informação (PDF/DOCX), usa PLN para atribuir uma nota de
**Saúde de Compliance (0 a 5)** e gera um plano de ação com sugestão de nova redação. Um módulo de
**Verificação Prática** testa, em laboratório isolado, se os controles descritos na política realmente existem.

Stack: Python · Streamlit · FastAPI · MongoDB (não relacional) · FAISS (busca semântica). O motor de PLN é por
regras explícitas, **sem LLM** (LLM + RAG fica como evolução futura).

> **Escopo ético:** todos os testes práticos rodam apenas contra ambientes de laboratório intencionalmente
> vulneráveis e isolados (DVWA, OWASP Juice Shop, Metasploitable). Nenhum sistema de terceiros é testado.

## Estrutura do repositório

```
AutoAudit/
├── .streamlit/config.toml     # tema do Streamlit (precisa ficar na raiz)
├── backend/
│   ├── main.py                # API FastAPI: uvicorn backend.main:app
│   ├── historico.py           # histórico por política: agrupa versões e compara lacunas (só biblioteca padrão)
│   ├── pln/
│   │   ├── extracao.py        # texto de PDF/DOCX, seções e sentenças
│   │   ├── regras.py          # regras de detecção de lacunas (termos vagos, MFA, senha, incidentes…)
│   │   ├── busca_normas.py    # busca semântica (FAISS) nas normas
│   │   └── analisador.py      # orquestra o pipeline, calcula as notas e liga as lacunas às normas
│   ├── avaliar_politicas.py   # mede o motor numa pasta de políticas (rode antes e depois de mexer nas regras)
│   ├── analisar_arquivo.py    # analisa um PDF/DOCX no terminal, sem API nem banco
│   ├── validar_gabarito.py    # confere as regras com o gabarito da política da Nimbus
│   ├── testar_busca.py        # mostra o que o FAISS devolve para cada lacuna
│   └── testar_api.py          # teste de ponta a ponta com a API no ar
├── tests/                     # testes automatizados (unittest): regras, normas/CIS, histórico e amostras
├── data/
│   ├── raw/                   # arquivos baixados (não vão para o Git)
│   ├── processed/             # índice FAISS e metadados gerados (não vão para o Git)
│   └── samples/               # políticas de teste (Nimbus, NexusPay, Alfa Saúde, Órion), gabarito e Nimbus revisada
├── db/
│   ├── init_db.py             # cria coleções, validadores $jsonSchema e índices (idempotente)
│   ├── seed_normas.py         # carrega NIST 800-53, LGPD e CIS Controls v8.1.2 (planilha manual) em `normas`
│   ├── seed_exemplo.py        # 6 auditorias e 3 relatórios fictícios de exemplo
│   ├── repositorio.py         # CRUD das três coleções, com as regras de integridade
│   ├── demo_crud.py           # demonstração ao vivo do CRUD
│   ├── build_faiss.py         # embeddings e índice FAISS
│   ├── testar_contrato.py     # teste de ida e volta entre o frontend e o banco
│   └── dump/                  # mongodump do banco (sem usuários nem senhas)
├── docs/
│   ├── der/                   # DER conceitual (Mermaid, PNG e PDF)
│   ├── modelagem_mongodb.md   # decisões de modelagem
│   ├── dicionario_dados.md    # campos, tipos, domínios, índices e relacionamentos
│   ├── licencas_fontes.md     # origem e licença de cada fonte normativa e o que pode ir para o Git
│   ├── roteiro_replicacao.md  # como recriar o banco em outra máquina (Linux)
│   ├── roteiro_replicacao_windows.md # idem, para Windows 10/11 (começa pelo WSL2)
│   └── roteiro_demonstracao.md# roteiro da apresentação do banco
├── frontend/
│   ├── app.py                 # interface Streamlit
│   ├── api_client.py          # chama a API do backend; sem ela, cai no modo simulado
│   └── mock_data.py           # relatório simulado (usado só quando a API está fora do ar)
├── scripts/                   # download do dataset (NIST, LGPD, NVD) + DATASETS.md
├── setup/environment.yml      # ambiente Conda (conda-forge) — uso local
├── .env.example               # copie para .env
├── docker-compose.yml         # MongoDB + mongo-express
└── requirements.txt           # dependências mínimas — usado pelo Streamlit Cloud
```

### Por que dois arquivos de dependências?

| Arquivo | Para quê | Conteúdo |
|---|---|---|
| `setup/environment.yml` | Desenvolvimento local e replicação em outras máquinas | Ambiente completo (conda-forge) |
| `requirements.txt` | Deploy no Streamlit Community Cloud | Só o que o frontend precisa |

O `environment.yml` fica em `setup/` de propósito, para o Streamlit Cloud não enxergá-lo e usar o
`requirements.txt`. Ao adicionar uma dependência que o app publicado precisa, atualize **os dois**.

## Ambiente local (conda-forge)

Requisito: [Miniforge](https://github.com/conda-forge/miniforge) (ou conda com o canal conda-forge) e Docker.
Os comandos são os mesmos no Windows (Anaconda/Miniforge Prompt) e no Linux.

```bash
conda env create -f setup/environment.yml
conda activate autoaudit
cp .env.example .env        # Windows: copy .env.example .env
```

Para atualizar o ambiente depois de mudanças no arquivo:

```bash
conda env update -f setup/environment.yml --prune
```

> Se algum pacote não resolver no conda-forge, mova-o para a seção `pip:` do `environment.yml`.

## Rodar o frontend

Sempre a partir da **raiz** do repositório (é de lá que o Streamlit lê o `.streamlit/config.toml`):

```bash
streamlit run frontend/app.py
```

O frontend chama a API do backend (`frontend/api_client.py`). Se a API estiver fora do ar, ele usa **dados
simulados** (`frontend/mock_data.py`) e avisa na tela: é o caso do app publicado no Streamlit Cloud, que não
alcança o MongoDB nem a API da máquina local. A URL da API vem de `AUTOAUDIT_API_URL` (variável de ambiente ou
`st.secrets`); o padrão é `http://localhost:8000`. O dicionário que a API devolve é o contrato com o frontend
(o mesmo que o banco guarda sem tradução; veja `db/testar_contrato.py`).

## Rodar o backend (Sprint 3)

Pré-requisitos: ambiente `autoaudit` ativo, MongoDB no ar (`docker compose up -d`), `.env` configurado e o
índice FAISS gerado (`python db/build_faiss.py`; veja a seção do índice). A partir da **raiz** do repositório:

```bash
uvicorn backend.main:app            # API em http://localhost:8000 (documentação interativa em /docs)
streamlit run frontend/app.py       # em outro terminal
```

Sem internet (por exemplo, na apresentação), suba a API com `HF_HUB_OFFLINE=1` para o modelo de embeddings já
baixado não tentar acessar o Hugging Face: `HF_HUB_OFFLINE=1 uvicorn backend.main:app --port 8000`.

Rotas: `POST /auditorias` (envia PDF/DOCX), `GET /auditorias`, `GET /relatorios`, `GET /relatorios/{id}`,
`GET /politicas`, `GET /politicas/{chave}`, `GET /saude`.
Fluxo: texto do documento → seções e sentenças → regras de detecção de lacunas → busca semântica nas normas (FAISS)
→ notas → gravação no MongoDB (`auditorias` e `relatorios`, via `db/repositorio.py`).

**Histórico por política** (`backend/historico.py`, rotas `/politicas`): auditorias de versões do mesmo documento
são agrupadas pelo nome do arquivo, ignorando extensão, `v2`, `final`, datas e `(1)`. Entre duas versões, uma lacuna
da anterior é a *mesma* da nova quando têm o mesmo tipo de problema e trechos parecidos (similaridade ≥ 0,8); o painel
mostra quantas foram **resolvidas**, **novas** e **persistentes**. O agrupamento é uma heurística pelo nome do
arquivo (o relatório não guarda o conteúdo do documento), e a curva de notas pode misturar auditorias feitas por
versões diferentes do motor de regras (a tela avisa isso).

Testes (os de `tests/` e o gabarito não precisam do MongoDB no ar):

```bash
python -m unittest discover -s tests      # 52 testes: regras, normas/CIS, histórico e amostras (precisa do pymongo)
python backend/validar_gabarito.py        # regras x gabarito da Nimbus (6 falhas plantadas, 0 falsos positivos)
python backend/analisar_arquivo.py data/samples/Politica_Seguranca_NexusPay.pdf   # política independente: 4,8/5, 1 lacuna
python backend/avaliar_politicas.py       # comportamento do motor nas políticas de data/raw/politicas_reais
python backend/testar_busca.py            # normas que o FAISS associa a cada lacuna (precisa do índice)
python backend/testar_api.py              # ponta a ponta, com a API e o MongoDB no ar
```

`avaliar_politicas.py` aceita `--salvar antes.json` e `--comparar antes.json` para ver o que mudou depois de mexer
nas regras. Sem especialista rotulando os documentos, ele mostra o **comportamento** do motor (quantas lacunas, de
que tipo, que nota), não a sua acurácia: a única verdade conhecida é o gabarito da Nimbus.

Limitações desta versão (ditas com franqueza na apresentação):

- A análise usa **regras explícitas** (expressões regulares e critérios de ausência), sem LLM: acha o que as regras
  conhecem. A busca semântica liga cada lacuna às normas do NIST, da LGPD e do CIS, com filtro de similaridade.
- As regras só entendem **português**, e as de ausência (backup, logs, criptografia, treinamento) detectam apenas se
  o tema aparece no texto, não a qualidade do que está escrito.
- As regras checam se o tema aparece e se a cláusula é objetiva, **não se o valor atende ao benchmark**: a regra de
  senha aceita qualquer número (8 caracteres com MFA está dentro do CIS 5.2, 4 caracteres não, e o motor não
  distingue), e prazos como os 15 dias da LGPD (art. 19) não são comparados com a lei.
- A **nota documental** é uma fórmula provisória (peso por severidade sobre o máximo possível), ainda não calibrada
  com rótulos de um especialista.
- A **Verificação Prática não é executada**: `nota_pratica` e `verificacoes` voltam vazios e o frontend mostra
  "não executada".
- PDF escaneado (imagem) não é suportado: não há OCR.

## Banco de dados (MongoDB)

Cada integrante roda a **própria instância** local via Docker (os dados não são compartilhados).
O banco `autoaudit` tem três coleções: `normas`, `auditorias` e `relatorios`. As lacunas e as verificações práticas
ficam embutidas no relatório. O dump versionado tem 1.087 normas (NIST SP 800-53 Rev.5 com 1.014 controles e LGPD
com 73 artigos). Quem carrega o CIS Controls v8.1.2 localmente (153 salvaguardas, ver abaixo) chega a 1.240; o CIS
**não** vai para o Git nem para o dump, por licença (`docs/licencas_fontes.md`).

Ambiente novo? Siga o [`docs/roteiro_replicacao.md`](docs/roteiro_replicacao.md) (Linux) ou o
[`docs/roteiro_replicacao_windows.md`](docs/roteiro_replicacao_windows.md) (Windows 10/11, com WSL2): ele cria o `.env`, sobe o
Docker, restaura o dump de `db/dump/` e confere tudo. Resumo dos comandos do dia a dia:

```bash
docker compose up -d                 # sobe MongoDB e mongo-express
python db/init_db.py                 # cria/atualiza coleções, validadores e índices (idempotente)
python db/demo_crud.py               # demonstração ao vivo do CRUD (Enter avança cada passo)
```

- Interface web: http://localhost:8081 (mongo-express, sem login em dev; acessível só nesta máquina)
- Shell: `docker exec -it autoaudit-mongo mongosh -u autoaudit -p`
- Para parar: `docker compose stop`. **Nunca** use `docker compose down -v`: a opção `-v` apaga os dados.

Documentação do banco:

| Documento | Conteúdo |
|---|---|
| [`docs/der/der_autoaudit.png`](docs/der/der_autoaudit.png) | DER conceitual (notação pé de galinha) |
| [`docs/modelagem_mongodb.md`](docs/modelagem_mongodb.md) | Decisões de modelagem (embutir × referenciar, integridade sem FK) |
| [`docs/dicionario_dados.md`](docs/dicionario_dados.md) | Campos, tipos, domínios, índices e relacionamentos |
| [`docs/roteiro_demonstracao.md`](docs/roteiro_demonstracao.md) | Roteiro da apresentação do banco |

### Índice FAISS (busca semântica)

O índice **não** vai para o Git. Para gerá-lo (com o Mongo no ar e as normas carregadas):

```bash
python db/build_faiss.py
python db/build_faiss.py --consulta "política de senhas e controle de acesso"
```

São 1.858 vetores de 768 dimensões (`paraphrase-multilingual-mpnet-base-v2`) com o CIS carregado; sem o CIS são
1.705 (NIST e LGPD). Na primeira execução o modelo (cerca de 1,1 GB) é baixado do Hugging Face. Os três arquivos
de `data/processed/` não vão para o Git: ao reconstruir o índice, copie-os **juntos** para as outras máquinas.

## Arquivos que não vão para o Git

Ao configurar outra máquina, estes itens precisam ser recriados ou copiados à mão:

| Item | Como obter |
|---|---|
| `.env` | `cp .env.example .env` e ajuste; nunca commite |
| `.streamlit/secrets.toml` | só se usar segredos locais; no Streamlit Cloud ficam em *Secrets* |
| `data/raw/nist_sp800-53_rev5_catalog.json`, `data/raw/lgpd_artigos.json` | `python scripts/download_nist_oscal.py` e `python scripts/download_lgpd.py` |
| `data/raw/cis/*.xlsx` | download manual (CC BY-NC-ND 4.0); ver `scripts/DATASETS.md` |
| `data/raw/politicas_reais/` | PDFs reais usados por `avaliar_politicas.py` e pela demonstração: copie à mão |
| `data/processed/` (`normas.index`, `normas_trechos.json`, `normas_index.json`) | `python db/build_faiss.py`, ou copie os **três juntos** e confira com `sha256sum` |
| Dados do MongoDB | volume Docker de cada máquina; restaure `db/dump/` (auditorias de teste não são compartilhadas) |
| Modelo de embeddings (cerca de 1,1 GB) | baixa sozinho na primeira execução com internet; para uso offline, rode uma vez antes |

## Baixar o dataset

Com o ambiente `autoaudit` ativado:

```bash
python scripts/download_nist_oscal.py
python scripts/download_lgpd.py
python scripts/download_nvd_sample.py --keyword mongodb --results 30
```

O CIS Controls v8.1.2 e os templates do SANS exigem download manual; a ISO 27001 **não deve** ser baixada
(direitos autorais). Passo a passo em [`scripts/DATASETS.md`](scripts/DATASETS.md).

Carga do CIS (planilha oficial em `data/raw/cis/`, pasta ignorada pelo Git), com o MongoDB no ar:

```bash
python db/seed_normas.py --fonte cis    # 153 salvaguardas na coleção `normas` (idempotente)
python db/build_faiss.py                # reconstrói o índice (1.858 vetores)
```

O CIS Controls é licenciado como **CC BY-NC-ND 4.0** (uso não comercial, com crédito à CIS, sem redistribuir material
modificado). Por isso a planilha, o texto carregado e o índice ficam fora do Git, e o dump de `db/dump/` **não deve ser
regenerado** a partir de um banco que já tenha o CIS. Regras completas em
[`docs/licencas_fontes.md`](docs/licencas_fontes.md).

## Deploy no Streamlit Community Cloud

1. Repositório: `A-Capelini/AutoAudit`, branch `main` (app publicado em https://autoaudit.streamlit.app).
2. **Main file path:** `frontend/app.py`
3. Em *Advanced settings*, escolha Python 3.11.
4. Segredos (chaves) vão em *Secrets* no painel — nunca no Git (`.streamlit/secrets.toml` está no `.gitignore`).
5. Sem `AUTOAUDIT_API_URL`, o app publicado não alcança nenhuma API e roda no modo simulado (com aviso na tela).

## Cronograma (4 sprints)

| Sprint | Entrega | Status |
|---|---|---|
| 1 — Frontend | Interface funcionando | Entregue em 13/10 (interface com dados simulados) |
| 2 — Banco de dados | DER, base com as coleções criadas e CRUD funcionando | Entregue em 20/10 (professor confirmou o MongoDB) |
| 3 — Backend | Lógica, FastAPI e integração do motor de PLN | **Concluída e apresentada em 03/11** (aprovada pelo professor): API, extração de texto, regras de lacunas, busca FAISS e gravação no MongoDB |
| 4 — Apresentação | Prévia (17/11), entrega final (24/11) e prova (01/12) | **Em andamento** (ver lista abaixo) |

Sprint 2 (banco de dados):

- [x] Modelagem das coleções `normas`, `auditorias` e `relatorios` (`docs/modelagem_mongodb.md`)
- [x] DER conceitual (`docs/der/`) e dicionário de dados (`docs/dicionario_dados.md`)
- [x] Coleções com validação de schema e índices (`db/init_db.py`)
- [x] CRUD das três coleções (`db/repositorio.py`) e demonstração (`db/demo_crud.py`)
- [x] Dados: 1.087 normas e 6 auditorias/3 relatórios de exemplo; dump para replicação (`db/dump/`)
- [x] Roteiros de replicação e de demonstração (`docs/`)
- [x] Banco apresentado em 20/10

Frontend (Sprint 1):

- [x] Interface Streamlit (nova auditoria, resultado, histórico) com dados simulados
- [x] Publicado no Streamlit Community Cloud (https://autoaudit.streamlit.app)
- [x] Revisão do código: fuso horário de São Paulo na data e HTML escapado nos trechos da política
- [ ] Revisar textos e visual (ajustes finos, sem prazo)

Sprint 3 (backend):

- [x] API FastAPI (`backend/main.py`): upload de PDF/DOCX, histórico e relatório, com gravação no MongoDB
- [x] Extração de texto e divisão em seções e sentenças (`backend/pln/extracao.py`)
- [x] Lacunas geradas a partir do documento enviado, com severidade normalizada (`alta`, `média`, `baixa`) (`backend/pln/regras.py`)
- [x] Busca semântica (FAISS) ligando cada lacuna às normas (`backend/pln/busca_normas.py`)
- [x] Validação contra o gabarito da Nimbus: 6 de 6 falhas achadas, sem falso positivo (`backend/validar_gabarito.py`)
- [x] Frontend integrado à API (com fallback simulado) e histórico lido do MongoDB
- [x] Documentação do backend: [`docs/AutoAudit_Documentacao_Backend_Sprint3.pdf`](docs/AutoAudit_Documentacao_Backend_Sprint3.pdf)
- Itens que ficaram para a Sprint 4: Verificação Prática, calibração da nota e novas regras, teste com templates do SANS (ver abaixo)

Trabalho de dados em paralelo (alimenta a Sprint 3):

- [x] Baixar o CIS Controls v8.1.2 (planilha oficial, manual) e carregá-lo na base (153 salvaguardas)
- [ ] Templates do SANS: adiados (o motor só entende português e a licença de cada template ainda não foi verificada)
- [x] Parser que estrutura cada fonte em documentos curtos: NIST (1.014 controles ativos), LGPD (73 artigos vigentes) e CIS (153 salvaguardas); falta o SANS
- [x] Embeddings (`paraphrase-multilingual-mpnet-base-v2`) e índice FAISS (`db/build_faiss.py`; normas longas divididas em trechos)
- [x] Coleções do MongoDB (`normas`, `auditorias`, `relatorios`)

Sprint 4 (apresentação final em 24/11; prova em 01/12), na ordem de execução:

- [x] README atualizado e documentação do backend em `docs/`
- [x] Mais regras de detecção (4 regras de ausência) e recalibração das existentes, com testes em `tests/` e o gabarito
  re-rodado (6 de 6, 0 falsos positivos); a fórmula da nota continua provisória, sem rótulos de especialista
- [x] Carga do CIS Controls v8.1.2 na base de normas, com índice FAISS reconstruído (1.858 vetores); licença em
  `docs/licencas_fontes.md`
- [ ] Templates do SANS: adiados (ver acima)
- [x] Histórico por política (versões da mesma política) a partir do MongoDB: rotas `/politicas` e comparação de lacunas
- [x] Pico de memória e tempo por auditoria medidos no notebook (i7-5500U, 8 GB, offline): pico da API ≈ 1.594 MiB;
  mediana ≈ 2,4 s e máximo ≈ 3,6 s em PDFs reais (`backend/medir_memoria.py`); ensaio completo offline feito
- [x] Teste independente com a política NexusPay (`data/samples/`, escrita por outra IA): revelou 2 falsos positivos
  (BYOD com controles em outra seção e o "adequado" do art. 33 da LGPD), corrigidos em `backend/pln/regras.py`
  (4,5/3 lacunas → 4,8/1); regressão em `tests/test_amostras.py`
- [x] Slides da prévia de 17/11 (5 min) prontos
- [ ] Artigo no modelo do professor (ainda não recebido; há versão provisória), slides e roteiro da apresentação final (24/11)
- [ ] Por último, só com o resto validado: Verificação Prática (DVWA, Juice Shop, Metasploitable; nmap/OWASP ZAP via contrato JSON; 3 a 5 controles; Gap Analysis). Se não houver tempo, a apresentação segue o cenário FCS da proposta, dito com franqueza
- LLM + RAG fica fora do escopo desta entrega (o motor segue por regras, sem LLM); é a evolução natural

> O índice FAISS (`data/processed/`) não vai para o Git: ao reconstruí-lo, copie os três arquivos juntos para as outras máquinas.

### Ferramentas de apoio (Sprint 3 e 4)

- `python backend/analisar_arquivo.py <arquivo> [--busca]` — analisa um PDF/DOCX no terminal, sem API nem banco.
- `python backend/avaliar_politicas.py [pasta] [--salvar f.json | --comparar f.json]` — mede o motor numa pasta de políticas.
- `python -m unittest discover -s tests` — testes automatizados (regras, normas/CIS, histórico e amostras).
- `data/samples/Politica_Seguranca_NexusPay.pdf` — política sintética independente, usada como teste de regressão.
- `python db/limpar_testes.py [--apagar]` — lista (ou apaga) as auditorias de teste, preservando os exemplos do seed.
- `data/samples/Politica_Seguranca_Nimbus_Logistica_Revisada.docx` — versão corrigida da Nimbus (fictícia), nota 5,0.
- `docs/roteiro_demonstracao_backend.md` — roteiro da demonstração ao vivo.
