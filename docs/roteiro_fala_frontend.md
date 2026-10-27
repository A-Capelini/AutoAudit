# Roteiro de fala — apresentação do frontend (27/10)

Duração sugerida: **10 a 12 minutos** (slides + demonstração), mais perguntas.
Arquivo dos slides: `AutoAudit_Frontend_Apresentacao.pptx` (as notas de orador seguem este roteiro).

## Antes de começar (faça às 18h30)

1. **Acorde o app publicado:** abra https://autoaudit.streamlit.app. Se aparecer "This app has gone to sleep",
   clique em *Yes, get this app back up!* e espere carregar (pode levar 1 minuto).
2. **Plano B local**, em outro terminal, na raiz do projeto com o ambiente ativo:
   ```bash
   conda activate autoaudit
   git pull
   streamlit run frontend/app.py
   ```
   Deixe a aba `http://localhost:8501` aberta, mas escondida.
3. **Copie os arquivos de exemplo** de `data/samples/` para uma pasta fácil de achar na janela de upload (por exemplo, `~/Desktop/demo`):
   - `Politica_Seguranca_Nimbus_Logistica.pdf` (1º envio, com Verificação Prática);
   - `Politica_Seguranca_Alfa_Saude.pdf` (2º envio, sem Verificação Prática);
   - `Politica_Seguranca_Orion_Pagamentos.pdf` (reserva, caso queira mostrar mais uma auditoria).

   **A versão atual não lê o conteúdo do arquivo:** as notas variam conforme o arquivo, mas as lacunas são sempre as mesmas.
4. Zoom do navegador em 125% (Ctrl +) para a plateia ler; modo tela cheia (F11) na hora da demonstração.
5. Abra os slides em modo de apresentação e a visão do apresentador (notas) no notebook, se possível.

## Fala por slide

**Slide 1 — Abertura (30 s)**
"Boa noite. Vamos apresentar o AutoAudit, que audita políticas de segurança da informação com PLN e dá uma nota
de **Saúde de Compliance** de 0 a 5. Hoje o foco é a interface, que já está publicada na nuvem. Já adianto: nesta
versão os resultados são simulados, porque o backend com o PLN real é a próxima sprint."

**Slide 2 — O que a interface faz (1 min)**
"O fluxo tem quatro momentos: o analista **envia** a política, o sistema **analisa**, mostra o **resultado** e guarda o
**histórico**. A nota combina duas avaliações: a **documental** (a política é clara e completa?) e a **prática** (os
controles existem de fato no ambiente?)."

**Slide 3 — Onde o frontend se encaixa (1 min)**
"Em verde, o que está pronto: o frontend, publicado, e o banco de dados, entregue em 20/10. Em laranja, o que falta:
o backend com PLN e a Verificação Prática, que fazem pentest controlado em laboratório. Por isso os dados são
simulados. O que já está definido é o **formato** dos dados: quando o backend existir, só muda uma função."

**Slide 4 — Tela 1: Nova auditoria (1 min)**
"Aqui o analista envia o PDF ou DOCX e escolhe se inclui a Verificação Prática. Quando ela está ligada, o app deixa claro
que os testes rodam **só no laboratório isolado**: DVWA, Juice Shop e Metasploitable. O botão só habilita depois do upload."

**Slide 5 — Tela 2: Resultado (1 min 30)**
"A nota principal é a Saúde de Compliance, com barra e uma faixa de leitura, de crítica a boa conformidade. Ao lado,
as duas notas de apoio. Hoje a nota geral é a **média simples** das duas; é uma regra provisória. Se a Verificação
Prática não rodou, vale só a parte documental. Dá para filtrar as lacunas por severidade para priorizar."

**Slide 6 — O que o analista recebe (1 min 30)**
"Cada lacuna mostra o **trecho original**, o problema, a **norma de referência** (NIST, LGPD), a técnica do **MITRE ATT&CK**
quando existe e uma **sugestão de nova redação**, pronta para copiar. A aba de verificação compara o que a política
exige com o que o ambiente tem. Como scanners geram falsos positivos, a interface avisa e pede validação do analista:
o AutoAudit é um **assistente**, não substitui a revisão humana."

**Slide 7 — Sem verificação e histórico (1 min)**
"Quando a Verificação Prática não é executada, a nota prática aparece como traço e o app explica o motivo. No histórico
vemos a tabela das auditorias, uma prévia da evolução da nota (na versão final, por política) e podemos reabrir qualquer resultado. Hoje o histórico vale só
para a sessão; com o banco conectado ele fica permanente."

