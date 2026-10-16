# Roteiro de replicação do ambiente no Windows 10/11 — AutoAudit

Para quem vai rodar o projeto em um computador com **Windows**. A ideia é instalar o **WSL2** (um Ubuntu
dentro do Windows) e executar tudo nele. Assim, todos os comandos são os mesmos do
[`roteiro_replicacao.md`](roteiro_replicacao.md), que foi validado em Ubuntu.

Cada integrante roda **a sua instância** do MongoDB: os dados não são compartilhados entre as máquinas.

**Ao final você terá:** o banco `autoaudit` com 1.087 normas (NIST 1.014 + LGPD 73), 6 auditorias e
3 relatórios de exemplo, schema validado e índices criados, e o `python db/demo_crud.py` rodando com sucesso.

Tempo estimado: 40 a 60 minutos, sem contar downloads. Dois comandos são em **PowerShell**
(blocos marcados como `powershell`); todo o resto roda no **terminal do Ubuntu** (blocos `bash`).

## Pré-requisitos

- Windows 10 (versão 22H2 ou superior) ou Windows 11, com acesso de administrador.
- **Virtualização ligada na BIOS/UEFI** (costuma aparecer como "Intel VT-x", "SVM Mode" ou "Virtualization").
  Para conferir: Gerenciador de Tarefas → aba Desempenho → CPU → "Virtualização: Habilitado".
- Pelo menos 8 GB de RAM e cerca de 10 GB livres em disco (imagens do Docker, ambiente e, se for gerar o
  índice FAISS, o modelo de 1,1 GB).
- Acesso ao repositório `A-Capelini/AutoAudit` (público para leitura).
- As portas **27017** (MongoDB) e **8081** (mongo-express) livres. Se você tiver um MongoDB instalado no
  Windows, pare o serviço dele.

## Passo a passo

### 1. Instalar o WSL2 com Ubuntu

Abra o **PowerShell como administrador** (botão direito no menu Iniciar → "Terminal (Administrador)") e rode:

```powershell
wsl --install
```

Reinicie o computador quando ele pedir. Na volta, o Ubuntu abre sozinho e pede para você criar um
**nome de usuário** e uma **senha** do Linux (sem relação com a senha do Windows). Anote a senha: ela é
pedida nos comandos com `sudo`.

Se o comando só mostrar uma lista de opções, em vez de instalar, use `wsl --install -d Ubuntu`.

Confira se o Ubuntu está na versão 2 do WSL (ainda no PowerShell):

```powershell
wsl -l -v
```

A coluna `VERSION` do Ubuntu deve mostrar `2`. Se mostrar `1`, rode `wsl --set-version Ubuntu 2`.

A partir daqui, **abra o Ubuntu pelo menu Iniciar** (ou pelo Windows Terminal, na aba "Ubuntu"). Todos os
blocos `bash` abaixo rodam nele.

### 2. Instalar o Docker Desktop e ligá-lo ao Ubuntu

1. Baixe o **Docker Desktop para Windows** em `https://www.docker.com/products/docker-desktop/` e instale,
   mantendo marcada a opção **"Use WSL 2 instead of Hyper-V"**.
2. Abra o Docker Desktop e aceite os termos.
3. Vá em **Settings → Resources → WSL Integration**, ligue **"Enable integration with my default WSL distro"** e
   marque o **Ubuntu**. Clique em **Apply & Restart**.

Agora, no terminal do Ubuntu, confira:

```bash
docker --version
docker compose version
docker ps
```

O `docker ps` deve responder com uma lista vazia (só o cabeçalho), sem erro. Se aparecer
`docker: command not found` ou `Cannot connect to the Docker daemon`, veja a tabela de problemas no final.

O Docker Desktop precisa estar **aberto** sempre que você for usar o banco.

