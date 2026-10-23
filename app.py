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
            # Bestehende SQLite-Datenbanken aktualisieren.
            cur.execute("PRAGMA table_info(bets)")
            columns = [row[1] for row in cur.fetchall()]
            if "fixture_id" not in columns:
                cur.execute(
                    "ALTER TABLE bets ADD COLUMN fixture_id TEXT NOT NULL DEFAULT ''"
                )

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
        return False, "Das Spiel hat bereits begonnen."

    conn = connect_db()
    try:
        cur = conn.cursor()

        sql = (
            "SELECT coins FROM users WHERE username=? FOR UPDATE"
            if DATABASE_URL
            else "SELECT coins FROM users WHERE username=?"
        )
        cur.execute(qmark(sql), (username,))
        row = cur.fetchone()

        if not row:
            return False, "Konto nicht gefunden."

        if int(row[0]) < stake:
            return False, "Du hast nicht genügend Coins."

        cur.execute(
            qmark("UPDATE users SET coins=coins-? WHERE username=?"),
            (stake, username),
        )

        cur.execute(
            qmark("""
                INSERT INTO bets
                (username,fixture_id,league,match_date,home_team,away_team,
                 selection,stake,odds,status,payout,result,created_at,settled_at)
                VALUES (?,?,?,?,?,?,?,?,?,'Offen',0,'',?,'')
            """),
            (
                username,
                str(fixture["Match_ID"]),
                fixture["Liga"],
                kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
                fixture["Heim"],
                fixture["Auswärts"],
                selection,
                stake,
                float(odds),
                utc_text(),
            ),
        )

        conn.commit()
        return True, "Wette erfolgreich platziert!"
    except Exception as exc:
        conn.rollback()
        return False, f"Wette konnte nicht gespeichert werden: {exc}"
    finally:
        conn.close()


# -------------------- FUSSBALLDATEN --------------------

@st.cache_data(ttl=300, show_spinner=False)
def api_matches(date_from, date_to):
    if not FOOTBALL_API_KEY:
        return [], "FOOTBALL_DATA_API_KEY fehlt."

    rows = []
    errors = []
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}

    for league_name, (code, _) in LEAGUES.items():
        try:
            response = requests.get(
                f"https://api.football-data.org/v4/competitions/{code}/matches",
                headers=headers,
                params={"dateFrom": date_from, "dateTo": date_to},
                timeout=20,
            )
            response.raise_for_status()

            for match in response.json().get("matches", []):
                home = match.get("homeTeam") or {}
                away = match.get("awayTeam") or {}

                if not home.get("name") or not away.get("name"):
                    continue

                score = match.get("score") or {}
                full_time = score.get("fullTime") or {}
                kickoff = pd.to_datetime(
                    match.get("utcDate"),
                    errors="coerce",
                    utc=True,
                )

                if pd.isna(kickoff):
                    continue

                rows.append({
                    "Datum": kickoff,
                    "Heim": home["name"],
                    "Auswärts": away["name"],
                    "Tore_Heim": full_time.get("home"),
                    "Tore_Auswärts": full_time.get("away"),
                    "Liga": league_name,
                    "Status": match.get("status", ""),
                    "Match_ID": str(match.get("id", "")),
                })

        except requests.RequestException as exc:
            errors.append(f"{league_name}: {exc}")

    return rows, "\n".join(errors) if errors else None


