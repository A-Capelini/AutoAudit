# Roteiro da demonstração — entrega do banco (20/10)

Entrega: **DER + base com as coleções criadas + CRUD funcionando** (Create, Read, Update, Delete).
Duração sugerida: cerca de 10 minutos, mais perguntas.

| Data | Evento |
|---|---|
| 19/10 | Ensaio |
| 20/10 | Entrega do banco |
| 24/11 | Apresentação final |

(Datas a conferir com o cronograma completo do professor, quando for incluído aqui.)

## Antes de apresentar

Na véspera e 15 minutos antes, na pasta do projeto com o ambiente `autoaudit` ativo:

```bash
git pull
git status --short
docker compose ps
python db/init_db.py
python db/demo_crud.py --sem-pausa
```

- `git status --short` deve vir vazio e o `mongodb` deve estar `healthy`.
- O ensaio deve terminar com `banco voltou ao estado inicial: SIM`. Isso também confirma o estado
  de partida: **1.087 normas, 6 auditorias, 3 relatórios**.
- Deixe abertos: `docs/der/der_autoaudit.png`, `docs/dicionario_dados.md` e
  `http://localhost:8081` (mongo-express, banco `autoaudit`).
- Terminal com fonte grande, na raiz do projeto.
- **Não mostre o `.env`**: não rode `cat .env` e feche o editor se ele estiver aberto com o arquivo.
- Grave um vídeo ou tire capturas do ensaio como plano B.

## Roteiro

### 1. Abertura (1 min)

- O AutoAudit audita políticas de segurança da informação com PLN e atribui uma nota de Saúde de
  Compliance de 0 a 5, validando os controles na prática (Verificação Prática).
- O banco guarda três coisas: a base de normas (NIST e LGPD), as execuções (auditorias) e os
  resultados (relatórios). O MongoDB foi confirmado pelo professor: as tabelas são as coleções.

### 2. DER e dicionário de dados (2 min)

Mostre `docs/der/der_autoaudit.png`:

- Três coleções: `normas`, `auditorias`, `relatorios`; `lacunas` e `verificacoes` são
  **embutidas** no relatório.
- Cardinalidades: auditoria 1 : 0..1 relatório (auditoria com erro ou em andamento não tem
  relatório); relatório 1 : N lacunas; lacuna N : M normas (`normas_ref`); norma N : M norma
  (`mapeamentos`).
- Embutir × referenciar: lacunas e verificações são sempre lidas junto com o relatório e cabem
  com folga nos 16 MiB por documento (limite do MongoDB); as normas são referenciadas porque várias lacunas
  citam a mesma norma.

Abra `docs/dicionario_dados.md` na tabela de `relatorios`: tipo, obrigatoriedade, domínio
(notas de 0 a 5, severidade `alta`/`média`/`baixa`) e a regra de que `nota_pratica` nula significa
"Verificação Prática não executada".

### 3. A base real (1,5 min) — mongo-express

No banco `autoaudit`:

- `normas`: 1.087 documentos. Abra uma (por exemplo, uma do NIST) e mostre `fonte`,
  `identificador`, `titulo` e `faiss_ids`. Cite o índice FAISS: 1.705 vetores de 768 dimensões; o
  MongoDB guarda só os ids que ligam o vetor ao texto.
- `relatorios`: 3 documentos. Abra o da Nimbus Logística e mostre as `lacunas` e `verificacoes`
  embutidas. Abra o da Alfa Saúde e mostre `nota_pratica: null` e `verificacoes: null`.
- `auditorias`: 6 documentos, um em cada estado (`pendente`, `processando`, `concluida`, `erro`).

### 4. CRUD ao vivo (4 min)

```bash
python db/demo_crud.py
```

O script mostra o título de cada passo e pausa **antes** de executá-lo, esperando Enter. Use as
pausas assim (a primeira, do passo 0, só mostra o estado inicial; use-a para dizer o que vem):

| Pausa antes do passo | O que já aconteceu | O que falar e onde olhar |
|---|---|---|
| 1. CREATE | Estado inicial mostrado. | Vai criar uma norma, uma auditoria e um relatório de demonstração, usando só `db/repositorio.py`. |
| 2. READ | Registros criados. | **Atualize o mongo-express**: apareceram `SANS:DEMO-CRUD-001`, a auditoria `demo_crud_politica_seguranca.pdf` (pendente) e o relatório. Note que `arquivo` do relatório foi copiado da auditoria. |
| 3. UPDATE | Consultas feitas (incluindo as normas reais do NIST). | Vai mudar o status (`pendente` → `processando` → `concluida`, com `concluida_em` preenchida sozinha), preencher a Verificação Prática e registrar o feedback do analista. |
| 4. REGRAS | Atualizações feitas. | Atualize o mongo-express: o relatório agora tem `nota_pratica: 2.1` e `feedback_analista`. Vai tentar 4 operações que **devem ser recusadas**. |
| 5. DELETE | As 4 recusas apareceram. | As recusas são: apagar norma em uso, segundo relatório para a mesma auditoria, relatório sem auditoria e severidade sem acento (erro 121 do validador do MongoDB). Mostre no mongo-express que os registros ainda existem; ao apertar Enter eles serão apagados na ordem certa. |
| Fim | Tudo apagado. | Atualize o mongo-express: voltou a 1.087 / 6 / 3. O script confirma `banco voltou ao estado inicial: SIM`. |

