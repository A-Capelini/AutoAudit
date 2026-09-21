# AutoAudit — Starter (Sprint 1)

Scaffold inicial do projeto: banco de dados, ambiente Python e scripts de
aquisição de dataset. Cobre a entrega da **Sprint 1** do cronograma
(infraestrutura + dataset).

## Estrutura

```
autoaudit-starter/
├── docker-compose.yml      # MongoDB + interface web (mongo-express)
├── .env.example             # copie para .env e preencha
├── requirements.txt          # mantido como referência (não usado no setup — veja environment.yml)
├── environment.yml           # ambiente conda-forge (use este no setup)
├── data/
│   ├── raw/                 # arquivos baixados (não vai pro Git)
│   └── processed/           # dados limpos/estruturados (não vai pro Git)
└── scripts/
    ├── download_nist_oscal.py   # NIST SP 800-53 (automático)
    ├── download_lgpd.py         # LGPD (automático)
    ├── download_nvd_sample.py   # amostra de CVEs (automático)
    └── DATASETS.md              # guia manual (CIS, SANS, nota sobre ISO 27001)
```

## Setup — Windows

1. Instale o **Docker Desktop** (usa WSL2 por baixo — o instalador configura
   sozinho na maioria dos casos).
2. Instale o **Miniforge** (conda-forge como canal padrão, mais leve que o
   Anaconda completo): https://github.com/conda-forge/miniforge
3. Abra o "Miniforge Prompt" na pasta do projeto:
   ```powershell
   conda env create -f environment.yml
   conda activate autoaudit
   copy .env.example .env
   ```
4. Suba o MongoDB:
   ```powershell
   docker compose up -d
   ```

## Setup — Linux

1. Instale Docker + Docker Compose (`sudo apt install docker.io docker-compose-plugin`
   ou o script oficial `get-docker.sh`).
2. Instale o Miniforge, se ainda não tiver: https://github.com/conda-forge/miniforge
3. Na pasta do projeto:
   ```bash
   conda env create -f environment.yml
   conda activate autoaudit
   cp .env.example .env
   ```
4. Suba o MongoDB:
   ```bash
   docker compose up -d
   ```

Use um ambiente **`autoaudit`** dedicado, separado do `nlp-analyzer` que você
já usa pros outros trabalhos de PLN — a stack aqui (LangChain, FAISS,
MongoDB, python-nmap) é mais pesada e específica, e misturar aumenta o
risco de quebrar algo que já está funcionando numa tarefa entregue.

O `environment.yml` já separa os pacotes: os que têm build binária pesada
(`faiss-cpu` principalmente) vêm do conda-forge; os que mudam rápido demais
pro conda-forge acompanhar (LangChain, sentence-transformers, python-nmap)
vêm do pip, instalados dentro do próprio ambiente conda. O `torch` também
é forçado pra build CPU-only, já que a máquina não tem GPU dedicada.

Em ambos os casos, o `docker-compose.yml` é o mesmo arquivo — essa é
literalmente a vantagem de rodar o banco em container em vez de instalar o
MongoDB nativo: quem está no Windows e quem está no Linux sobem exatamente o
mesmo ambiente.

## Verificar que o Mongo subiu

- Interface web: http://localhost:8081 (mongo-express, sem login em dev)
- Ou via shell: `docker exec -it autoaudit-mongo mongosh -u autoaudit -p`

## Baixar o dataset

Com o ambiente conda ativado:

```bash
python scripts/download_nist_oscal.py
python scripts/download_lgpd.py
python scripts/download_nvd_sample.py --keyword mongodb --results 30
```

Os três já testados e funcionando (o NIST inclusive baixa **324 controles**
reais em `data/raw/`). Para CIS Controls v8, templates do SANS e a nota
sobre a ISO 27001 (que **não deve** ser baixada por questão de direitos
autorais), veja `scripts/DATASETS.md`.

## Próximos passos (restante da Sprint 1)

- [ ] Rodar os 3 scripts e conferir os arquivos em `data/raw/`
- [ ] Baixar CIS Controls v8 e templates do SANS manualmente (`DATASETS.md`)
- [ ] Escrever o parser que estrutura cada fonte em "documentos curtos"
      (um por cláusula/artigo/controle) — formato comum pra todas as fontes
- [ ] Gerar os embeddings (`paraphrase-multilingual-mpnet-base-v2`) e montar
      o índice FAISS inicial
- [ ] Definir as coleções do MongoDB (ex.: `normas`, `auditorias`, `relatorios`)
