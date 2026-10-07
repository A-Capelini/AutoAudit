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
│   └── processed/             # dados estruturados (não vão para o Git)
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

Por enquanto a interface usa **dados simulados** (`frontend/mock_data.py`). O dicionário que
`analisar_documento()` devolve é o contrato com a futura API: quando o backend existir, só essa função muda.

## Banco de dados (MongoDB)

Cada integrante roda a própria instância local via Docker:

```bash
docker compose up -d
```

- Interface web: http://localhost:8081 (mongo-express, sem login em dev)
- Shell: `docker exec -it autoaudit-mongo mongosh -u autoaudit -p`

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

1. Repositório: `A-Capelini/AutoAudit`, branch `main`.
2. **Main file path:** `frontend/app.py`
3. Em *Advanced settings*, escolha Python 3.11.
4. Segredos (URL da API, chaves) vão em *Secrets* no painel — nunca no Git (`.streamlit/secrets.toml` está no `.gitignore`).

## Cronograma (4 sprints)

| Sprint | Entrega | Status |
|---|---|---|
| 1 — Frontend | Interface funcionando (prazo: 12/10) | Em andamento — interface com dados simulados pronta |
| 2 — Banco de dados | Modelagem e persistência no MongoDB | Pendente |
| 3 — Backend | Lógica, FastAPI e integração do motor de PLN | Pendente |
| 4 — Apresentação | Preparação e entrega final (24/11) | Pendente |

Pendências da Sprint 1:

- [x] Interface Streamlit (nova auditoria, resultado, histórico) com dados simulados
- [ ] Revisar textos e visual
- [ ] Testar com um template de política do SANS
- [ ] Publicar no Streamlit Cloud

Trabalho de dados em paralelo (alimenta as Sprints 2 e 3):

- [ ] Baixar CIS Controls v8 e templates do SANS
- [ ] Parser que estrutura cada fonte em documentos curtos (um por cláusula/artigo/controle)
- [ ] Embeddings (`paraphrase-multilingual-mpnet-base-v2`) e índice FAISS inicial
- [ ] Coleções do MongoDB (ex.: `normas`, `auditorias`, `relatorios`)
