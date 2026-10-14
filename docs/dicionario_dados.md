# Dicionário de dados — AutoAudit

Banco MongoDB `autoaudit`, com três coleções: `normas`, `auditorias` e `relatorios`.
Este documento detalha cada campo; o desenho geral está em `docs/der/der_autoaudit.png`
e as decisões de modelagem em `docs/modelagem_mongodb.md`. O schema (validação `$jsonSchema`
e índices) é criado por `python db/init_db.py`, que é idempotente; a opção `--reset` apaga as
três coleções e deve ser usada apenas em desenvolvimento.

## Convenções

- **Tipos** são tipos BSON do MongoDB: `ObjectId`, `String`, `Int`, `Long`, `Double`, `Bool`,
  `Date`, `Array<T>` e `Object`. "ou Null" indica que o campo aceita o valor nulo. Os campos de
  nota aceitam `Double` ou `Int`.
- **Obrigatório = Sim** significa que o campo consta em `required` do `$jsonSchema`: o documento
  não pode ser gravado sem ele. **Não** significa que o campo pode estar ausente.
- **PK** é a chave primária (`_id`, gerado pelo MongoDB). **AK** é chave alternativa, com
  unicidade garantida por índice único. **FK lógica** é uma referência a outra coleção: o MongoDB
  não impõe integridade referencial, então a aplicação (`db/repositorio.py`) a mantém.
- **Embutido** é um subdocumento guardado dentro de outro documento, sem coleção própria.
- Os nomes dos campos de `relatorios` seguem exatamente o dicionário devolvido por
  `analisar_documento()` (contrato do frontend). As diferenças deliberadas estão em
  `modelagem_mongodb.md`.
- Datas: em `auditorias` o gênero acompanha a entidade (`criada_em`, `concluida_em`); em `normas`
  e `relatorios` usa-se `criado_em`.
- A validação é `moderate`: vale para inserções e atualizações, mas não invalida documentos
  antigos se o schema evoluir. O schema não proíbe campos extras.

## Visão geral

| Coleção | Papel | Volume atual / esperado |
|---|---|---|
| `normas` | Uma unidade curta por controle ou artigo; é a base de grounding da busca semântica (RAG). | 1.087 documentos (NIST SP 800-53 Rev. 5: 1.014; LGPD: 73); esperado: milhares |
| `auditorias` | A execução: qual arquivo foi auditado, quando e em que estado. | Dezenas a centenas |
| `relatorios` | O resultado entregue ao analista: notas, lacunas e verificações. | No máximo um por auditoria |

---

## Coleção `auditorias`

Registra cada execução, com ciclo de vida `pendente` → `processando` → `concluida` ou `erro`.
Existe mesmo quando não há resultado (por exemplo, quando ocorre erro).

| Campo | Tipo | Obrigatório | Chave | Domínio / restrição | Descrição e exemplo |
|---|---|---|---|---|---|
| `_id` | ObjectId | Sim | PK | gerado pelo MongoDB | Identificador da auditoria. |
| `arquivo` | String | Sim | | | Nome do arquivo auditado. Ex.: `Politica_Seguranca_Nimbus_Logistica.pdf` |
| `sha256` | String | Sim | | indexado | Hash SHA-256 do conteúdo do arquivo; permite detectar documento já auditado. |
| `formato` | String ou Null | Não | | `pdf` ou `docx` | Formato do arquivo. |
| `tamanho_bytes` | Int, Long ou Null | Não | | | Tamanho do arquivo em bytes. Ex.: `184233` |
| `com_verificacao` | Bool | Sim | | | Indica se a auditoria inclui a Verificação Prática (pentest controlado em laboratório). |
| `status` | String | Sim | | `pendente`, `processando`, `concluida` ou `erro`; indexado | Estado do ciclo de vida da auditoria. |
| `modelo_llm` | String ou Null | Não | | | Modelo de linguagem usado na análise. Nulo quando não informado (por exemplo, nos dados de demonstração). |
| `erro` | String ou Null | Não | | | Mensagem de erro quando `status = erro`; nulo nos demais casos. |
| `criada_em` | Date | Sim | | índice decrescente | Momento em que a auditoria foi registrada. |
| `concluida_em` | Date ou Null | Não | | | Momento em que a auditoria terminou; ausente ou nulo enquanto não concluir. |

**Índices:** `ix_criada_em` (`criada_em` decrescente, listagem recente); `ix_sha256`
(detectar documento repetido); `ix_status` (filtrar por estado).

---

## Coleção `relatorios`

O resultado de uma auditoria concluída. É o documento que o frontend exibe e o que o
histórico lista. Relação com `auditorias`: **0..1 relatório por auditoria**.

