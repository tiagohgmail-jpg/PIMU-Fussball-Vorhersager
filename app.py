
import math
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

API_URL = "https://v3.football.api-sports.io"
START_YEAR = 2022

LEAGUES = {
    "Premier League (England)": 39,
    "La Liga (Spanien)": 140,
    "Bundesliga (Deutschland)": 78,
    "Serie A (Italien)": 135,
    "Ligue 1 (Frankreich)": 61,
    "Champions League": 2,
    "Europa League": 3,
    "Super League (Schweiz)": 207,
}

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f, #10243a);
    color: #f5f7fb;
}
[data-testid="stSidebar"] {
    background: #091421;
}
.hero {
    padding: 28px;
    border-radius: 18px;
    background: linear-gradient(120deg, #142a45, #12483a);
    border: 1px solid #31556a;
    margin-bottom: 20px;
}
.hero h1 { font-size: 40px; }
.hero p { color: #d1dfed; font-size: 16px; }
.metric {
    padding: 18px;
    background: #13243a;
    border: 1px solid #29415e;
    border-radius: 14px;
    margin-bottom: 12px;
}
.metric-label { color: #b5c7da; font-size: 14px; }
.metric-value {
    color: #56e6a5;
    font-size: 28px;
    font-weight: 800;
}
div.stButton > button {
    background: #43dfa0;
    color: #06131b;
    border: 0;
    border-radius: 10px;
    font-weight: 750;
    min-height: 43px;
}
div.stButton > button:hover {
    background: #82f2bd;
    color: #06131b;
}
</style>
""", unsafe_allow_html=True)


def get_api_key():
    try:
        return st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        return ""


def api_get(endpoint, api_key, params=None, retries=4):
    """API-Anfrage mit Wartezeit bei Rate-Limits und temporären Fehlern."""
    headers = {"x-apisports-key": api_key}
    last_error = "Unbekannter API-Fehler"

    for attempt in range(retries + 1):
        try:
            response = requests.get(
                f"{API_URL}/{endpoint}",
                headers=headers,
                params=params or {},
                timeout=35,
            )

            if response.status_code == 429:
                last_error = (
                    "API-Anfragelimit erreicht (HTTP 429). "
                    "Die Anwendung wartet automatisch."
                )
                if attempt < retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        wait_seconds = int(retry_after)
                    except (TypeError, ValueError):
                        wait_seconds = min(15 * (2 ** attempt), 90)
                    time.sleep(max(5, min(wait_seconds, 120)))
                    continue
                raise RuntimeError(
                    last_error + " Bitte später erneut versuchen."
                )

            if response.status_code >= 500 and attempt < retries:
                time.sleep(min(5 * (2 ** attempt), 30))
                continue

            try:
                data = response.json()
            except ValueError:
                data = {}

            if response.status_code != 200:
                raise RuntimeError(
                    f"HTTP {response.status_code}: "
                    f"{data.get('errors', response.text[:250])}"
                )

            if isinstance(data, dict) and data.get("errors"):
                raise RuntimeError(str(data["errors"]))

            return data

        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(5 * (2 ** attempt), 30))
                continue
            raise RuntimeError(
                f"Verbindung zur Fussball-API fehlgeschlagen: {last_error}"
            )

    raise RuntimeError(last_error)


@st.cache_data(ttl=86400, show_spinner=False)
def load_available_seasons(league_id, api_key):
    """Saisonliste höchstens einmal pro Tag abrufen."""
    data = api_get("leagues", api_key, {"id": int(league_id)})
    years = set()
    current_year = datetime.now(timezone.utc).year

    for entry in data.get("response", []):
        for season in entry.get("seasons", []):
            year = season.get("year")
            if year is not None:
                year = int(year)
                if START_YEAR <= year <= current_year:
                    years.add(year)

    if not years:
        raise RuntimeError(
            "Die API hat für diese Liga keine verfügbaren Saisons "
            f"ab {START_YEAR} zurückgegeben."
        )

    return sorted(years)


@st.cache_data(ttl=86400, show_spinner=False)
def load_matches(league_id, api_key):
    """
    Lädt abgeschlossene Spiele ab 2022.
    Pro Saison wird nur eine Fixture-Abfrage gesendet.
    Es wird absichtlich kein page-Parameter verwendet.
    """
    all_matches = []
    errors = []
    seasons = load_available_seasons(league_id, api_key)

    yesterday = (
        datetime.now(timezone.utc).date() - timedelta(days=1)
    )

    for index, season in enumerate(seasons):
        try:
            data = api_get(
                "fixtures",
                api_key,
                {
                    "league": int(league_id),
                    "season": int(season),
                },
            )

            for item in data.get("response", []):
                fixture = item.get("fixture", {})
                teams = item.get("teams", {})
                goals = item.get("goals", {})
                status = fixture.get("status", {}).get("short")

                home = teams.get("home", {}).get("name")
                away = teams.get("away", {}).get("name")
                home_goals = goals.get("home")
                away_goals = goals.get("away")
                fixture_date = fixture.get("date")

                if not all([home, away, fixture_date]):
                    continue

                match_date = pd.to_datetime(
                    fixture_date, utc=True, errors="coerce"
                )

                if pd.isna(match_date):
                    continue

                # Nur abgeschlossene Spiele bis einschliesslich gestern.
                if match_date.date() > yesterday:
                    continue

                if status not in ("FT", "AET", "PEN"):
                    continue

                if home_goals is None or away_goals is None:
                    continue

                all_matches.append({
                    "Datum": match_date,
                    "Heim": home,
                    "Auswärts": away,
                    "Tore_Heim": int(home_goals),
                    "Tore_Auswärts": int(away_goals),
                    "Saison": int(season),
                })

        except Exception as exc:
            errors.append(f"Saison {season}: {exc}")

        # Zwischen Saison-Abfragen warten, um die API zu entlasten.
        if index < len(seasons) - 1:
            time.sleep(6)

    df = pd.DataFrame(all_matches)

    if df.empty:
        return df, errors, seasons

    df = df.drop_duplicates(
        subset=["Datum", "Heim", "Auswärts"]
    )
    df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors, seasons


def team_stats(df, team, venue=None, last_n=12):
    home = df[df["Heim"] == team].copy()
    away = df[df["Auswärts"] == team].copy()

    home["Eigen"] = home["Tore_Heim"]
    home["Gegner"] = home["Tore_Auswärts"]
    away["Eigen"] = away["Tore_Auswärts"]
    away["Gegner"] = away["Tore_Heim"]

    if venue == "home":
        matches = home
    elif venue == "away":
        matches = away
    else:
        matches = pd.concat([home, away], ignore_index=True)

    matches = matches.sort_values("Datum").tail(last_n)

    if matches.empty:
        return None

    return {
        "spiele": len(matches),
        "tore": float(matches["Eigen"].mean()),
        "gegentreffer": float(matches["Gegner"].mean()),
    }


def poisson_probability(goals, expected):
    expected = max(0.05, float(expected))
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

    home_attack = 0.65 * home["tore"] + 0.35 * home_all["tore"]
    away_defence = (
        0.65 * away["gegentreffer"]
        + 0.35 * away_all["gegentreffer"]
    )
    away_attack = 0.65 * away["tore"] + 0.35 * away_all["tore"]
    home_defence = (
        0.65 * home["gegentreffer"]
        + 0.35 * home_all["gegentreffer"]
    )

    expected_home = max(
        0.15, min(4.0, home_attack / league_home * away_defence)
    )
    expected_away = max(
        0.15, min(4.0, away_attack / league_away * home_defence)
    )

    home_win = draw = away_win = 0.0
    scorelines = []

    for hg in range(11):
        for ag in range(11):
            probability = (
                poisson_probability(hg, expected_home)
                * poisson_probability(ag, expected_away)
            )
            scorelines.append((hg, ag, probability))

            if hg > ag:
                home_win += probability
            elif hg == ag:
                draw += probability
            else:
                away_win += probability

    total = home_win + draw + away_win
    if total <= 0:
        return None

    home_win /= total
    draw /= total
    away_win /= total

    best_score = max(scorelines, key=lambda row: row[2])

    if home_win >= draw and home_win >= away_win:
        winner = f"Sieg {home_team}"
    elif away_win >= home_win and away_win >= draw:
        winner = f"Sieg {away_team}"
    else:
        winner = "Unentschieden"

    return {
        "home": home_win,
        "draw": draw,
        "away": away_win,
        "winner": winner,
        "score": f"{best_score[0]} : {best_score[1]}",
        "expected_home": expected_home,
        "expected_away": expected_away,
    }


def metric(title, value, subtitle=""):
    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-label">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-label">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Navigation
st.sidebar.title("⚽ KickPredict AI")
page = st.sidebar.radio(
    "Menü",
    ["Home", "Spielprognose", "Über uns"],
)
st.sidebar.divider()
st.sidebar.caption("Erstellt von Tiago Faruk und Yigit")

api_key = get_api_key()

if not api_key:
    st.error(
        "API-Schlüssel fehlt. Füge ihn in Streamlit unter "
        "Settings → Secrets ein."
    )
    st.code('API_FOOTBALL_KEY = "DEIN_API_SCHLUESSEL"')
    st.stop()


if page == "Home":
    st.markdown("""
    <div class="hero">
        <h1>⚽ KickPredict AI</h1>
        <p>Statistiken analysieren. Teams vergleichen.
        Fussballprognosen verstehen.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Willkommen bei KickPredict AI")

    a, b, c = st.columns(3)
    with a:
        metric("Daten ab", "2022", "Soweit die API sie bereitstellt")
    with b:
        metric("Prognose", "1X2", "Heimsieg · Remis · Auswärtssieg")
    with c:
        metric("Ligen", str(len(LEAGUES)), "Internationale Wettbewerbe")

    st.markdown("### Was bietet die Website?")
    st.write(
        "KickPredict AI lädt historische Ergebnisse, vergleicht "
        "Heim- und Auswärtsleistungen und schätzt die Wahrscheinlichkeit "
        "von Heimsieg, Unentschieden und Auswärtssieg."
    )
    st.info(
        "Die Trefferquote kann nicht garantiert werden. Verletzungen, "
        "Aufstellungen, Motivation und viele weitere Faktoren können "
        "das tatsächliche Ergebnis beeinflussen."
    )


elif page == "Spielprognose":
    st.markdown("""
    <div class="hero">
        <h1>🔮 Spielprognose</h1>
        <p>Wähle eine Liga und vergleiche zwei Teams.</p>
    </div>
    """, unsafe_allow_html=True)

    league_name = st.selectbox("Liga auswählen", list(LEAGUES.keys()))
    league_id = LEAGUES[league_name]

    if st.button("🔄 Daten vollständig aktualisieren"):
        load_matches.clear()
        load_available_seasons.clear()
        st.rerun()

    try:
        with st.spinner(
            "Lade Saisonliste und abgeschlossene Spiele. "
            "Bei API-Limits kann es etwas dauern ..."
        ):
            df, errors, seasons = load_matches(league_id, api_key)

    except Exception as exc:
        st.error(f"Die Daten konnten nicht geladen werden: {exc}")
        st.info(
            "Wenn ein API-Limit erreicht wurde, warte einige Minuten "
            "und versuche es erneut. Prüfe auch dein API-Kontingent."
        )
        st.stop()

    if errors:
        with st.expander("API-Meldungen anzeigen"):
            for error in errors:
                st.warning(error)

    if df.empty:
        st.error(
            "Es wurden keine abgeschlossenen Spiele gefunden. "
            "Möglicherweise blockiert dein API-Tarif die benötigten Daten."
        )
        st.stop()

    first_date = df["Datum"].min()
    last_date = df["Datum"].max()

    a, b, c = st.columns(3)
    with a:
        metric("Geladene Spiele", f"{len(df):,}".replace(",", "."))
    with b:
        metric("Saisons", str(len(seasons)), f"{seasons[0]}–{seasons[-1]}")
    with c:
        metric("Letztes geladenes Spiel", last_date.strftime("%d.%m.%Y"))

    st.caption(
        f"Zeitraum: {first_date.strftime('%d.%m.%Y')} bis "
        f"{last_date.strftime('%d.%m.%Y')}. "
        "Es werden nur Daten angezeigt, die die API zurückliefert."
    )

    teams = sorted(
        set(df["Heim"].dropna()) | set(df["Auswärts"].dropna())
    )

    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Heimteam", teams, key="home_team")

    away_options = [team for team in teams if team != home_team]
    with col2:
        away_team = st.selectbox(
            "Auswärtsteam", away_options, key="away_team"
        )

    if st.button("🚀 Prognose berechnen"):
        result = predict_match(df, home_team, away_team)

        if result is None:
            st.error("Zu wenige Daten für eine Prognose dieser Teams.")
        else:
            st.session_state["result"] = result
            st.session_state["teams"] = (home_team, away_team)

    if "result" in st.session_state:
        result = st.session_state["result"]
        home_saved, away_saved = st.session_state["teams"]

        st.divider()
        st.subheader(f"{home_saved} vs. {away_saved}")

        a, b, c = st.columns(3)
        with a:
            metric("Heimsieg", f"{result['home'] * 100:.1f}%")
        with b:
            metric("Unentschieden", f"{result['draw'] * 100:.1f}%")
        with c:
            metric("Auswärtssieg", f"{result['away'] * 100:.1f}%")

        chart = pd.DataFrame({
            "Ausgang": ["Heimsieg", "Unentschieden", "Auswärtssieg"],
            "Wahrscheinlichkeit (%)": [
                result["home"] * 100,
                result["draw"] * 100,
                result["away"] * 100,
            ],
        }).set_index("Ausgang")
        st.bar_chart(chart)

        a, b = st.columns(2)
        with a:
            st.markdown("**Wahrscheinlichster Ausgang**")
            st.subheader(result["winner"])
        with b:
            st.markdown("**Möglicher Spielstand**")
            st.subheader(result["score"])

        st.caption(
            f"Geschätzte Tore: {result['expected_home']:.2f} für "
            f"{home_saved} und {result['expected_away']:.2f} für "
            f"{away_saved}."
        )
        st.warning(
            "Das ist eine statistische Schätzung, keine Garantie "
            "und keine bestätigte Trefferquote."
        )

    with st.expander("Geladene Resultate ansehen"):
        view = df.copy()
        view["Datum"] = (
            view["Datum"]
            .dt.tz_convert("Europe/Zurich")
            .dt.strftime("%d.%m.%Y")
        )
        st.dataframe(
            view.sort_values("Datum", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


elif page == "Über uns":
    st.markdown("""
    <div class="hero">
        <h1>Über KickPredict AI</h1>
        <p>Fussball und Datenanalyse in einer Website.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Unsere Idee")
    st.write(
        "KickPredict AI nutzt historische Spielergebnisse, um "
        "Wahrscheinlichkeiten für mögliche Spielausgänge zu schätzen."
    )

    st.subheader("Funktionen")
    st.write(
        "- Internationale Ligen\n"
        "- Historische Ergebnisse ab 2022, soweit verfügbar\n"
        "- Vergleich von Heim- und Auswärtsteams\n"
        "- 1X2-Wahrscheinlichkeiten\n"
        "- Geschätzter Spielstand"
    )

    st.subheader("Erstellt von")
    st.markdown("## Tiago Faruk und Yigit")

    st.caption(
        "Unabhängiges Projekt. Keine Garantie für tatsächliche "
        "Spielergebnisse oder Prognosetreffer."
    )

st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Fussballprognosen")