Ponto para explicar no passo 5: **relatório antes da auditoria**. Sem transações, se o processo
cair entre os dois passos, sobra uma auditoria sem relatório, que é um estado válido (1 : 0..1).
Na ordem inversa sobraria um relatório órfão, apontando para uma auditoria que não existe.

### 5. Fechamento (1 min)

- Pronto: DER, dicionário de dados, 3 coleções com schema validado e índices, 1.087 normas, índice
  FAISS, repositório com CRUD, dados de exemplo e dump para replicação (`docs/roteiro_replicacao.md`).
- Próximos passos: backend (Sprint 3) gravando e lendo o dicionário de `analisar_documento()` sem
  tradução, carga do CIS (hoje os `mapeamentos` apontam para uma fonte ainda não carregada) e a
  Verificação Prática real. Apresentação final em 24/11.

## Perguntas prováveis

| Pergunta | Resposta curta |
|---|---|
| Por que MongoDB e não relacional? | O resultado da auditoria é um documento aninhado (relatório com lacunas e verificações), lido sempre junto; no relacional seriam várias tabelas e joins. |
| Se não há chave estrangeira, onde está a integridade? | Em três camadas: índices únicos (`fonte`+`identificador` e `auditoria_id`), validador `$jsonSchema` (tipos, domínios, notas de 0 a 5) e o repositório (ordem de criação e exclusão, existência da auditoria e das normas citadas, norma em uso não é apagada). Tudo isso aparece no passo 4. |
| Por que sem transações? | O MongoDB do Docker Compose é uma instância única (standalone) e transações multi-documento exigem replica set. A ordem das operações faz uma falha no meio deixar um estado válido. Limitação assumida: as checagens não são atômicas; com um usuário por instância o risco é baixo. |
| Onde ficam os embeddings? | No índice FAISS (1.705 vetores de 768 dimensões). O MongoDB guarda `faiss_ids`. Normas longas viram vários trechos, um vetor por trecho. |
| Há redundância no modelo? | Sim, deliberada e documentada: `arquivo` também em `relatorios` (histórico sem join), `saude_compliance` derivada das notas e `faiss_id` igual ao primeiro de `faiss_ids`. |
| O frontend precisa mudar? | Não. Os campos de `relatorios` têm os nomes do dicionário de `analisar_documento()`. A API só converte `_id`/`auditoria_id` e `criado_em` (para `dd/mm/YYYY HH:MM`). |
| O que ainda falta? | `mapeamentos` para o CIS (não carregado), o backend (Sprint 3) e a Verificação Prática real. |
| Os dados da demonstração ficam no banco? | Não: o script apaga tudo o que cria. As 6 auditorias e 3 relatórios de exemplo vêm de `db/seed_exemplo.py`. |
| Como outra pessoa replica o banco? | `docs/roteiro_replicacao.md`, com o dump em `db/dump/`. |

## Plano B

- **MongoDB fora do ar:** `docker compose up -d` e espere `healthy` em `docker compose ps`.
- **Falha ou travamento ao vivo:** mostre o vídeo ou as capturas do ensaio.
- **Contagens diferentes de 1.087 / 6 / 3:** `python db/seed_exemplo.py` completa os dados de
  exemplo e `python db/seed_normas.py` completa as normas (ambos idempotentes).
- **mongo-express indisponível:** mostre um relatório pelo terminal:

  ```bash
  docker compose exec -T mongodb sh -c 'mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin autoaudit --eval "db.relatorios.findOne()"'
  ```

## Se os dados mudarem

O dump em `db/dump/` é uma foto do banco no dia em que foi gerado. Se normas ou dados de exemplo
mudarem, gere de novo e commite (o `grep` deve imprimir `0`: a senha do `.env` não está no dump):

```bash
docker compose exec -T mongodb sh -c 'mongodump --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db autoaudit --archive --gzip' > db/dump/autoaudit.archive.gz
gunzip -t db/dump/autoaudit.archive.gz && echo "gzip íntegro"
gunzip -c db/dump/autoaudit.archive.gz | grep -a -c -F "$(grep '^MONGO_ROOT_PASS=' .env | cut -d= -f2-)"
git add db/dump/autoaudit.archive.gz
git commit -m "chore(db): atualiza dump do banco autoaudit"
```
