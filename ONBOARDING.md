# Sistema de Relatórios Meta Ads — Guia de Replicação

Este guia explica como configurar o sistema completo de relatórios e dashboard Meta Ads para novos clientes.

## O que este sistema faz

- Busca dados diários da Meta Ads API (gastos, leads, seguidores por campanha)
- Preenche automaticamente a planilha Google Sheets do cliente
- Disponibiliza um dashboard visual no Streamlit com métricas, gráficos e metas

## Pré-requisitos

1. **Python 3.10+** instalado
2. **Git** instalado
3. **Meta Access Token** (token de longa duração de 60 dias da API do Meta)
4. **Google Sheets API** configurada (credenciais OAuth2)
5. **Conta no Streamlit Cloud** (gratuita) para hospedar o dashboard

## Configuração inicial (fazer uma vez)

### 1. Clonar o repositório

```powershell
git clone https://github.com/leandrotanuri/dashboard.git
cd dashboard
pip install -r requirements.txt
```

### 2. Criar o arquivo .env

Crie um arquivo `.env` na raiz com:

```
META_ACCESS_TOKEN=seu_token_aqui
META_APP_ID=id_do_app_meta
META_APP_SECRET=secret_do_app_meta
```

### 3. Autenticar com o Google

```powershell
python autenticar_google.py
```

Isso vai abrir o navegador para autorizar o acesso ao Google Sheets e salvar o `token.json`.

### 4. Criar a planilha do cliente

A planilha deve ter abas mensais no formato `📈 Jan`, `📈 Fev`, etc., com:
- Coluna D:E → WhatsApp (investido / leads)
- Coluna G:H → Lead Ads (investido / leads)
- Coluna J:K → Landing Page (investido / leads)
- Coluna M:N → Seguidores (investido / quantidade)
- Linha 5 = dia 01, linha 6 = dia 02, etc.

## Adicionar um novo cliente

Use o comando `/setup-meta-dashboard` no Claude Code. Ele vai pedir:

1. Nome do cliente
2. Meta Ad Account ID (encontra no Gerenciador de Anúncios)
3. Google Spreadsheet ID (da URL da planilha)
4. Tipo: `clinica_geral` (consultas + cirurgias) ou `tricologia` (só pacientes)
5. Metas mensais do cliente
6. ID da planilha de agendamentos (opcional)

O Claude cria todos os arquivos automaticamente e faz o push pro GitHub.

## Estrutura do projeto

```
tools/
  daily_{cliente}.py     → script de atualização diária por cliente
  fill_all_sheets.py     → atualiza todos os clientes de uma vez
  dashboard.py           → dashboard Streamlit
  generate_insights.py   → análise semanal automática
  sheets_client.py       → cliente Google Sheets (não mexer)

run_daily_{cliente}.bat  → atalho para rodar o script (Windows)
run_daily_all_clients.bat → roda todos os clientes
```

## Dashboard Streamlit

O dashboard está em: **[URL do app]**

Para adicionar um cliente ao dashboard:
1. Adicionar no `CLIENTS` de `tools/dashboard.py` (feito pelo `/setup-meta-dashboard`)
2. Adicionar a senha nos Secrets do Streamlit Cloud:

```toml
[passwords]
"Nome do Cliente" = "senha"
admin = "sua_senha_admin"
```

## Atualização diária

Cada cliente tem um `.bat` que pode ser agendado no Windows Task Scheduler:
- `run_daily_{cliente}.bat` → atualiza só aquele cliente
- `run_daily_all_clients.bat` → atualiza todos

## Dúvidas

Abra o Claude Code na pasta do projeto e pergunte. O arquivo `CLAUDE.md` contém as instruções do agente e a arquitetura do sistema.