### 3. Atualizar o Ubuntu e instalar as ferramentas básicas

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl unzip nano
git --version
```

Configure o seu nome e e-mail no Git (use os **seus** dados, não os de outra pessoa):

```bash
git config --global user.name "Seu Nome Completo"
git config --global user.email "seu-email@exemplo.com"
```

Se você vai fazer `git push`, o e-mail deve ser o de uma conta GitHub sua, de preferência o endereço
`noreply` (GitHub → Settings → Emails). Para apenas rodar o projeto, não precisa de conta nem de chave SSH.

### 4. Instalar o Miniforge (conda com conda-forge)

No terminal do Ubuntu:

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

Aceite a licença (Enter até o fim e `yes`), aceite o local padrão e responda `yes` quando ele perguntar
se deve inicializar o conda. **Feche o terminal do Ubuntu e abra de novo.** Depois confira:

```bash
conda --version
rm Miniforge3-*.sh
```

O prompt passa a mostrar `(base)`, que é normal. Este é o Miniforge para **Linux**, instalado dentro do WSL.
Não use o instalador de Windows, porque o projeto roda no Ubuntu.

### 5. Baixar o projeto

Baixe o projeto **dentro do sistema de arquivos do Linux**, e não em `/mnt/c/...` (a pasta do Windows):
no Linux o Git, o Python e o Docker ficam bem mais rápidos e sem problemas de permissão.

```bash
mkdir -p ~/projetos
cd ~/projetos
git clone https://github.com/A-Capelini/AutoAudit.git
cd AutoAudit
ls db/dump/
```

O `ls` deve mostrar `autoaudit.archive.gz`.

### 6. Criar o ambiente Python 3.11

```bash
conda env create -f setup/environment.yml
conda activate autoaudit
python --version
```

O último comando deve mostrar `Python 3.11.x`. A criação do ambiente leva alguns minutos.

### 7. Criar o seu `.env`

```bash
cp .env.example .env
nano .env
```

No `nano`, troque `troque_esta_senha` por uma senha simples (só letras e números) **nos dois lugares**: na
linha `MONGO_ROOT_PASS` e dentro de `MONGO_URI` (entre `autoaudit:` e `@localhost`). Mantenha
`MONGO_DB_NAME=autoaudit`. As chaves de NVD e LLM podem ficar em branco. Para salvar: `Ctrl+O`, Enter,
`Ctrl+X`.

Confira que o arquivo existe com o nome certo (com o ponto):

```bash
ls -la .env
```

Faça isso **antes** do passo 8: o usuário e a senha do MongoDB são criados na primeira subida e ficam gravados
no volume do Docker. Mudar o `.env` depois **não** muda a senha já criada. Edite o `.env` sempre pelo `nano`
(ou pelo VS Code conectado ao WSL), e não pelo Bloco de Notas do Windows: ele pode salvar com outro final de
linha ou com o nome errado (`.env.txt`).

O `.env` nunca vai para o Git (já está no `.gitignore`).

### 8. Subir o MongoDB e o mongo-express

Com o Docker Desktop aberto:

```bash
docker compose up -d
docker compose ps
```

Espere o serviço `mongodb` aparecer como `healthy` (leva até cerca de um minuto na primeira vez, porque as
imagens são baixadas). Repita `docker compose ps` até aparecer.

### 9. Restaurar o dump

O dump `db/dump/autoaudit.archive.gz` contém as três coleções com dados, índices e validador de schema.
Ele **não** contém usuários nem senhas.

```bash
docker cp db/dump/autoaudit.archive.gz autoaudit-mongo:/tmp/autoaudit.archive.gz
docker compose exec -T mongodb sh -c 'mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --archive=/tmp/autoaudit.archive.gz --gzip'
docker compose exec -T mongodb rm /tmp/autoaudit.archive.gz
```

A última linha do `mongorestore` deve ser `1096 document(s) restored successfully. 0 document(s) failed to
restore.` (1.087 normas + 6 auditorias + 3 relatórios). Restaure **uma vez**, em banco vazio.

### 10. Rodar o `init_db.py` (confere o schema)

```bash
python db/init_db.py
```

É idempotente: deve imprimir `[ok] ... validador atualizado` para `normas`, `auditorias` e `relatorios`, com
os índices de cada uma, e terminar em `Pronto.`

### 11. Conferir tudo com a demonstração

```bash
python db/demo_crud.py --sem-pausa
```

No passo 0 devem aparecer `normas: 1087`, `auditorias: 6` e `relatorios: 3`. No passo 4, quatro linhas
`[recusado, como esperado]` (a última com `WriteError: código 121`). No final:
`banco voltou ao estado inicial: SIM`.

### 12. (Opcional) Ver os dados no navegador do Windows

Abra o navegador normal do Windows em `http://localhost:8081`, entre no banco `autoaudit` e veja as três
coleções. O mongo-express está sem login; por isso só abre na sua máquina. Nunca exponha a porta 8081 na rede.