@st.cache_data(ttl=900, show_spinner=False)
def historical_data(filename):
    rows = []

    for season in SEASONS:
        try:
            response = requests.get(
                f"{BASE_URL}/{season}/{filename}",
                timeout=15,
            )

            if response.status_code == 404:
                continue

            response.raise_for_status()

            for match in response.json().get("matches", []):
                date = pd.to_datetime(
                    match.get("date"),
                    errors="coerce",
                    utc=True,
                )
                score = match.get("score") or {}
                ft = score.get("ft") if isinstance(score, dict) else None

                if (
                    pd.isna(date)
                    or not isinstance(ft, (list, tuple))
                    or len(ft) != 2
                    or ft[0] is None
                    or ft[1] is None
                ):
                    continue

                if date > pd.Timestamp.now(tz="UTC"):
                    continue

                rows.append({
                    "Datum": date,
                    "Heim": str(match.get("team1", "")),
                    "Auswärts": str(match.get("team2", "")),
                    "Tore_Heim": int(ft[0]),
                    "Tore_Auswärts": int(ft[1]),
                    "Saison": season,
                })

        except (requests.RequestException, ValueError, TypeError):
            continue

    df = pd.DataFrame(rows)

    if not df.empty:
        df = (
            df.drop_duplicates(subset=["Datum", "Heim", "Auswärts"])
            .sort_values("Datum")
        )

    return df


# -------------------- PROGNOSEMODELL --------------------

def team_stats(df, team, venue=None, last_n=20):
    if df.empty:
        return None

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
    }


def poisson(goals, expected):
    expected = max(0.05, float(expected))
    return math.exp(-expected) * expected**goals / math.factorial(goals)


def predict_match(df, home_team, away_team):
    """
    Berechnet die Wahrscheinlichkeiten für Heimsieg, Unentschieden
    und Auswärtssieg anhand eines Poisson-Tormodells.
    """

    if df.empty:
        return None

    home = team_stats(df, home_team, "home")
    away = team_stats(df, away_team, "away")
    home_all = team_stats(df, home_team)
    away_all = team_stats(df, away_team)

    if any(x is None for x in [home, away, home_all, away_all]):
        return None

    league_home = max(0.1, float(df["Tore_Heim"].mean()))
    league_away = max(0.1, float(df["Tore_Auswärts"].mean()))

    # Erwartete Tore beider Teams
    eh = (
        (0.65 * home["tore"] + 0.35 * home_all["tore"])
        / league_home
    ) * (
        0.65 * away["gegentreffer"]
        + 0.35 * away_all["gegentreffer"]
    )

    ea = (
        (0.65 * away["tore"] + 0.35 * away_all["tore"])
        / league_away
    ) * (
        0.65 * home["gegentreffer"]
        + 0.35 * home_all["gegentreffer"]
    )

    eh = max(0.15, min(4.5, eh))
    ea = max(0.15, min(4.5, ea))

    # WICHTIG: Alle drei Wahrscheinlichkeiten werden korrekt addiert.
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    scores = []

    for hg in range(11):
        for ag in range(11):
            probability = poisson(hg, eh) * poisson(ag, ea)
            scores.append((hg, ag, probability))

            if hg > ag:
                p_home += probability
            elif hg == ag:
                # KORREKTUR: Unentschieden-Wahrscheinlichkeit addieren!
                p_draw += probability
            else:
                p_away += probability

    # Die Wahrscheinlichkeiten normalisieren, damit sie zusammen 100 % ergeben.
    total = p_home + p_draw + p_away

    if total <= 0:
        return None

    p_home /= total
    p_draw /= total
    p_away /= total

    probabilities = [p_home, p_draw, p_away]
    labels = ["Heimsieg", "Unentschieden", "Auswärtssieg"]
    best_score = max(scores, key=lambda x: x[2])

    return {
        "home": p_home,
        "draw": p_draw,
        "away": p_away,
        "winner": labels[probabilities.index(max(probabilities))],
        "score": f"{best_score[0]} : {best_score[1]}",
        "expected_home": eh,
        "expected_away": ea,
    }


def virtual_odds(result):
    margin = 1.12

    return {
        "Heimsieg": round(
            min(10, max(1.10, margin / max(result["home"], 0.01))), 2
        ),
        "Unentschieden": round(
            min(10, max(1.10, margin / max(result["draw"], 0.01))), 2
        ),
        "Auswärtssieg": round(
            min(10, max(1.10, margin / max(result["away"], 0.01))), 2
        ),
    }


# -------------------- WETTEN ABRECHNEN --------------------

