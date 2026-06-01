"""
Cliente Google Sheets sem DLLs — usa apenas requests.
Lê/renova token.json automaticamente.
"""

import json
import time
from pathlib import Path
import requests as req

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"


def _load_token() -> dict:
    # Streamlit Cloud: lê do secrets
    try:
        import streamlit as st
        if "google_token" in st.secrets:
            token = dict(st.secrets["google_token"])
            token.setdefault("expires_at", 0)
            return token
    except Exception:
        pass
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "token.json não encontrado. Execute autenticar_google.py primeiro."
        )
    return json.loads(TOKEN_FILE.read_text())


def _get_access_token() -> str:
    token = _load_token()

    # Renova se expirado (ou falta menos de 5 min)
    if time.time() >= token.get("expires_at", 0) - 300:
        r = req.post(token["token_uri"], data={
            "client_id":     token["client_id"],
            "client_secret": token["client_secret"],
            "refresh_token": token["refresh_token"],
            "grant_type":    "refresh_token",
        })
        r.raise_for_status()
        new = r.json()
        token["access_token"] = new["access_token"]
        token["expires_at"]   = time.time() + new.get("expires_in", 3600)
        TOKEN_FILE.write_text(json.dumps(token, indent=2))

    return token["access_token"]


def batch_update(spreadsheet_id: str, data: list) -> None:
    """
    data = lista de dicts com 'range', 'majorDimension', 'values'
    Nunca toca colunas de fórmula — só os ranges passados.
    """
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}/values:batchUpdate"
    body  = {"data": data, "valueInputOption": "USER_ENTERED"}
    r = req.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def update_range(spreadsheet_id: str, range_: str, values: list) -> None:
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}/values/{urllib.parse.quote(range_, safe='')}?valueInputOption=USER_ENTERED"
    r = req.put(url, json={"values": values}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def clear_range(spreadsheet_id: str, range_: str) -> None:
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}/values/{urllib.parse.quote(range_, safe='')}:clear"
    r = req.post(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()


def read_range(spreadsheet_id: str, range_: str) -> list:
    """Retorna lista de linhas [[v1, v2, ...], ...] para o range informado."""
    import urllib.parse
    token = _get_access_token()
    url = f"{SHEETS_URL}/{spreadsheet_id}/values/{urllib.parse.quote(range_, safe='')}"
    r = req.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json().get("values", [])


def get_sheet_titles(spreadsheet_id: str) -> list:
    token = _get_access_token()
    url   = f"{SHEETS_URL}/{spreadsheet_id}?fields=sheets.properties.title"
    r = req.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return [s["properties"]["title"] for s in r.json().get("sheets", [])]


def ensure_tab(spreadsheet_id: str, tab_name: str) -> None:
    titles = get_sheet_titles(spreadsheet_id)
    if tab_name not in titles:
        token = _get_access_token()
        url   = f"{SHEETS_URL}/{spreadsheet_id}:batchUpdate"
        body  = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        r = req.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()


def write_tab(spreadsheet_id: str, tab_name: str, rows: list) -> None:
    """Sobrescreve uma aba inteira com os dados passados."""
    import urllib.parse
    ensure_tab(spreadsheet_id, tab_name)
    clear_range(spreadsheet_id, tab_name)
    token = _get_access_token()
    range_ = urllib.parse.quote(f"{tab_name}!A1", safe="")
    url    = f"{SHEETS_URL}/{spreadsheet_id}/values/{range_}?valueInputOption=USER_ENTERED"
    r = req.put(url, json={"values": rows}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
