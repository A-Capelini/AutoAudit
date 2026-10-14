# Modelagem do MongoDB — AutoAudit (Sprint 2)

Banco: `autoaudit`. Três coleções. Criação/validação: `python db/init_db.py`.

**Regra central:** os campos de `relatorios` têm exatamente os nomes do dicionário que
`analisar_documento()` devolve em `frontend/mock_data.py`. Quando o backend (Sprint 3)
existir, ele grava e lê esse dicionário sem tradução, e o frontend não muda.

## Visão geral

```
normas  <-- normas_ref (opcional) --  relatorios  -- auditoria_id -->  auditorias
(base de grounding)                   (resultado, = contrato)           (execução)
```

| Coleção | Papel | Volume esperado |
|---|---|---|
| `normas` | Uma unidade curta por controle/artigo (NIST, CIS, LGPD, ISO Anexo A, SANS). Alimenta o RAG. | Milhares |
| `auditorias` | A execução: qual arquivo, quando, em que estado (`pendente` → `processando` → `concluida` ou `erro`). | Dezenas/centenas |
| `relatorios` | O resultado entregue ao analista: notas, lacunas, verificações. No máximo um por auditoria (0..1). | Menor ou igual a `auditorias` |

## Decisões

1. **Contrato do frontend é a fonte da verdade.** Ele já está no ar; o banco se adapta a ele.
2. **Auditoria ≠ relatório.** A auditoria tem ciclo de vida (processando, erro) mesmo sem resultado; o relatório só existe quando há resultado. Por isso a relação é **auditoria 1 : 0..1 relatório** (não 1:1): uma auditoria `pendente`, `processando` ou com `erro` não tem relatório. O histórico lista `relatorios`.
3. **Lacunas e verificações embutidas no relatório.** São sempre lidas juntas e o tamanho fica muito abaixo de 16 MB por documento.
4. **Embeddings ficam no FAISS.** O Mongo guarda só `faiss_ids`, para ir do vetor ao texto da norma.
   O modelo lê no máximo 256 tokens por vez e ~22% do NIST e ~34% da LGPD passam disso (ex.: Art. 7º tem
   684 tokens). Essas normas são divididas em **trechos** (por inciso, parágrafo ou frase, ~150 tokens cada, repetindo
   o título e a primeira linha da norma como contexto), um vetor por trecho. Uma norma tem, portanto, vários
   `faiss_ids`; `faiss_id` é só o primeiro. Na consulta, trechos da mesma norma viram um resultado só.
   (Sem a divisão, o Art. 7º não aparecia para a pergunta sobre hipóteses legais de tratamento.)
5. **`nota_pratica` e `verificacoes` aceitam `null`** — é o estado "Verificação Prática não executada" (cenário FCS) que o frontend já trata.
6. **Validação `moderate`:** valida inserções/atualizações, mas não quebra documentos antigos se o schema evoluir.
7. **Severidade com acento** (`alta`, `média`, `baixa`), igual ao `CORES_SEV` do `app.py`; sem acento o Mongo rejeita.
8. **Convenção dos campos de data.** Em `auditorias` o gênero acompanha a entidade, como no valor `status = "concluida"`: `criada_em` e `concluida_em`. Em `normas` e `relatorios` vale `criado_em` (o de `relatorios` também é exigência do contrato). A diferença é deliberada: renomear `auditorias` para `criado_em` deixaria `concluido_em` em desacordo com o valor `"concluida"`.

## Coleção `relatorios` (= contrato)

```json
{
  "auditoria_id": "<ObjectId>",
  "arquivo": "Politica_Seguranca_Nimbus_Logistica.pdf",
  "criado_em": "<date>",
  "nota_documental": 3.4,
  "nota_pratica": 2.1,
  "saude_compliance": 2.8,
  "lacunas": [{
    "clausula": "Seção 4.2 — Senhas",
    "trecho": "Os usuários devem utilizar senhas seguras.",
    "severidade": "alta",
    "referencia": "NIST SP 800-53 IA-5; CIS Controls v8 5.2",
    "problema": "Termo 'seguras' não é mensurável...",
    "sugestao": "Senhas devem ter no mínimo 12 caracteres...",
    "mitre": "T1110 — Brute Force",
    "normas_ref": ["<ObjectId>"]
  }],
  "verificacoes": [{
    "controle": "Portas não utilizadas fechadas",
    "acao": "check_port",
    "alvo": "ssh (22)",
    "esperado": "closed",
    "observado": "open",
    "status": "falhou"
  }],
  "feedback_analista": null
}
```

Diferenças deliberadas em relação ao dict do mock (o backend converte na borda da API):

| No mock | No Mongo | Motivo |
|---|---|---|
| `id` (int do hash) | `_id` do relatório / `auditoria_id` | ObjectId é único de verdade; o hash colidiria |
| `data` ("dd/mm/YYYY HH:MM") | `criado_em` (date) | permite ordenar e filtrar; a API formata para o frontend |
| — | `normas_ref`, `feedback_analista` | extras; o frontend ignora |

Índices: `auditoria_id` único (garante no máximo um relatório por auditoria); `criado_em` decrescente (histórico).

## Coleção `auditorias`

```json
{
  "arquivo": "Politica_Seguranca_Nimbus_Logistica.pdf",
  "sha256": "<hash do conteúdo>",
  "formato": "pdf",
  "tamanho_bytes": 184233,
  "com_verificacao": true,
  "status": "concluida",
  "modelo_llm": null,
  "erro": null,
  "criada_em": "<date>",
  "concluida_em": "<date>"
}
```

Índices: `criada_em` decrescente, `sha256` (detectar documento já auditado), `status`.

## Coleção `normas`

```json
{
  "fonte": "NIST_800_53",
  "identificador": "AC-2",
  "titulo": "Account Management",
  "texto": "...",
  "idioma": "en",
  "familia": "AC",
  "grupo_implementacao": null,
  "versao_fonte": "Rev. 5",
  "faiss_id": 17,
  "faiss_ids": [17, 18],
  "embedding_modelo": "paraphrase-multilingual-mpnet-base-v2",
  "mapeamentos": ["CIS_V8:5.1"],
  "criado_em": "<date>"
}
```

Índices: `(fonte, identificador)` único; `faiss_id` e `faiss_ids` esparsos.

Carga atual: NIST SP 800-53 Rev. 5 com 1.014 unidades (1.196 itens entre controles e melhorias, menos 182 retirados);
LGPD com 73 artigos vigentes (só a redação mais recente de cada artigo; vetados e revogados ficam de fora).
Índice FAISS: 1.705 vetores de 768 dimensões para essas 1.087 normas.

## Como foi verificado

O schema foi convertido para JSON Schema comum e validado contra a saída real de
`analisar_documento()` (com e sem Verificação Prática), e contra casos inválidos
(severidade sem acento, nota 6, status inexistente). **Ainda não foi executado contra um
MongoDB de verdade** — o primeiro `python db/init_db.py` no seu Docker é o teste final.
