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
│   ├── roteiro_replicacao.md  # como recriar o banco em outra máquina
│   └── roteiro_demonstracao.md# roteiro da apresentação do banco
├── frontend/
│   ├── app.py                 # interface Streamlit
│   └── mock_data.py           # relatório simulado (será trocado pela API)
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

A interface usa **dados simulados** (`frontend/mock_data.py`); o backend (Sprint 3) ainda não existe. O dicionário que
`analisar_documento()` devolve é o contrato com a futura API: quando o backend existir, só essa função muda.
O banco já foi desenhado para guardar esse dicionário sem tradução (veja `db/testar_contrato.py`).

## Banco de dados (MongoDB)

Cada integrante roda a **própria instância** local via Docker (os dados não são compartilhados).
O banco `autoaudit` tem três coleções: `normas` (1.087 documentos: NIST SP 800-53 Rev.5 com 1.014 controles e
LGPD com 73 artigos), `auditorias` e `relatorios`. As lacunas e as verificações práticas ficam embutidas no relatório.

Ambiente novo? Siga o [`docs/roteiro_replicacao.md`](docs/roteiro_replicacao.md): ele cria o `.env`, sobe o
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
4. Segredos (URL da API, chaves) vão em *Secrets* no painel — nunca no Git (`.streamlit/secrets.toml` está no `.gitignore`).

## Cronograma (4 sprints)

| Sprint | Entrega | Status |
|---|---|---|
| 1 — Frontend | Interface funcionando | Entregue em 13/10 (interface com dados simulados) |
| 2 — Banco de dados | DER, base com as coleções criadas e CRUD funcionando | Pronto; **entrega e demonstração em 20/10** |
| 3 — Backend | Lógica, FastAPI e integração do motor de PLN | Pendente |
| 4 — Apresentação | Preparação e entrega final (24/11) | Pendente |

Sprint 2 (banco de dados):

- [x] Modelagem das coleções `normas`, `auditorias` e `relatorios` (`docs/modelagem_mongodb.md`)
- [x] DER conceitual (`docs/der/`) e dicionário de dados (`docs/dicionario_dados.md`)
- [x] Coleções com validação de schema e índices (`db/init_db.py`)
- [x] CRUD das três coleções (`db/repositorio.py`) e demonstração (`db/demo_crud.py`)
- [x] Dados: 1.087 normas e 6 auditorias/3 relatórios de exemplo; dump para replicação (`db/dump/`)
- [x] Roteiros de replicação e de demonstração (`docs/`)
- [ ] Apresentar o banco em 20/10

Frontend (Sprint 1):

- [x] Interface Streamlit (nova auditoria, resultado, histórico) com dados simulados
- [x] Publicado no Streamlit Community Cloud (https://autoaudit.streamlit.app)
- [x] Revisão do código: fuso horário de São Paulo na data e HTML escapado nos trechos da política
- [ ] Revisar textos e visual (ajustes finos, sem prazo)

Pendências para a Sprint 3 (backend):

- [ ] Testar o motor de PLN com templates do SANS (o frontend atual não lê o conteúdo do arquivo)
- [ ] Gerar lacunas a partir do documento enviado (hoje o mock devolve sempre as mesmas) e normalizar a severidade (`alta`, `média`, `baixa`) antes de devolver o relatório

Trabalho de dados em paralelo (alimenta a Sprint 3):

- [ ] Baixar CIS Controls v8 e templates do SANS (hoje os `mapeamentos` das normas citam o CIS, que ainda não está carregado)
- [x] Parser que estrutura cada fonte em documentos curtos: NIST (1.014 controles ativos) e LGPD (73 artigos vigentes) prontos; faltam CIS e SANS
- [x] Embeddings (`paraphrase-multilingual-mpnet-base-v2`) e índice FAISS (`db/build_faiss.py`; normas longas divididas em trechos)
- [x] Coleções do MongoDB (`normas`, `auditorias`, `relatorios`)