def settle_bets(username, results_by_id):
    conn = connect_db()
    count = 0

    try:
        cur = conn.cursor()
        cur.execute(
            qmark("""
                SELECT id,fixture_id,selection,stake,odds
                FROM bets
                WHERE username=? AND status='Offen'
            """),
            (username,),
        )

        for bet_id, fixture_id, selection, stake, odds in cur.fetchall():
            match = results_by_id.get(str(fixture_id))

            if not match or match["Status"] != "FINISHED":
                continue

            hg = match["Tore_Heim"]
            ag = match["Tore_Auswärts"]

            if hg is None or ag is None:
                continue

            actual = (
                "Heimsieg" if hg > ag
                else "Unentschieden" if hg == ag
                else "Auswärtssieg"
            )

            won = selection == actual
            payout = int(round(int(stake) * float(odds))) if won else 0
            status = "Gewonnen" if won else "Verloren"

            cur.execute(
                qmark("""
                    UPDATE bets
                    SET status=?,payout=?,result=?,settled_at=?
                    WHERE id=? AND username=? AND status='Offen'
                """),
                (
                    status,
                    payout,
                    f"{hg} : {ag}",
                    utc_text(),
                    bet_id,
                    username,
                ),
            )

            if cur.rowcount and won:
                cur.execute(
                    qmark("UPDATE users SET coins=coins+? WHERE username=?"),
                    (payout, username),
                )

            count += cur.rowcount

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return count


# -------------------- DATENBANK STARTEN --------------------

try:
    init_db()
except Exception as exc:
    st.error("Datenbankfehler. Prüfe DATABASE_URL und die Datenbank.")
    st.exception(exc)
    st.stop()


# -------------------- LOGIN --------------------

def login_screen():
    hero(
        "Willkommen bei KickPredict AI",
        "Melde dich an oder erstelle dein Konto.",
    )

    tab1, tab2 = st.tabs(["🔐 Anmelden", "✨ Konto erstellen"])

    with tab1:
        with st.form("login"):
            username = st.text_input("Benutzername").strip().lower()
            password = st.text_input("Passwort", type="password")
            submit = st.form_submit_button(
                "Anmelden", use_container_width=True
            )

        if submit:
            if verify_user(username, password):
                st.session_state["user"] = username
                st.rerun()
            else:
                st.error("Benutzername oder Passwort ist falsch.")

    with tab2:
        with st.form("register"):
            new_user = st.text_input("Neuer Benutzername")
            new_password = st.text_input(
                "Passwort (mindestens 8 Zeichen)", type="password"
            )
            confirm = st.text_input(
                "Passwort wiederholen", type="password"
            )
            submit = st.form_submit_button(
                "Konto erstellen", use_container_width=True
            )

        if submit:
            if new_password != confirm:
                st.error("Die Passwörter stimmen nicht überein.")
            else:
                ok, message = create_user(new_user, new_password)
                (st.success if ok else st.error)(message)

    st.info("Jedes Konto startet mit 1'000 virtuellen Coins.")
    attribution()


if "user" not in st.session_state:
    login_screen()
    st.stop()

username = st.session_state["user"]

st.sidebar.markdown("## ⚽ KickPredict AI")
st.sidebar.caption(f"Angemeldet als **{username}**")
st.sidebar.metric("Dein Spielgeld", f"{user_info(username):,} Coins")

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Home",
        "🎰 Virtuelle Wetten",
        "💼 Mein Wettkonto",
        "🔮 Spielprognose",
        "🧠 Team-Analyse",
        "📊 Statistiken",
        "ℹ️ Über uns",
    ],
)

if st.sidebar.button("🚪 Abmelden", use_container_width=True):
    st.session_state.pop("user", None)
    st.rerun()

st.sidebar.markdown("**Erstellt von**")
st.sidebar.write("Tiago Faruk und Yigit")

# Kommende Spiele und kürzlich gespielte Partien laden.
today = now_utc().date()

