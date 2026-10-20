# AutoAudit — Escolha do banco de dados (MongoDB)

**Entrega da Sprint Um (base de dados) — 20/10/2026**
Disciplina de Processamento de Linguagem Natural — Fatec Cotia — Prof. Braz Izaias da Silva Junior
Dupla: Anderson Capelini Andrade (RA 2701352423046) e Moisés Germano Leite (RA 2701352423043)

## Banco escolhido

**MongoDB 7** (não relacional, orientado a documentos), executado em Docker, com acesso pelo `pymongo`.
O professor confirmou que, em um banco não relacional, as "tabelas" são as **coleções**.

## Por que o MongoDB

1. **O resultado da auditoria é um documento aninhado.** Um relatório tem notas, uma lista de
   lacunas e uma lista de verificações práticas, e é sempre lido **inteiro**. No MongoDB isso é um
   único documento. Em um banco relacional seriam ao menos três tabelas e `JOIN` a cada leitura.
2. **O frontend já existe e define o formato dos dados.** Os campos de `relatorios` têm os nomes
   do dicionário que `analisar_documento()` devolve. Quando o backend (FastAPI) for criado, ele
   grava e lê esse dicionário sem tradução, e o frontend não muda.
3. **O formato varia.** A Verificação Prática é opcional: `nota_pratica` e `verificacoes` podem
   ser `null`. As normas vêm de fontes diferentes (NIST, LGPD, CIS) com campos próprios. Um
   documento flexível acomoda isso sem colunas vazias.
4. **Integra com a busca semântica.** Os vetores ficam no índice FAISS (1.705 vetores de 768
   dimensões); o MongoDB guarda só os `faiss_ids` que ligam cada vetor ao texto da norma.
5. **Simples de replicar.** Cada integrante roda a própria instância local com `docker compose`.
   O banco é recriado a partir de um dump versionado, em poucos minutos.

## Como a integridade é garantida (sem chave estrangeira)

O MongoDB não tem chave estrangeira. Compensamos em três camadas:

| Camada | O que garante |
|---|---|
| Índices únicos | Uma norma por `fonte` + `identificador`; no máximo um relatório por `auditoria_id`. |
| Validador `$jsonSchema` | Tipos, campos obrigatórios, notas de 0 a 5 e severidade em `alta`, `média` ou `baixa`. |
| Repositório (`db/repositorio.py`) | Ordem de criação e exclusão, existência da auditoria e das normas citadas, norma em uso não é apagada. |

**Limitação assumida:** o MongoDB do Docker Compose é uma instância única, sem transações entre
documentos. A ordem das operações faz uma falha no meio deixar um estado válido.

## O que está pronto

- 3 coleções com schema validado e índices: `normas` (1.087 documentos: NIST e LGPD),
  `auditorias` e `relatorios` (dados de exemplo).
- DER e dicionário de dados.
- CRUD completo (Create, Read, Update, Delete) em `db/repositorio.py`, com demonstração em
  `db/demo_crud.py`.
- Dump do banco para replicação.

## Onde ver cada item

| Item | Arquivo |
|---|---|
| DER | [`docs/der/der_autoaudit.png`](der/der_autoaudit.png) |
| Dicionário de dados | [`docs/dicionario_dados.md`](dicionario_dados.md) |
| Modelagem e decisões | [`docs/modelagem_mongodb.md`](modelagem_mongodb.md) |
| Replicar o banco (Linux) | [`docs/roteiro_replicacao.md`](roteiro_replicacao.md) |
| Replicar o banco (Windows) | [`docs/roteiro_replicacao_windows.md`](roteiro_replicacao_windows.md) |
| Roteiro da demonstração | [`docs/roteiro_demonstracao.md`](roteiro_demonstracao.md) |
| Código do banco | [`db/`](../db/) |

## Como acessar a base

O banco roda localmente em Docker; não há servidor online. Para acessá-lo, siga
[`docs/roteiro_replicacao.md`](roteiro_replicacao.md): clonar o repositório, subir o MongoDB,
restaurar o dump e conferir os dados no mongo-express (`http://localhost:8081`). A demonstração
do CRUD roda com `python db/demo_crud.py`.
