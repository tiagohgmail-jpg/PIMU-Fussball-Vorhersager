
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

# ---------------- DESIGN ----------------

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
    padding: 16px;
    border-radius: 12px;
    border: 1px solid #29415f;
}
.stButton > button {
    background: #20d99a;
    color: #07111f;
    font-weight: bold;
    border-radius: 10px;
    border: none;
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
SEASONS = [2024, 2023, 2022]


# ---------------- NAVIGATION ----------------

st.sidebar.title("⚽ KickPredict AI")

page = st.sidebar.radio(
    "Navigation",
    ["Home", "Spielprognose", "Über uns"]
)

st.sidebar.caption("Erstellt von Tiago Faruk und Yigit")


# ---------------- API ----------------

def get_api_key():
    try:
        return st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        return os.getenv("API_FOOTBALL_KEY", "")


def api_request(endpoint, params=None):
    key = get_api_key()

    if not key:
        raise ValueError(
            "API-Schlüssel fehlt. Bitte API_FOOTBALL_KEY "
            "in Streamlit Secrets eintragen."
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
    matches = []
    errors = []

    for season in SEASONS:
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
                details = fixture.get("fixture", {})

                home = teams.get("home", {}).get("name")
                away = teams.get("away", {}).get("name")
                hg = goals.get("home")
                ag = goals.get("away")

                if (
                    home and away
                    and hg is not None and ag is not None
                ):
                    matches.append({
                        "Heimteam": home,
                        "Auswärtsteam": away,
                        "Heimtore": int(hg),
                        "Auswärtstore": int(ag),
                        "Datum": details.get("date", ""),
                        "Saison": season
                    })

        except Exception as error:
            errors.append(f"{season}: {error}")

    df = pd.DataFrame(matches)

    if df.empty:
        message = "Keine Spiele wurden geladen."
        if errors:
            message += " API-Fehler: " + " | ".join(errors)
        raise ValueError(message)

    df["Datum"] = pd.to_datetime(
        df["Datum"], errors="coerce", utc=True
    )

    df = df.dropna(subset=["Datum"])
    df = df.drop_duplicates(
        subset=["Heimteam", "Auswärtsteam", "Datum"]
    )

    df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors


# ---------------- GEWICHTETE STATISTIKEN ----------------

def weighted_mean(values, dates, reference_date):
    values = np.asarray(values, dtype=float)
    dates = pd.to_datetime(dates, utc=True)

    age_days = (
        reference_date - dates
    ).dt.total_seconds().to_numpy() / 86400

    age_days = np.maximum(age_days, 0)

    # Ältere Spiele erhalten weniger Gewicht.
    weights = np.exp(-np.log(2) * age_days / 240)

    if weights.sum() == 0:
        return float(np.mean(values))

    return float(np.average(values, weights=weights))


def team_statistics(df, team, venue, reference_date):
    if venue == "home":
        games = df[df["Heimteam"] == team].copy()
        scored_col = "Heimtore"
        conceded_col = "Auswärtstore"
    else:
        games = df[df["Auswärtsteam"] == team].copy()
        scored_col = "Auswärtstore"
        conceded_col = "Heimtore"

    if games.empty:
        return None

    # Letzte 12 Heim- oder Auswärtsspiele stärker berücksichtigen.
    games = games.sort_values("Datum").tail(12)

    scored = weighted_mean(
        games[scored_col], games["Datum"], reference_date
    )
    conceded = weighted_mean(
        games[conceded_col], games["Datum"], reference_date
    )

    return {
        "scored": scored,
        "conceded": conceded,
        "games": len(games)
    }


# ---------------- PROGNOSEMODELL ----------------

def predict_match(df, home_team, away_team):
    if home_team == away_team:
        raise ValueError("Bitte zwei unterschiedliche Teams wählen.")

    # Nur Spiele vor dem Prognosezeitpunkt verwenden.
    reference_date = df["Datum"].max() + pd.Timedelta(seconds=1)

    home_stats = team_statistics(
        df, home_team, "home", reference_date
    )
    away_stats = team_statistics(
        df, away_team, "away", reference_date
    )

    if home_stats is None or away_stats is None:
        raise ValueError(
            "Für eines der Teams fehlen genügend Heim- oder Auswärtsdaten."
        )

    # Liga-Durchschnitt als Basis
    avg_home = weighted_mean(
        df["Heimtore"], df["Datum"], reference_date
    )
    avg_away = weighted_mean(
        df["Auswärtstore"], df["Datum"], reference_date
    )

    if avg_home <= 0 or avg_away <= 0:
        raise ValueError("Die Tordaten dieser Liga sind unvollständig.")

    # Angriffs- und Abwehrstärke relativ zum Ligadurchschnitt
    home_attack = home_stats["scored"] / avg_home
    home_defence = home_stats["conceded"] / avg_away

    away_attack = away_stats["scored"] / avg_away
    away_defence = away_stats["conceded"] / avg_home

    # Extreme Werte abmildern, damit kleine Stichproben
    # nicht zu unrealistischen Torerwartungen führen.
    home_attack = np.clip(home_attack, 0.45, 1.8)
    home_defence = np.clip(home_defence, 0.45, 1.8)
    away_attack = np.clip(away_attack, 0.45, 1.8)
    away_defence = np.clip(away_defence, 0.45, 1.8)

    expected_home = avg_home * home_attack * away_defence
    expected_away = avg_away * away_attack * home_defence

    # Begrenzung für numerische Stabilität
    expected_home = float(np.clip(expected_home, 0.15, 4.5))
    expected_away = float(np.clip(expected_away, 0.15, 4.5))

    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    scorelines = []

    # Gemeinsame Poisson-Wahrscheinlichkeiten
    for h in range(11):
        for a in range(11):
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

    # Auf 100 % normieren
    total = home_win + draw + away_win

    if total <= 0:
        raise ValueError("Die Prognose konnte nicht berechnet werden.")

    home_win /= total
    draw /= total
    away_win /= total

    best_score = max(scorelines, key=lambda item: item[2])

    return {
        "home": home_win,
        "draw": draw,
        "away": away_win,
        "expected_home": expected_home,
        "expected_away": expected_away,
        "score": f"{best_score[0]} : {best_score[1]}",
        "home_games": home_stats["games"],
        "away_games": away_stats["games"]
    }


# ---------------- HOME ----------------

if page == "Home":
    st.title("⚽ KickPredict AI")
    st.subheader("Fussballprognosen auf Datenbasis")

    st.write(
        "Analysiere historische Spielergebnisse und berechne "
        "Wahrscheinlichkeiten für Heimsieg, Unentschieden und Auswärtssieg."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Prognose", "1X2")
    c2.metric("Modell", "Poisson")
    c3.metric("Datenbasis", "Historische Ergebnisse")

    st.markdown("### So funktioniert es")
    st.write(
        "Das Modell berücksichtigt die Heim- und Auswärtstore der Teams "
        "sowie die durchschnittlichen Tore der jeweiligen Liga. "
        "Neuere Spiele werden stärker gewichtet."
    )

    st.warning(
        "Die Prognosen sind Schätzungen. Das Modell berücksichtigt "
        "nicht automatisch Verletzungen, Aufstellungen oder alle "
        "aktuellen Informationen."
    )


# ---------------- SPIELPROGNOSE ----------------

elif page == "Spielprognose":
    st.title("🔮 Spielprognose")

    st.write(
        "Wähle eine Liga, lade die verfügbaren historischen Spiele "
        "und berechne deine Prognose."
    )

    league_name = st.selectbox(
        "Liga auswählen",
        list(LEAGUES.keys()),
        key="league_select"
    )

    # Ligawechsel setzt alte Daten und alte Prognosen zurück.
    if st.session_state.get("active_league") != league_name:
        st.session_state.pop("matches", None)
        st.session_state.pop("load_errors", None)
        st.session_state.pop("prediction", None)
        st.session_state["active_league"] = league_name

    if st.button("Spieldaten laden", key="load_matches"):
        try:
            with st.spinner("Lade historische Spieldaten ..."):
                df, errors = load_matches(LEAGUES[league_name])

            st.session_state["matches"] = df
            st.session_state["load_errors"] = errors
            st.session_state.pop("prediction", None)

            st.success(f"{len(df)} abgeschlossene Spiele geladen.")

        except Exception as error:
            st.session_state.pop("matches", None)
            st.error(str(error))

    df = st.session_state.get("matches")

    if df is not None and not df.empty:
        st.caption(
            f"Liga: {league_name} · "
            f"Zeitraum: {df['Datum'].min().date()} bis "
            f"{df['Datum'].max().date()}"
        )

        errors = st.session_state.get("load_errors", [])
        if errors:
            with st.expander("Hinweise zu nicht geladenen Saisons"):
                for error in errors:
                    st.write(error)

        home_teams = sorted(df["Heimteam"].dropna().unique())
        away_teams = sorted(df["Auswärtsteam"].dropna().unique())

        col1, col2 = st.columns(2)

        with col1:
            home_team = st.selectbox(
                "Heimteam",
                home_teams,
                key="home_team"
            )

        with col2:
            away_team = st.selectbox(
                "Auswärtsteam",
                away_teams,
                key="away_team"
            )

        if st.button("Prognose berechnen", key="calculate"):
            try:
                result = predict_match(df, home_team, away_team)
                st.session_state["prediction"] = {
                    "home_team": home_team,
                    "away_team": away_team,
                    "league": league_name,
                    "result": result
                }
            except Exception as error:
                st.error(str(error))
                st.session_state.pop("prediction", None)

        prediction = st.session_state.get("prediction")

        if (
            prediction
            and prediction["league"] == league_name
            and prediction["home_team"] in home_teams
            and prediction["away_team"] in away_teams
        ):
            result = prediction["result"]

            st.divider()
            st.subheader(
                f"{prediction['home_team']} gegen "
                f"{prediction['away_team']}"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric("1 · Heimsieg", f"{result['home']:.1%}")
            c2.metric("X · Unentschieden", f"{result['draw']:.1%}")
            c3.metric("2 · Auswärtssieg", f"{result['away']:.1%}")

            st.progress(
                min(1.0, max(0.0, result["home"])),
                text="Wahrscheinlichkeit Heimsieg"
            )
            st.progress(
                min(1.0, max(0.0, result["draw"])),
                text="Wahrscheinlichkeit Unentschieden"
            )
            st.progress(
                min(1.0, max(0.0, result["away"])),
                text="Wahrscheinlichkeit Auswärtssieg"
            )

            st.markdown("### Erwartete Tore")
            c1, c2 = st.columns(2)
            c1.metric(
                prediction["home_team"],
                f"{result['expected_home']:.2f}"
            )
            c2.metric(
                prediction["away_team"],
                f"{result['expected_away']:.2f}"
            )

            st.metric(
                "Wahrscheinlichstes Ergebnis",
                result["score"]
            )

            st.caption(
                "Datenbasis: bis zu 12 jüngere Heimspiele des Heimteams "
                "und bis zu 12 jüngere Auswärtsspiele des Auswärtsteams. "
                "Die Prozentwerte sind Modellschätzungen und keine Quoten "
                "eines Buchmachers."
            )

            st.caption(
                f"Verwendete Spiele: {result['home_games']} Heimspiele "
                f"und {result['away_games']} Auswärtsspiele."
            )

    else:
        st.info(
            "Wähle zuerst eine Liga und klicke auf «Spieldaten laden»."
        )


# ---------------- ÜBER UNS ----------------

elif page == "Über uns":
    st.title("Über KickPredict AI")

    st.write(
        "KickPredict AI ist ein Fussballprojekt, das historische "
        "Ergebnisse analysiert und daraus Wahrscheinlichkeiten berechnet."
    )

    st.markdown("### Unser Ziel")
    st.write(
        "Wir wollen Fussballstatistiken verständlich machen und zeigen, "
        "wie Daten bei Spielprognosen eingesetzt werden können."
    )

    st.markdown("### Erstellt von")
    st.write("**Tiago Faruk und Yigit**")

    st.markdown("### Technologie")
    st.write(
        "- Python und Streamlit\n"
        "- API-Football\n"
        "- Pandas und NumPy\n"
        "- Poisson-Modell"
    )

    st.info(
        "Das Projekt garantiert keine bestimmte Trefferquote. "
        "Die Qualität muss mit historischen Testdaten überprüft werden."
    )

st.divider()
st.caption("KickPredict AI © 2026 · Erstellt von Tiago Faruk und Yigit")
