"""
Dashboard de Campanhas Meta Ads
Seguidores (E1-DIST) e Mensagens (E2-CAP)
"""

import ast
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent.parent / ".env")

# Streamlit Cloud: carrega secrets como variáveis de ambiente
try:
    import streamlit as _st
    for _k, _v in _st.secrets.items():
        if isinstance(_v, str) and not os.getenv(_k):
            os.environ[_k] = _v
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

# ── autenticação ───────────────────────────────────────────────────────────────
def _load_passwords() -> dict:
    """Retorna {senha: cliente} lendo de st.secrets ou .env."""
    try:
        pw = st.secrets.get("passwords", {})
        return {v: k for k, v in pw.items()}  # inverte: senha → nome_chave
    except Exception:
        return {}

def _check_auth():
    """Gerencia login. Retorna (cliente_forçado_ou_None, is_admin)."""
    passwords_raw = {}
    try:
        passwords_raw = dict(st.secrets.get("passwords", {}))
    except Exception:
        pass

    admin_pass   = passwords_raw.pop("admin", None)
    # cliente_key → senha  (ex: "Dr. Vinicius" → "abc123")
    client_passes = {v: k for k, v in passwords_raw.items()}  # senha → client_key

    if "auth_client" not in st.session_state:
        st.session_state.auth_client = None
        st.session_state.auth_admin  = False

    if st.session_state.auth_client or st.session_state.auth_admin:
        return st.session_state.auth_client, st.session_state.auth_admin

    # Tela de login
    st.set_page_config(page_title="Dashboard de Campanhas", page_icon="📊", layout="wide")
    st.title("📊 Dashboard de Campanhas")
    st.markdown("---")
    col = st.columns([1, 2, 1])[1]
    with col:
        st.subheader("Acesso restrito")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if admin_pass and senha == admin_pass:
                st.session_state.auth_admin  = True
                st.session_state.auth_client = None
                st.rerun()
            elif senha in client_passes:
                st.session_state.auth_client = client_passes[senha]
                st.session_state.auth_admin  = False
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

_forced_client, _is_admin = _check_auth()
API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

FOLLOWER_KEYWORD = "E1-DIST"
MESSAGING_KEYWORD = "E2-CAP"
FIELDS_CAMPAIGN = "campaign_name,impressions,clicks,inline_link_clicks,spend,reach,ctr,cpm,actions"

# ── config por cliente ─────────────────────────────────────────────────────────
MONTH_TAB = {
    1:"📈 Jan",2:"📈 Fev",3:"📈 Mar",4:"📈 Abr",
    5:"📈 Mai",6:"📈 Jun",7:"📈 Jul",8:"📈 Ago",
    9:"📈 Set",10:"📈 Out",11:"📈 Nov",12:"📈 Dez",
}

CLIENTS = {
    "CA - Instituto Master Beauty": {
        "account_id": "act_400205609739120",
        "spreadsheet_id": None,
        "agendamentos_id": None,
        "tipo": "mensagens_lead",
        "msg_keywords":  ["ENGJ"],
        "lead_keywords": ["LEAD"],
        "leads_first": True,
        "metas_cursos": {
            "The Art Full Face": 4,
            "Endolaser Gabi":    4,
        },
    },
    "Dra. Roberta Esteves": {
        "account_id": "act_1388498128427677",
        "spreadsheet_id": None,
        "agendamentos_id": None,
        "tipo": "mensagens_lead",
        "msg_keywords":  ["ENGJ"],
        "lead_keywords": ["LEAD"],
        "leads_first": True,
        "metas_cursos": {
            "The Art Full Face": 4,
            "Endolaser Gabi":    4,
        },
    },
    "CA - CLINICA MASTER BEAUTY": {
        "account_id": "act_1007230201772374",
        "spreadsheet_id": None,
        "agendamentos_id": None,
        "tipo": "mensagens_lead",
        "msg_keywords":  ["ENGJ"],
        "lead_keywords": ["LEAD"],
        "leads_first": True,
        "metas_cursos": {
            "The Art Full Face": 4,
            "Endolaser Gabi":    4,
        },
    },
}

DEFAULT_CLIENT = "CA - Instituto Master Beauty"

# ── helpers de formatação ──────────────────────────────────────────────────────

def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_num(value: float) -> str:
    return f"{int(value):,}".replace(",", ".")

def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"

def extract_action(raw, action_type: str) -> int:
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return 0
    try:
        actions = ast.literal_eval(raw) if isinstance(raw, str) else raw
        for a in actions:
            if a.get("action_type") == action_type:
                return int(a.get("value", 0))
    except Exception:
        pass
    return 0

