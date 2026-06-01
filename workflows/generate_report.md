# Workflow: Gerar Relatório de Performance

## Objetivo
Consolidar dados do Meta Ads em um relatório de performance e enviar para o Google Sheets com três abas: Resumo, Campanhas e Diário.

## Pré-requisitos

### 1. Variáveis de ambiente (`.env`)
```
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=act_...
GOOGLE_SPREADSHEET_ID=...
```

### 2. Google Workspace CLI (gws)
Instalar e autenticar uma única vez:
```bash
npm install -g @googleworkspace/cli
gws auth setup   # configura o client secret (requer projeto no Google Cloud Console)
gws auth login   # abre o fluxo OAuth no navegador
```
Após isso, as credenciais ficam armazenadas localmente pelo gws — não é necessário nenhum `credentials.json` no projeto.

---

## Execução Rápida (recomendada)

Um único comando executa o pipeline completo:

```bash
python tools/run_report.py \
  --date_start 2026-03-01 \
  --date_end   2026-03-31 \
  --level      campaign
```

O script imprime o progresso em 3 etapas e atualiza as abas automaticamente.

---

## Execução Manual (passo a passo)

### 1. Buscar dados da API Meta

```bash
python tools/fetch_meta_insights.py \
  --date_start 2026-03-01 \
  --date_end   2026-03-31 \
  --level      campaign
```

Saída: `output/meta_insights_campaign_2026-03-01_2026-03-31.csv`

### 2. Processar dados

```bash
python tools/process_insights.py \
  --input output/meta_insights_campaign_2026-03-01_2026-03-31.csv
```

Saídas geradas:
- `output/resumo.csv` — totais do período (1 linha)
- `output/campanhas.csv` — performance por campanha
- `output/diario.csv` — performance dia a dia

### 3. Enviar para Google Sheets

```bash
python tools/upload_to_sheets.py --folder output/
```

---

## Output Esperado

Planilha Google Sheets atualizada com três abas:

| Aba | Fonte | Conteúdo |
|---|---|---|
| Resumo | `output/resumo.csv` | Totais do período: spend, impressions, clicks, reach, CTR, CPC, CPM |
| Campanhas | `output/campanhas.csv` | Performance por campanha, ordenado por spend desc |
| Diário | `output/diario.csv` | Performance dia a dia, ordenado por data asc |

---

## Casos Excepcionais

- **`gws` não encontrado**: Instalar com `npm install -g @googleworkspace/cli` e autenticar com `gws auth login`.
- **Erro de autenticação no gws**: Reautenticar com `gws auth login`. O token OAuth pode ter expirado.
- **Dados faltando**: Se o CSV estiver vazio, verificar se a conta teve atividade no período e se o `META_AD_ACCOUNT_ID` está correto (deve ter prefixo `act_`).
- **Token Meta expirado**: Tokens de usuário expiram em 60 dias. Prefira usar um System User Token para evitar reautenticação.
- **Rate limit Meta (erro 80004)**: Aguardar alguns minutos e tentar novamente. Documentado também em `workflows/fetch_meta_ads_data.md`.
- **Planilha não encontrada**: Verificar o `GOOGLE_SPREADSHEET_ID` no `.env` e confirmar que a conta autenticada tem acesso de editor à planilha.
- **Colunas ausentes no processamento**: Ao usar `--level campaign`, as colunas `adset_name` e `ad_name` não estarão presentes — isso é esperado e tratado automaticamente por `process_insights.py`.
- **Divisão por zero**: Linhas com `impressions=0` resultam em CTR/CPM=0.0 e são tratadas com guard em `process_insights.py`.
