
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

API_URL = "https://v3.football.api-sports.io"

LEAGUES = {
    "Premier League (England)": 39,
    "La Liga (Spanien)": 140,
    "Bundesliga (Deutschland)": 78,
    "Serie A (Italien)": 135,
    "Ligue 1 (Frankreich)": 61,
    "Champions League": 2,
    "Super League (Schweiz)": 207,
    "Europa League": 3,
}

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #08111f 0%, #101d30 100%);
        color: #f4f7fb;
    }
    [data-testid="stSidebar"] {
        background-color: #0b1422;
    }
    h1, h2, h3, p, label {
        color: #f4f7fb;
    }
    .hero {
        padding: 30px;
        border-radius: 20px;
        background: linear-gradient(120deg, #142a45, #173d36);
        border: 1px solid #294b5c;
        margin-bottom: 22px;
    }
    .hero h1 {
        font-size: 42px;
        margin-bottom: 8px;
    }
    .hero p {
        color: #c5d4e5;
        font-size: 17px;
    }
    .metric-card {
        background: #132238;
        border: 1px solid #29405c;
        padding: 18px;
        border-radius: 14px;
        margin-bottom: 10px;
    }
    .metric-value {
        font-size: 29px;
        font-weight: 800;
        color: #54e0a1;
    }
    .small-muted {
        color: #a9bad0;
        font-size: 13px;
    }
    div[data-baseweb="select"] > div {
        background-color: #ffffff;
        color: #111827;
    }
    div[data-baseweb="select"] * {
        color: #111827;
    }
    input, textarea {
        background-color: #ffffff !important;
        color: #111827 !important;
    }
    div.stButton > button {
        border-radius: 10px;
        border: 1px solid #38d99a;
        background-color: #38d99a;
        color: #07131c;
        font-weight: 750;
        min-height: 44px;
    }
    div.stButton > button:hover {
        background-color: #72efba;
        border-color: #72efba;
        color: #07131c;
    }
    hr {
        border-color: #263b53;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_api_key():
    try:
        return st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        return ""


def api_get(endpoint, api_key, params=None):
    headers = {"x-apisports-key": api_key}
    response = requests.get(
        f"{API_URL}/{endpoint}",
        headers=headers,
        params=params or {},
        timeout=30,
    )

    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code != 200:
        message = data.get("errors", {}) if isinstance(data, dict) else {}
        raise RuntimeError(
            f"HTTP {response.status_code}: {message or response.text[:200]}"
        )

    if isinstance(data, dict) and data.get("errors"):
        raise RuntimeError(str(data["errors"]))

    return data


@st.cache_data(ttl=3600, show_spinner=False)
def load_matches(league_id, api_key):
    """Lädt abgeschlossene Spiele ab 2022 für alle API-verfügbaren Saisons."""
    matches = []
    errors = []

    try:
        league_data = api_get(
            "leagues",
            api_key,
            {"id": int(league_id)},
        )
        entries = league_data.get("response", [])

        available_seasons = set()
        current_year = datetime.now(timezone.utc).year

        for entry in entries:
            for season_info in entry.get("seasons", []):
                year = season_info.get("year")
                if year is not None:
                    year = int(year)
                    if 2022 <= year <= current_year:
                        available_seasons.add(year)

        if not available_seasons:
            return pd.DataFrame(), [
                "Die API hat keine verfügbaren Saisons ab 2022 zurückgegeben."
            ]

    except Exception as exc:
        return pd.DataFrame(), [f"Saisonliste konnte nicht geladen werden: {exc}"]

    for season in sorted(available_seasons):
        page = 1

        try:
            while True:
                data = api_get(
                    "fixtures",
                    api_key,
                    {
                        "league": int(league_id),
                        "season": season,
                        "status": "FT",
                        "page": page,
                    },
                )

                for item in data.get("response", []):
                    fixture = item.get("fixture", {})
                    teams = item.get("teams", {})
                    goals = item.get("goals", {})
                    status = fixture.get("status", {}).get("short")

                    home = teams.get("home", {}).get("name")
                    away = teams.get("away", {}).get("name")
                    hg = goals.get("home")
                    ag = goals.get("away")

                    if (
                        status in ("FT", "AET", "PEN")
                        and home
                        and away
                        and hg is not None
                        and ag is not None
                    ):
                        matches.append(
                            {
                                "Datum": pd.to_datetime(
                                    fixture.get("date"), utc=True
                                ),
                                "Heim": home,
                                "Auswärts": away,
                                "Tore_Heim": int(hg),
                                "Tore_Auswärts": int(ag),
                                "Saison": season,
                            }
                        )

                pagination = data.get("paging", {})
                pages = int(pagination.get("total", 1))

                if page >= pages:
                    break

                page += 1

        except Exception as exc:
            errors.append(f"Saison {season}: {exc}")

    df = pd.DataFrame(matches)

    if df.empty:
        return df, errors

    df = df.drop_duplicates(
        subset=["Datum", "Heim", "Auswärts"]
    )
    df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors


def team_statistics(df, team, venue=None, last_n=12):
    """Berechnet die durchschnittlichen Tore eines Teams."""
    if df.empty:
        return None

    home_matches = df[df["Heim"] == team].copy()
    away_matches = df[df["Auswärts"] == team].copy()

    home_matches["Tore_Eigen"] = home_matches["Tore_Heim"]
    home_matches["Tore_Gegner"] = home_matches["Tore_Auswärts"]

    away_matches["Tore_Eigen"] = away_matches["Tore_Auswärts"]
    away_matches["Tore_Gegner"] = away_matches["Tore_Heim"]

    if venue == "home":
        team_matches = home_matches
    elif venue == "away":
        team_matches = away_matches
    else:
        team_matches = pd.concat(
            [home_matches, away_matches],
            ignore_index=True,
        )

    team_matches = team_matches.sort_values("Datum").tail(last_n)

    if team_matches.empty:
        return None

    return {
        "spiele": len(team_matches),
        "tore": float(team_matches["Tore_Eigen"].mean()),
        "gegentreffer": float(team_matches["Tore_Gegner"].mean()),
    }


def poisson_probability(goals, expected_goals):
    expected_goals = max(0.05, float(expected_goals))
    return (
        math.exp(-expected_goals)
        * expected_goals**goals
        / math.factorial(goals)
    )


def predict_match(df, home_team, away_team):
    """Schätzt die 1X2-Wahrscheinlichkeiten aus bisherigen Ergebnissen."""
    home_stats = team_statistics(df, home_team, "home")
    away_stats = team_statistics(df, away_team, "away")

    home_overall = team_statistics(df, home_team)
    away_overall = team_statistics(df, away_team)

    if not home_stats or not away_stats:
        return None

    if not home_overall or not away_overall:
        return None

    league_home_goals = float(df["Tore_Heim"].mean())
    league_away_goals = float(df["Tore_Auswärts"].mean())

    if league_home_goals <= 0 or league_away_goals <= 0:
        return None

    # Mischung aus Heim-/Auswärtsleistung und allgemeiner Form.
    home_attack = (
        0.65 * home_stats["tore"]
        + 0.35 * home_overall["tore"]
    )
    away_defence = (
        0.65 * away_stats["gegentreffer"]
        + 0.35 * away_overall["gegentreffer"]
    )
    away_attack = (
        0.65 * away_stats["tore"]
        + 0.35 * away_overall["tore"]
    )
    home_defence = (
        0.65 * home_stats["gegentreffer"]
        + 0.35 * home_overall["gegentreffer"]
    )

    expected_home = (
        home_attack / league_home_goals
    ) * away_defence
    expected_away = (
        away_attack / league_away_goals
    ) * home_defence

    # Begrenzung verhindert unrealistische Extremwerte.
    expected_home = max(0.15, min(4.0, expected_home))
    expected_away = max(0.15, min(4.0, expected_away))

    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    scorelines = []

    max_goals = 10

    for hg in range(max_goals + 1):
        p_home = poisson_probability(hg, expected_home)

        for ag in range(max_goals + 1):
            p_away = poisson_probability(ag, expected_away)
            probability = p_home * p_away

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

    best_score = max(scorelines, key=lambda item: item[2])

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
        "home_matches": home_stats["spiele"],
        "away_matches": away_stats["spiele"],
    }


def show_metric(title, value, subtitle=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="small-muted">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="small-muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Sidebar
st.sidebar.markdown("## ⚽ KickPredict AI")
st.sidebar.caption("Fussballprognosen auf Deutsch")
page = st.sidebar.radio(
    "Navigation",
    ["Home", "Spielprognose", "Über uns"],
)

st.sidebar.divider()
st.sidebar.caption("Erstellt von Tiago Faruk und Yigit")
st.sidebar.caption("Prognosen sind Schätzungen, keine Garantien.")

api_key = get_api_key()

if not api_key:
    st.sidebar.warning("API-Schlüssel fehlt.")
    st.sidebar.markdown(
        """
        Füge in Streamlit unter **Settings → Secrets**
        deinen API-Schlüssel ein:
        """
    )
    st.sidebar.code('API_FOOTBALL_KEY = "DEIN_API_SCHLUESSEL"')


if page == "Home":
    st.markdown(
        """
        <div class="hero">
            <h1>⚽ KickPredict AI</h1>
            <p>Analysiere Fussballteams und entdecke datenbasierte
            1X2-Prognosen für verschiedene Ligen.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Willkommen bei KickPredict AI")

    col1, col2, col3 = st.columns(3)

    with col1:
        show_metric("Datenstart", "2022", "Frühester gewünschter Zeitraum")

    with col2:
        show_metric("Prognose", "1X2", "Heimsieg · Remis · Auswärtssieg")

    with col3:
        show_metric("Ligen", str(len(LEAGUES)), "Auswahl internationaler Ligen")

    st.markdown("### Was kann die Website?")
    st.markdown(
        """
        - Vergangene Spielergebnisse aus einer Fussball-API laden.
        - Die letzten verfügbaren Leistungen der Teams auswerten.
        - Wahrscheinlichkeiten für Heimsieg, Unentschieden und Auswärtssieg schätzen.
        - Eine mögliche Torverteilung berechnen.
        """
    )

    st.info(
        "Die Prognosen beruhen auf historischen Resultaten. "
        "Verletzungen, Aufstellungen, rote Karten und andere Faktoren "
        "sind nicht vollständig berücksichtigt."
    )

    if st.button("Zur Spielprognose", use_container_width=True):
        st.session_state["page"] = "Spielprognose"
        st.rerun()


elif page == "Spielprognose":
    st.markdown(
        """
        <div class="hero">
            <h1>🔮 Spielprognose</h1>
            <p>Wähle eine Liga und zwei Teams für eine datenbasierte Schätzung.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not api_key:
        st.error(
            "Kein API-Schlüssel gefunden. Öffne die Streamlit-Secrets "
            "und trage API_FOOTBALL_KEY ein."
        )
        st.stop()

    league_name = st.selectbox("Fussball-Liga", list(LEAGUES.keys()))
    league_id = LEAGUES[league_name]

    if st.button("🔄 Daten aktualisieren", use_container_width=True):
        load_matches.clear()

    with st.spinner("Lade verfügbare Saisons und Spielergebnisse …"):
        df, errors = load_matches(league_id, api_key)

    if errors:
        with st.expander("API-Meldungen anzeigen"):
            for error in errors:
                st.warning(error)

    if df.empty:
        st.error(
            "Es konnten keine abgeschlossenen Spiele geladen werden. "
            "Prüfe deinen API-Schlüssel, die API-Berechtigungen und "
            "die Meldungen oben."
        )
        st.stop()

    first_date = df["Datum"].min()
    last_date = df["Datum"].max()
    seasons = sorted(df["Saison"].unique())

    col1, col2, col3 = st.columns(3)

    with col1:
        show_metric("Abgeschlossene Spiele", f"{len(df):,}".replace(",", "."))

    with col2:
        show_metric("Geladene Saisons", str(len(seasons)), f"{seasons[0]}–{seasons[-1]}")

    with col3:
        show_metric("Letztes geladenes Spiel", last_date.strftime("%d.%m.%Y"))

    st.caption(
        f"Datenzeitraum: {first_date.strftime('%d.%m.%Y')} bis "
        f"{last_date.strftime('%d.%m.%Y')} · Quelle: API-Football"
    )

    teams = sorted(
        set(df["Heim"].dropna().unique())
        | set(df["Auswärts"].dropna().unique())
    )

    st.markdown("### Wähle dein Spiel")

    col1, col2 = st.columns(2)

    with col1:
        home_team = st.selectbox("Heimteam", teams, index=0)

    away_options = [team for team in teams if team != home_team]

    with col2:
        away_team = st.selectbox(
            "Auswärtsteam",
            away_options,
            index=0 if away_options else None,
        )

    if st.button("🚀 Prognose berechnen", use_container_width=True):
        if home_team == away_team:
            st.error("Bitte wähle zwei unterschiedliche Teams.")
        else:
            result = predict_match(df, home_team, away_team)

            if result is None:
                st.error(
                    "Für diese Teams gibt es zu wenige passende Daten "
                    "für eine Prognose."
                )
            else:
                st.session_state["prediction_result"] = result
                st.session_state["prediction_teams"] = (
                    home_team,
                    away_team,
                )

    if "prediction_result" in st.session_state:
        result = st.session_state["prediction_result"]
        saved_home, saved_away = st.session_state["prediction_teams"]

        st.divider()
        st.markdown("### 📊 Ergebnis der Prognose")
        st.subheader(f"{saved_home} vs. {saved_away}")

        col1, col2, col3 = st.columns(3)

        with col1:
            show_metric("Heimsieg", f"{result['home'] * 100:.1f}%")

        with col2:
            show_metric("Unentschieden", f"{result['draw'] * 100:.1f}%")

        with col3:
            show_metric("Auswärtssieg", f"{result['away'] * 100:.1f}%")

        st.markdown("#### Wahrscheinlichkeiten")
        chart_data = pd.DataFrame(
            {
                "Ausgang": [
                    f"Heimsieg ({saved_home})",
                    "Unentschieden",
                    f"Auswärtssieg ({saved_away})",
                ],
                "Wahrscheinlichkeit": [
                    result["home"] * 100,
                    result["draw"] * 100,
                    result["away"] * 100,
                ],
            }
        ).set_index("Ausgang")

        st.bar_chart(chart_data)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Wahrscheinlichster Ausgang**")
            st.markdown(f"### {result['winner']}")

        with col2:
            st.markdown("**Möglicher Spielstand**")
            st.markdown(f"### {result['score']}")

        st.caption(
            f"Geschätzte Tore: {result['expected_home']:.2f} für "
            f"{saved_home} und {result['expected_away']:.2f} für "
            f"{saved_away}. Grundlage: bis zu 12 Heim- bzw. Auswärtsspiele "
            "und die allgemeine Teamform."
        )

        st.warning(
            "Diese Zahlen sind statistische Schätzungen und keine "
            "garantierten Resultate. Die Trefferquote von 6 aus 10 "
            "kann nicht versprochen werden."
        )

    with st.expander("Zuletzt geladene Ergebnisse ansehen"):
        display_df = df.copy()
        display_df["Datum"] = (
            display_df["Datum"]
            .dt.tz_convert("Europe/Zurich")
            .dt.strftime("%d.%m.%Y")
        )
        st.dataframe(
            display_df.sort_values("Datum", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


elif page == "Über uns":
    st.markdown(
        """
        <div class="hero">
            <h1>Über KickPredict AI</h1>
            <p>Fussball, Daten und Technologie in einem Projekt.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Unsere Idee")
    st.write(
        "KickPredict AI wertet historische Fussballresultate aus und "
        "berechnet daraus Wahrscheinlichkeiten für mögliche Spielausgänge. "
        "Die Website soll Fussballfans helfen, Statistiken besser zu verstehen."
    )

    st.markdown("### Funktionen")
    st.write(
        "- Internationale Ligen auswählen\n"
        "- Vergangene Spiele ab 2022 laden, soweit verfügbar\n"
        "- Heim- und Auswärtsteam vergleichen\n"
        "- 1X2-Wahrscheinlichkeiten und einen möglichen Spielstand anzeigen"
    )

    st.markdown("### Erstellt von")
    st.markdown("## Tiago Faruk und Yigit")

    st.caption(
        "KickPredict AI ist ein unabhängiges Projekt. "
        "Prognosen sind keine Garantie für den tatsächlichen Spielausgang."
    )

st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Datenbasierte Fussballprognosen")