api_rows, api_error = api_matches(
    (today - timedelta(days=30)).isoformat(),
    (today + timedelta(days=3)).isoformat(),
)

results_by_id = {
    str(row["Match_ID"]): row
    for row in api_rows
}

try:
    settle_bets(username, results_by_id)
except Exception as exc:
    st.warning(f"Abrechnung aktuell nicht möglich: {exc}")


# -------------------- HOME --------------------

if page == "🏠 Home":
    hero(
        "KickPredict AI",
        "Fussball analysieren. Prognosen erstellen. Virtuelle Coins sammeln.",
    )

    bets = get_bets(username)

    a, b, c = st.columns(3)

    with a:
        metric("Dein Guthaben", f"{user_info(username):,}", "Virtuelle Coins")

    with b:
        metric("Alle Wetten", str(len(bets)))

    with c:
        open_bets = int((bets["status"] == "Offen").sum()) if not bets.empty else 0
        metric("Offene Wetten", str(open_bets))

    st.markdown("### Willkommen")
    st.write(
        "Wähle eine Partie, schau dir die Modellquoten an "
        "und setze virtuelle Coins."
    )
    st.info("Prognosen sind Schätzungen und garantieren keine Trefferquote.")
    attribution()


# -------------------- VIRTUELLE WETTEN --------------------

elif page == "🎰 Virtuelle Wetten":
    hero(
        "Virtuelle Wetten",
        "Wähle Spiele der nächsten 3 Tage und setze deine Coins.",
    )

    if not FOOTBALL_API_KEY:
        st.error("Es fehlt der API-Schlüssel für kommende Spiele und Resultate.")
        st.markdown(
            "Registrierung: [football-data.org]"
            "(https://www.football-data.org/client/register)"
        )
        st.code('FOOTBALL_DATA_API_KEY = "DEIN_API_SCHLUESSEL"')
        st.stop()

    if api_error:
        st.warning(f"Einige Ligen konnten nicht geladen werden:\n\n{api_error}")

    now = pd.Timestamp.now(tz="UTC")

    fixtures = [
        row for row in api_rows
        if row["Status"] in ("SCHEDULED", "TIMED")
        and now <= row["Datum"] <= now + pd.Timedelta(days=3)
    ]

    if not fixtures:
        st.warning(
            "Für die nächsten drei Tage wurden keine verfügbaren Spiele gefunden."
        )
    else:
        chosen_league = st.selectbox("Liga wählen", list(LEAGUES))
        league_fixtures = [
            m for m in fixtures if m["Liga"] == chosen_league
        ]

        if not league_fixtures:
            st.info("In dieser Liga gibt es im gewählten Zeitraum keine kommenden Spiele.")
        else:
            labels = [
                f"{m['Datum'].tz_convert('Europe/Zurich').strftime('%d.%m. %H:%M')} · "
                f"{m['Heim']} – {m['Auswärts']}"
                for m in league_fixtures
            ]

            selected = st.selectbox(
                "Spiel auswählen",
                range(len(labels)),
                format_func=lambda i: labels[i],
            )
            match = league_fixtures[selected]

            hist = historical_data(LEAGUES[chosen_league][1])

            if hist.empty:
                st.warning("Historische Resultate sind momentan nicht verfügbar.")
                st.stop()

            hist = hist[hist["Datum"] < match["Datum"]]
            prediction = predict_match(hist, match["Heim"], match["Auswärts"])

            if not prediction:
                st.warning(
                    "Für mindestens eines der Teams fehlen genügend historische Daten."
                )
                st.stop()

            odds = virtual_odds(prediction)

            st.subheader(f"{match['Heim']} vs. {match['Auswärts']}")

            local_time = match["Datum"].tz_convert("Europe/Zurich")
            st.caption(
                f"Anpfiff: {local_time.strftime('%d.%m.%Y, %H:%M')} Schweizer Zeit"
            )

            a, b, c = st.columns(3)

            with a:
                metric(
                    "1 · Heimsieg",
                    f"{prediction['home'] * 100:.1f}%",
                    f"Quote {odds['Heimsieg']:.2f}",
                )

            with b:
                metric(
                    "X · Unentschieden",
                    f"{prediction['draw'] * 100:.1f}%",
                    f"Quote {odds['Unentschieden']:.2f}",
                )

            with c:
                metric(
                    "2 · Auswärtssieg",
                    f"{prediction['away'] * 100:.1f}%",
                    f"Quote {odds['Auswärtssieg']:.2f}",
                )

            with st.form("place_bet"):
                selection = st.radio(
                    "Dein Tipp",
                    ["Heimsieg", "Unentschieden", "Auswärtssieg"],
                    horizontal=True,
                )

                stake = st.number_input(
                    "Einsatz in Coins",
                    min_value=1,
                    max_value=MAX_STAKE,
                    value=100,
                    step=10,
                )

                st.write(f"Quote: **{odds[selection]:.2f}**")
                st.write(
                    "Mögliche Gesamtauszahlung: "
                    f"**{int(round(stake * odds[selection])):,} Coins**"
                )

                confirmed = st.checkbox(
                    "Ich bestätige: Das ist nur virtuelles Spielgeld."
                )

                submit = st.form_submit_button(
                    "🎯 Wette platzieren",
                    use_container_width=True,
                )

            if submit:
                if not confirmed:
                    st.error(
                        "Bitte bestätige zuerst die Nutzung von virtuellem Spielgeld."
                    )
                else:
                    ok, message = place_bet(
                        username,
                        match,
                        selection,
                        int(stake),
                        odds[selection],
                    )
                    (st.success if ok else st.error)(message)

                    if ok:
                        st.rerun()

    st.markdown("### Deine letzten Wetten")
    bets = get_bets(username)

    if bets.empty:
        st.info("Du hast noch keine Wetten platziert.")
    else:
        st.dataframe(
            bets.drop(columns=["fixture_id"], errors="ignore"),
            use_container_width=True,
            hide_index=True,
        )


