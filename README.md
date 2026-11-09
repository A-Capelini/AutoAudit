# AutoAudit

**Auditoria Automatizada de Políticas de Segurança com PLN e Verificação Prática de Conformidade**

Projeto da disciplina de Processamento de Linguagem Natural (PLN) — Ciência de Dados, Fatec Cotia.
Professor: Braz Izaias da Silva Junior.

Equipe: Anderson Capelini Andrade (RA 2701352423046) · Moisés Germano Leite (RA 2701352423043)

## O que é

O AutoAudit lê uma política de segurança da informação (PDF/DOCX), usa PLN para atribuir uma nota de
**Saúde de Compliance (0 a 5)** e gera um plano de ação com sugestão de nova redação. Um módulo de
**Verificação Prática** testa, em laboratório isolado, se os controles descritos na política realmente existem.

Stack: Python · Streamlit · FastAPI · LangChain + LLM · MongoDB (não relacional) · FAISS (busca semântica).

> **Escopo ético:** todos os testes práticos rodam apenas contra ambientes de laboratório intencionalmente
> vulneráveis e isolados (DVWA, OWASP Juice Shop, Metasploitable). Nenhum sistema de terceiros é testado.

## Estrutura do repositório

```
AutoAudit/
├── .streamlit/config.toml     # tema do Streamlit (precisa ficar na raiz)
├── backend/
│   ├── main.py                # API FastAPI: uvicorn backend.main:app
│   ├── pln/
│   │   ├── extracao.py        # texto de PDF/DOCX, seções e sentenças
│   │   ├── regras.py          # regras de detecção de lacunas (termos vagos, MFA, senha, incidentes…)
│   │   ├── busca_normas.py    # busca semântica (FAISS) nas normas
│   │   └── analisador.py      # orquestra o pipeline, calcula as notas e liga as lacunas às normas
│   ├── validar_gabarito.py    # confere as regras com o gabarito da política da Nimbus
│   ├── testar_busca.py        # mostra o que o FAISS devolve para cada lacuna
│   └── testar_api.py          # teste de ponta a ponta com a API no ar
├── data/
│   ├── raw/                   # arquivos baixados (não vão para o Git)
│   ├── processed/             # índice FAISS e metadados gerados (não vão para o Git)
│   └── samples/               # política fictícia (Nimbus Logística) e gabarito para testes
├── db/
│   ├── init_db.py             # cria coleções, validadores $jsonSchema e índices (idempotente)
│   ├── seed_normas.py         # carrega NIST 800-53 e LGPD na coleção `normas`
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

Rotas: `POST /auditorias` (envia PDF/DOCX), `GET /auditorias`, `GET /relatorios`, `GET /relatorios/{id}`, `GET /saude`.
Fluxo: texto do documento → seções e sentenças → regras de detecção de lacunas → busca semântica nas normas (FAISS)
→ notas → gravação no MongoDB (`auditorias` e `relatorios`, via `db/repositorio.py`).

Testes (os dois primeiros não precisam do MongoDB):

```bash
python backend/validar_gabarito.py  # regras x gabarito da Nimbus (6 falhas plantadas, 0 falsos positivos)
python backend/testar_busca.py      # normas que o FAISS associa a cada lacuna (precisa do índice)
python backend/testar_api.py        # ponta a ponta, com a API e o MongoDB no ar
```

Limitações desta versão (ditas com franqueza na apresentação):

- A análise usa **regras explícitas** (expressões regulares e critérios de ausência), sem LLM: acha o que as regras
  conhecem. A busca semântica liga cada lacuna às normas do NIST e da LGPD, com filtro de similaridade.
- A **nota documental** é uma fórmula provisória (peso por severidade sobre o máximo possível); falta calibrar.
- A **Verificação Prática não é executada**: `nota_pratica` e `verificacoes` voltam vazios e o frontend mostra
  "não executada".
- PDF escaneado (imagem) não é suportado: não há OCR.

## Banco de dados (MongoDB)

Cada integrante roda a **própria instância** local via Docker (os dados não são compartilhados).
O banco `autoaudit` tem três coleções: `normas` (1.087 documentos: NIST SP 800-53 Rev.5 com 1.014 controles e
LGPD com 73 artigos), `auditorias` e `relatorios`. As lacunas e as verificações práticas ficam embutidas no relatório.

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

São 1.705 vetores de 768 dimensões (`paraphrase-multilingual-mpnet-base-v2`). Na primeira execução o modelo
(cerca de 1,1 GB) é baixado do Hugging Face.

## Baixar o dataset

Com o ambiente `autoaudit` ativado:

```bash
python scripts/download_nist_oscal.py
python scripts/download_lgpd.py
python scripts/download_nvd_sample.py --keyword mongodb --results 30
```

CIS Controls v8 e templates do SANS exigem download manual; a ISO 27001 **não deve** ser baixada
(direitos autorais). Detalhes em [`scripts/DATASETS.md`](scripts/DATASETS.md).

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
| 4 — Apresentação | Preparação e entrega final (24/11); prova em 01/12 | **Em andamento** (ver lista abaixo) |

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

- [ ] Baixar CIS Controls v8 e templates do SANS (hoje os `mapeamentos` das normas citam o CIS, que ainda não está carregado)
- [x] Parser que estrutura cada fonte em documentos curtos: NIST (1.014 controles ativos) e LGPD (73 artigos vigentes) prontos; faltam CIS e SANS
- [x] Embeddings (`paraphrase-multilingual-mpnet-base-v2`) e índice FAISS (`db/build_faiss.py`; normas longas divididas em trechos)
- [x] Coleções do MongoDB (`normas`, `auditorias`, `relatorios`)

Sprint 4 (apresentação final em 24/11; prova em 01/12), na ordem de execução:

- [x] README atualizado e documentação do backend em `docs/`
- [ ] Mais regras de detecção e calibração da nota, re-rodando o gabarito
- [ ] Carga do CIS Controls v8 e dos templates do SANS na base de normas, com reconstrução do índice FAISS
- [ ] Histórico por política (versões da mesma política) a partir do MongoDB
- [ ] Artigo no modelo do professor, slides e roteiro da apresentação final
- [ ] Por último, só com o resto validado: Verificação Prática (DVWA, Juice Shop, Metasploitable; nmap/OWASP ZAP via contrato JSON; 3 a 5 controles; Gap Analysis). Se não houver tempo, a apresentação segue o cenário FCS da proposta, dito com franqueza
- LLM + RAG fica fora do escopo desta entrega (o motor segue por regras, sem LLM); é a evolução natural

> O índice FAISS (`data/processed/`) não vai para o Git: ao reconstruí-lo, copie os três arquivos juntos para as outras máquinas.

### Ferramentas de apoio (Sprint 3)

- `python backend/analisar_arquivo.py <arquivo> [--busca]` — analisa um PDF/DOCX no terminal, sem API nem banco.
- `python db/limpar_testes.py [--apagar]` — lista (ou apaga) as auditorias de teste, preservando os exemplos do seed.
- `data/samples/Politica_Seguranca_Nimbus_Logistica_Revisada.docx` — versão corrigida da Nimbus (fictícia), nota 5,0.
- `docs/roteiro_demonstracao_backend.md` — roteiro da demonstração ao vivo.