# ── busca de dados ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=7200)
def fetch_campaign_insights(date_start: str, date_end: str, account_id: str) -> pd.DataFrame:
    url = f"{BASE_URL}/{account_id}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "level": "campaign",
        "fields": FIELDS_CAMPAIGN,
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "time_increment": 1,
        "limit": 500,
    }
    rows = []
    while url:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ["impressions", "clicks", "inline_link_clicks", "spend", "reach", "ctr", "cpm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    actions_col = df.get("actions", pd.Series(dtype=object))
    df["messaging_contacts"] = actions_col.apply(
        lambda x: extract_action(x, "onsite_conversion.messaging_first_reply")
    )
    df["date_start"] = pd.to_datetime(df["date_start"])
    return df


GWS_CMD   = r"C:\Users\leand\AppData\Roaming\npm\gws.cmd"
NODE_PATH = r"C:\Program Files\nodejs"

def _read_sheets_range(spreadsheet_id: str, range_: str) -> list:
    """Lê range via gws (local) ou sheets_client (cloud)."""
    import json, subprocess
    if os.path.exists(GWS_CMD):
        env = os.environ.copy()
        env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
        result = subprocess.run(
            [GWS_CMD, "sheets", "spreadsheets", "values", "get",
             "--params", json.dumps({"spreadsheetId": spreadsheet_id, "range": range_})],
            capture_output=True, text=True, env=env, shell=True,
        )
        return json.loads(result.stdout).get("values", [])
    else:
        from sheets_client import read_range
        return read_range(spreadsheet_id, range_)

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_sheets_seguidores(spreadsheet_id: str, month: int) -> pd.DataFrame:
    """Lê colunas M (investido E1-DIST) e N (seguidores)."""
    tab = MONTH_TAB[month]
    range_ = f"'{tab}'!M5:N35"
    try:
        rows = _read_sheets_range(spreadsheet_id, range_)
    except Exception as e:
        raise RuntimeError(f"Erro ao ler seguidores (aba '{tab}'): {e}") from e

    records = []
    for i, row in enumerate(rows):
        dia = i + 1
        investido = float(str(row[0]).replace(",", ".").replace("R$", "").strip()) if len(row) > 0 and row[0] not in ("", None) else 0.0
        seguidores = int(float(str(row[1]).replace(",", "."))) if len(row) > 1 and row[1] not in ("", None) else 0
        records.append({"dia": dia, "investido_seg": investido, "seguidores": seguidores})

    return pd.DataFrame(records) if records else pd.DataFrame(columns=["dia", "investido_seg", "seguidores"])


# ── layout ─────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Dashboard de Campanhas", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

/* ── Base ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main,
[data-testid="block-container"] {
    background-color: #0b0d17 !important;
    color: #e0e4f0 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stHeader"] {
    background: #0b0d17 !important;
    border-bottom: 1px solid #1e2235 !important;
}
[data-testid="stToolbar"] { background: #0b0d17 !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1120 0%, #0b0d17 100%) !important;
    border-right: 1px solid #1e2235 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
    color: #b0b8d0 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #e0e4f0 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: #161829 !important;
    color: #b0b8d0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
    transition: all .15s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #1e2235 !important;
    border-color: #00d4ff !important;
    color: #00d4ff !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: #161829 !important;
    color: #c8cce8 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
}

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #0f1120 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
}
div[data-testid="metric-container"] label,
div[data-testid="metric-container"] [data-testid="stMetricLabel"] p {
    color: #3d4466 !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] > div {
    color: #00d4ff !important;
    font-size: 1.4rem !important;
    font-weight: 900 !important;
    letter-spacing: -0.5px !important;
    white-space: nowrap;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent !important;
    border-bottom: 1px solid #1e2235 !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background: transparent !important;
    color: #5a607a !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 16px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00d4ff !important;
    border-bottom: 2px solid #00d4ff !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding-top: 16px !important;
}

/* ── Dividers ── */
hr { border-color: #1e2235 !important; }

/* ── Headings & text ── */
h1, h2, h3, h4 { color: #e0e4f0 !important; font-family: 'Inter', sans-serif !important; }
p { color: #c8cfe0 !important; }

/* ── Date inputs ── */
[data-testid="stDateInput"] input {
    background: #0f1120 !important;
    color: #e0e4f0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
}
[data-testid="stDateInput"] label { color: #3d4466 !important; font-size: 0.72rem !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 1px !important; }

/* ── Selectbox ── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background: #0f1120 !important;
    color: #e0e4f0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
}
[data-testid="stSelectbox"] label { color: #3d4466 !important; font-size: 0.72rem !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 1px !important; }

/* ── Dataframes ── */
[data-testid="stDataFrame"] {
    background: #0f1120 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 10px !important;
}
[data-testid="stDataFrame"] * { color: #c8cfe0 !important; }

/* ── Buttons ── */
.stButton > button {
    background: #161829 !important;
    color: #b0b8d0 !important;
    border: 1px solid #1e2235 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all .15s !important;
}
.stButton > button:hover {
    background: #1e2235 !important;
    border-color: #00d4ff !important;
    color: #00d4ff !important;
}

/* ── Progress bar ── */
[data-testid="stProgress"] > div {
    background: #161829 !important;
    border-radius: 4px !important;
}
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #00d4ff, #00e676) !important;
    border-radius: 4px !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    background: #0f1120 !important;
    border: 1px solid #1e2235 !important;
}
[data-testid="stAlert"] p { color: #c8cfe0 !important; }

/* ── Caption ── */
[data-testid="stCaptionContainer"] p { color: #3d4466 !important; font-size: 0.75rem !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] * { color: #00d4ff !important; }

/* ── Oculta UI padrão Streamlit ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
[data-testid="stDecoration"] { display:none; }
[data-testid="stStatusWidget"] { display:none; }
[data-testid="collapsedControl"] { display:none; }

/* ── Tabela customizada ── */
.tbl-wrap { overflow-x:auto; margin-top:4px; }
.tbl-wrap table { width:100%; border-collapse:collapse; font-size:12px; }
.tbl-wrap th {
    color:#3d4466; font-weight:700; font-size:10px; text-transform:uppercase;
    letter-spacing:.8px; padding:9px 12px; text-align:left;
    border-bottom:1px solid #1e2235; white-space:nowrap;
}
.tbl-wrap td { padding:10px 12px; border-bottom:1px solid #161829; color:#8892b0; white-space:nowrap; }
.tbl-wrap tr:hover td { background:#161829; }
.tbl-wrap td.bold { color:#fff; font-weight:700; }
.tbl-wrap td.green { color:#00e676; font-weight:700; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0b0d17; }
::-webkit-scrollbar-thumb { background: #1e2235; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a2f4a; }

/* ── KPI Cards customizados ── */
.kpi-grid { display:grid; gap:12px; margin-bottom:8px; }
.kpi-card {
    background:#0f1120; border:1px solid #1e2235; border-radius:12px;
    padding:18px 20px; display:flex; flex-direction:column; gap:8px;
    transition:.2s; overflow:hidden;
}
.kpi-card:hover { border-color:#2a2f50; transform:translateY(-1px); }
.kpi-label { font-size:10px; font-weight:700; color:#3d4466; text-transform:uppercase; letter-spacing:1.2px; }
.kpi-value { font-size:30px; font-weight:900; line-height:1; letter-spacing:-1px; }
.kpi-sub { font-size:11px; color:#3d4466; display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.kpi-bar { height:2px; border-radius:2px; margin-top:2px; }

/* ── KPI Cards variante pequena (métricas do funil) ── */
.kpi-card.sm { padding:14px 14px; gap:0; border-radius:10px; height:115px; justify-content:space-between; }
.kpi-card.sm .kpi-label { font-size:9px; letter-spacing:1px; }
.kpi-card.sm .kpi-value { font-size:19px; letter-spacing:-.5px; }
.kpi-card.sm .kpi-sub   { font-size:10px; }
.kpi-card.sm .kpi-bar   { margin-top:0; }
.badge { padding:2px 8px; border-radius:99px; font-size:10px; font-weight:700; }
.badge.ok   { background:#00d4ff22; color:#00d4ff; }
.badge.up   { background:#00e67622; color:#00e676; }
.badge.down { background:#ff444422; color:#ff4444; }
.badge.warn { background:#ffd60022; color:#ffd600; }

/* ── Pills (TX. Passagem) — destaque ── */
.pill { display:inline-block; padding:4px 13px; border-radius:99px; font-size:12px; font-weight:700; letter-spacing:.4px; min-width:64px; text-align:center; }
.pill.ok   { background:rgba(0,230,118,.18); color:#00e676; border:1px solid rgba(0,230,118,.4); }
.pill.warn { background:rgba(255,214,0,.18);  color:#ffd600; border:1px solid rgba(255,214,0,.4); }
.pill.bad  { background:rgba(255,68,68,.18);  color:#ff4444; border:1px solid rgba(255,68,68,.4); }

/* ── Metric rows customizados ── */
.metrics-col { display:flex; flex-direction:column; gap:7px; }
.metric-row {
    background:#161829; border-radius:8px; padding:12px 14px;
    display:flex; justify-content:space-between; align-items:center;
    border:1px solid #1e2235;
}
.metric-row .ml { font-size:10px; color:#3d4466; font-weight:700; text-transform:uppercase; letter-spacing:.8px; }
.metric-row .mv { font-size:16px; font-weight:800; }

/* ── Roas / visão geral cards ── */
.vg-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:4px; }
.vg-card {
    background:#0f1120; border:1px solid #1e2235; border-radius:10px;
    padding:14px 18px; display:flex; flex-direction:column; gap:4px;
}
.vg-label { font-size:10px; font-weight:700; color:#3d4466; text-transform:uppercase; letter-spacing:1px; }
.vg-value { font-size:22px; font-weight:900; color:#e0e4f0; }
</style>
""", unsafe_allow_html=True)

# template base para todos os gráficos Plotly
_PD = dict(
    paper_bgcolor="#0b0d17",
    plot_bgcolor="#0f1120",
    font=dict(color="#c8cfe0", family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#1e2235", linecolor="#1e2235", tickfont=dict(color="#5a607a")),
    yaxis=dict(gridcolor="#1e2235", linecolor="#1e2235", tickfont=dict(color="#5a607a")),
    margin=dict(t=10, l=8, r=8, b=8),
)

_COL = {"cyan":"#00d4ff","green":"#00e676","yellow":"#ffd600","white":"#ffffff","red":"#ff4444","purple":"#a78bfa"}
_BAR = {
    "cyan":   "linear-gradient(90deg,#00d4ff,#7B6CF6)",
    "green":  "linear-gradient(90deg,#00e676,#00b248)",
    "yellow": "linear-gradient(90deg,#ffd600,#ff8f00)",
    "white":  "linear-gradient(90deg,#7B6CF6,#a855f7)",
    "red":    "linear-gradient(90deg,#ff4444,#c62828)",
    "purple": "linear-gradient(90deg,#a78bfa,#7B6CF6)",
}

def _kpi_html(cards: list, cols: int = 0, small: bool = False) -> str:
    """Renderiza linha de KPI cards com visual idêntico ao preview."""
    n   = cols if cols > 0 else len(cards)
    sm  = " sm" if small else ""
    items = []
    for c in cards:
        col    = c.get("color", "cyan")
        badge  = c.get("badge", "")
        bcls   = c.get("badge_cls", "ok")
        sub    = c.get("sub", "")
        badge_html = f'<span class="badge {bcls}">{badge}</span>' if badge else ""
        items.append(
            f'<div class="kpi-card{sm}">'
            f'<div class="kpi-label">{c["label"]}</div>'
            f'<div class="kpi-value" style="color:{_COL.get(col,col)}">{c["value"]}</div>'
            f'<div class="kpi-sub">{badge_html}{sub}</div>'
            f'<div class="kpi-bar" style="background:{_BAR.get(col,"")}"></div>'
            f'</div>'
        )
    return (f'<div class="kpi-grid" style="grid-template-columns:repeat({n},1fr)">'
            + "".join(items) + "</div>")

def _metric_rows_html(rows: list) -> str:
    """Renderiza coluna de métricas de performance como linhas escuras."""
    items = []
    for r in rows:
        col = _COL.get(r.get("color","white"), r.get("color","#fff"))
        items.append(
            f'<div class="metric-row">'
            f'<div class="ml">{r["label"]}</div>'
            f'<div class="mv" style="color:{col}">{r["value"]}</div>'
            f'</div>'
        )
    return '<div class="metrics-col">' + "".join(items) + "</div>"

def _pill(val_str: str) -> str:
    """Converte 'XX.XX%' num pill colorido (verde/amarelo/vermelho)."""
    try:
        v = float(val_str.replace("%", "").replace(",", "."))
        cls = "ok" if v >= 50 else ("warn" if v >= 35 else "bad")
    except Exception:
        cls = "ok"
    return f'<span class="pill {cls}">{val_str}</span>'

def _tabela_html(dt_out: pd.DataFrame, tipo_cli: str) -> str:
    """Renderiza tabela Por Dia como HTML customizado com pills e dark style."""
    base_cols  = ["Dia", "Invest. c/ Imposto", "CPM", "CPC", "CTR", "Tx Passagem", "Leads", "CPL", "Consultas", "Custo por Consulta"]
    extra_cols = ["Cirurgias Confirmadas", "Custo por Cirurgia"] if tipo_cli == "clinica_geral" else []
    headers_lbl = ["DIA", "INVEST.", "CPM", "CPC", "CTR", "TX. PASSAGEM", "LEADS", "CPL", "CONSULTAS", "CUSTO/CONS."]
    if tipo_cli == "clinica_geral":
        headers_lbl += ["CIRURGIAS", "CUSTO/CIR."]
    all_cols = base_cols + extra_cols

    thead = "".join(f"<th>{h}</th>" for h in headers_lbl)
    rows  = []
    for _, row in dt_out.iterrows():
        cells = []
        for col in all_cols:
            val = str(row.get(col, "—"))
            if col == "Tx Passagem":
                cells.append(f"<td>{_pill(val)}</td>")
            elif col == "Leads":
                cells.append(f'<td class="bold">{val}</td>')
            elif col in ("Consultas", "Cirurgias Confirmadas") and val not in ("—", "0"):
                cells.append(f'<td class="green">{val}</td>')
            elif col == "Dia":
                cells.append(f'<td style="color:#c8cfe0;font-weight:600">{val}</td>')
            else:
                cells.append(f"<td>{val}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="tbl-wrap">'
        f'<table><thead><tr>{thead}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

def _tabela_campanha_html(camp_out: pd.DataFrame, first_col: str = "CAMPANHA") -> str:
    """Renderiza tabela Por Campanha como HTML customizado."""
    cols = list(camp_out.columns)
    thead = "".join(f"<th>{c.upper()}</th>" for c in [first_col] + cols)
    rows  = []
    for idx, row in camp_out.iterrows():
        name_cell = f'<td style="color:#c8cfe0;font-weight:600;max-width:320px;overflow:hidden;text-overflow:ellipsis">{idx}</td>'
        cells = [name_cell] + [f"<td>{row[c]}</td>" for c in cols]
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="tbl-wrap">'
        f'<table><thead><tr>{thead}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

def build_funnel_html(labels, values, colors, pcts=None) -> str:
    """Funil visual com blocos de largura decrescente — efeito funil real."""
    _WIDTHS = [100, 82, 66, 52, 40]
    items = []
    for i, (label, val, color) in enumerate(zip(labels, values, colors)):
        w = _WIDTHS[i] if i < len(_WIDTHS) else 36
        val_str = f"{val:,}".replace(",", ".")
        if i == 0:
            pct_sub = "100% do alcance"
        elif pcts and i < len(pcts) and pcts[i] is not None:
            pct_sub = f"{pcts[i]:.2f}% do anterior"
        else:
            pct_sub = ""
        # seta de conversão entre blocos
        connector = ""
        if i > 0 and pcts and i < len(pcts) and pcts[i] is not None:
            connector = (
                f'<div style="width:{w}%;margin:0 auto;text-align:center;'
                f'color:#3d4466;font-size:10px;padding:2px 0;letter-spacing:.5px">▼ {pcts[i]:.1f}%</div>'
            )
        items.append(
            connector +
            f'<div style="width:{w}%;margin:0 auto;background:{color}15;'
            f'border:1px solid {color}40;border-left:4px solid {color};'
            f'border-radius:8px;padding:14px 20px;'
            f'display:flex;align-items:center;justify-content:space-between">'
            f'<div>'
            f'<div style="font-size:10px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:1.2px">{label}</div>'
            f'<div style="font-size:10px;color:#3d4466;margin-top:3px">{pct_sub}</div>'
            f'</div>'
            f'<div style="font-size:24px;font-weight:900;color:#fff">{val_str}</div>'
            f'</div>'
        )
    return '<div style="display:flex;flex-direction:column;gap:2px;padding:6px 0">' + "".join(items) + "</div>"

def _vg_html(cards: list) -> str:
    """Renderiza cards de visão geral (ROAS, investimento)."""
    items = []
    for c in cards:
        col = _COL.get(c.get("color","white"), c.get("color","#e0e4f0"))
        items.append(
            f'<div class="vg-card">'
            f'<div class="vg-label">{c["label"]}</div>'
            f'<div class="vg-value" style="color:{col}">{c["value"]}</div>'
            f'</div>'
        )
    return '<div class="vg-grid">' + "".join(items) + "</div>"

st.title("📊 Dashboard de Campanhas")

if not CLIENTS:
    st.warning("Nenhum cliente configurado. Abra o Claude Code nesta pasta e use `/setup-meta-dashboard` para adicionar o primeiro cliente.")
    st.stop()

# ── sidebar — seleção de cliente ───────────────────────────────────────────────

with st.sidebar:
    st.header("Configurações")
    if _is_admin:
        _keys = list(CLIENTS.keys())
        _default_idx = _keys.index(DEFAULT_CLIENT) if DEFAULT_CLIENT in _keys else 0
        client_name = st.selectbox("Cliente", _keys, index=_default_idx)
    else:
        client_name = _forced_client
        st.markdown(f"**{client_name}**")
    if st.button("Sair", use_container_width=True):
        st.session_state.auth_client = None
        st.session_state.auth_admin  = False
        st.rerun()
    if st.button("🔄 Atualizar Dados", use_container_width=True, help="Limpa o cache e rebusca todos os dados"):
        st.cache_data.clear()
        st.rerun()

client_cfg = CLIENTS[client_name]
account_id = client_cfg["account_id"]
spreadsheet_id = client_cfg.get("spreadsheet_id")
agendamentos_id = client_cfg.get("agendamentos_id")

# ── filtros de data ────────────────────────────────────────────────────────────

from datetime import timedelta as _td
today     = date.today()
first_day = today.replace(day=1)
_pmL = first_day - _td(days=1)          # último dia do mês passado
_pmF = _pmL.replace(day=1)              # primeiro dia do mês passado
_wsM = today - _td(days=today.weekday())# segunda-feira desta semana
_lwS = _wsM - _td(days=7)              # início semana passada
_lwE = _wsM - _td(days=1)              # fim semana passada

_PERIODOS = {
    "Hoje":             (today,               today),
    "Ontem":            (today - _td(days=1), today - _td(days=1)),
    "Esta semana":      (_wsM,                today),
    "Semana passada":   (_lwS,                _lwE),
    "Este mês":         (first_day,           today),
    "Mês passado":      (_pmF,                _pmL),
    "Últimos 7 dias":   (today - _td(days=7), today - _td(days=1)),
    "Últimos 14 dias":  (today - _td(days=14),today - _td(days=1)),
    "Últimos 30 dias":  (today - _td(days=30),today - _td(days=1)),
    "Personalizado":    None,
}

_col_per, _col_de, _col_ate = st.columns([3, 2, 2])

with _col_per:
    _periodo = st.selectbox(
        "Período", list(_PERIODOS.keys()), index=4,
        key="periodo_sel", label_visibility="collapsed"
    )

if _PERIODOS[_periodo] is not None:
    date_start, date_end = _PERIODOS[_periodo]
    with _col_de:
        st.markdown(
            f'<div style="padding:6px 12px;background:#0f1120;border:1px solid #1e2235;'
            f'border-radius:8px;font-size:13px;color:#8b92b8;margin-top:2px">'
            f'📅 {date_start.strftime("%d/%m/%Y")}</div>',
            unsafe_allow_html=True)
    with _col_ate:
        st.markdown(
            f'<div style="padding:6px 12px;background:#0f1120;border:1px solid #1e2235;'
            f'border-radius:8px;font-size:13px;color:#8b92b8;margin-top:2px">'
            f'📅 {date_end.strftime("%d/%m/%Y")}</div>',
            unsafe_allow_html=True)
else:
    with _col_de:
        date_start = st.date_input("De", value=first_day, max_value=today,
                                   label_visibility="collapsed")
    with _col_ate:
        date_end = st.date_input("Até", value=today, max_value=today,
                                 label_visibility="collapsed")

if date_start > date_end:
    st.error("A data inicial deve ser anterior à data final.")
    st.stop()

# ── carrega dados ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_monthly_history(account_id: str, n_months: int = 6) -> pd.DataFrame:
    """Agrega métricas dos últimos N meses completos + mês atual parcial."""
    import calendar as _cal
    today_ = date.today()
    records = []
    for i in range(n_months - 1, -1, -1):
        yr, mo = today_.year, today_.month - i
        while mo <= 0:
            mo += 12
            yr -= 1
        first = date(yr, mo, 1)
        last  = today_ if i == 0 else date(yr, mo, _cal.monthrange(yr, mo)[1])
        df_h  = fetch_campaign_insights(str(first), str(last), account_id)
        if df_h.empty:
            continue
        df_m = df_h[df_h["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)]
        spend    = df_h["spend"].sum()
        contacts = int(df_m["messaging_contacts"].sum()) if not df_m.empty and "messaging_contacts" in df_m.columns else 0
        imps     = int(df_h["impressions"].sum())
        clicks   = int(df_h["inline_link_clicks"].sum()) if "inline_link_clicks" in df_h.columns else 0
        records.append({
            "mes":       first.strftime("%b/%y").capitalize(),
            "mes_dt":    first,
            "investido": spend,
            "contatos":  contacts,
            "impressoes": imps,
            "cpl":       spend * TAX_MULTIPLIER / contacts if contacts > 0 else None,
            "cpm":       spend / imps * 1000 if imps > 0 else None,
            "ctr":       clicks / imps * 100 if imps > 0 else None,
            "parcial":   i == 0,
        })
    return pd.DataFrame(records)


@st.cache_data(ttl=7200, show_spinner=False)
def fetch_agendamentos(spreadsheet_id: str, date_start: str, date_end: str) -> pd.DataFrame:
    """Lê planilha de agendamentos filtrando pelo período selecionado."""
    _empty_cols = ["data","consultas","valor_consulta","total_consultas","cirurgias","valor_cirurgia","total_cirurgias"]
    try:
        rows = _read_sheets_range(spreadsheet_id, "'Planilha agendamento'!A2:G400")
    except Exception as e:
        # Erro de API — não cacheia, lança para o caller decidir o que exibir
        raise RuntimeError(f"Erro ao ler agendamentos: {e}") from e
    if not rows:
        return pd.DataFrame(columns=_empty_cols)

    records = []
    for row in rows:
        if not row or not row[0]:
            continue
        def parse_brl(val):
            if not val or val in ("", None):
                return 0.0
            try:
                return float(str(val).replace("R$","").replace(".","").replace(",",".").strip() or 0)
            except (ValueError, TypeError):
                return 0.0
        def parse_num(val):
            if not val or val in ("", None):
                return 0
            try:
                return int(float(str(val).replace(",",".")))
            except (ValueError, TypeError):
                return 0
        records.append({
            "data":           row[0] if len(row) > 0 else "",
            "consultas":      parse_num(row[1]) if len(row) > 1 else 0,
            "valor_consulta": parse_brl(row[2]) if len(row) > 2 else 0.0,
            "total_consultas":parse_brl(row[3]) if len(row) > 3 else 0.0,
            "cirurgias":      parse_num(row[4]) if len(row) > 4 else 0,
            "valor_cirurgia": parse_brl(row[5]) if len(row) > 5 else 0.0,
            "total_cirurgias":parse_brl(row[6]) if len(row) > 6 else 0.0,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Filtra pelo período selecionado (formato dd/mm na planilha)
    ds = pd.to_datetime(date_start)
    de = pd.to_datetime(date_end)
    current_year = ds.year
    df["dt"] = pd.to_datetime(df["data"] + f"/{current_year}", format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["dt"])
    df = df[(df["dt"] >= ds) & (df["dt"] <= de)]
    return df

with st.spinner("Buscando dados..."):
    df = fetch_campaign_insights(str(date_start), str(date_end), account_id)
    if spreadsheet_id:
        try:
            df_sheets = fetch_sheets_seguidores(spreadsheet_id, date_start.month)
        except RuntimeError as _e:
            st.warning(f"⚠️ {_e} — clique em **Atualizar Dados** na barra lateral para tentar novamente.")
            df_sheets = pd.DataFrame(columns=["dia", "investido_seg", "seguidores"])
    else:
        df_sheets = pd.DataFrame(columns=["dia", "investido_seg", "seguidores"])
    try:
        df_agend = fetch_agendamentos(agendamentos_id, str(date_start), str(date_end)) if agendamentos_id else pd.DataFrame()
    except RuntimeError as _e:
        st.warning(f"⚠️ {_e} — clique em **Atualizar Dados** na barra lateral para tentar novamente.")
        df_agend = pd.DataFrame()

st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')} · Cache renova a cada 2h")

if df.empty:
    st.warning("Nenhum dado encontrado para o período selecionado.")
    st.stop()

# ── filtra por tipo de campanha ────────────────────────────────────────────────

df_seg  = df[df["campaign_name"].str.contains(FOLLOWER_KEYWORD,  case=False, na=False)].copy()
df_msg  = df[df["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)].copy()
df_lead = df[df["campaign_name"].str.contains(r"\bLEAD\b",       case=False, na=False, regex=True)].copy()

# Para clientes com keywords customizados, sobrescreve df_msg e df_lead com filtros exclusivos
if client_cfg.get("tipo") == "mensagens_lead":
    _msg_kws  = client_cfg.get("msg_keywords",  [MESSAGING_KEYWORD])
    _lead_kws = client_cfg.get("lead_keywords", ["LEAD"])
    _msg_pat  = "|".join(_msg_kws)
    _lead_pat = "|".join(_lead_kws)
    # df_msg: contém qualquer msg_keyword MAS não contém lead_keyword (evita overlap)
    df_msg  = df[
        df["campaign_name"].str.contains(_msg_pat,  case=False, na=False) &
       ~df["campaign_name"].str.contains(_lead_pat, case=False, na=False)
    ].copy()
    # df_lead: contém lead_keyword (exclusivo)
    df_lead = df[df["campaign_name"].str.contains(_lead_pat, case=False, na=False)].copy()


TAX_MULTIPLIER = 1.1385

_tipo_cliente = client_cfg.get("tipo", "clinica_geral")

if _tipo_cliente == "mensagens":
    tab1, tab5 = st.tabs(["💬 Mensagens · E2-CAP", "📈 Evolução"])
    tab2 = tab3 = tab4 = tab_lead = tab_metas = tab_funil = None
elif _tipo_cliente == "mensagens_lead":
    _has_metas = bool(client_cfg.get("metas_cursos"))
    if client_cfg.get("leads_first", False):
        if _has_metas:
            tab_lead, tab1, tab_funil, tab_metas, tab5 = st.tabs(["📋 Formulários · LEAD", "💬 Mensagens · ENGJ", "📊 Funil Completo", "🎯 Metas", "📈 Evolução"])
        else:
            tab_lead, tab1, tab_funil, tab5 = st.tabs(["📋 Formulários · LEAD", "💬 Mensagens · ENGJ", "📊 Funil Completo", "📈 Evolução"])
            tab_metas = None
    else:
        if _has_metas:
            tab1, tab_lead, tab_funil, tab_metas, tab5 = st.tabs(["💬 Mensagens · E2-CAP", "📋 Formulários · LEAD", "📊 Funil Completo", "🎯 Metas", "📈 Evolução"])
        else:
            tab1, tab_lead, tab_funil, tab5 = st.tabs(["💬 Mensagens · E2-CAP", "📋 Formulários · LEAD", "📊 Funil Completo", "📈 Evolução"])
            tab_metas = None
    tab2 = tab3 = tab4 = None
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["💬 Mensagens · E2-CAP", "👥 Seguidores · E1-DIST", "📊 Funil Completo", "🎯 Metas", "📈 Evolução"])
    tab_lead = None
    tab_metas = None
    tab_funil = None

# ══ TAB 1 — MENSAGENS ═════════════════════════════════════════════════════════

with tab1:
    if df_msg.empty:
        st.info("Nenhuma campanha com E2-CAP encontrada no período.")
    else:
        total_spend_m = df_msg["spend"].sum()
        total_impressions_m = df_msg["impressions"].sum()
        total_clicks_m = df_msg["clicks"].sum()
        total_contacts = df_msg["messaging_contacts"].sum()

        total_investido_impostos_m = total_spend_m * TAX_MULTIPLIER
        avg_cpm_m = (total_spend_m / total_impressions_m * 1000) if total_impressions_m > 0 else 0
        avg_ctr_m = (total_clicks_m / total_impressions_m * 100) if total_impressions_m > 0 else 0
        custo_contato = (total_spend_m * TAX_MULTIPLIER / total_contacts) if total_contacts > 0 else None
        custo_contato_sem_imp = (total_spend_m / total_contacts) if total_contacts > 0 else None

        total_link_clicks_m = df_msg["inline_link_clicks"].sum() if "inline_link_clicks" in df_msg.columns else total_clicks_m
        avg_cpc_m = (total_spend_m / total_link_clicks_m) if total_link_clicks_m > 0 else None

        st.markdown(_kpi_html([
            {"label": "Investido (sem imp.)", "value": fmt_brl(total_spend_m), "color": "cyan"},
            {"label": "CPL (sem imp.)",       "value": fmt_brl(custo_contato_sem_imp) if custo_contato_sem_imp else "—", "color": "yellow"},
        ], cols=2), unsafe_allow_html=True)

        st.markdown(_kpi_html([
            {"label": "Investimento c/ Impostos", "value": fmt_brl(total_investido_impostos_m),
             "color": "cyan"},
            {"label": "Novos Contatos",            "value": fmt_num(total_contacts) if total_contacts > 0 else "—",
             "color": "green"},
            {"label": "CPL Real",                  "value": fmt_brl(custo_contato) if custo_contato else "—",
             "color": "yellow"},
            {"label": "CPM",  "value": fmt_brl(avg_cpm_m),  "color": "white"},
            {"label": "CTR",  "value": fmt_pct(avg_ctr_m),  "color": "white"},
            {"label": "CPC",  "value": fmt_brl(avg_cpc_m) if avg_cpc_m else "—", "color": "white"},
        ], cols=6), unsafe_allow_html=True)

        st.divider()

        # Dados diários
        daily_msg = (
            df_msg.groupby("date_start")
            .agg(
                spend=("spend", "sum"),
                impressions=("impressions", "sum"),
                clicks=("clicks", "sum"),
                Contatos=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        daily_msg["Custo/Contato"] = daily_msg.apply(
            lambda r: r["spend"] * TAX_MULTIPLIER / r["Contatos"] if r["Contatos"] > 0 else None, axis=1
        )

        # Funil SVG customizado (removido da tab1 — mantido só no Funil Completo)

        # (build_funnel_svg movida para módulo — não usada aqui)

        # Gráficos
        _n_bars = len(daily_msg)
        _bar_colors = [
            f"rgb({int(0 + 0*i/max(_n_bars-1,1))},{int(212 - 2*i/max(_n_bars-1,1))},{int(255 - (255-118)*i/max(_n_bars-1,1))})"
            for i in range(_n_bars)
        ]  # gradiente cyan → verde barra a barra

        fig_contatos = go.Figure(data=[go.Bar(
            x=daily_msg["date_start"],
            y=daily_msg["Contatos"],
            marker=dict(color=_bar_colors, line=dict(width=0)),
            hovertemplate="%{x|%d/%m}<br>%{y} contatos<extra></extra>",
        )])
        fig_contatos.update_layout(
            showlegend=False, xaxis_title="", yaxis_title="",
            bargap=0.25, **_PD
        )
        fig_contatos.update_xaxes(tickformat="%d/%m", nticks=10)

        _cpl_data = daily_msg.dropna(subset=["Custo/Contato"])
        fig_custo = go.Figure(data=[go.Scatter(
            x=_cpl_data["date_start"],
            y=_cpl_data["Custo/Contato"],
            mode="lines",
            line=dict(color="#ffd600", width=2),
            fill="tozeroy",
            fillcolor="rgba(255,214,0,0.06)",
            hovertemplate="%{x|%d/%m}<br>R$ %{y:.2f}<extra></extra>",
        )])
        fig_custo.update_layout(xaxis_title="", yaxis_title="", **_PD)
        fig_custo.update_xaxes(tickformat="%d/%m", nticks=10)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown('<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">Novos Contatos por Dia</p>'
                        '<p style="font-size:11px;color:#3d4466;margin:0 0 4px">Mensagens iniciadas no período</p>',
                        unsafe_allow_html=True)
            st.plotly_chart(fig_contatos, use_container_width=True)
        with col_g2:
            st.markdown('<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">CPL por Dia (R$)</p>'
                        '<p style="font-size:11px;color:#3d4466;margin:0 0 4px">Custo por contato com imposto</p>',
                        unsafe_allow_html=True)
            st.plotly_chart(fig_custo, use_container_width=True)

        # Tabela por campanha
        st.markdown('<div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:16px 0 8px">Por Campanha</div>', unsafe_allow_html=True)
        camp_msg = (
            df_msg.groupby("campaign_name")
            .agg(
                Investido=("spend", "sum"),
                Impressões=("impressions", "sum"),
                Cliques=("clicks", "sum"),
                LinkCliques=("inline_link_clicks", "sum"),
                Contatos=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        camp_msg["CPM"]           = camp_msg["Investido"] / camp_msg["Impressões"] * 1000
        camp_msg["CTR"]           = camp_msg["Cliques"] / camp_msg["Impressões"] * 100
        camp_msg["CPC"]           = camp_msg.apply(lambda r: r["Investido"] / r["LinkCliques"] if r["LinkCliques"] > 0 else None, axis=1)
        camp_msg["Custo/Contato"] = camp_msg.apply(lambda r: r["Investido"] / r["Contatos"] if r["Contatos"] > 0 else None, axis=1)
        camp_msg = camp_msg.rename(columns={"campaign_name": "Campanha"})
        # Formata e reordena colunas
        camp_out = camp_msg[["Campanha"]].copy()
        camp_out["Investido"]      = camp_msg["Investido"].apply(fmt_brl)
        camp_out["Contatos"]       = camp_msg["Contatos"].apply(fmt_num)
        camp_out["Custo/Contato"]  = camp_msg["Custo/Contato"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        camp_out["Impressões"]     = camp_msg["Impressões"].apply(fmt_num)
        camp_out["CPM"]            = camp_msg["CPM"].apply(fmt_brl)
        camp_out["CTR"]            = camp_msg["CTR"].apply(fmt_pct)
        camp_out["CPC"]            = camp_msg["CPC"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        st.markdown(_tabela_campanha_html(camp_out.set_index("Campanha")), unsafe_allow_html=True)

        # ── Tabela por dia ────────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:20px 0 2px">Por Dia</div>
        <div style="font-size:11px;color:#3d4466;margin-bottom:10px">Detalhamento diário</div>
        """, unsafe_allow_html=True)

        daily_tab = (
            df_msg.groupby("date_start")
            .agg(
                spend=("spend", "sum"),
                impressions=("impressions", "sum"),
                link_clicks=("inline_link_clicks", "sum"),
                leads=("messaging_contacts", "sum"),
            )
            .reset_index()
        )
        daily_tab["invest_imp"] = daily_tab["spend"] * TAX_MULTIPLIER
        daily_tab["CPM"]        = daily_tab.apply(lambda r: r["spend"] / r["impressions"] * 1000 if r["impressions"] > 0 else None, axis=1)
        daily_tab["CPC"]        = daily_tab.apply(lambda r: r["spend"] / r["link_clicks"] if r["link_clicks"] > 0 else None, axis=1)
        daily_tab["CTR"]        = daily_tab.apply(lambda r: r["link_clicks"] / r["impressions"] * 100 if r["impressions"] > 0 else None, axis=1)
        daily_tab["CPL"]        = daily_tab.apply(lambda r: r["invest_imp"] / r["leads"] if r["leads"] > 0 else None, axis=1)
        daily_tab["Tx Passagem"]= daily_tab.apply(lambda r: r["leads"] / r["link_clicks"] * 100 if r["link_clicks"] > 0 else None, axis=1)

        # Cruza com agendamentos por dia
        if not df_agend.empty and "dt" in df_agend.columns:
            agend_day = (
                df_agend.groupby("dt")
                .agg(consultas=("consultas","sum"), cirurgias=("cirurgias","sum"),
                     fat_consultas=("total_consultas","sum"), fat_cirurgias=("total_cirurgias","sum"))
                .reset_index()
            )
            agend_day = agend_day.rename(columns={"dt": "date_start"})
            daily_tab = daily_tab.merge(agend_day, on="date_start", how="left")
        else:
            daily_tab["consultas"]     = None
            daily_tab["cirurgias"]     = None
            daily_tab["fat_consultas"] = None
            daily_tab["fat_cirurgias"] = None

        daily_tab["custo_consulta"] = daily_tab.apply(
            lambda r: r["invest_imp"] / r["consultas"] if pd.notna(r.get("consultas")) and r.get("consultas", 0) > 0 else None, axis=1)
        daily_tab["custo_cirurgia"] = daily_tab.apply(
            lambda r: r["invest_imp"] / r["cirurgias"] if pd.notna(r.get("cirurgias")) and r.get("cirurgias", 0) > 0 else None, axis=1)

        # Monta tabela formatada
        tipo_cli = client_cfg.get("tipo", "clinica_geral")
        dt_out = pd.DataFrame()
        dt_out["Dia"]                  = daily_tab["date_start"].dt.strftime("%d/%m/%Y")
        dt_out["Invest. c/ Imposto"]   = daily_tab["invest_imp"].apply(fmt_brl)
        dt_out["CPM"]                  = daily_tab["CPM"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        dt_out["CPC"]                  = daily_tab["CPC"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        dt_out["CTR"]                  = daily_tab["CTR"].apply(lambda v: fmt_pct(v) if v is not None else "—")
        dt_out["Tx Passagem"]          = daily_tab["Tx Passagem"].apply(lambda v: fmt_pct(v) if v is not None else "—")
        dt_out["Leads"]                = daily_tab["leads"].apply(fmt_num)
        dt_out["CPL"]                  = daily_tab["CPL"].apply(lambda v: fmt_brl(v) if v is not None else "—")
        dt_out["Consultas"]            = daily_tab["consultas"].apply(lambda v: fmt_num(v) if pd.notna(v) else "—")
        dt_out["Custo por Consulta"]   = daily_tab["custo_consulta"].apply(lambda v: fmt_brl(v) if pd.notna(v) else "—")
        if tipo_cli == "clinica_geral":
            dt_out["Cirurgias Confirmadas"] = daily_tab["cirurgias"].apply(lambda v: fmt_num(v) if pd.notna(v) else "—")
            dt_out["Custo por Cirurgia"]    = daily_tab["custo_cirurgia"].apply(lambda v: fmt_brl(v) if pd.notna(v) else "—")

        st.markdown(_tabela_html(dt_out, tipo_cli), unsafe_allow_html=True)

# ══ TAB LEAD — FORMULÁRIOS ════════════════════════════════════════════════════

if tab_lead is not None:
    with tab_lead:
        if df_lead.empty:
            st.info("Nenhuma campanha com LEAD encontrada no período.")
        else:
            total_spend_lead = df_lead["spend"].sum()
            total_imp_lead   = df_lead["impressions"].sum()
            total_clk_lead   = df_lead["clicks"].sum()
            total_inv_imp_lead = total_spend_lead * TAX_MULTIPLIER
            avg_cpm_lead = (total_spend_lead / total_imp_lead * 1000) if total_imp_lead > 0 else 0
            avg_ctr_lead = (total_clk_lead / total_imp_lead * 100) if total_imp_lead > 0 else 0
            total_lc_lead = df_lead["inline_link_clicks"].sum() if "inline_link_clicks" in df_lead.columns else total_clk_lead
            avg_cpc_lead = (total_spend_lead / total_lc_lead) if total_lc_lead > 0 else None

            # Extrai leads das actions
            df_lead["lead_count"] = df_lead["actions"].apply(
                lambda x: extract_action(x, "onsite_conversion.lead_grouped")
                       or extract_action(x, "offsite_conversion.fb_pixel_lead")
                       or extract_action(x, "lead")
            )
            total_leads = int(df_lead["lead_count"].sum())
            cpl_lead_sem_imp = (total_spend_lead / total_leads) if total_leads > 0 else None
            cpl_lead_imp     = (total_inv_imp_lead / total_leads) if total_leads > 0 else None

            # Cards sem imposto (acima)
            st.markdown(_kpi_html([
                {"label": "Investido (sem imp.)", "value": fmt_brl(total_spend_lead),  "color": "cyan"},
                {"label": "CPL (sem imp.)",       "value": fmt_brl(cpl_lead_sem_imp) if cpl_lead_sem_imp else "—", "color": "yellow"},
            ], cols=2), unsafe_allow_html=True)

            # Cards com imposto (abaixo)
            st.markdown(_kpi_html([
                {"label": "Investimento c/ Impostos", "value": fmt_brl(total_inv_imp_lead), "color": "cyan"},
                {"label": "Total de Leads",           "value": fmt_num(total_leads) if total_leads > 0 else "—", "color": "green"},
                {"label": "CPL Real",                 "value": fmt_brl(cpl_lead_imp) if cpl_lead_imp else "—", "color": "yellow"},
                {"label": "CPM",  "value": fmt_brl(avg_cpm_lead), "color": "white"},
                {"label": "CTR",  "value": fmt_pct(avg_ctr_lead), "color": "white"},
                {"label": "CPC",  "value": fmt_brl(avg_cpc_lead) if avg_cpc_lead else "—", "color": "white"},
            ], cols=6), unsafe_allow_html=True)

            st.divider()

            # Dados diários
            daily_lead = (
                df_lead.groupby("date_start")
                .agg(
                    spend=("spend", "sum"),
                    impressions=("impressions", "sum"),
                    clicks=("clicks", "sum"),
                    Leads=("lead_count", "sum"),
                )
                .reset_index()
            )
            daily_lead["CPL"] = daily_lead.apply(
                lambda r: r["spend"] * TAX_MULTIPLIER / r["Leads"] if r["Leads"] > 0 else None, axis=1
            )

            _n_lead = len(daily_lead)
            _lead_colors = [
                f"rgb({int(138 + (255-138)*i/max(_n_lead-1,1))},{int(43 + (100-43)*i/max(_n_lead-1,1))},{int(226 - (226-100)*i/max(_n_lead-1,1))})"
                for i in range(_n_lead)
            ]  # gradiente roxo → laranja

            fig_leads = go.Figure(data=[go.Bar(
                x=daily_lead["date_start"],
                y=daily_lead["Leads"],
                marker=dict(color=_lead_colors, line=dict(width=0)),
                hovertemplate="%{x|%d/%m}<br>%{y} leads<extra></extra>",
            )])
            fig_leads.update_layout(showlegend=False, xaxis_title="", yaxis_title="", bargap=0.25, **_PD)
            fig_leads.update_xaxes(tickformat="%d/%m", nticks=10)

            _cpl_lead_data = daily_lead.dropna(subset=["CPL"])
            fig_cpl_lead = go.Figure(data=[go.Scatter(
                x=_cpl_lead_data["date_start"],
                y=_cpl_lead_data["CPL"],
                mode="lines",
                line=dict(color="#ffd600", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,214,0,0.06)",
                hovertemplate="%{x|%d/%m}<br>R$ %{y:.2f}<extra></extra>",
            )])
            fig_cpl_lead.update_layout(xaxis_title="", yaxis_title="", **_PD)
            fig_cpl_lead.update_xaxes(tickformat="%d/%m", nticks=10)

            col_gl1, col_gl2 = st.columns(2)
            with col_gl1:
                st.markdown('<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">Leads por Dia</p>'
                            '<p style="font-size:11px;color:#3d4466;margin:0 0 4px">Formulários preenchidos no período</p>',
                            unsafe_allow_html=True)
                st.plotly_chart(fig_leads, use_container_width=True)
            with col_gl2:
                st.markdown('<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">CPL por Dia (R$)</p>'
                            '<p style="font-size:11px;color:#3d4466;margin:0 0 4px">Custo por lead com imposto</p>',
                            unsafe_allow_html=True)
                st.plotly_chart(fig_cpl_lead, use_container_width=True)

            # Tabela por campanha
            st.markdown('<div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:16px 0 8px">Por Campanha</div>', unsafe_allow_html=True)
            camp_lead = (
                df_lead.groupby("campaign_name")
                .agg(
                    Investido=("spend", "sum"),
                    Impressões=("impressions", "sum"),
                    Cliques=("clicks", "sum"),
                    LinkCliques=("inline_link_clicks", "sum"),
                    Leads=("lead_count", "sum"),
                )
                .reset_index()
            )
            camp_lead["CPM"] = camp_lead["Investido"] / camp_lead["Impressões"] * 1000
            camp_lead["CTR"] = camp_lead["Cliques"] / camp_lead["Impressões"] * 100
            camp_lead["CPC"] = camp_lead.apply(lambda r: r["Investido"] / r["LinkCliques"] if r["LinkCliques"] > 0 else None, axis=1)
            camp_lead["CPL"] = camp_lead.apply(lambda r: r["Investido"] / r["Leads"] if r["Leads"] > 0 else None, axis=1)
            camp_lead = camp_lead.rename(columns={"campaign_name": "Campanha"})
            camp_out_l = camp_lead[["Campanha"]].copy()
            camp_out_l["Investido"] = camp_lead["Investido"].apply(fmt_brl)
            camp_out_l["Leads"]     = camp_lead["Leads"].apply(fmt_num)
            camp_out_l["CPL"]       = camp_lead["CPL"].apply(lambda v: fmt_brl(v) if v is not None else "—")
            camp_out_l["Impressões"]= camp_lead["Impressões"].apply(fmt_num)
            camp_out_l["CPM"]       = camp_lead["CPM"].apply(fmt_brl)
            camp_out_l["CTR"]       = camp_lead["CTR"].apply(fmt_pct)
            camp_out_l["CPC"]       = camp_lead["CPC"].apply(lambda v: fmt_brl(v) if v is not None else "—")
            st.markdown(_tabela_campanha_html(camp_out_l.set_index("Campanha")), unsafe_allow_html=True)

            # Tabela por dia
            st.markdown('<div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:24px 0 8px">Por Dia</div>', unsafe_allow_html=True)
            dl_imp = daily_lead["impressions"] if "impressions" in daily_lead.columns else pd.Series(0, index=daily_lead.index)
            dl_clk = daily_lead["clicks"] if "clicks" in daily_lead.columns else pd.Series(0, index=daily_lead.index)
            dl_out = pd.DataFrame()
            dl_out["Dia"]              = daily_lead["date_start"].apply(lambda d: d.strftime("%d/%m") if hasattr(d, "strftime") else str(d))
            dl_out["Invest. c/ Imp."]  = daily_lead["spend"].apply(lambda v: fmt_brl(v * TAX_MULTIPLIER))
            dl_out["CPM"]              = (daily_lead["spend"] / dl_imp.replace(0, float("nan")) * 1000).apply(lambda v: fmt_brl(v) if pd.notna(v) else "—")
            dl_out["CTR"]              = (dl_clk / dl_imp.replace(0, float("nan")) * 100).apply(lambda v: fmt_pct(v) if pd.notna(v) else "—")
            dl_out["Leads"]            = daily_lead["Leads"].apply(fmt_num)
            dl_out["CPL"]              = daily_lead["CPL"].apply(lambda v: fmt_brl(v) if v is not None else "—")
            st.markdown(_tabela_campanha_html(dl_out.set_index("Dia"), first_col="DIA"), unsafe_allow_html=True)

# ══ TAB FUNIL — FUNIL COMPLETO (mensagens_lead) ══════════════════════════════

if tab_funil is not None:
    with tab_funil:
        df_fl = df_lead.copy()
        df_fl["lead_count"] = df_fl["actions"].apply(
            lambda x: extract_action(x, "onsite_conversion.lead_grouped")
                   or extract_action(x, "offsite_conversion.fb_pixel_lead")
                   or extract_action(x, "lead")
        )
        invest_liq_fl   = df_fl["spend"].sum()
        invest_imp_fl   = invest_liq_fl * TAX_MULTIPLIER
        total_imp_fl    = int(df_fl["impressions"].sum()) if "impressions" in df_fl.columns else 0
        total_clk_fl    = int(df_fl["inline_link_clicks"].sum()) if "inline_link_clicks" in df_fl.columns else int(df_fl["clicks"].sum()) if "clicks" in df_fl.columns else 0
        total_leads_fl  = int(df_fl["lead_count"].sum())
        total_alunos_fl = client_cfg.get("total_alunos", 0)

        cpm_fl   = invest_liq_fl / total_imp_fl * 1000 if total_imp_fl > 0 else 0
        ctr_fl   = total_clk_fl / total_imp_fl * 100    if total_imp_fl > 0 else 0
        cpc_fl   = invest_liq_fl / total_clk_fl          if total_clk_fl > 0 else 0
        cpl_fl   = invest_imp_fl / total_leads_fl         if total_leads_fl > 0 else 0
        tx_lead  = total_leads_fl / total_clk_fl * 100   if total_clk_fl > 0 else 0
        custo_al = invest_imp_fl / total_alunos_fl        if total_alunos_fl > 0 else None

        st.subheader("Visão Geral")
        st.markdown(_kpi_html([
            {"label": "Investimento Líquido",    "value": fmt_brl(invest_liq_fl), "color": "cyan"},
            {"label": "Investimento + Impostos", "value": fmt_brl(invest_imp_fl), "color": "cyan"},
            {"label": "CPL Real",                "value": fmt_brl(cpl_fl) if cpl_fl else "—", "color": "yellow"},
            {"label": "Custo/Aluno",             "value": fmt_brl(custo_al) if custo_al else "—", "color": "green"},
        ]), unsafe_allow_html=True)

        st.divider()

        col_funil_fl, col_metricas_fl = st.columns([1, 1])

        with col_funil_fl:
            st.markdown('<div style="font-size:13px;font-weight:700;color:#c8cce8;margin-bottom:4px">Funil de Captação</div>', unsafe_allow_html=True)
            st.markdown(build_funnel_html(
                ["Impressões", "Cliques", "Leads", "Alunos"],
                [total_imp_fl, total_clk_fl, total_leads_fl, total_alunos_fl],
                ["#00d4ff", "#7B6CF6", "#00e676", "#ffd600"],
                [100.0, ctr_fl, tx_lead, (total_alunos_fl / total_leads_fl * 100 if total_leads_fl > 0 else None)],
            ), unsafe_allow_html=True)

        with col_metricas_fl:
            st.markdown(
                '<div style="font-size:12px;font-weight:700;color:#3d4466;'
                'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                'Métricas de Performance</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_kpi_html([
                {"label": "CPM",          "value": fmt_brl(cpm_fl),                        "color": "cyan",   "sub": "Custo/mil impressões"},
                {"label": "CTR",          "value": fmt_pct(ctr_fl),                        "color": "green",  "sub": "Taxa de cliques"},
                {"label": "CPC",          "value": fmt_brl(cpc_fl) if cpc_fl else "—",    "color": "white",  "sub": "Custo por clique"},
                {"label": "CPL Real",     "value": fmt_brl(cpl_fl) if cpl_fl else "—",    "color": "yellow", "sub": f"▲ {total_leads_fl} leads"},
                {"label": "TX. Lead",     "value": fmt_pct(tx_lead),                       "color": "green",  "sub": "Leads por clique"},
                {"label": "Alunos",       "value": fmt_num(total_alunos_fl),               "color": "yellow", "sub": "Confirmados (Kommo em breve)"},
            ], cols=2), unsafe_allow_html=True)

# ══ TAB METAS — METAS POR CURSO ══════════════════════════════════════════════

if tab_metas is not None:
    with tab_metas:
        metas_cursos = client_cfg.get("metas_cursos", {})

        df_lead_m = df_lead.copy()
        df_lead_m["lead_count"] = df_lead_m["actions"].apply(
            lambda x: extract_action(x, "onsite_conversion.lead_grouped")
                   or extract_action(x, "offsite_conversion.fb_pixel_lead")
                   or extract_action(x, "lead")
        )
        df_lead_m["curso"] = df_lead_m["campaign_name"].apply(
            lambda n: n.split("|")[-1].strip() if "|" in n else n.strip()
        )
        leads_por_curso = (
            df_lead_m.groupby("curso")
            .agg(leads=("lead_count", "sum"), spend=("spend", "sum"))
            .reset_index()
        )

        st.markdown('<div style="font-size:13px;color:#3d4466;margin-bottom:20px">Leads captados vs meta de alunos · Período selecionado</div>', unsafe_allow_html=True)

        for curso, meta in metas_cursos.items():
            row = leads_por_curso[leads_por_curso["curso"].str.lower() == curso.lower()]
            leads = int(row["leads"].sum()) if not row.empty else 0
            spend = float(row["spend"].sum()) if not row.empty else 0.0
            pct   = min(leads / meta * 100, 100) if meta > 0 else 0
            cpl   = spend * TAX_MULTIPLIER / leads if leads > 0 else None
            faltam = max(meta - leads, 0)

            bar_color = "#00e676" if pct >= 80 else ("#ffd600" if pct >= 50 else "#00d4ff")
            badge_cls = "up" if pct >= 80 else ("warn" if pct >= 50 else "ok")

            cpl_html = (
                f'<div><div class="kpi-label">CPL</div>'
                f'<div style="font-size:22px;font-weight:900;color:#a78bfa">{fmt_brl(cpl)}</div></div>'
            ) if cpl else ""

            st.markdown(
                f'<div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:22px 24px;margin-bottom:14px">'
                f'  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">'
                f'    <div style="font-size:17px;font-weight:800;color:#e0e4f0">{curso}</div>'
                f'    <span class="badge {badge_cls}">{pct:.0f}% da meta</span>'
                f'  </div>'
                f'  <div style="display:flex;gap:36px;margin-bottom:16px">'
                f'    <div><div class="kpi-label">Leads</div><div style="font-size:26px;font-weight:900;color:#00d4ff">{leads}</div></div>'
                f'    <div><div class="kpi-label">Meta</div><div style="font-size:26px;font-weight:900;color:#e0e4f0">{meta} alunos</div></div>'
                f'    <div><div class="kpi-label">Faltam</div><div style="font-size:26px;font-weight:900;color:#ffd600">{faltam}</div></div>'
                f'    {cpl_html}'
                f'  </div>'
                f'  <div style="background:#161829;border-radius:4px;height:7px;overflow:hidden">'
                f'    <div style="width:{pct:.1f}%;height:100%;background:{bar_color};border-radius:4px"></div>'
                f'  </div>'
                f'  <div style="display:flex;justify-content:space-between;margin-top:6px">'
                f'    <div style="font-size:10px;color:#3d4466">{leads} leads captados</div>'
                f'    <div style="font-size:10px;color:#3d4466">Meta: {meta} alunos</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True
            )

# ══ TAB 2 — SEGUIDORES ════════════════════════════════════════════════════════

if tab2 is not None:
 with tab2:
    if df_seg.empty:
        st.info("Nenhuma campanha com E1-DIST encontrada no período.")
    else:
        # Métricas da API Meta
        total_spend_api = df_seg["spend"].sum()
        total_impressions = df_seg["impressions"].sum()
        total_clicks = df_seg["clicks"].sum()
        total_investido_impostos = total_spend_api * TAX_MULTIPLIER
        avg_cpm = (total_spend_api / total_impressions * 1000) if total_impressions > 0 else 0
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

        # Métricas da planilha (seguidores e custo por seguidor)
        sheets_period = df_sheets[
            (df_sheets["dia"] >= date_start.day) & (df_sheets["dia"] <= date_end.day)
        ] if date_start.month == date_end.month else df_sheets
        total_investido_seg = sheets_period["investido_seg"].sum()
        total_follows = int(sheets_period["seguidores"].sum())
        custo_seg = (total_investido_seg * TAX_MULTIPLIER / total_follows) if total_follows > 0 else None
        custo_seg_sem_imp = (total_investido_seg / total_follows) if total_follows > 0 else None

        total_link_clicks = df_seg["inline_link_clicks"].sum() if "inline_link_clicks" in df_seg.columns else total_clicks
        avg_cpc = (total_spend_api / total_link_clicks) if total_link_clicks > 0 else None

        st.markdown(_kpi_html([
            {"label": "Investido (sem imp.)",     "value": fmt_brl(total_spend_api), "color": "cyan"},
            {"label": "Custo/Seguidor (sem imp.)", "value": fmt_brl(custo_seg_sem_imp) if custo_seg_sem_imp else "—", "color": "yellow"},
        ], cols=2), unsafe_allow_html=True)

        st.markdown(_kpi_html([
            {"label": "Investimento c/ Impostos", "value": fmt_brl(total_investido_impostos),
             "color": "cyan"},
            {"label": "Seguidores Ganhos", "value": fmt_num(total_follows) if total_follows > 0 else "—",
             "color": "green"},
            {"label": "Custo por Seguidor",       "value": fmt_brl(custo_seg) if custo_seg else "—",
             "color": "yellow"},
            {"label": "CPM", "value": fmt_brl(avg_cpm),  "color": "white"},
            {"label": "CTR", "value": fmt_pct(avg_ctr),  "color": "white"},
            {"label": "CPC", "value": fmt_brl(avg_cpc) if avg_cpc else "—", "color": "white"},
        ], cols=6), unsafe_allow_html=True)

        st.divider()

        # Gráfico diário — cruza API Meta com Sheets
        daily_seg = (
            df_seg.groupby("date_start")
            .agg(spend=("spend", "sum"), impressions=("impressions", "sum"), clicks=("clicks", "sum"))
            .reset_index()
        )
        daily_seg["dia"] = daily_seg["date_start"].dt.day
        daily_seg["CPM"] = daily_seg["spend"] / daily_seg["impressions"] * 1000
        daily_seg = daily_seg.merge(
            df_sheets[["dia", "seguidores"]].rename(columns={"seguidores": "Seguidores"}),
            on="dia", how="left"
        )
        daily_seg["Seguidores"] = daily_seg["Seguidores"].fillna(0)

        _n_seg = len(daily_seg)
        _seg_colors = [
            f"rgb({int(0 + 123*i/max(_n_seg-1,1))},{int(212 - 4*i/max(_n_seg-1,1))},{int(255 - 5*i/max(_n_seg-1,1))})"
            for i in range(_n_seg)
        ]  # gradiente cyan → ciano-azul

        fig1 = go.Figure(data=[go.Bar(
            x=daily_seg["date_start"],
            y=daily_seg["Seguidores"],
            marker=dict(color=_seg_colors, line=dict(width=0)),
            hovertemplate="%{x|%d/%m}<br>%{y} seguidores<extra></extra>",
        )])
        fig1.update_layout(showlegend=False, xaxis_title="", yaxis_title="", bargap=0.25, **_PD)
        fig1.update_xaxes(tickformat="%d/%m", nticks=10)

        fig2 = go.Figure(data=[go.Scatter(
            x=daily_seg["date_start"],
            y=daily_seg["CPM"],
            mode="lines",
            line=dict(color="#a78bfa", width=2),
            fill="tozeroy",
            fillcolor="rgba(167,139,250,0.06)",
            hovertemplate="%{x|%d/%m}<br>R$ %{y:.2f}<extra></extra>",
        )])
        fig2.update_layout(xaxis_title="", yaxis_title="", **_PD)
        fig2.update_xaxes(tickformat="%d/%m", nticks=10)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown('<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">Seguidores por Dia</p>'
                        '<p style="font-size:11px;color:#3d4466;margin:0 0 4px">Novos seguidores no período</p>',
                        unsafe_allow_html=True)
            st.plotly_chart(fig1, use_container_width=True)
        with col_g2:
            st.markdown('<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">CPM por Dia (R$)</p>'
                        '<p style="font-size:11px;color:#3d4466;margin:0 0 4px">Custo por mil impressões</p>',
                        unsafe_allow_html=True)
            st.plotly_chart(fig2, use_container_width=True)

        # Tabela por campanha
        st.markdown('<div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:16px 0 8px">Por Campanha</div>', unsafe_allow_html=True)
        camp_seg = (
            df_seg.groupby("campaign_name")
            .agg(Investido=("spend", "sum"), Impressões=("impressions", "sum"), Cliques=("clicks", "sum"))
            .reset_index()
        )
        camp_seg["CPM"] = camp_seg["Investido"] / camp_seg["Impressões"] * 1000
        camp_seg["CTR"] = camp_seg["Cliques"] / camp_seg["Impressões"] * 100
        camp_seg = camp_seg.rename(columns={"campaign_name": "Campanha"})
        camp_seg["Investido"] = camp_seg["Investido"].apply(fmt_brl)
        camp_seg["CPM"] = camp_seg["CPM"].apply(fmt_brl)
        camp_seg["CTR"] = camp_seg["CTR"].apply(fmt_pct)
        st.markdown(_tabela_campanha_html(camp_seg.set_index("Campanha")), unsafe_allow_html=True)

        # ── Por Dia — seguidores ───────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:18px;font-weight:800;color:#e0e4f0;margin:24px 0 2px">Por Dia</div>
        <div style="font-size:11px;color:#3d4466;margin-bottom:10px">Seguidores ganhos por dia</div>
        """, unsafe_allow_html=True)

        seg_tab = daily_seg[["date_start", "spend", "Seguidores"]].copy()
        seg_tab["Dia"]       = seg_tab["date_start"].dt.strftime("%d/%m/%Y")
        seg_tab["Investido"] = seg_tab["spend"].apply(fmt_brl)
        seg_tab["Seg."]      = seg_tab["Seguidores"].apply(
            lambda v: fmt_num(int(v)) if pd.notna(v) and v > 0 else "—"
        )
        seg_tab["Custo/Seg"] = seg_tab.apply(
            lambda r: fmt_brl(r["spend"] * TAX_MULTIPLIER / r["Seguidores"])
            if pd.notna(r["Seguidores"]) and r["Seguidores"] > 0 else "—",
            axis=1,
        )

        seg_thead = "".join(f"<th>{h}</th>" for h in ["DIA", "INVESTIDO", "SEGUIDORES", "CUSTO/SEG C/ IMP."])
        seg_rows  = []
        for _, r in seg_tab.iterrows():
            s = r["Seg."]
            seg_cell = f'<td class="green">{s}</td>' if s != "—" else f"<td>{s}</td>"
            custo_cell = f'<td style="color:#ffd600;font-weight:700">{r["Custo/Seg"]}</td>'
            seg_rows.append(
                f'<tr><td style="color:#c8cfe0;font-weight:600">{r["Dia"]}</td>'
                f'<td>{r["Investido"]}</td>{seg_cell}{custo_cell}</tr>'
            )
        st.markdown(
            f'<div class="tbl-wrap"><table><thead><tr>{seg_thead}</tr></thead>'
            f'<tbody>{"".join(seg_rows)}</tbody></table></div>',
            unsafe_allow_html=True
        )

# ══ TAB 3 — FUNIL COMPLETO ════════════════════════════════════════════════════

if tab3 is not None:
 with tab3:
    if df_agend is None or df_agend.empty:
        st.info("Nenhum dado de agendamentos encontrado para o período.")
    else:
        # Totais da planilha de agendamentos
        total_consultas   = int(df_agend["consultas"].sum())
        total_cirurgias   = int(df_agend["cirurgias"].sum())
        fat_consultas     = df_agend["total_consultas"].sum()
        fat_cirurgias     = df_agend["total_cirurgias"].sum()
        fat_total         = fat_consultas + fat_cirurgias

        ticket_consulta   = (fat_consultas / total_consultas) if total_consultas > 0 else 0
        ticket_cirurgia   = (fat_cirurgias / total_cirurgias) if total_cirurgias > 0 else 0

        # Totais das campanhas — E2-CAP + E1-DIST
        invest_liq        = (df_msg["spend"].sum() if not df_msg.empty else 0) + \
                            (df_seg["spend"].sum() if not df_seg.empty else 0)
        invest_imp        = invest_liq * TAX_MULTIPLIER
        total_msgs        = int(df_msg["messaging_contacts"].sum()) if not df_msg.empty else 0
        total_cliques     = int(df_msg["clicks"].sum()) if not df_msg.empty else 0
        total_impressoes  = int(df_msg["impressions"].sum()) if not df_msg.empty else 0
        reach_total_f     = int(df_msg["reach"].sum()) if not df_msg.empty and "reach" in df_msg.columns else 0

        # ROAS
        roas              = (fat_total / invest_liq) if invest_liq > 0 else 0
        roas_imp          = (fat_total / invest_imp) if invest_imp > 0 else 0

        # Taxas
        tx_passagem       = (total_msgs / total_cliques * 100) if total_cliques > 0 else 0
        tx_agend          = (total_consultas / total_msgs * 100) if total_msgs > 0 else 0
        tx_fech           = (total_cirurgias / total_consultas * 100) if total_consultas > 0 else 0
        tx_conv           = (total_cirurgias / total_cliques * 100) if total_cliques > 0 else 0

        # Custos
        cpm_f             = (invest_liq / total_impressoes * 1000) if total_impressoes > 0 else 0
        ctr_f             = (total_cliques / total_impressoes * 100) if total_impressoes > 0 else 0
        cpc_f             = (invest_liq / total_cliques) if total_cliques > 0 else 0
        cpl_f             = (invest_liq / total_msgs) if total_msgs > 0 else 0
        custo_consulta    = (invest_imp / total_consultas) if total_consultas > 0 else 0
        custo_cirurgia    = (invest_imp / total_cirurgias) if total_cirurgias > 0 else 0

        # ── Linha 1: Investimento + ROAS ──────────────────────────────────────
        st.subheader("Visão Geral")
        st.markdown(_kpi_html([
            {"label": "Investimento Líquido",    "value": fmt_brl(invest_liq),  "color": "cyan"},
            {"label": "Investimento + Impostos", "value": fmt_brl(invest_imp),  "color": "cyan"},
            {"label": "ROAS",                    "value": f"{roas:.1f}x",       "color": "green"},
            {"label": "ROAS c/ Impostos",        "value": f"{roas_imp:.1f}x",   "color": "green"},
        ]), unsafe_allow_html=True)

        st.divider()

        # ── Linha 2: Funil ────────────────────────────────────────────────────
        tipo_funil = client_cfg.get("tipo", "clinica_geral")
        col_funil, col_metricas = st.columns([1, 1])

        with col_funil:
            st.markdown('<div style="font-size:13px;font-weight:700;color:#c8cce8;margin-bottom:4px">Funil de Captação</div>', unsafe_allow_html=True)
            if tipo_funil == "tricologia":
                funil_labels_f = ["Impressões", "Cliques", "Mensagens", "Consultas"]
                funil_values_f = [total_impressoes, total_cliques, total_msgs, total_consultas]
                funil_colors_f = ["#00d4ff", "#7B6CF6", "#00e676", "#ffd600"]
                funil_pcts_f   = [100.0,
                                  ctr_f,
                                  tx_passagem,
                                  tx_agend]
            else:
                funil_labels_f = ["Impressões", "Cliques", "Mensagens", "Consultas", "Cirurgias"]
                funil_values_f = [total_impressoes, total_cliques, total_msgs, total_consultas, total_cirurgias]
                funil_colors_f = ["#00d4ff", "#7B6CF6", "#00e676", "#ffd600", "#ff6b6b"]
                funil_pcts_f   = [100.0, ctr_f, tx_passagem, tx_agend, tx_fech]

            st.markdown(build_funnel_html(funil_labels_f, funil_values_f, funil_colors_f, funil_pcts_f),
                        unsafe_allow_html=True)

        with col_metricas:
            st.markdown(
                '<div style="font-size:12px;font-weight:700;color:#3d4466;'
                'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                'Métricas de Performance</div>',
                unsafe_allow_html=True,
            )
            if tipo_funil == "tricologia":
                _m_cards = [
                    {"label": "Faturamento Gerado", "value": fmt_brl(fat_consultas), "color": "yellow",
                     "sub": f"▲ {total_consultas} pacientes"},
                    {"label": "ROI da Operação",    "value": f"{roas_imp:.2f}x",     "color": "yellow",
                     "sub": f"▲ {fmt_brl(invest_imp)} investido"},
                    {"label": "CPM",                "value": fmt_brl(cpm_f),         "color": "cyan",
                     "sub": "Custo/mil impressões"},
                    {"label": "CTR",                "value": fmt_pct(ctr_f),         "color": "green",
                     "sub": "Taxa de cliques"},
                    {"label": "CPL Real",           "value": fmt_brl(cpl_f),         "color": "green",
                     "sub": f"▲ {total_msgs} mensagens"},
                    {"label": "TX. Passagem",       "value": fmt_pct(tx_passagem),   "color": "green",
                     "sub": "Msg por clique"},
                    {"label": "TX. Agendamento",    "value": fmt_pct(tx_agend),      "color": "green",
                     "sub": "Consultas por msg"},
                    {"label": "Custo/Paciente",     "value": fmt_brl(custo_consulta),"color": "yellow",
                     "sub": f"▲ {total_consultas} pacientes"},
                ]
            else:
                _m_cards = [
                    {"label": "Faturamento Total",  "value": fmt_brl(fat_total),     "color": "yellow",
                     "sub": f"▲ {total_cirurgias} cirurgias"},
                    {"label": "ROI da Operação",    "value": f"{roas_imp:.2f}x",     "color": "yellow",
                     "sub": f"▲ {fmt_brl(invest_imp)} investido"},
                    {"label": "CPM",                "value": fmt_brl(cpm_f),         "color": "cyan",
                     "sub": "Custo/mil impressões"},
                    {"label": "CTR",                "value": fmt_pct(ctr_f),         "color": "green",
                     "sub": "Taxa de cliques"},
                    {"label": "CPL Real",           "value": fmt_brl(cpl_f),         "color": "green",
                     "sub": f"▲ {total_msgs} mensagens"},
                    {"label": "TX. Passagem",       "value": fmt_pct(tx_passagem),   "color": "green",
                     "sub": "Msg por clique"},
                    {"label": "TX. Agendamento",    "value": fmt_pct(tx_agend),      "color": "green",
                     "sub": "Consultas por msg"},
                    {"label": "TX. Fechamento",     "value": fmt_pct(tx_fech),       "color": "green",
                     "sub": "Cirurgias por consulta"},
                    {"label": "Custo/Consulta",     "value": fmt_brl(custo_consulta),"color": "yellow",
                     "sub": ""},
                    {"label": "Custo/Cirurgia",     "value": fmt_brl(custo_cirurgia),"color": "yellow",
                     "sub": f"▲ {total_cirurgias} cirurgias"},
                ]
            st.markdown(_kpi_html(_m_cards, cols=2, small=True), unsafe_allow_html=True)

        st.divider()

        # ── Linha 3: Faturamento ──────────────────────────────────────────────
        st.subheader("Faturamento")
        if tipo_funil == "tricologia":
            st.markdown(_kpi_html([
                {"label": "Consultas",             "value": fmt_num(total_consultas),  "color": "white"},
                {"label": "Ticket Médio Consulta", "value": fmt_brl(ticket_consulta),  "color": "yellow"},
                {"label": "Faturamento Total",     "value": fmt_brl(fat_consultas),    "color": "green"},
            ]), unsafe_allow_html=True)
        else:
            st.markdown(_kpi_html([
                {"label": "Consultas",              "value": fmt_num(total_consultas),  "color": "white"},
                {"label": "Ticket Médio Consulta",  "value": fmt_brl(ticket_consulta),  "color": "yellow"},
                {"label": "Fat. Consultas",         "value": fmt_brl(fat_consultas),    "color": "green"},
                {"label": "Cirurgias",              "value": fmt_num(total_cirurgias),  "color": "white"},
                {"label": "Ticket Médio Cirurgia",  "value": fmt_brl(ticket_cirurgia),  "color": "yellow"},
                {"label": "Faturamento Total",      "value": fmt_brl(fat_total),        "color": "green"},
            ]), unsafe_allow_html=True)

# ══ TAB 4 — METAS ════════════════════════════════════════════════════════════

if tab4 is not None:
 with tab4:
    import calendar
    from datetime import date as _date

    # Usa o período selecionado pelo usuário, não a data de hoje
    _mes_ref       = date_start  # primeiro dia do período selecionado
    hoje           = _date.today()
    primeiro_dia   = _mes_ref.replace(day=1).strftime("%Y-%m-%d")
    ultimo_dia     = _mes_ref.replace(day=calendar.monthrange(_mes_ref.year, _mes_ref.month)[1]).strftime("%Y-%m-%d")
    dias_no_mes    = calendar.monthrange(_mes_ref.year, _mes_ref.month)[1]
    # dias_passados: se for o mês atual usa hoje, senão considera o mês completo
    _mes_atual     = hoje.year == _mes_ref.year and hoje.month == _mes_ref.month
    dias_passados  = hoje.day if _mes_atual else dias_no_mes
    dias_restantes = dias_no_mes - dias_passados

    tipo_cliente = client_cfg.get("tipo", "clinica_geral")

    try:
        df_metas = fetch_agendamentos(agendamentos_id, primeiro_dia, ultimo_dia) if agendamentos_id else pd.DataFrame()
    except RuntimeError as _e:
        st.warning(f"⚠️ {_e} — clique em **Atualizar Dados** na barra lateral para tentar novamente.")
        df_metas = pd.DataFrame()

    st.markdown(
        f'<div style="font-size:20px;font-weight:900;color:#e0e4f0;margin-bottom:2px">'
        f'Metas de {_mes_ref.strftime("%B de %Y").capitalize()}</div>'
        f'<div style="font-size:11px;color:#3d4466;margin-bottom:16px">'
        f'Dia {dias_passados} de {dias_no_mes} · {dias_restantes} dias restantes</div>',
        unsafe_allow_html=True
    )

    def _meta_block(titulo, atual, meta, ritmo, proj, dias_rest, unidade="pacientes"):
        faltam  = max(meta - atual, 0)
        pct     = min(atual / meta * 100, 100) if meta > 0 else 0
        nec     = faltam / dias_rest if dias_rest > 0 else 0
        bater   = proj >= meta
        cor_txt = "#00e676" if bater else "#ffd600"
        status  = (f"✅ No ritmo atual ({ritmo:.1f}/dia) vai bater a meta — projeção: <b>{proj}</b> {unidade}."
                   if bater else
                   f"⚠️ Projeção: <b>{proj}</b> {unidade}. Precisa de <b>{nec:.1f}/dia</b> para bater a meta.")
        pct_bar = round(pct)
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(
                f'<div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:20px 24px">'
                f'<div style="font-size:12px;font-weight:700;color:#3d4466;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">{titulo}</div>'
                f'<div style="font-size:28px;font-weight:900;color:#e0e4f0;margin-bottom:4px">{atual} <span style="font-size:16px;color:#5a607a">/ {meta}</span></div>'
                f'<div style="font-size:11px;color:#3d4466;margin-bottom:12px">faltam <b style="color:{cor_txt}">{faltam}</b> {unidade}</div>'
                f'<div style="background:#161829;border-radius:4px;height:6px;margin-bottom:12px">'
                f'<div style="background:linear-gradient(90deg,#00d4ff,#00e676);height:100%;border-radius:4px;width:{pct_bar}%"></div></div>'
                f'<div style="font-size:12px;color:#8892b0">{status}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(_kpi_html([
                {"label": "Realizado",          "value": f"{atual}/{meta}",    "color": "cyan"},
                {"label": "Projeção no mês",    "value": str(proj),            "color": "green" if bater else "yellow"},
                {"label": "Ritmo atual",        "value": f"{ritmo:.1f}/dia",   "color": "white"},
            ], cols=1), unsafe_allow_html=True)

    if tipo_cliente == "tricologia":
        META_PACIENTES = client_cfg.get("meta_pacientes", 20)

        if df_metas is None or df_metas.empty:
            total_msgs_m = int(df_msg["messaging_contacts"].sum()) if not df_msg.empty else 0
            ritmo = total_msgs_m / dias_passados if dias_passados > 0 else 0
            proj  = round(ritmo * dias_no_mes)
            _meta_block("👤 Pacientes (Novos Contatos)", total_msgs_m, META_PACIENTES, ritmo, proj, dias_restantes, "pacientes")
        else:
            pacientes_atual = int(df_metas["consultas"].sum())
            ritmo = pacientes_atual / dias_passados if dias_passados > 0 else 0
            proj  = round(ritmo * dias_no_mes)
            _meta_block("👤 Pacientes Atendidos", pacientes_atual, META_PACIENTES, ritmo, proj, dias_restantes, "pacientes")

            # ── LTV Anual (apenas para clientes com show_ltv=True) ────────────
            if client_cfg.get("show_ltv", True):
                fat_m             = df_metas["total_consultas"].sum() if "total_consultas" in df_metas.columns else 0
                ticket_m          = fat_m / pacientes_atual if pacientes_atual > 0 else 0
                consultas_por_ano = client_cfg.get("consultas_por_ano", 4)
                ltv_por_pac       = consultas_por_ano * ticket_m
                ltv_atual_total   = pacientes_atual * ltv_por_pac
                ltv_meta_m        = META_PACIENTES * ltv_por_pac
                ltv_anual_run     = proj * 12 * ltv_por_pac

                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:20px;font-weight:900;color:#e0e4f0;margin-bottom:2px">📈 Projeção LTV Anual</div>'
                    f'<div style="font-size:11px;color:#3d4466;margin-bottom:14px">'
                    f'Cada paciente realiza até {consultas_por_ano} consultas/ano · '
                    f'Ticket médio atual: {fmt_brl(ticket_m)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(_kpi_html([
                    {"label": "LTV / Paciente",
                     "value": fmt_brl(ltv_por_pac),
                     "color": "cyan",
                     "sub": f"{consultas_por_ano} consultas × {fmt_brl(ticket_m)}"},
                    {"label": f"LTV Gerado ({pacientes_atual} pctes)",
                     "value": fmt_brl(ltv_atual_total),
                     "color": "green",
                     "sub": f"▲ {pacientes_atual} pacientes confirmados"},
                    {"label": f"LTV Meta Mensal ({META_PACIENTES} pctes)",
                     "value": fmt_brl(ltv_meta_m),
                     "color": "yellow",
                     "sub": f"Se bater {META_PACIENTES} pacientes/mês"},
                    {"label": "LTV Anual Projetado",
                     "value": fmt_brl(ltv_anual_run),
                     "color": "purple",
                     "sub": f"Ritmo atual: {proj} pctes/mês × 12 meses"},
                ]), unsafe_allow_html=True)

    else:
        META_CONSULTAS = client_cfg.get("meta_consultas", 40)
        META_CIRURGIAS = client_cfg.get("meta_cirurgias", 16)

        if df_metas is None or df_metas.empty:
            st.info("Nenhum dado de agendamentos encontrado para este mês.")
        else:
            consultas_atual = int(df_metas["consultas"].sum())
            cirurgias_atual = int(df_metas["cirurgias"].sum())

            ritmo_consultas = consultas_atual / dias_passados if dias_passados > 0 else 0
            ritmo_cirurgias = cirurgias_atual / dias_passados if dias_passados > 0 else 0
            proj_consultas  = round(ritmo_consultas * dias_no_mes)
            proj_cirurgias  = round(ritmo_cirurgias * dias_no_mes)

            _meta_block("📅 Agendamentos (Consultas)", consultas_atual, META_CONSULTAS,
                        ritmo_consultas, proj_consultas, dias_restantes, "consultas")
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            _meta_block("🔬 Cirurgias", cirurgias_atual, META_CIRURGIAS,
                        ritmo_cirurgias, proj_cirurgias, dias_restantes, "cirurgias")

# ══ TAB 5 — COMPARATIVO MENSAL ════════════════════════════════════════════════

with tab5:
    import calendar as _cal

    _PT_MONTHS = {1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
                  7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"}

    # ── Gera lista dos últimos 13 meses (do mais antigo ao mais recente) ───────
    _today = date.today()
    _opts  = []
    for _i in range(12, -1, -1):
        _yr, _mo = _today.year, _today.month - _i
        while _mo <= 0: _mo += 12; _yr -= 1
        _opts.append((f"{_PT_MONTHS[_mo]} {_yr}", date(_yr, _mo, 1)))
    _opt_labels = [o[0] for o in _opts]
    _opt_dates  = {o[0]: o[1] for o in _opts}

    st.markdown(
        '<div style="font-size:20px;font-weight:900;color:#e0e4f0;margin-bottom:2px">Comparativo Mensal</div>'
        '<div style="font-size:11px;color:#3d4466;margin-bottom:16px">'
        'Selecione dois meses para comparar os resultados lado a lado</div>',
        unsafe_allow_html=True,
    )

    col_sel1, _gap, col_sel2 = st.columns([5, 1, 5])
    with col_sel1:
        lbl_a = st.selectbox("Mês A (base)", _opt_labels,
                             index=max(0, len(_opt_labels) - 2), key="cmp_a")
    with col_sel2:
        lbl_b = st.selectbox("Mês B (comparar)", _opt_labels,
                             index=len(_opt_labels) - 1, key="cmp_b")

    _first_a = _opt_dates[lbl_a]
    _first_b = _opt_dates[lbl_b]
    _last_a  = (_today if (_first_a.year == _today.year and _first_a.month == _today.month)
                else date(_first_a.year, _first_a.month, _cal.monthrange(_first_a.year, _first_a.month)[1]))
    _last_b  = (_today if (_first_b.year == _today.year and _first_b.month == _today.month)
                else date(_first_b.year, _first_b.month, _cal.monthrange(_first_b.year, _first_b.month)[1]))

    with st.spinner("Buscando dados dos dois meses..."):
        _df_a = fetch_campaign_insights(str(_first_a), str(_last_a), account_id)
        _df_b = fetch_campaign_insights(str(_first_b), str(_last_b), account_id)
        try:
            _ag_a = fetch_agendamentos(agendamentos_id, str(_first_a), str(_last_a)) if agendamentos_id else pd.DataFrame()
        except RuntimeError:
            _ag_a = pd.DataFrame()
        try:
            _ag_b = fetch_agendamentos(agendamentos_id, str(_first_b), str(_last_b)) if agendamentos_id else pd.DataFrame()
        except RuntimeError:
            _ag_b = pd.DataFrame()

    def _cmp_metrics(df, ag):
        """Calcula métricas agregadas de um mês para comparativo."""
        if df.empty:
            return dict(spend=0, spend_imp=0, contacts=0, cpl=None, cpm=None,
                        agend=0, custo_agend=None, cirurg=0, custo_cirurg=None)
        df_m   = df[df["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)]
        spend  = df["spend"].sum()
        imps   = int(df["impressions"].sum())
        ctts   = int(df_m["messaging_contacts"].sum()) if not df_m.empty and "messaging_contacts" in df_m.columns else 0
        agend  = int(ag["consultas"].sum())  if ag is not None and not ag.empty and "consultas"  in ag.columns else 0
        cirurg = int(ag["cirurgias"].sum())  if ag is not None and not ag.empty and "cirurgias"  in ag.columns else 0
        return dict(
            spend        = spend,
            spend_imp    = spend * TAX_MULTIPLIER,
            contacts     = ctts,
            cpl          = spend * TAX_MULTIPLIER / ctts   if ctts   > 0 else None,
            cpm          = spend * TAX_MULTIPLIER / imps * 1000 if imps > 0 else None,
            agend        = agend,
            custo_agend  = spend * TAX_MULTIPLIER / agend  if agend  > 0 else None,
            cirurg       = cirurg,
            custo_cirurg = spend * TAX_MULTIPLIER / cirurg if cirurg > 0 else None,
        )

    ma = _cmp_metrics(_df_a, _ag_a)
    mb = _cmp_metrics(_df_b, _ag_b)

    def _delta_html(va, vb, lower_is_better=False):
        """Retorna HTML do badge de variação (vb vs va)."""
        if va is None or va == 0 or vb is None:
            return '<span style="color:#3d4466;font-size:11px">—</span>'
        pct      = (vb - va) / abs(va) * 100
        sign     = "+" if pct >= 0 else ""
        improved = (pct < 0) if lower_is_better else (pct > 0)
        color    = "#00e676" if improved else "#ff4444"
        arrow    = "▲" if pct >= 0 else "▼"
        return (f'<span style="color:{color};font-size:12px;font-weight:700">'
                f'{arrow} {sign}{pct:.1f}%</span>')

    # ── Tabela comparativa ─────────────────────────────────────────────────────
    parcial_a = _first_a.year == _today.year and _first_a.month == _today.month
    parcial_b = _first_b.year == _today.year and _first_b.month == _today.month
    suf_a = " <span style='font-size:9px;color:#3d4466'>(parcial)</span>" if parcial_a else ""
    suf_b = " <span style='font-size:9px;color:#3d4466'>(parcial)</span>" if parcial_b else ""

    rows_cmp = [
        ("💰 Investido c/ imp.",  fmt_brl(ma["spend_imp"]),  fmt_brl(mb["spend_imp"]),
         _delta_html(ma["spend_imp"],  mb["spend_imp"])),
        ("💬 Contatos",           fmt_num(ma["contacts"]),   fmt_num(mb["contacts"]),
         _delta_html(ma["contacts"],   mb["contacts"])),
        ("📉 CPL c/ imp.",        fmt_brl(ma["cpl"])   if ma["cpl"]   else "—",
                                  fmt_brl(mb["cpl"])   if mb["cpl"]   else "—",
         _delta_html(ma["cpl"],   mb["cpl"],   lower_is_better=True)),
        ("📊 CPM c/ imp.",        fmt_brl(ma["cpm"])   if ma["cpm"]   else "—",
                                  fmt_brl(mb["cpm"])   if mb["cpm"]   else "—",
         _delta_html(ma["cpm"],   mb["cpm"],   lower_is_better=True)),
    ]

    # Adiciona agendamentos apenas para clientes com planilha de agendamentos
    if agendamentos_id:
        rows_cmp += [
            ("📅 Agendamentos",       fmt_num(ma["agend"]),      fmt_num(mb["agend"]),
             _delta_html(ma["agend"],       mb["agend"])),
            ("🏥 Custo/Agendamento",  fmt_brl(ma["custo_agend"]) if ma["custo_agend"] else "—",
                                      fmt_brl(mb["custo_agend"]) if mb["custo_agend"] else "—",
             _delta_html(ma["custo_agend"], mb["custo_agend"], lower_is_better=True)),
        ]

    # Adiciona cirurgias apenas para clientes com essa métrica (ex.: Dr. Vinicius)
    if client_cfg.get("meta_cirurgias"):
        rows_cmp += [
            ("🔬 Cirurgias",          fmt_num(ma["cirurg"]),     fmt_num(mb["cirurg"]),
             _delta_html(ma["cirurg"],       mb["cirurg"])),
            ("💊 Custo/Cirurgia",     fmt_brl(ma["custo_cirurg"]) if ma["custo_cirurg"] else "—",
                                      fmt_brl(mb["custo_cirurg"]) if mb["custo_cirurg"] else "—",
             _delta_html(ma["custo_cirurg"], mb["custo_cirurg"], lower_is_better=True)),
        ]

    table_rows = ""
    for i, (metrica, val_a, val_b, delta) in enumerate(rows_cmp):
        bg = "background:rgba(255,255,255,0.02)" if i % 2 == 0 else ""
        table_rows += (
            f'<tr style="{bg}">'
            f'<td style="padding:14px 18px;font-size:12px;color:#8b92b8;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid #1e2235">{metrica}</td>'
            f'<td style="padding:14px 18px;font-size:18px;font-weight:800;color:#e0e4f0;'
            f'text-align:right;border-bottom:1px solid #1e2235">{val_a}</td>'
            f'<td style="padding:14px 18px;font-size:18px;font-weight:800;color:#e0e4f0;'
            f'text-align:right;border-bottom:1px solid #1e2235">{val_b}</td>'
            f'<td style="padding:14px 18px;text-align:center;border-bottom:1px solid #1e2235">{delta}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div style="background:#0f1120;border:1px solid #1e2235;border-radius:14px;overflow:hidden;margin-top:8px">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#141728">'
        f'<th style="padding:14px 18px;font-size:10px;color:#3d4466;font-weight:700;'
        f'text-align:left;letter-spacing:1px;text-transform:uppercase">MÉTRICA</th>'
        f'<th style="padding:14px 18px;font-size:12px;color:#00d4ff;font-weight:800;'
        f'text-align:right">{lbl_a}{suf_a}</th>'
        f'<th style="padding:14px 18px;font-size:12px;color:#a78bfa;font-weight:800;'
        f'text-align:right">{lbl_b}{suf_b}</th>'
        f'<th style="padding:14px 18px;font-size:10px;color:#3d4466;font-weight:700;'
        f'text-align:center;letter-spacing:1px;text-transform:uppercase">VARIAÇÃO</th>'
        f'</tr></thead>'
        f'<tbody>{table_rows}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )

    # ── Gráficos sobrepostos dia a dia ─────────────────────────────────────────
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:16px;font-weight:800;color:#e0e4f0;margin-bottom:4px">Evolução Diária</div>'
        '<div style="font-size:11px;color:#3d4466;margin-bottom:14px">'
        'Os dois meses sobrepostos na mesma escala — dia a dia</div>',
        unsafe_allow_html=True,
    )

    def _daily_series(df, col, agg="sum"):
        """Agrega coluna por dia-do-mês."""
        if df.empty or col not in df.columns:
            return pd.Series(dtype=float)
        tmp = df.copy()
        tmp["dia"] = pd.to_datetime(tmp["date_start"]).dt.day
        return tmp.groupby("dia")[col].sum()

    # Investimento diário (todas campanhas)
    _spend_a = _daily_series(_df_a, "spend")
    _spend_b = _daily_series(_df_b, "spend")

    # Contatos diários (só campanha mensagens)
    _dfm_a = _df_a[_df_a["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)] if not _df_a.empty else _df_a
    _dfm_b = _df_b[_df_b["campaign_name"].str.contains(MESSAGING_KEYWORD, case=False, na=False)] if not _df_b.empty else _df_b
    _ctts_a = _daily_series(_dfm_a, "messaging_contacts")
    _ctts_b = _daily_series(_dfm_b, "messaging_contacts")

    _col_a, _col_b_chart = "#00d4ff", "#a78bfa"   # cyan = Mês A, roxo = Mês B

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown(
            f'<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">Investimento Diário</p>'
            f'<p style="font-size:11px;color:#3d4466;margin:0 0 4px">'
            f'<span style="color:{_col_a}">█</span> {lbl_a} &nbsp;'
            f'<span style="color:{_col_b_chart}">━●</span> {lbl_b}</p>',
            unsafe_allow_html=True)
        fig_sp = go.Figure()
        if not _spend_a.empty:
            fig_sp.add_trace(go.Bar(
                x=_spend_a.index, y=_spend_a.values * TAX_MULTIPLIER,
                name=lbl_a, marker_color=_col_a,
                opacity=0.85,
                hovertemplate="Dia %{x}<br>R$ %{y:,.2f}<extra>" + lbl_a + "</extra>",
            ))
        if not _spend_b.empty:
            fig_sp.add_trace(go.Scatter(
                x=_spend_b.index, y=_spend_b.values * TAX_MULTIPLIER,
                name=lbl_b, mode="lines+markers",
                line=dict(color=_col_b_chart, width=2),
                marker=dict(size=5, color=_col_b_chart),
                hovertemplate="Dia %{x}<br>R$ %{y:,.2f}<extra>" + lbl_b + "</extra>",
            ))
        fig_sp.update_layout(bargap=0.25, showlegend=False, xaxis_title="", yaxis_title="", **_PD)
        st.plotly_chart(fig_sp, use_container_width=True)

    with col_g2:
        st.markdown(
            f'<p style="font-size:13px;font-weight:700;color:#c8cce8;margin:0 0 2px">Contatos Diários</p>'
            f'<p style="font-size:11px;color:#3d4466;margin:0 0 4px">'
            f'<span style="color:{_col_a}">█</span> {lbl_a} &nbsp;'
            f'<span style="color:{_col_b_chart}">━●</span> {lbl_b}</p>',
            unsafe_allow_html=True)
        fig_ct = go.Figure()
        if not _ctts_a.empty:
            fig_ct.add_trace(go.Bar(
                x=_ctts_a.index, y=_ctts_a.values,
                name=lbl_a, marker_color=_col_a,
                opacity=0.85,
                hovertemplate="Dia %{x}<br>%{y} contatos<extra>" + lbl_a + "</extra>",
            ))
        if not _ctts_b.empty:
            fig_ct.add_trace(go.Scatter(
                x=_ctts_b.index, y=_ctts_b.values,
                name=lbl_b, mode="lines+markers",
                line=dict(color=_col_b_chart, width=2),
                marker=dict(size=5, color=_col_b_chart),
                hovertemplate="Dia %{x}<br>%{y} contatos<extra>" + lbl_b + "</extra>",
            ))
        fig_ct.update_layout(bargap=0.25, showlegend=False, xaxis_title="", yaxis_title="", **_PD)
        st.plotly_chart(fig_ct, use_container_width=True)