# -------------------- WETTKONTO --------------------

elif page == "💼 Mein Wettkonto":
    hero(
        "Mein Wettkonto",
        "Deine virtuellen Coins und deine Wettstatistik.",
    )

    bets = get_bets(username)

    settled = (
        bets[bets["status"].isin(["Gewonnen", "Verloren"])]
        if not bets.empty else pd.DataFrame()
    )

    won = int((settled["status"] == "Gewonnen").sum()) if not settled.empty else 0
    lost = int((settled["status"] == "Verloren").sum()) if not settled.empty else 0
    net = int(settled["payout"].sum() - settled["stake"].sum()) if not settled.empty else 0

    a, b, c, d = st.columns(4)

    with a:
        metric("Guthaben", f"{user_info(username):,}", "Coins")

    with b:
        metric("Gewonnen", str(won))

    with c:
        metric("Verloren", str(lost))

    with d:
        metric("Netto", f"{net:+,}", "Coins")

    if bets.empty:
        st.info("Noch keine Wetten vorhanden.")
    else:
        st.dataframe(
            bets.drop(columns=["fixture_id"], errors="ignore"),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "⬇️ Wettverlauf als CSV",
            bets.to_csv(index=False).encode("utf-8-sig"),
            file_name="kickpredict_wettverlauf.csv",
            mime="text/csv",
        )


# -------------------- SPIELPROGNOSE --------------------