| Campo | Tipo | Obrigatório | Chave | Domínio / restrição | Descrição e exemplo |
|---|---|---|---|---|---|
| `_id` | ObjectId | Sim | PK | gerado pelo MongoDB | Identificador do relatório. |
| `auditoria_id` | ObjectId | Sim | FK lógica → `auditorias._id` | único | Auditoria que originou o relatório. O índice único garante no máximo um relatório por auditoria. |
| `arquivo` | String | Sim | | | Nome do arquivo auditado. Cópia de `auditorias.arquivo`, mantida de propósito para o histórico listar relatórios sem consultar `auditorias`. |
| `criado_em` | Date | Sim | | índice decrescente | Momento da geração do relatório. Corresponde ao campo `data` do mock; a API formata como `dd/mm/YYYY HH:MM` para o frontend. |
| `nota_documental` | Double ou Int | Sim | | de 0 a 5 | Nota da análise do documento de política. Ex.: `3.4` |
| `nota_pratica` | Double, Int ou Null | Não | | de 0 a 5 | Nota da Verificação Prática. **Nulo = Verificação Prática não executada**, estado que o frontend já trata. Ex.: `2.1` |
| `saude_compliance` | Double ou Int | Sim | | de 0 a 5 | Nota final de Saúde de Compliance. **Campo derivado** das notas documental e prática, gravado para não recalcular a cada consulta; a regra de cálculo fica no backend (Sprint 3). Ex.: `2.8` |
| `lacunas` | Array\<Object\> | Sim | | embutido; pode ser vazio | Lacunas encontradas no documento (ver abaixo). |
| `verificacoes` | Array\<Object\> ou Null | Não | | embutido | Resultados da Verificação Prática (ver abaixo). **Nulo ou ausente = não executada.** |
| `feedback_analista` | Object ou Null | Não | | ver abaixo | Retorno do analista sobre o relatório (melhoria contínua). Fora do contrato do frontend, que o ignora. |

**Índices:** `uq_auditoria_id` (`auditoria_id` único); `ix_criado_em` (`criado_em`
decrescente, histórico).

### Subdocumento `lacunas[]` (embutido em `relatorios`)

Cada item descreve uma cláusula problemática do documento. Relação com o relatório: 0..N.

| Campo | Tipo | Obrigatório | Chave | Domínio / restrição | Descrição e exemplo |
|---|---|---|---|---|---|
| `clausula` | String | Sim | | | Seção ou cláusula do documento. Ex.: `Seção 4.2 — Senhas` |
| `trecho` | String | Sim | | | Trecho literal do documento que motivou a lacuna. Ex.: `Os usuários devem utilizar senhas seguras.` |
| `severidade` | String | Sim | | `alta`, `média` ou `baixa` (**com acento**, igual ao `CORES_SEV` do frontend) | Gravidade da lacuna. Sem acento o MongoDB rejeita. |
| `referencia` | String | Sim | | | Norma(s) relacionadas em texto livre, exibido ao usuário. Ex.: `NIST SP 800-53 IA-5; CIS Controls v8 5.2` |
| `problema` | String | Sim | | | Explicação do problema encontrado. |
| `sugestao` | String | Sim | | | Redação ou ação corretiva sugerida. |
| `mitre` | String ou Null | Não | | | Técnica MITRE ATT&CK associada. Ex.: `T1110 — Brute Force` |
| `normas_ref` | Array\<ObjectId\> | Não | FK lógica → `normas._id` | | Vínculo estruturado com as normas que fundamentam a lacuna (rastreabilidade do grounding). Extra: o frontend ignora. |

### Subdocumento `verificacoes[]` (embutido em `relatorios`)

Cada item é o resultado de um controle testado na Verificação Prática. Relação com o
relatório: 0..N (nenhum quando o campo é nulo ou ausente).

| Campo | Tipo | Obrigatório | Chave | Domínio / restrição | Descrição e exemplo |
|---|---|---|---|---|---|
| `controle` | String | Sim | | | Controle verificado. Ex.: `Portas não utilizadas fechadas` |
| `acao` | String | Sim | | | Ação executada pelo módulo de verificação. Ex.: `check_port` |
| `alvo` | String | Sim | | | Alvo da ação. Ex.: `ssh (22)` |
| `esperado` | String | Sim | | | Resultado esperado pelo controle. Ex.: `closed` |
| `observado` | String | Sim | | | Resultado efetivamente observado. Ex.: `open` |
| `status` | String | Sim | | `passou` ou `falhou` | Resultado da verificação. |

### Subdocumento `feedback_analista` (embutido em `relatorios`)

Relação com o relatório: 0..1. Nenhum dos campos é obrigatório.

| Campo | Tipo | Obrigatório | Chave | Domínio / restrição | Descrição e exemplo |
|---|---|---|---|---|---|
| `avaliacao` | String ou Null | Não | | `util`, `parcial` ou `inutil` | Avaliação do analista sobre a utilidade do relatório. |
| `comentario` | String ou Null | Não | | | Comentário livre do analista. |

---

## Coleção `normas`

Base de conhecimento usada na busca semântica. Cada documento é uma unidade curta (controle
ou artigo). Os vetores de embedding **não** ficam no MongoDB: ficam no índice FAISS, e o
MongoDB guarda apenas os ids para ligar vetor e texto.

