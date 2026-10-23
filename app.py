
import os
import math
import hmac
import hashlib
import secrets
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# KICKPREDICT AI – Fussballanalyse und virtuelle Spielwetten
# Erstellt von Tiago Faruk und Yigit
# Ausschliesslich virtuelles Spielgeld – kein echtes Geld
# ============================================================

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "openfootball/football.json/master"
)

SEASONS = [
    "2026-27", "2025-26", "2024-25", "2023-24",
    "2022-23", "2021-22", "2020-21"
]

LEAGUES = {
    "Premier League 🇬🇧": "en.1.json",
    "La Liga 🇪🇸": "es.1.json",
    "Bundesliga 🇩🇪": "de.1.json",
    "Serie A 🇮🇹": "it.1.json",
    "Ligue 1 🇫🇷": "fr.1.json",
    "Champions League 🏆": None,
    "Europa League 🌍": None,
    "Super League 🇨🇭": None,
}

START_COINS = 1000
MAX_STAKE = 10000
DB_URL = os.environ.get("DATABASE_URL", "").strip()

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
)

st.markdown("""
<style>
.stApp {
    background:linear-gradient(135deg,#07111f,#0b192a 55%,#102a36);
    color:#f4f7fb;
}
[data-testid="stSidebar"] {background:#07111e;}
[data-testid="stHeader"] {background:transparent;}
.hero {
    padding:28px;border-radius:20px;
    background:linear-gradient(115deg,#142943,#12513f);
    border:1px solid #315b68;margin-bottom:22px;
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
div.stButton>button,[data-testid="stDownloadButton"] button {
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


# -------------------- DESIGN --------------------

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


def attribution():
    st.markdown(
        "[Fussballdaten: OpenFootball auf GitHub]"
        "(https://github.com/openfootball/football.json)"
    )


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# -------------------- DATEN LADEN --------------------

@st.cache_data(ttl=600, show_spinner=False)
def load_matches(filename):
    columns = [
        "Datum", "Heim", "Auswärts",
        "Tore_Heim", "Tore_Auswärts", "Saison", "Liga"
    ]

    if not filename:
        return pd.DataFrame(columns=columns), []

    rows, errors = [], []
    session = requests.Session()
    session.headers.update({"User-Agent": "KickPredictAI/2.0"})

    for season in SEASONS:
        url = f"{BASE_URL}/{season}/{filename}"

        try:
            response = session.get(url, timeout=15)
            if response.status_code == 404:
                continue

            response.raise_for_status()
            payload = response.json()

            for match in payload.get("matches", []):
                date = pd.to_datetime(
                    match.get("date"), errors="coerce", utc=True
                )
                if pd.isna(date):
                    continue

                score = match.get("score") or {}
                ft = score.get("ft") if isinstance(score, dict) else None

                if not isinstance(ft, (list, tuple)) or len(ft) != 2:
                    continue
                if ft[0] is None or ft[1] is None:
                    continue

                home, away = match.get("team1"), match.get("team2")
                if not home or not away:
                    continue

                try:
                    hg, ag = int(ft[0]), int(ft[1])
                except (TypeError, ValueError):
                    continue

                # Nur Spiele verwenden, deren Datum bereits vergangen ist.
                if date.to_pydatetime() > datetime.now(timezone.utc):
                    continue

                rows.append({
                    "Datum": date,
                    "Heim": str(home),
                    "Auswärts": str(away),
                    "Tore_Heim": hg,
                    "Tore_Auswärts": ag,
                    "Saison": season,
                    "Liga": filename,
                })

        except (requests.RequestException, ValueError, TypeError) as exc:
            errors.append(f"{season}: {exc}")

    session.close()
    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Datum", "Heim", "Auswärts"]
        )
        df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors


# -------------------- PROGNOSEMODELL --------------------

def team_stats(df, team, venue=None, last_n=20):
    home = df[df["Heim"] == team].copy()
    away = df[df["Auswärts"] == team].copy()

    home["Eigen"] = home["Tore_Heim"]
    home["Gegner"] = home["Tore_Auswärts"]
    away["Eigen"] = away["Tore_Auswärts"]
    away["Gegner"] = away["Tore_Heim"]

    if venue == "home":
        games = home
    elif venue == "away":
        games = away
    else:
        games = pd.concat([home, away], ignore_index=True)

    games = games.sort_values("Datum").tail(last_n)
    if games.empty:
        return None

    wins = int((games["Eigen"] > games["Gegner"]).sum())
    draws = int((games["Eigen"] == games["Gegner"]).sum())
    losses = int((games["Eigen"] < games["Gegner"]).sum())

    return {
        "spiele": len(games),
        "tore": float(games["Eigen"].mean()),
        "gegentreffer": float(games["Gegner"].mean()),
        "siege": wins,
        "remis": draws,
        "niederlagen": losses,
        "punkte": wins * 3 + draws,
        "form": games,
    }


def poisson(goals, expected):
    expected = max(0.05, expected)
    return math.exp(-expected) * expected**goals / math.factorial(goals)


def predict_match(df, home_team, away_team):
    home = team_stats(df, home_team, "home")
    away = team_stats(df, away_team, "away")
    home_all = team_stats(df, home_team)
    away_all = team_stats(df, away_team)

    if not all([home, away, home_all, away_all]):
        return None

    league_home = max(0.1, float(df["Tore_Heim"].mean()))
    league_away = max(0.1, float(df["Tore_Auswärts"].mean()))

    expected_home = (
        (0.65 * home["tore"] + 0.35 * home_all["tore"])
        / league_home
    ) * (0.65 * away["gegentreffer"] + 0.35 * away_all["gegentreffer"])

    expected_away = (
        (0.65 * away["tore"] + 0.35 * away_all["tore"])
        / league_away
    ) * (0.65 * home["gegentreffer"] + 0.35 * home_all["gegentreffer"])

    expected_home = max(0.15, min(4.5, expected_home))
    expected_away = max(0.15, min(4.5, expected_away))

    p_home, p_draw, p_away = 0.0, 0.0, 0.0
    scores = []

    for hg in range(11):
        for ag in range(11):
            prob = poisson(hg, expected_home) * poisson(ag, expected_away)
            scores.append((hg, ag, prob))
            if hg > ag:
                p_home += prob
            elif hg == ag:
                p_draw += prob
            else:
                p_away += prob

    total = p_home + p_draw + p_away
    if total <= 0:
        return None

    probs = [p_home / total, p_draw / total, p_away / total]
    labels = ["Heimsieg", "Unentschieden", "Auswärtssieg"]
    best_score = max(scores, key=lambda x: x[2])

    return {
        "home": probs[0], "draw": probs[1], "away": probs[2],
        "winner": labels[probs.index(max(probs))],
        "score": f"{best_score[0]} : {best_score[1]}",
        "expected_home": expected_home,
        "expected_away": expected_away,
    }


def virtual_odds(result):
    # Virtuelle Quoten aus Modellwahrscheinlichkeiten.
    # Der Aufschlag begrenzt die theoretische Auszahlung.
    margin = 1.12
    return {
        "Heimsieg": round(min(10.0, max(1.10, 1 / max(result["home"], 0.01) * margin)), 2),
        "Unentschieden": round(min(10.0, max(1.10, 1 / max(result["draw"], 0.01) * margin)), 2),
        "Auswärtssieg": round(min(10.0, max(1.10, 1 / max(result["away"], 0.01) * margin)), 2),
    }


def outcome_chart(labels, values, title):
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=["#4be0a0", "#6bbf9a", "#328c6a"],
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        title=title, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#122238", font=dict(color="#f4f7fb"),
        height=350, margin=dict(l=20, r=20, t=55, b=40),
        yaxis=dict(gridcolor="#293f58", rangemode="tozero"),
        xaxis=dict(gridcolor="#293f58"), showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# -------------------- DATENBANK --------------------
# PostgreSQL empfohlen. DATABASE_URL in Streamlit Secrets setzen.
# SQLite-Fallback ist nur für lokale Tests gedacht.

def get_connection():
    if DB_URL:
        import psycopg
        return psycopg.connect(DB_URL, autocommit=False)

    import sqlite3
    return sqlite3.connect("kickpredict_local.db", timeout=15)


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        if DB_URL:
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

        conn.commit()
    finally:
        conn.close()


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt), 300_000
    ).hex()


def create_user(username, password):
    username = username.strip().lower()

    if not 3 <= len(username) <= 24:
        return False, "Der Benutzername muss 3–24 Zeichen haben."
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Nur Buchstaben, Zahlen, _ und - sind erlaubt."
    if len(password) < 8:
        return False, "Das Passwort muss mindestens 8 Zeichen haben."

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    conn = get_connection()

    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, salt, password_hash, coins, created_at) "
            "VALUES (%s, %s, %s, %s, %s)" if DB_URL else
            "INSERT INTO users (username, salt, password_hash, coins, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, salt, password_hash, START_COINS, utc_now())
        )
        conn.commit()
        return True, "Konto erstellt! Du kannst dich jetzt anmelden."
    except Exception:
        conn.rollback()
        return False, "Dieser Benutzername ist bereits vergeben."
    finally:
        conn.close()


def verify_user(username, password):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT salt, password_hash FROM users WHERE username = %s"
            if DB_URL else
            "SELECT salt, password_hash FROM users WHERE username = ?",
            (username.strip().lower(),)
        )
        row = cur.fetchone()
        if not row:
            return False
        return hmac.compare_digest(hash_password(password, row[0]), row[1])
    finally:
        conn.close()


def user_info(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT coins FROM users WHERE username = %s"
            if DB_URL else
            "SELECT coins FROM users WHERE username = ?",
            (username,)
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def get_bets(username):
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT id, league, match_date, home_team, away_team, selection, "
            "stake, odds, status, payout, result, created_at "
            "FROM bets WHERE username = %s ORDER BY id DESC"
            if DB_URL else
            "SELECT id, league, match_date, home_team, away_team, selection, "
            "stake, odds, status, payout, result, created_at "
            "FROM bets WHERE username = ? ORDER BY id DESC",
            conn, params=(username,)
        )
    finally:
        conn.close()


def place_bet(username, league, match_date, home, away, selection, stake, odds):
    if stake < 1 or stake > MAX_STAKE:
        return False, f"Der Einsatz muss zwischen 1 und {MAX_STAKE} Coins liegen."

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Guthaben prüfen und abbuchen – in einer Datenbanktransaktion.
        cur.execute(
            "SELECT coins FROM users WHERE username = %s FOR UPDATE"
            if DB_URL else
            "SELECT coins FROM users WHERE username = ?",
            (username,)
        )
        row = cur.fetchone()
        if not row:
            return False, "Konto nicht gefunden."
        if int(row[0]) < stake:
            return False, "Du hast nicht genügend Coins."

        cur.execute(
            "UPDATE users SET coins = coins - %s WHERE username = %s"
            if DB_URL else
            "UPDATE users SET coins = coins - ? WHERE username = ?",
            (stake, username)
        )

        cur.execute(
            "INSERT INTO bets (username, league, match_date, home_team, away_team, "
            "selection, stake, odds, status, payout, result, created_at, settled_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Offen',0,'',%s,'')"
            if DB_URL else
            "INSERT INTO bets (username, league, match_date, home_team, away_team, "
            "selection, stake, odds, status, payout, result, created_at, settled_at) "
            "VALUES (?,?,?,?,?,?,?,?,'Offen',0,'',?,'')",
            (username, league, match_date, home, away, selection, stake, odds, utc_now())
        )

        conn.commit()
        return True, "Wette erfolgreich platziert!"
    except Exception as exc:
        conn.rollback()
        return False, f"Wette konnte nicht gespeichert werden: {exc}"
    finally:
        conn.close()


def settle_bets(username, all_data):
    """Rechnet offene Wetten ab, sobald ein Endresultat geladen wurde."""
    conn = get_connection()
    settled_count = 0

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, league, match_date, home_team, away_team, selection, "
            "stake, odds FROM bets WHERE username = %s AND status = 'Offen'"
            if DB_URL else
            "SELECT id, league, match_date, home_team, away_team, selection, "
            "stake, odds FROM bets WHERE username = ? AND status = 'Offen'",
            (username,)
        )
        open_bets = cur.fetchall()

        for bet in open_bets:
            bet_id, league, match_date, home, away, selection, stake, odds = bet
            df = all_data.get(league)

            if df is None or df.empty:
                continue

            matches = df[
                (df["Heim"] == home)
                & (df["Auswärts"] == away)
                & (df["Datum"].dt.strftime("%Y-%m-%d") == match_date[:10])
            ]

            if matches.empty:
                continue

            match = matches.iloc[-1]
            hg, ag = int(match["Tore_Heim"]), int(match["Tore_Auswärts"])

            if hg > ag:
                actual = "Heimsieg"
            elif hg == ag:
                actual = "Unentschieden"
            else:
                actual = "Auswärtssieg"

            won = selection == actual
            payout = int(round(int(stake) * float(odds))) if won else 0
            status = "Gewonnen" if won else "Verloren"
            result_text = f"{hg} : {ag}"

            cur.execute(
                "UPDATE bets SET status=%s, payout=%s, result=%s, settled_at=%s "
                "WHERE id=%s AND username=%s AND status='Offen'"
                if DB_URL else
                "UPDATE bets SET status=?, payout=?, result=?, settled_at=? "
                "WHERE id=? AND username=? AND status='Offen'",
                (status, payout, result_text, utc_now(), bet_id, username)
            )

            if won:
                cur.execute(
                    "UPDATE users SET coins=coins+%s WHERE username=%s"
                    if DB_URL else
                    "UPDATE users SET coins=coins+? WHERE username=?",
                    (payout, username)
                )
            settled_count += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return settled_count


# Datenbank initialisieren. Für die Demo wird bei fehlender
# DATABASE_URL eine lokale SQLite-Datei verwendet.
try:
    init_db()
except Exception as exc:
    st.error(
        "Die Datenbank konnte nicht initialisiert werden. "
        "Prüfe DATABASE_URL und die Datenbankverbindung."
    )
    st.exception(exc)
    st.stop()


# -------------------- LOGIN / REGISTRIERUNG --------------------

def login_screen():
    hero("Willkommen bei KickPredict AI", "Melde dich an oder erstelle dein kostenloses Konto.")

    tab_login, tab_register = st.tabs(["🔐 Anmelden", "✨ Konto erstellen"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Benutzername").strip().lower()
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", use_container_width=True)

        if submitted:
            if verify_user(username, password):
                st.session_state["user"] = username
                st.rerun()
            else:
                st.error("Benutzername oder Passwort ist falsch.")

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Neuer Benutzername")
            new_password = st.text_input("Passwort (mindestens 8 Zeichen)", type="password")
            confirm = st.text_input("Passwort wiederholen", type="password")
            registered = st.form_submit_button("Konto erstellen", use_container_width=True)

        if registered:
            if new_password != confirm:
                st.error("Die Passwörter stimmen nicht überein.")
            else:
                ok, message = create_user(new_user, new_password)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

    st.info("Jedes Konto startet mit 1'000 virtuellen Coins. Kein echtes Geld.")
    attribution()


if "user" not in st.session_state:
    login_screen()
    st.stop()

username = st.session_state["user"]


# -------------------- NAVIGATION --------------------

st.sidebar.markdown("## ⚽ KickPredict AI")
st.sidebar.caption(f"Angemeldet als **{username}**")
st.sidebar.metric("Dein Spielgeld", f"{user_info(username):,} Coins")

page = st.sidebar.radio("Navigation", [
    "🏠 Home",
    "🔮 Spielprognose",
    "🎰 Virtuelle Wetten",
    "💼 Mein Wettkonto",
    "🧠 Team-Analyse",
    "📊 Statistiken",
    "📅 Ergebnisse",
    "ℹ️ Über uns",
])

if st.sidebar.button("🚪 Abmelden", use_container_width=True):
    st.session_state.pop("user", None)
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("**Erstellt von**")
st.sidebar.write("Tiago Faruk und Yigit")
st.sidebar.caption("Nur virtuelles Spielgeld. Keine Echtgeldwetten.")


# -------------------- DATEN LADEN --------------------

all_data = {}
load_errors = {}

for name, filename in LEAGUES.items():
    if filename:
        data, errors = load_matches(filename)
        all_data[name] = data
        if errors:
            load_errors[name] = errors

# Offene Wetten nach jedem Seitenaufruf abgleichen.
try:
    settle_bets(username, all_data)
except Exception as exc:
    st.warning(f"Automatische Abrechnung vorübergehend nicht möglich: {exc}")


# -------------------- HOME --------------------

if page == "🏠 Home":
    hero("KickPredict AI", "Fussball analysieren. Prognosen erstellen. Virtuelle Coins sammeln.")

    a, b, c = st.columns(3)
    with a:
        metric("Dein Guthaben", f"{user_info(username):,}", "Virtuelle Coins")
    with b:
        bets = get_bets(username)
        metric("Deine Wetten", str(len(bets)), "Alle bisherigen Wetten")
    with c:
        open_count = int((bets["status"] == "Offen").sum()) if not bets.empty else 0
        metric("Offene Wetten", str(open_count), "Warten auf Resultate")

    st.markdown("### Deine Plattform")
    st.markdown("""
    <div class="panel"><h3>🎰 Virtuelle Wetten</h3>
    Wähle einen Ausgang, setze Spielgeld und verfolge deine Ergebnisse.</div>
    <div class="panel"><h3>🔮 Spielprognose</h3>
    Berechne die Wahrscheinlichkeiten für Heimsieg, Remis und Auswärtssieg.</div>
    <div class="panel"><h3>💼 Mein Wettkonto</h3>
    Sieh dein Guthaben, deine Treffer und deinen Gewinn-/Verlustverlauf.</div>
    """, unsafe_allow_html=True)

    st.info("Die Prognosen sind statistische Schätzungen. Eine Trefferquote wird nicht garantiert.")
    attribution()


# -------------------- VIRTUELLE WETTEN --------------------

elif page == "🎰 Virtuelle Wetten":
    hero("Virtuelle Wetten", "Setze Coins auf Fussballspiele – ohne echtes Geld.")

    league_name = st.selectbox(
        "Liga wählen",
        [name for name, filename in LEAGUES.items() if filename],
        key="bet_league",
    )
    df = all_data.get(league_name, pd.DataFrame())

    if df.empty:
        st.warning("Für diese Liga sind aktuell keine Resultate verfügbar.")
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))
    st.caption(
        "Die Quoten sind Modellwerte, keine echten Buchmacherquoten. "
        "Eine Wette wird erst abgerechnet, wenn ein passendes Resultat in den Daten erscheint."
    )

    # Das vorhandene Dataset enthält überwiegend abgeschlossene Spiele.
    # Daher werden nur anstehende Begegnungen angezeigt, wenn Datenquelle
    # und Modell sie tatsächlich liefern. Keine erfundenen Fixtures.
    st.markdown("### Spiel auswählen")

    # Zukunftsspiele aus derselben Datenquelle, falls vorhanden.
    # Historische Spiele dürfen nicht als kommende Spiele angeboten werden.
    upcoming = df[df["Datum"] > pd.Timestamp.now(tz="UTC")]

    if upcoming.empty:
        st.warning(
            "Die aktuelle Datenquelle enthält keine kommenden Spiele für diese Liga. "
            "Deshalb wird keine erfundene Begegnung zum Wetten angezeigt. "
            "Sobald eine zukünftige Spielplan-Datenquelle ergänzt wird, erscheinen hier echte Fixtures."
        )
        st.markdown("### Deine bisherigen Wetten")
        bets = get_bets(username)
        if not bets.empty:
            st.dataframe(bets, use_container_width=True, hide_index=True)
        st.stop()

    upcoming = upcoming.sort_values("Datum")
    upcoming["Anzeige"] = upcoming.apply(
        lambda r: (
            f"{r['Datum'].strftime('%d.%m.%Y')} · "
            f"{r['Heim']} vs. {r['Auswärts']}"
        ),
        axis=1,
    )
    selected_label = st.selectbox("Begegnung", upcoming["Anzeige"].tolist())
    match = upcoming[upcoming["Anzeige"] == selected_label].iloc[0]

    home, away = str(match["Heim"]), str(match["Auswärts"])
    match_date = match["Datum"].strftime("%Y-%m-%d")

    result = predict_match(df[df["Datum"] < match["Datum"]], home, away)

    if result is None:
        st.warning("Für diese Begegnung fehlen genügend historische Teamdaten.")
        st.stop()

    odds = virtual_odds(result)

    st.markdown(f"### {home} vs. {away}")
    a, b, c = st.columns(3)
    with a:
        metric("Heimsieg", f"{result['home']*100:.1f}%", f"Quote {odds['Heimsieg']:.2f}")
    with b:
        metric("Unentschieden", f"{result['draw']*100:.1f}%", f"Quote {odds['Unentschieden']:.2f}")
    with c:
        metric("Auswärtssieg", f"{result['away']*100:.1f}%", f"Quote {odds['Auswärtssieg']:.2f}")

    with st.form("place_bet_form"):
        selection = st.selectbox("Dein Tipp", ["Heimsieg", "Unentschieden", "Auswärtssieg"])
        stake = st.number_input(
            "Einsatz in Coins",
            min_value=1,
            max_value=MAX_STAKE,
            value=100,
            step=10,
        )
        chosen_odds = odds[selection]
        possible_payout = int(round(stake * chosen_odds))
        st.write(f"**Virtuelle Quote:** {chosen_odds:.2f}")
        st.write(f"**Mögliche Gesamtauszahlung:** {possible_payout:,} Coins")
        st.write(f"**Möglicher Nettogewinn:** {possible_payout - int(stake):,} Coins")
        confirmed = st.checkbox("Ich bestätige, dass dies nur virtuelles Spielgeld ist.")
        submit = st.form_submit_button("🎯 Virtuelle Wette platzieren", use_container_width=True)

    if submit:
        if not confirmed:
            st.error("Bitte bestätige zuerst, dass es um virtuelles Spielgeld geht.")
        else:
            ok, message = place_bet(
                username, league_name, match_date,
                home, away, selection, int(stake), float(chosen_odds)
            )
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.markdown("### Dein Wettverlauf")
    bets = get_bets(username)
    if bets.empty:
        st.info("Du hast noch keine Wetten platziert.")
    else:
        st.dataframe(bets, use_container_width=True, hide_index=True)


# -------------------- MEIN WETTKONTO --------------------

elif page == "💼 Mein Wettkonto":
    hero("Mein Wettkonto", "Dein persönliches Spielgeld, deine Resultate und deine Statistik.")

    bets = get_bets(username)
    coins = user_info(username)

    settled = bets[bets["status"].isin(["Gewonnen", "Verloren"])] if not bets.empty else pd.DataFrame()
    won = int((settled["status"] == "Gewonnen").sum()) if not settled.empty else 0
    lost = int((settled["status"] == "Verloren").sum()) if not settled.empty else 0
    total_staked = int(settled["stake"].sum()) if not settled.empty else 0
    total_payout = int(settled["payout"].sum()) if not settled.empty else 0
    net = total_payout - total_staked

    a, b, c, d = st.columns(4)
    with a:
        metric("Kontostand", f"{coins:,}", "Coins")
    with b:
        metric("Gewonnen", str(won), "Abgerechnete Wetten")
    with c:
        metric("Verloren", str(lost), "Abgerechnete Wetten")
    with d:
        metric("Netto", f"{net:+,}", "Coins aus abgerechneten Wetten")

    st.markdown("### Alle Wetten")
    if bets.empty:
        st.info("Noch keine Wetten vorhanden.")
    else:
        display = bets.copy()
        display["Potenzieller/effektiver Nettogewinn"] = display.apply(
            lambda r: (
                int(r["payout"]) - int(r["stake"])
                if r["status"] == "Gewonnen"
                else -int(r["stake"])
                if r["status"] == "Verloren"
                else int(round(int(r["stake"]) * float(r["odds"]))) - int(r["stake"])
            ),
            axis=1,
        )
        st.dataframe(display, use_container_width=True, hide_index=True)

        if not settled.empty:
            chart = settled.groupby("status").size().reset_index(name="Anzahl")
            fig = px.pie(chart, names="status", values="Anzahl", hole=0.55)
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f4f7fb"),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.download_button(
            "⬇️ Wettverlauf als CSV herunterladen",
            data=bets.to_csv(index=False).encode("utf-8-sig"),
            file_name="kickpredict_wettverlauf.csv",
            mime="text/csv",
        )

    st.caption("Offene Wetten werden beim nächsten Seitenaufruf erneut auf verfügbare Resultate geprüft.")


# -------------------- SPIELPROGNOSE --------------------

elif page == "🔮 Spielprognose":
    hero(page, "Statistische Einschätzungen für ausgewählte Teams.")

    league_name = st.selectbox(
        "Liga wählen", [n for n, f in LEAGUES.items() if f], key="pred_league"
    )
    df = all_data.get(league_name, pd.DataFrame())

    if df.empty:
        st.warning("Keine Daten verfügbar.")
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))
    a, b = st.columns(2)
    with a:
        home = st.selectbox("Heimteam", teams)
    with b:
        away = st.selectbox("Auswärtsteam", [t for t in teams if t != home])

    if st.button("🚀 Prognose berechnen", use_container_width=True):
        result = predict_match(df, home, away)
        if result:
            st.session_state["prediction"] = result
            st.session_state["prediction_teams"] = (home, away)
        else:
            st.error("Nicht genügend Daten für diese Prognose.")

    if "prediction" in st.session_state:
        result = st.session_state["prediction"]
        home_saved, away_saved = st.session_state["prediction_teams"]
        st.subheader(f"{home_saved} vs. {away_saved}")

        a, b, c = st.columns(3)
        with a:
            metric("Heimsieg", f"{result['home']*100:.1f}%")
        with b:
            metric("Unentschieden", f"{result['draw']*100:.1f}%")
        with c:
            metric("Auswärtssieg", f"{result['away']*100:.1f}%")

        outcome_chart(
            ["Heimsieg", "Unentschieden", "Auswärtssieg"],
            [result["home"]*100, result["draw"]*100, result["away"]*100],
            "Wahrscheinlichkeiten",
        )
        st.write("**Wahrscheinlichster Ausgang:**", result["winner"])
        st.write("**Geschätzter Spielstand:**", result["score"])
        st.caption(
            f"Erwartete Tore: {result['expected_home']:.2f} – "
            f"{result['expected_away']:.2f}"
        )


# -------------------- TEAM-ANALYSE --------------------

elif page == "🧠 Team-Analyse":
    hero(page, "Form, Tore und Heim-/Auswärtsleistung.")

    league_name = st.selectbox(
        "Liga wählen", [n for n, f in LEAGUES.items() if f], key="team_league"
    )
    df = all_data.get(league_name, pd.DataFrame())
    if df.empty:
        st.warning("Keine Daten verfügbar.")
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))
    team = st.selectbox("Team auswählen", teams)
    stats = team_stats(df, team)

    if stats:
        a, b, c, d = st.columns(4)
        with a:
            metric("Spiele", str(stats["spiele"]))
        with b:
            metric("Ø Tore", f"{stats['tore']:.2f}")
        with c:
            metric("Ø Gegentore", f"{stats['gegentreffer']:.2f}")
        with d:
            metric("Punkte", str(stats["punkte"]))

        form = [
            "S" if r["Eigen"] > r["Gegner"]
            else "U" if r["Eigen"] == r["Gegner"] else "N"
            for _, r in stats["form"].iterrows()
        ]
        st.write("Letzte Spiele:", " – ".join(form))
        st.caption("S = Sieg · U = Unentschieden · N = Niederlage")

        home_stats = team_stats(df, team, "home")
        away_stats = team_stats(df, team, "away")
        comparison = pd.DataFrame({
            "Kategorie": ["Ø Tore", "Ø Gegentore"],
            "Heim": [
                home_stats["tore"] if home_stats else 0,
                home_stats["gegentreffer"] if home_stats else 0,
            ],
            "Auswärts": [
                away_stats["tore"] if away_stats else 0,
                away_stats["gegentreffer"] if away_stats else 0,
            ],
        })
        st.bar_chart(comparison.set_index("Kategorie"))


# -------------------- STATISTIKEN --------------------

elif page == "📊 Statistiken":
    hero(page, "Ligaweite Tore und Spielausgänge.")

    league_name = st.selectbox(
        "Liga wählen", [n for n, f in LEAGUES.items() if f], key="stats_league"
    )
    df = all_data.get(league_name, pd.DataFrame())
    if df.empty:
        st.warning("Keine Daten verfügbar.")
        st.stop()

    total_goals = int(df["Tore_Heim"].sum() + df["Tore_Auswärts"].sum())
    home_wins = int((df["Tore_Heim"] > df["Tore_Auswärts"]).sum())
    draws = int((df["Tore_Heim"] == df["Tore_Auswärts"]).sum())
    away_wins = int((df["Tore_Heim"] < df["Tore_Auswärts"]).sum())

    a, b, c, d = st.columns(4)
    with a:
        metric("Spiele", str(len(df)))
    with b:
        metric("Tore", str(total_goals))
    with c:
        metric("Tore pro Spiel", f"{total_goals/len(df):.2f}")
    with d:
        metric("Heimsiege", f"{home_wins/len(df)*100:.1f}%")

    outcome_chart(
        ["Heimsieg", "Remis", "Auswärtssieg"],
        [home_wins, draws, away_wins], "Spielausgänge"
    )

    totals = (
        df.groupby("Heim")["Tore_Heim"].sum()
        .add(df.groupby("Auswärts")["Tore_Auswärts"].sum(), fill_value=0)
        .sort_values(ascending=False).head(10)
    )
    chart_df = totals.rename("Tore").reset_index()
    chart_df.columns = ["Team", "Tore"]
    fig = px.bar(
        chart_df.sort_values("Tore"), x="Tore", y="Team",
        orientation="h", color_discrete_sequence=["#4be0a0"]
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#122238",
        font=dict(color="#f4f7fb"),
    )
    st.plotly_chart(fig, use_container_width=True)


# -------------------- ERGEBNISSE --------------------

elif page == "📅 Ergebnisse":
    hero(page, "Abgeschlossene Spiele durchsuchen und exportieren.")

    league_name = st.selectbox(
        "Liga wählen", [n for n, f in LEAGUES.items() if f], key="results_league"
    )
    df = all_data.get(league_name, pd.DataFrame())
    if df.empty:
        st.warning("Keine Daten verfügbar.")
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))
    team_filter = st.selectbox("Team filtern", ["Alle Teams"] + teams)
    seasons = sorted(df["Saison"].unique().tolist(), reverse=True)
    season_filter = st.selectbox("Saison", ["Alle Saisons"] + seasons)

    results = df.copy()
    if team_filter != "Alle Teams":
        results = results[
            (results["Heim"] == team_filter) |
            (results["Auswärts"] == team_filter)
        ]
    if season_filter != "Alle Saisons":
        results = results[results["Saison"] == season_filter]

    results["Datum"] = results["Datum"].dt.strftime("%d.%m.%Y")
    results["Resultat"] = (
        results["Tore_Heim"].astype(str) + " : " +
        results["Tore_Auswärts"].astype(str)
    )
    display = results[
        ["Datum", "Heim", "Resultat", "Auswärts", "Saison"]
    ].sort_values("Datum", ascending=False)

    st.write(f"**{len(display)} Resultate gefunden**")
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ CSV exportieren",
        data=display.to_csv(index=False).encode("utf-8-sig"),
        file_name="kickpredict_ergebnisse.csv",
        mime="text/csv",
    )


# -------------------- ÜBER UNS --------------------

elif page == "ℹ️ Über uns":
    hero(page, "Das Projekt hinter KickPredict AI.")
    st.markdown("### Unsere Idee")
    st.write(
        "KickPredict AI analysiert vergangene Fussballresultate und erstellt "
        "statistische Prognosen. Das virtuelle Wettkonto dient nur zum "
        "spielerischen Testen von Prognosen mit Spielgeld."
    )
    st.markdown("### Erstellt von")
    st.markdown("## Tiago Faruk und Yigit")
    st.info(
        "Es gibt keine Echtgeldwetten, keine echten Einzahlungen und "
        "keine Garantie für die Richtigkeit einer Prognose."
    )

st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Virtual Coins · No real money")
