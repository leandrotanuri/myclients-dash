# Workflow: Buscar Dados do Meta Ads

## Objetivo
Extrair métricas de campanhas, conjuntos de anúncios e anúncios da API do Meta Ads para um período definido.

## Inputs Necessários
- `date_start`: Data de início no formato YYYY-MM-DD
- `date_end`: Data de fim no formato YYYY-MM-DD
- `level`: Nível de extração — `campaign`, `adset` ou `ad`
- `fields`: Lista de métricas desejadas (ex: impressions, clicks, spend, ctr, cpc, cpm, reach)

## Ferramenta
`tools/fetch_meta_insights.py`

## Como Executar
```bash
python tools/fetch_meta_insights.py \
  --date_start 2026-03-01 \
  --date_end 2026-03-31 \
  --level campaign \
  --fields impressions,clicks,spend,ctr,cpc,cpm,reach
```

## Output Esperado
Arquivo CSV em `output/meta_insights_<level>_<date_start>_<date_end>.csv`

## Casos Excepcionais
- **Rate limit**: A API do Meta limita requisições. Se ocorrer erro 80004, aguardar alguns minutos e tentar novamente em batch menor.
- **Token expirado**: Tokens de usuário expiram em 60 dias. Usar token de sistema (System User Token) para evitar isso.
- **Account ID inválido**: Confirmar que o ID inclui o prefixo `act_`.

## Notas
- Tokens de acesso ficam em `.env` — nunca commitar esse arquivo
- O output vai para a pasta `output/` local (intermediário), depois é enviado ao Google Sheets