| Campo | Tipo | Obrigatório | Chave | Domínio / restrição | Descrição e exemplo |
|---|---|---|---|---|---|
| `_id` | ObjectId | Sim | PK | gerado pelo MongoDB | Identificador da norma. |
| `fonte` | String | Sim | AK (com `identificador`) | `NIST_800_53`, `CIS_V8`, `LGPD`, `ISO27001_ANEXO_A` ou `SANS` | Origem da norma. Hoje há cargas de `NIST_800_53` e `LGPD`. |
| `identificador` | String | Sim | AK (com `fonte`) | | Código da unidade na fonte. Ex.: `AC-2` (NIST), `Art. 46` (LGPD), `5.2` (CIS) |
| `titulo` | String | Sim | | | Título da unidade. Ex.: `Account Management` |
| `texto` | String | Sim | | | Texto da norma, usado como contexto para a análise. |
| `idioma` | String | Sim | | `pt` ou `en` | Idioma do texto. |
| `familia` | String ou Null | Não | | | Família ou agrupamento na fonte. Ex.: `AC` |
| `grupo_implementacao` | String ou Null | Não | | `IG1`, `IG2` ou `IG3` | Grupo de implementação; só existe no CIS Controls. |
| `versao_fonte` | String ou Null | Não | | | Versão da fonte. Ex.: `Rev. 5` |
| `faiss_id` | Int, Long ou Null | Não | | índice esparso | Id do **primeiro** vetor da norma no FAISS (redundante com `faiss_ids[0]`, mantido como atalho). |
| `faiss_ids` | Array\<Int ou Long\> | Não | | índice esparso | Ids de todos os vetores da norma. Normas longas são divididas em trechos (~150 tokens), um vetor por trecho; na consulta, trechos da mesma norma viram um resultado só. |
| `embedding_modelo` | String ou Null | Não | | | Modelo que gerou os vetores. Ex.: `paraphrase-multilingual-mpnet-base-v2` (768 dimensões) |
| `mapeamentos` | Array\<String\> | Não | referência textual a outra norma | formato `FONTE:IDENTIFICADOR` | Normas equivalentes em outra fonte. Ex.: `CIS_V8:5.1` |
| `criado_em` | Date | Não | | | Momento da carga da norma. |

**Índices:** `uq_fonte_identificador` (`fonte` + `identificador`, único); `ix_faiss_id`
(esparso); `ix_faiss_ids` (esparso).

**Carga atual:** NIST SP 800-53 Rev. 5 com 1.014 unidades (1.196 itens entre controles e
melhorias, menos 182 retirados); LGPD com 73 artigos vigentes (só a redação mais recente de
cada artigo; vetados e revogados ficam de fora). Índice FAISS: 1.705 vetores de 768 dimensões.

---

## Relacionamentos

| Origem | Destino | Cardinalidade | Forma | Campo | Observação |
|---|---|---|---|---|---|
| `auditorias` | `relatorios` | 1 : 0..1 | referência | `relatorios.auditoria_id` | Auditoria `pendente`, `processando` ou com `erro` não tem relatório. |
| `relatorios` | `lacunas` | 1 : 0..N | embutido | `relatorios.lacunas` | Lidas sempre junto com o relatório. |
| `relatorios` | `verificacoes` | 1 : 0..N | embutido | `relatorios.verificacoes` | Nulo ou ausente quando a Verificação Prática não foi executada. |
| `relatorios` | `feedback_analista` | 1 : 0..1 | embutido | `relatorios.feedback_analista` | Opcional. |
| `lacunas` | `normas` | N : M | referência | `lacunas[].normas_ref` | Opcional; uma lacuna pode citar várias normas e uma norma fundamentar várias lacunas. |
| `normas` | `normas` | N : M | referência textual | `normas.mapeamentos` | Aponta por `FONTE:IDENTIFICADOR`, não por `_id`. |

## Regras de integridade mantidas pela aplicação

O MongoDB não impõe chaves estrangeiras e este projeto não usa transações. Por isso
`db/repositorio.py` respeita a ordem abaixo:

- **Criação:** primeiro a auditoria, depois o relatório que aponta para ela.
- **Exclusão:** primeiro o relatório, depois a auditoria. Apagar a auditoria antes deixaria um
  relatório com `auditoria_id` apontando para um documento inexistente.
- **Unicidade:** `(fonte, identificador)` em `normas` e `auditoria_id` em `relatorios` são
  garantidas por índice único, não pela aplicação.

## Redundâncias e limitações assumidas

- `relatorios.arquivo` repete `auditorias.arquivo` (desnormalização para o histórico).
- `saude_compliance` é derivada das duas notas e `faiss_id` é derivado de `faiss_ids`.
- `mapeamentos` guarda referências textuais. A fonte `CIS_V8` já é aceita pelo schema, mas o CIS
  ainda não foi carregado, então esses vínculos não têm destino na base. Estão previstos para a
  Sprint 3.
- O vínculo entre `normas` e o índice FAISS é por id: se as normas forem recarregadas, o
  índice deve ser reconstruído com `build_faiss.py`.