elif page == "🔮 Spielprognose":
    hero(
        "Spielprognose",
        "Wahrscheinlichkeiten aus vergangenen Resultaten.",
    )

    league = st.selectbox("Liga", list(LEAGUES), key="prediction_league")
    hist = historical_data(LEAGUES[league][1])

    if hist.empty:
        st.warning("Keine historischen Resultate verfügbar.")
        st.stop()

    teams = sorted(set(hist["Heim"]) | set(hist["Auswärts"]))
    home = st.selectbox("Heimteam", teams)
    away = st.selectbox("Auswärtsteam", [t for t in teams if t != home])

    if st.button("Prognose berechnen"):
        result = predict_match(hist, home, away)

        if result:
            st.session_state["prediction_result"] = result
            st.session_state["prediction_pair"] = (home, away)
        else:
            st.error("Nicht genügend Daten.")

    if "prediction_result" in st.session_state:
        result = st.session_state["prediction_result"]
        saved_home, saved_away = st.session_state["prediction_pair"]

        st.subheader(f"{saved_home} vs. {saved_away}")

        a, b, c = st.columns(3)

        with a:
            metric("Heimsieg", f"{result['home'] * 100:.1f}%")

        with b:
            metric("Unentschieden", f"{result['draw'] * 100:.1f}%")

        with c:
            metric("Auswärtssieg", f"{result['away'] * 100:.1f}%")

        fig = go.Figure(go.Bar(
            x=["Heimsieg", "Unentschieden", "Auswärtssieg"],
            y=[
                result["home"] * 100,
                result["draw"] * 100,
                result["away"] * 100,
            ],
            marker_color=["#4be0a0", "#6bbf9a", "#328c6a"],
        ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#122238",
            font=dict(color="#f4f7fb"),
            yaxis_title="Wahrscheinlichkeit (%)",
            yaxis=dict(range=[0, 100]),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.write("Wahrscheinlichster Ausgang:", result["winner"])
        st.write("Geschätzter Spielstand:", result["score"])

        st.caption(
            "Die Prozentwerte sind statistische Schätzungen und keine Garantie."
        )


# -------------------- TEAM-ANALYSE --------------------

elif page == "🧠 Team-Analyse":
    hero("Team-Analyse", "Form und Torstatistik.")

    league = st.selectbox("Liga", list(LEAGUES), key="team_league")
    hist = historical_data(LEAGUES[league][1])

    if hist.empty:
        st.warning("Keine Daten verfügbar.")
        st.stop()

    team = st.selectbox(
        "Team",
        sorted(set(hist["Heim"]) | set(hist["Auswärts"])),
    )

    stats = team_stats(hist, team)

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


# -------------------- STATISTIKEN --------------------

elif page == "📊 Statistiken":
    hero("Statistiken", "Ligaweite Tore und Spielausgänge.")

    league = st.selectbox("Liga", list(LEAGUES), key="stats_league")
    hist = historical_data(LEAGUES[league][1])

    if hist.empty:
        st.warning("Keine Resultate verfügbar.")
        st.stop()

    total = len(hist)
    goals = int(hist["Tore_Heim"].sum() + hist["Tore_Auswärts"].sum())
    home_wins = int((hist["Tore_Heim"] > hist["Tore_Auswärts"]).sum())
    draws = int((hist["Tore_Heim"] == hist["Tore_Auswärts"]).sum())
    away_wins = int((hist["Tore_Heim"] < hist["Tore_Auswärts"]).sum())

    a, b, c = st.columns(3)

    with a:
        metric("Spiele", str(total))

    with b:
        metric("Tore insgesamt", str(goals))

    with c:
        metric("Tore pro Spiel", f"{goals / total:.2f}")

    fig = px.pie(
        names=["Heimsieg", "Unentschieden", "Auswärtssieg"],
        values=[home_wins, draws, away_wins],
        hole=0.5,
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f4f7fb"),
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------- ÜBER UNS --------------------

elif page == "ℹ️ Über uns":
    hero("Über uns", "Das Projekt hinter KickPredict AI.")

    st.markdown("### Unsere Idee")
    st.write(
        "KickPredict AI wertet vergangene Fussballresultate aus und erstellt "
        "statistische Prognosen. Das virtuelle Wettkonto ist zum spielerischen "
        "Testen von Tipps mit Spielgeld gedacht."
    )

    st.markdown("### Erstellt von")
    st.subheader("Tiago Faruk und Yigit")

    st.info(
        "Keine Echtgeldwetten, keine Einzahlungen und keine garantierten Prognosen."
    )

attribution()