**Slide 8 — Do frontend ao banco (1 min)**
"O banco foi modelado a partir do que o frontend já devolve. A coleção `relatorios` tem os mesmos campos do dicionário
de `analisar_documento()`. Para conectar, trocamos só a função que simula a análise por uma chamada à API. O relatório
da Nimbus Logística que está no banco tem exatamente a lacuna de senhas que vamos ver na demonstração."

**Slide 9 — Demonstração ao vivo (transição)**
"Vamos ao app publicado." (Alt+Tab para o navegador, tela cheia.)

## Demonstração (3 a 4 min)

| # | O que fazer | O que falar |
|---|---|---|
| 1 | Em **Nova auditoria**, clique em *Upload* e escolha `Politica_Seguranca_Nimbus_Logistica.pdf`. Deixe a chave **ligada**. | "Envio uma política e mantenho a Verificação Prática ligada." Aponte o aviso do laboratório isolado. |
| 2 | Clique em **Analisar política**. Aparece o spinner e a tela de **Resultado**. | "O app mostra o spinner enquanto analisa e abre o resultado sozinho." Aponte a nota grande e as duas notas de apoio. |
| 3 | Abra **Seção 4.2 — Senhas**. | "Trecho original, problema, norma, técnica MITRE e a redação sugerida: 12 caracteres e bloqueio após 5 tentativas." |
| 4 | No filtro de severidade, **remova "baixa" e "média"**; depois recoloque. | "Posso focar só nas lacunas de severidade alta." |
| 5 | Abra a aba **Verificação prática**. | "3 de 4 falharam: a política diz uma coisa e o ambiente tem outra. Exemplo: a senha exige 12 caracteres e o ambiente aceita 6." |
| 6 | Volte a **Nova auditoria**, envie `Politica_Seguranca_Alfa_Saude.pdf`, **desligue** a chave e analise. | "Agora sem a Verificação Prática." Mostre o traço na nota prática e a aba explicando. |
| 7 | Abra **Histórico**. | "Aqui ficam as auditorias da sessão, com a nota prática vazia na segunda. O gráfico de evolução é uma prévia: na versão final ele compara **versões da mesma política** ao longo do tempo, para mostrar se a empresa melhorou." (Não entre em detalhes do gráfico: hoje ele liga todas as auditorias, de qualquer empresa.) |
| 8 | Selecione a primeira no seletor e clique em **Abrir resultado**. | "Reabro qualquer auditoria anterior." |

Volte aos slides (Alt+Tab) para o slide 10.

## Fechamento

**Slide 10 — Próximos passos (30 s)**
"Na Sprint 3: PLN real (testar com os modelos de política SANS, extrair as lacunas do documento e normalizar a
severidade), backend em FastAPI gravando no MongoDB, carga do CIS Controls e a Verificação Prática de verdade.
A apresentação final é em 24/11."

**Slide 11 — Perguntas.**

## Perguntas prováveis

| Pergunta | Resposta curta |
|---|---|
| Os resultados são reais? | Não: nesta versão são simulados e isso está escrito na barra lateral. A análise real (PLN e Verificação Prática) é a Sprint 3. O que está pronto é a interface e o formato dos dados. |
| Então por que a nota muda de um arquivo para outro? | A função simulada gera as notas a partir do conteúdo do arquivo (hash), então o mesmo arquivo dá sempre a mesma nota. As lacunas são fixas por enquanto. |
| O histórico compara empresas diferentes? | Hoje ele lista todas as auditorias da sessão. A evolução só faz sentido para a mesma política em versões diferentes; agrupar por política é um dos pontos da Sprint 3, junto com o banco. |
| Como a nota é calculada? | Média simples da nota documental e da prática; se não há Verificação Prática, vale só a documental. É provisória e deve ser refinada com o professor. |
| Por que Streamlit? | Rápido para prototipar em Python, a mesma linguagem do PLN e do backend, e publica na nuvem gratuitamente. |
| Onde ficam os dados? | Hoje só na sessão do navegador. Com o backend, no MongoDB (coleção `relatorios`), que já está modelado e replicável. |
| E os falsos positivos? | A interface avisa e pede validação por um analista; a ferramenta é um apoio à decisão. |
| Os testes práticos atacam qualquer sistema? | Não: só o laboratório isolado (DVWA, Juice Shop, Metasploitable). Isso aparece na tela. |
| O que acontece com o arquivo enviado? | Na versão atual, nada é gravado: o arquivo só gera um hash para a simulação. |

## Plano B

- **App na nuvem não abre:** use a aba local (`streamlit run frontend/app.py`).
- **Nada funciona:** percorra os slides 4 a 7, que têm capturas reais das telas, e explique os mesmos pontos.
- **Upload não responde:** recarregue a página (F5) e tente de novo; o histórico da sessão será perdido, e isso é esperado.
