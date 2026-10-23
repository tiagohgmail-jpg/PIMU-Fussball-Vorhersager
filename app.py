
import os
import requests
import pandas as pd
import streamlit as st
import numpy as np
from scipy.stats import poisson

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f, #101d30);
    color: #f3f6fc;
}
h1, h2, h3 {
    color: #ffffff;
}
div[data-testid="stMetric"] {
    background: #17263b;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #29415f;
}
.stButton > button {
    background: #20d99a;
    color: #07111f;
    font-weight: bold;
    border-radius: 10px;
    border: none;
    padding: 10px 18px;
}
</style>
""", unsafe_allow_html=True)

LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Champions League": 2,
    "Conference League": 848,
}

API_URL = "https://v3.football.api-sports.io"

st.sidebar.title("⚽ KickPredict AI")
page = st.sidebar.radio(
    "Navigation",
    ["Home", "Spielprognose", "Über uns"]
)

st.sidebar.caption("Erstellt von Tiago Faruk und Yigit")

def get_api_key():
    try:
        return st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        return os.getenv("API_FOOTBALL_KEY", "")

def api_request(endpoint, params=None):
    key = get_api_key()
    if not key:
        raise ValueError(
            "API-Schlüssel fehlt. Trage API_FOOTBALL_KEY "
            "in den Streamlit-Secrets ein."
        )

    response = requests.get(
        API_URL + endpoint,
        headers={"x-apisports-key": key},
        params=params or {},
        timeout=25
    )
    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        raise ValueError(str(data["errors"]))

    return data.get("response", [])

@st.cache_data(ttl=21600, show_spinner=False)
def load_matches(league_id):
    all_matches = []

    # Kostenloser API-Zugang: verfügbare historische Saisons
    for season in [2024, 2023, 2022]:
        try:
            fixtures = api_request(
                "/fixtures",
                {
                    "league": league_id,
                    "season": season,
                    "status": "FT"
                }
            )

            for fixture in fixtures:
                teams = fixture.get("teams", {})
                goals = fixture.get("goals", {})
                home = teams.get("home", {}).get("name")
                away = teams.get("away", {}).get("name")
                hg = goals.get("home")
                ag = goals.get("away")

                if home and away and hg is not None and ag is not None:
                    all_matches.append({
                        "Heimteam": home,
                        "Auswärtsteam": away,
                        "Heimtore": hg,
                        "Auswärtstore": ag,
                        "Datum": fixture.get("fixture", {}).get("date", "")
                    })

        except Exception:
            continue

    df = pd.DataFrame(all_matches)

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Heimteam", "Auswärtsteam", "Datum"]
        )

    return df

def predict_match(df, home_team, away_team):
    home_matches = df[df["Heimteam"] == home_team]
    away_matches = df[df["Auswärtsteam"] == away_team]

    if home_matches.empty or away_matches.empty:
        raise ValueError(
            "Für eines der Teams gibt es zu wenige passende Heim- "
            "oder Auswärtsdaten."
        )

    avg_home_goals = df["Heimtore"].mean()
    avg_away_goals = df["Auswärtstore"].mean()

    home_scored = home_matches["Heimtore"].mean()
    home_conceded = home_matches["Auswärtstore"].mean()
    away_scored = away_matches["Auswärtstore"].mean()
    away_conceded = away_matches["Heimtore"].mean()

    home_attack = home_scored / max(avg_home_goals, 0.1)
    home_defence = home_conceded / max(avg_away_goals, 0.1)
    away_attack = away_scored / max(avg_away_goals, 0.1)
    away_defence = away_conceded / max(avg_home_goals, 0.1)

    expected_home = max(
        0.1, avg_home_goals * home_attack * away_defence
    )
    expected_away = max(
        0.1, avg_away_goals * away_attack * home_defence
    )

    home_win = 0
    draw = 0
    away_win = 0
    scorelines = []

    for h in range(8):
        for a in range(8):
            probability = (
                poisson.pmf(h, expected_home)
                * poisson.pmf(a, expected_away)
            )
            scorelines.append((h, a, probability))

            if h > a:
                home_win += probability
            elif h == a:
                draw += probability
            else:
                away_win += probability

    total = home_win + draw + away_win
    home_win /= total
    draw /= total
    away_win /= total

    best_score = max(scorelines, key=lambda x: x[2])

    return {
        "home": home_win,
        "draw": draw,
        "away": away_win,
        "expected_home": expected_home,
        "expected_away": expected_away,
        "score": f"{best_score[0]} : {best_score[1]}"
    }

if page == "Home":
    st.title("⚽ KickPredict AI")
    st.subheader("Deine Fussball-Prognoseplattform")
    st.write(
        "Analysiere historische Fussballergebnisse und erhalte "
        "modellbasierte 1X2-Prognosen für ausgewählte Teams."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Prognosetyp", "1X2")
    c2.metric("Datenbasis", "Historische Spiele")
    c3.metric("Modell", "Poisson")

    st.warning(
        "Eine Prognose ist keine Garantie. Das Modell kann falsch liegen "
        "und verspricht keine bestimmte Trefferquote."
    )

elif page == "Spielprognose":
    st.title("🔮 Spielprognose")
    st.write(
        "Wähle eine Liga und zwei Teams. Die Daten werden über "
        "API-Football geladen."
    )

    league_name = st.selectbox("Liga auswählen", list(LEAGUES.keys()))

    if st.button("Spieldaten laden"):
        try:
            with st.spinner("Lade historische Spieldaten ..."):
                df = load_matches(LEAGUES[league_name])

            if df.empty:
                st.error(
                    "Keine historischen Spiele geladen. Prüfe deinen "
                    "API-Schlüssel und die API-Zugriffsrechte."
                )
            else:
                st.session_state["matches"] = df
                st.session_state["league"] = league_name
                st.success(f"{len(df)} Spiele geladen.")

        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")

    df = st.session_state.get("matches")

    if df is not None and not df.empty:
        st.caption(
            f"Daten für: {st.session_state.get('league', league_name)}"
        )

        home_teams = sorted(df["Heimteam"].dropna().unique().tolist())
        away_teams = sorted(df["Auswärtsteam"].dropna().unique().tolist())

        home_team = st.selectbox("Heimteam", home_teams)
        away_team = st.selectbox("Auswärtsteam", away_teams)

        if st.button("Prognose berechnen"):
            if home_team == away_team:
                st.warning("Bitte wähle zwei unterschiedliche Teams.")
            else:
                try:
                    result = predict_match(df, home_team, away_team)

                    st.subheader(
                        f"{home_team} gegen {away_team}"
                    )

                    col1, col2, col3 = st.columns(3)
                    col1.metric(
                        "1 – Heimsieg",
                        f"{result['home'] * 100:.1f}%"
                    )
                    col2.metric(
                        "X – Unentschieden",
                        f"{result['draw'] * 100:.1f}%"
                    )
                    col3.metric(
                        "2 – Auswärtssieg",
                        f"{result['away'] * 100:.1f}%"
                    )

                    st.subheader("Torerwartung")
                    st.write(
                        f"{home_team}: {result['expected_home']:.2f} Tore"
                    )
                    st.write(
                        f"{away_team}: {result['expected_away']:.2f} Tore"
                    )
                    st.metric("Wahrscheinlichstes Ergebnis", result["score"])

                    st.caption(
                        "Die Prozentwerte sind Modellschätzungen auf Basis "
                        "historischer Ergebnisse, keine sicheren Vorhersagen."
                    )

                except Exception as e:
                    st.error(f"Prognose nicht möglich: {e}")

elif page == "Über uns":
    st.title("Über KickPredict AI")
    st.write(
        "KickPredict AI ist ein Fussball-Projekt, das historische "
        "Spielergebnisse analysiert und daraus Wahrscheinlichkeiten "
        "für Heimsieg, Unentschieden oder Auswärtssieg berechnet."
    )

    st.markdown("### Unser Ziel")
    st.write(
        "Wir wollen Fussballstatistiken verständlich machen und zeigen, "
        "wie Daten für Prognosen eingesetzt werden können."
    )

    st.markdown("### Erstellt von")
    st.write("**Tiago Faruk und Yigit**")

    st.markdown("### Technologie")
    st.write(
        "- Python und Streamlit\n"
        "- API-Football für Spieldaten\n"
        "- Poisson-Modell für Wahrscheinlichkeiten"
    )

    st.info(
        "KickPredict AI ist ein Analyseprojekt. Es garantiert keine "
        "Trefferquote von 6 aus 10 oder höher."
    )

st.divider()
st.caption("KickPredict AI © 2026 · Erstellt von Tiago Faruk und Yigit")