## Índice FAISS (opcional para a entrega do banco)

O índice de busca semântica **não** está no repositório nem no dump. Ele não é necessário para o CRUD, só
para a busca semântica. Para gerá-lo na sua máquina:

```bash
python db/build_faiss.py
python db/build_faiss.py --consulta "política de senhas e controle de acesso"
```

Na primeira execução ele baixa o modelo de embeddings (cerca de 1,1 GB) do Hugging Face. O WSL pode usar
bastante memória nessa etapa; se o computador ficar lento, feche outros programas.

## No dia a dia

1. Abra o **Docker Desktop** e espere ele terminar de iniciar.
2. Abra o **Ubuntu** (menu Iniciar) e rode:

```bash
cd ~/projetos/AutoAudit
conda activate autoaudit
git pull
docker compose up -d
```

3. Para parar o banco ao terminar: `docker compose stop`. **Nunca** use `docker compose down -v`: a opção `-v`
   apaga os dados.

Para abrir os arquivos do projeto no VS Code a partir do Ubuntu: instale o VS Code no Windows, a extensão
**WSL**, e rode `code .` dentro de `~/projetos/AutoAudit`.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `wsl --install` mostra só ajuda | Versão do Windows sem a instalação automática, ou comando incompleto | Use `wsl --install -d Ubuntu`; se não funcionar, atualize o Windows (Windows Update). |
| Erro de virtualização ao abrir o Ubuntu ou o Docker Desktop | Virtualização desligada na BIOS/UEFI | Reinicie, entre na BIOS e ligue "Intel VT-x" ou "SVM Mode". |
| `wsl -l -v` mostra `VERSION 1` | Ubuntu instalado na versão antiga do WSL | `wsl --set-version Ubuntu 2` no PowerShell. |
| `docker: command not found` no Ubuntu | Integração com o WSL desligada | Docker Desktop → Settings → Resources → WSL Integration → marque o Ubuntu → Apply & Restart. |
| `Cannot connect to the Docker daemon` | Docker Desktop fechado ou ainda iniciando | Abra o Docker Desktop e espere o ícone indicar que está rodando. |
| `permission denied` ao rodar `docker` | Integração incompleta ou sessão antiga | Feche e abra o Ubuntu; se continuar, `wsl --shutdown` no PowerShell e abra o Docker Desktop de novo. |
| `port is already allocated` (27017 ou 8081) | Outro MongoDB ou container usa a porta (inclusive um MongoDB instalado no Windows) | `docker ps` mostra os containers; pare **o outro container** com `docker stop <nome>` ou o serviço do Windows. Não apague volumes. |
| Tudo muito lento | Projeto em `/mnt/c/...` | Use `~/projetos` dentro do Ubuntu (passo 5). |
| `MONGO_URI não definida` | O `.env` não existe, está vazio ou com nome errado (por exemplo `.env.txt`) | `ls -la .env` na pasta do projeto; refaça o passo 7 com o `nano`. |
| `Authentication failed` | A senha do `.env` é diferente da usada na primeira subida do Docker, ou as duas senhas do `.env` diferem | Veja a tabela e o comando de troca de senha no [`roteiro_replicacao.md`](roteiro_replicacao.md), seção "Problemas comuns". |
| `docker compose ps` mostra `starting` | O MongoDB ainda está iniciando | Espere e repita. |
| `mongorestore` com erros `E11000 duplicate key` | O dump já tinha sido restaurado antes | Nada a fazer: os dados já estão lá. Confira com o passo 11. |
| `conda: command not found` | O terminal foi aberto antes de terminar a instalação do Miniforge | Feche e abra o Ubuntu de novo; se persistir, rode `~/miniforge3/bin/conda init bash` e reabra. |

## Lembretes do projeto

- Nunca commite o `.env`.
- Nunca use `docker compose down -v` (a opção `-v` apaga os dados).
- Python 3.11 e pacotes pelo conda-forge, dentro do Ubuntu do WSL.
- Cada pessoa usa a sua própria identidade no Git (`user.name` e `user.email`).
- Se mudar dados e quiser compartilhar, gere o dump de novo e commite (comando em
  `docs/roteiro_demonstracao.md`, seção "Se os dados mudarem").
