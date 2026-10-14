# Roteiro de replicação do ambiente — AutoAudit

Para o Moisés (e para qualquer integrante) recriar o banco na própria máquina. Cada pessoa roda
**a sua instância** do MongoDB: os dados não são compartilhados entre as máquinas.

**Ao final você terá:** o banco `autoaudit` com 1.087 normas (NIST 1.014 + LGPD 73), 6 auditorias
e 3 relatórios de exemplo, schema validado e índices criados, e o `python db/demo_crud.py`
rodando com sucesso.

Os comandos são para bash (Linux, macOS ou WSL2 no Windows). Tempo estimado: 20 a 30 minutos,
sem contar o download do Docker e do conda.

## Pré-requisitos

- Git.
- Docker com Compose v2 (confira com `docker compose version`).
- conda (Miniforge ou Miniconda) usando o canal **conda-forge**.
- Acesso ao repositório `A-Capelini/AutoAudit` (se for privado, o Anderson precisa convidar você
  como colaborador).
- As portas **27017** (MongoDB) e **8081** (mongo-express) livres. Ambas escutam só em
  `127.0.0.1`, então só a sua máquina acessa.

## Passo a passo

### 1. Clonar o repositório

```bash
git clone https://github.com/A-Capelini/AutoAudit.git
cd AutoAudit
```

### 2. Criar o ambiente Python 3.11

```bash
conda env create -f setup/environment.yml
conda activate autoaudit
python --version
```

O último comando deve mostrar `Python 3.11.x`.

### 3. Criar o seu `.env`

```bash
cp .env.example .env
```

Abra o `.env` e troque `troque_esta_senha` por uma senha simples (só letras e números) **nos dois
lugares**: na linha `MONGO_ROOT_PASS` e dentro de `MONGO_URI` (entre `autoaudit:` e `@localhost`).
Mantenha `MONGO_DB_NAME=autoaudit`. As chaves de NVD e LLM podem ficar em branco por enquanto.

Faça isso **antes** do passo 4: o usuário e a senha do MongoDB são criados na primeira subida e
ficam gravados no volume do Docker. Mudar o `.env` depois **não** muda a senha já criada. O
`.env` nunca vai para o Git (já está no `.gitignore`).

### 4. Subir o MongoDB e o mongo-express

```bash
docker compose up -d
docker compose ps
```

Espere o serviço `mongodb` aparecer como `healthy` (leva até cerca de um minuto na primeira vez).
Repita `docker compose ps` até aparecer.

### 5. Restaurar o dump

O dump `db/dump/autoaudit.archive.gz` contém as três coleções com dados, índices e validador de
schema. Ele **não** contém usuários nem senhas.

```bash
docker cp db/dump/autoaudit.archive.gz autoaudit-mongo:/tmp/autoaudit.archive.gz
docker compose exec -T mongodb sh -c 'mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --archive=/tmp/autoaudit.archive.gz --gzip'
docker compose exec -T mongodb rm /tmp/autoaudit.archive.gz
```

A última linha do `mongorestore` deve ser `1096 document(s) restored successfully. 0 document(s)
failed to restore.` (1.087 normas + 6 auditorias + 3 relatórios). Restaure **uma vez**, em banco
vazio.

### 6. Rodar o `init_db.py` (confere o schema)

```bash
python db/init_db.py
```

É idempotente: deve imprimir `[ok] ... validador atualizado` para `normas`, `auditorias` e
`relatorios`, com os índices de cada uma, e terminar em `Pronto.`

### 7. Conferir tudo com a demonstração

```bash
python db/demo_crud.py --sem-pausa
```

No passo 0 devem aparecer `normas: 1087`, `auditorias: 6` e `relatorios: 3`. No passo 4, quatro
linhas `[recusado, como esperado]` (a última com `WriteError: código 121`). No final:
`banco voltou ao estado inicial: SIM`. A demonstração só mexe nos próprios registros e apaga tudo
o que cria.

### 8. (Opcional) Ver os dados no navegador

Abra `http://localhost:8081`, entre no banco `autoaudit` e veja as três coleções. O mongo-express
está sem login; por isso só abre na sua máquina. Nunca exponha a porta 8081 na rede.

## Índice FAISS (opcional para a entrega do banco)

O índice de busca semântica **não** está no repositório (`*.index` está no `.gitignore`) nem no
dump. Ele não é necessário para o CRUD, só para a busca semântica. Há duas formas de obtê-lo:

- **Gerar na sua máquina (recomendado):**

  ```bash
  python db/build_faiss.py
  python db/build_faiss.py --consulta "política de senhas e controle de acesso"
  ```

  O primeiro comando lê as normas do MongoDB, grava `data/processed/normas.index`,
  `data/processed/normas_trechos.json` e `data/processed/normas_index.json` e atualiza
  `faiss_id`, `faiss_ids` e `embedding_modelo` nas normas, sempre consistentes com o índice. Na
  primeira execução ele baixa o modelo de embeddings (cerca de 1,1 GB) do Hugging Face. O segundo
  comando só pesquisa (top 5).
- **Copiar do Anderson** os três arquivos de `data/processed/`. Só serve se eles forem do mesmo
  build do dump; se o Anderson refizer o índice depois do dump, use a opção acima.

## Alternativa: sem o dump (do zero)

Use só se o restore não funcionar. Baixa as normas da internet e carrega no banco:

```bash
python db/init_db.py
python scripts/download_nist_oscal.py
python scripts/download_lgpd.py
python db/seed_normas.py
python db/seed_exemplo.py
```

O resultado tem as mesmas normas, mas os `_id` (ObjectId) serão diferentes dos do dump.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `port is already allocated` (27017 ou 8081) | Outro MongoDB ou container já usa a porta (por exemplo, o da atividade de BD-noSQL). | Veja com `docker ps` e pare **o outro container** (`docker stop <nome>`). Não apague volumes. |
| `Authentication failed` | A senha do `.env` é diferente da usada quando o volume foi criado, ou a senha em `MONGO_URI` não é igual à de `MONGO_ROOT_PASS`. | Deixe as duas senhas iguais e use a senha da primeira subida. Evite símbolos como `@`, `:` e `/` na senha (quebram a URI). |
| `docker compose ps` mostra `starting` | O MongoDB ainda está iniciando. | Espere e repita. |
| `mongorestore` com erros `E11000 duplicate key` | O dump já tinha sido restaurado antes. | Nada a fazer: os dados já estão lá. Confira com o passo 7. |
| `MONGO_URI não definida` | O `.env` não existe ou está vazio. | Refaça o passo 3 na pasta do projeto. |

## Lembretes do projeto

- Nunca commite o `.env`.
- Para parar o banco use `docker compose stop` (ou `docker compose down`, que mantém o volume).
  Nunca use a opção `-v`, que apaga os dados.
- Python 3.11 e pacotes pelo conda-forge.
- Se mudar dados e quiser compartilhar, gere o dump de novo e commite (comando em
  `docs/roteiro_demonstracao.md`, seção "Se os dados mudarem").
