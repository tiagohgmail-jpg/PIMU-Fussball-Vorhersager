import os
import math
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# KICKPREDICT AI
# Erstellt von Tiago Faruk und Yigit
# Ausschliesslich virtuelles Spielgeld
# ============================================================

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
)

LEAGUES = {
    "Premier League 🇬🇧": ("PL", "en.1.json"),
    "La Liga 🇪🇸": ("PD", "es.1.json"),
    "Bundesliga 🇩🇪": ("BL1", "de.1.json"),
    "Serie A 🇮🇹": ("SA", "it.1.json"),
    "Ligue 1 🇫🇷": ("FL1", "fr.1.json"),
}

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "openfootball/football.json/master"
)

SEASONS = [
    "2026-27", "2025-26", "2024-25", "2023-24",
    "2022-23", "2021-22", "2020-21",
]

START_COINS = 1000
MAX_STAKE = 10000
TIAGO_BONUS = 999999
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

try:
    FOOTBALL_API_KEY = st.secrets.get("FOOTBALL_DATA_API_KEY", "")
except Exception:
    FOOTBALL_API_KEY = ""

FOOTBALL_API_KEY = (
    FOOTBALL_API_KEY
    or os.environ.get("FOOTBALL_DATA_API_KEY", "")
).strip()

# -------------------- DESIGN --------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg,#07111f,#0b192a 55%,#102a36);
    color: #f4f7fb;
}
[data-testid="stSidebar"] {background:#07111e;}
[data-testid="stHeader"] {background:transparent;}
.hero {
    padding:28px;
    border-radius:20px;
    background:linear-gradient(115deg,#142943,#12513f);
    border:1px solid #315b68;
    margin-bottom:22px;
}
.hero h1 {font-size:38px;font-weight:850;color:#f4f7fb;}
.hero p {color:#d2e2ee;font-size:16px;}
.eyebrow {
    color:#63edaf;text-transform:uppercase;font-weight:800;
    letter-spacing:2px;font-size:12px;
}
.metric {
    background:linear-gradient(145deg,#152940,#101e31);
    border:1px solid #2b435e;border-radius:15px;
    padding:17px;min-height:105px;
}
.metric-label {color:#aebfd2;font-size:13px;}
.metric-value {color:#5ce6a6;font-size:26px;font-weight:850;margin-top:5px;}
.panel {
    background:#122238;border:1px solid #293f58;
    border-radius:15px;padding:18px;margin-bottom:12px;
}
.muted {color:#aebfd2;font-size:13px;}
div.stButton>button,[data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button {
    background:#4be0a0;color:#07131c;border:0;
    border-radius:10px;font-weight:800;min-height:42px;
}
[data-baseweb="select"]>div,[data-baseweb="input"]>div {
    background:#122238;color:#f4f7fb;border-color:#36516c;
}
h1,h2,h3,h4,p,label {color:#f4f7fb;}
hr {border-color:#273d53;}
</style>
""", unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(
        f'<div class="hero"><div class="eyebrow">'
        f'KickPredict AI · Analytics</div><h1>{title}</h1>'
        f'<p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def metric(label, value, subtitle=""):
    st.markdown(
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="muted">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def now_utc():
    return datetime.now(timezone.utc)


def utc_text():
    return now_utc().isoformat()


def attribution():
    st.caption("KickPredict AI · Erstellt von Tiago Faruk und Yigit")
    st.caption("Nur virtuelles Spielgeld. Keine Echtgeldwetten.")


# -------------------- DATENBANK --------------------

def connect_db():
    if DATABASE_URL:
        import psycopg
        return psycopg.connect(DATABASE_URL)
    return sqlite3.connect("kickpredict_local.db", timeout=20)


def qmark(sql):
    return sql.replace("?", "%s") if DATABASE_URL else sql


def init_db():
    conn = connect_db()
    try:
        cur = conn.cursor()

        if DATABASE_URL:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    coins BIGINT NOT NULL DEFAULT 1000,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    fixture_id TEXT NOT NULL DEFAULT '',
                    league TEXT NOT NULL,
                    match_date TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    stake BIGINT NOT NULL,
                    odds DOUBLE PRECISION NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Offen',
                    payout BIGINT NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    settled_at TEXT NOT NULL DEFAULT ''
                )
            """)
            cur.execute("""
                ALTER TABLE bets
                ADD COLUMN IF NOT EXISTS fixture_id TEXT NOT NULL DEFAULT ''
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    coins INTEGER NOT NULL DEFAULT 1000,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    fixture_id TEXT NOT NULL DEFAULT '',
                    league TEXT NOT NULL,
                    match_date TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    stake INTEGER NOT NULL,
                    odds REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Offen',
                    payout INTEGER NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    settled_at TEXT NOT NULL DEFAULT ''
                )
            """)
            cur.execute("PRAGMA table_info(bets)")
            columns = [row[1] for row in cur.fetchall()]
            if "fixture_id" not in columns:
                cur.execute(
                    "ALTER TABLE bets ADD COLUMN fixture_id TEXT NOT NULL DEFAULT ''"
                )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bonus_claims (
                username TEXT PRIMARY KEY,
                claimed_at TEXT NOT NULL
            )
        """)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        300_000,
    ).hex()


def create_user(username, password):
    username = username.strip().lower()

    if not 3 <= len(username) <= 24:
        return False, "Benutzername: 3–24 Zeichen."

    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Erlaubt sind Buchstaben, Zahlen, _ und -."

    if len(password) < 8:
        return False, "Das Passwort braucht mindestens 8 Zeichen."

    salt = secrets.token_hex(16)
    hashed = hash_password(password, salt)
    conn = connect_db()

    try:
        cur = conn.cursor()
        cur.execute(
            qmark("""
                INSERT INTO users
                (username,salt,password_hash,coins,created_at)
                VALUES (?,?,?,?,?)
            """),
            (username, salt, hashed, START_COINS, utc_text()),
        )
        conn.commit()
        return True, "Konto erstellt! Du kannst dich anmelden."
    except Exception:
        conn.rollback()
        return False, "Dieser Benutzername ist bereits vergeben."
    finally:
        conn.close()


def verify_user(username, password):
    conn = connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            qmark("SELECT salt,password_hash FROM users WHERE username=?"),
            (username.strip().lower(),),
        )
        row = cur.fetchone()
        return bool(
            row and hmac.compare_digest(
                hash_password(password, row[0]), row[1]
            )
        )
    finally:
        conn.close()


def user_info(username):
    conn = connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            qmark("SELECT coins FROM users WHERE username=?"),
            (username,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def give_tiago_bonus():
    conn = connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            qmark("SELECT username FROM users WHERE username=?"),
            ("tiago",),
        )
        if not cur.fetchone():
            conn.rollback()
            return False

        cur.execute(
            qmark("""
                INSERT INTO bonus_claims (username, claimed_at)
                VALUES (?, ?)
                ON CONFLICT(username) DO NOTHING
            """),
            ("tiago", utc_text()),
        )

        if cur.rowcount == 0:
            conn.rollback()
            return False

        cur.execute(
            qmark("UPDATE users SET coins=coins+? WHERE username=?"),
            (TIAGO_BONUS, "tiago"),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_bets(username):
    conn = connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            qmark("""
                SELECT id,fixture_id,league,match_date,home_team,away_team,
                       selection,stake,odds,status,payout,result,created_at
                FROM bets
                WHERE username=?
                ORDER BY id DESC
            """),
            (username,),
        )
        rows = cur.fetchall()
        columns = [
            "id", "fixture_id", "league", "match_date", "home_team",
            "away_team", "selection", "stake", "odds", "status",
            "payout", "result", "created_at",
        ]
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


def place_bet(username, fixture, selection, stake, odds):
    stake = int(stake)

    if stake < 1 or stake > MAX_STAKE:
        return False, "Ungültiger Einsatz."

    if selection not in ("Heimsieg", "Unentschieden", "Auswärtssieg"):
        return False, "Ungültiger Tipp."

    if not 1.0 <= float(odds) <= 10.0:
        return False, "Ungültige Quote."

    kickoff = pd.Timestamp(fixture["Datum"])
    if kickoff.tzinfo is None:
        kickoff = kickoff.tz_localize("UTC")

    if kickoff <= pd.Timestamp.now(tz="UTC"):
        return False, "Für vergangene Spiele kannst du nicht tippen."

    conn = connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            qmark("SELECT coins FROM users WHERE username=?"),
            (username,),
        )
        row = cur.fetchone()

        if not row or int(row[0]) < stake:
            return False, "Du hast nicht genügend Coins."

        cur.execute(
            qmark("""
                UPDATE users
                SET coins=coins-?
                WHERE username=? AND coins>=?
            """),
            (stake, username, stake),
        )

        if cur.rowcount != 1:
            conn.rollback()
            return False, "Nicht genügend Coins."

        cur.execute(
            qmark("""
                INSERT INTO bets
                (username,fixture_id,league,match_date,home_team,away_team,
                 selection,stake,odds,status,payout,result,created_at,settled_at)
                VALUES (?,?,?,?,?,?,?,?,?,'Offen',0,'',?,'')
            """),
            (
                username,
                str(fixture.get("Fixture-ID", "")),
                str(fixture["Liga"]),
                str(fixture["Datum"]),
                str(fixture["Heimteam"]),
                str(fixture["Auswärtsteam"]),
                selection,
                stake,
                float(odds),
                utc_text(),
            ),
        )

        conn.commit()
        return True, "Tipp erfolgreich platziert!"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
