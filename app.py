
import math
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

API_URL = "https://v3.football.api-sports.io"

LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Champions League": 2,
    "Nations League": 5,
    "Conference League": 848,
}

FINISHED = {"FT", "AET", "PEN"}
UPCOMING = {"NS", "TBD"}

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ KickPredict AI")
st.caption("Deine Fussball-Prognoseplattform · Erstellt von Tiago Faruk und Yigit")

st.info(
    "KickPredict verwendet historische Resultate und ein Poisson-Modell. "
    "Die Wahrscheinlichkeiten sind Modellschätzungen, keine sicheren Tipps."
)

if "API_FOOTBALL_KEY" not in st.secrets:
    st.error(
        "API-Schlüssel fehlt. Trage API_FOOTBALL_KEY in "
        "Streamlit → Settings → Secrets ein."
    )
    st.stop()

API_KEY = st.secrets["API_FOOTBALL_KEY"]


@st.cache_data(ttl=21600, show_spinner=False)
def get_fixtures(league_id, season, api_key):
    """Lädt Spiele einer Liga und Saison; Cache für sechs Stunden."""
    response = requests.get(
        f"{API_URL}/fixtures",
        headers={"x-apisports-key": api_key},
        params={"league": league_id, "season": season},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        raise ValueError(str(data["errors"]))

    return data.get("response", [])


def fixtures_to_df(fixtures, league_name):
    rows = []

    for item in fixtures:
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        league = item.get("league", {})

        rows.append({
            "Date": pd.to_datetime(
                fixture.get("date"), errors="coerce", utc=True
            ),
            "League": league_name,
            "LeagueID": league.get("id"),
            "Season": league.get("season"),
            "HomeTeam": teams.get("home", {}).get("name"),
            "AwayTeam": teams.get("away", {}).get("name"),
            "HomeID": teams.get("home", {}).get("id"),
            "AwayID": teams.get("away", {}).get("id"),
            "FTHG": goals.get("home"),
            "FTAG": goals.get("away"),
            "Status": fixture.get("status", {}).get("short"),
            "Venue": fixture.get("venue", {}).get("name"),
        })

    return pd.DataFrame(rows)


def load_competition_data(league_name, league_id):
    """Lädt die letzte und aktuelle Saison, sofern verfügbar."""
    all_rows = []
    errors = []

    current_year = date.today().year

    for season in (current_year - 1, current_year):
        try:
            fixtures = get_fixtures(league_id, season, API_KEY)
            all_rows.extend(fixtures_to_df(fixtures, league_name).to_dict("records"))
        except Exception as exc:
            errors.append(f"{season}: {exc}")

    if not all_rows:
        return pd.DataFrame(), errors

    df = pd.DataFrame(all_rows)
    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam"])
    df = df.drop_duplicates(
        subset=["LeagueID", "Season", "HomeID", "AwayID", "Date"]
    )
    return df.sort_values("Date"), errors


def poisson_probs(lam, max_goals=10):
    probabilities = [
        math.exp(-lam) * (lam ** goals) / math.factorial(goals)
        for goals in range(max_goals + 1)
    ]
    total = sum(probabilities)
    return [p / total for p in probabilities]


def team_rates(history, team):
    matches = history[
        (history["HomeTeam"] == team) | (history["AwayTeam"] == team)
    ].sort_values("Date").tail(10)

    scored, conceded = [], []

    for _, match in matches.iterrows():
        if match["HomeTeam"] == team:
            scored.append(float(match["FTHG"]))
            conceded.append(float(match["FTAG"]))
        else:
            scored.append(float(match["FTAG"]))
            conceded.append(float(match["FTHG"]))

    if not scored:
        return None, None

    return sum(scored) / len(scored), sum(conceded) / len(conceded)


def predict(history, home, away):
    history = history.dropna(subset=["FTHG", "FTAG"]).copy()

    if history.empty:
        raise ValueError("Für diese Liga gibt es noch keine Resultate.")

    avg_home = max(float(history["FTHG"].mean()), 0.2)
    avg_away = max(float(history["FTAG"].mean()), 0.2)

    home_scored, home_conceded = team_rates(history, home)
    away_scored, away_conceded = team_rates(history, away)

    if home_scored is None or away_scored is None:
        raise ValueError(
            "Für eines der Teams fehlen historische Resultate."
        )

    home_attack = home_scored / avg_home
    home_defence = home_conceded / avg_away
    away_attack = away_scored / avg_away
    away_defence = away_conceded / avg_home

    home_lambda = avg_home * home_attack * away_defence * 1.08
    away_lambda = avg_away * away_attack * home_defence * 0.94

    home_lambda = max(0.15, min(home_lambda, 4.0))
    away_lambda = max(0.15, min(away_lambda, 4.0))

    home_probs = poisson_probs(home_lambda)
    away_probs = poisson_probs(away_lambda)

    p_home = p_draw = p_away = 0.0
    best_score = "1–1"
    best_probability = -1.0

    for hg, ph in enumerate(home_probs):
        for ag, pa in enumerate(away_probs):
            probability = ph * pa

            if hg > ag:
                p_home += probability
            elif hg == ag:
                p_draw += probability
            else:
                p_away += probability

            if probability > best_probability:
                best_probability = probability
                best_score = f"{hg}–{ag}"

    return {
        "1 – Heimsieg": p_home,
        "X – Unentschieden": p_draw,
        "2 – Auswärtssieg": p_away,
    }, best_score, home_lambda, away_lambda


with st.sidebar:
    st.header("⚙️ Einstellungen")
    competition = st.selectbox("Liga / Wettbewerb", list(LEAGUES.keys()))
    st.caption("Spieldaten werden automatisch geladen.")
    if st.button("🔄 Daten aktualisieren"):
        get_fixtures.clear()
        st.rerun()

league_id = LEAGUES[competition]

with st.spinner(f"Lade Fussballdaten für {competition} …"):
    try:
        all_matches, load_errors = load_competition_data(
            competition, league_id
        )
    except Exception as exc:
        st.error(f"Fehler beim Laden der API-Daten: {exc}")
        st.stop()

if all_matches.empty:
    st.warning(
        "Es wurden keine Spiele geladen. Prüfe deinen API-Schlüssel, "
        "dein API-Limit und ob die Liga für diese Saisons verfügbar ist."
    )
    if load_errors:
        with st.expander("Details zum Fehler"):
            st.write("\n".join(load_errors))
    st.stop()

history = all_matches[
    all_matches["Status"].isin(FINISHED)
    & all_matches["FTHG"].notna()
    & all_matches["FTAG"].notna()
].copy()

upcoming = all_matches[
    all_matches["Status"].isin(UPCOMING)
    & (all_matches["Date"] >= pd.Timestamp.now(tz="UTC"))
].copy()

m1, m2, m3 = st.columns(3)
m1.metric("Geladene Spiele", len(all_matches))
m2.metric("Abgeschlossene Spiele", len(history))
m3.metric("Kommende Spiele", len(upcoming))

st.divider()
st.subheader("🔮 Spielprognosen")

if history.empty:
    st.warning(
        "Für diesen Wettbewerb wurden noch keine abgeschlossenen Spiele "
        "gefunden. Ohne historische Resultate kann das Modell nicht rechnen."
    )
else:
    teams = sorted(
        set(history["HomeTeam"].astype(str))
        | set(history["AwayTeam"].astype(str))
    )

    if upcoming.empty:
        st.info(
            "Die API hat aktuell keine kommenden Spiele mit dem Status "
            "NS oder TBD geliefert. Du kannst unten eine eigene Paarung wählen."
        )
        col1, col2 = st.columns(2)
        with col1:
            home = st.selectbox("Heimteam", teams, key="manual_home")
        with col2:
            away_options = [team for team in teams if team != home]
            away = st.selectbox("Auswärtsteam", away_options, key="manual_away")
    else:
        upcoming = upcoming.copy()
        upcoming["Anzeige"] = (
            upcoming["Date"].dt.strftime("%d.%m.%Y %H:%M UTC")
            + " · " + upcoming["HomeTeam"]
            + " – " + upcoming["AwayTeam"]
        )
        selected = st.selectbox(
            "Kommendes Spiel auswählen",
            upcoming.index,
            format_func=lambda i: upcoming.loc[i, "Anzeige"],
        )
        home = upcoming.loc[selected, "HomeTeam"]
        away = upcoming.loc[selected, "AwayTeam"]

    if home == away:
        st.error("Bitte zwei verschiedene Teams auswählen.")
    else:
        try:
            outcomes, score, lh, la = predict(history, home, away)
            best = max(outcomes, key=outcomes.get)

            st.subheader(f"{home} – {away}")
            st.metric(
                "Modell-Tipp",
                best,
                f"{outcomes[best] * 100:.1f} % Wahrscheinlichkeit",
            )

            cols = st.columns(3)
            for col, (name, probability) in zip(cols, outcomes.items()):
                col.metric(name, f"{probability * 100:.1f} %")

            st.write(f"**Häufigstes genaues Resultat:** {score}")
            st.caption(
                f"Erwartete Tore: {home} {lh:.2f} · {away} {la:.2f}"
            )

            chart = pd.DataFrame({
                "Wahrscheinlichkeit (%)": [
                    probability * 100 for probability in outcomes.values()
                ]
            }, index=list(outcomes.keys()))
            st.bar_chart(chart)

        except ValueError as exc:
            st.warning(str(exc))

st.divider()
st.subheader("📅 Aktuelle Spieldaten")

if not upcoming.empty:
    display = upcoming[
        ["Date", "HomeTeam", "AwayTeam", "Status", "Venue"]
    ].copy()
    display["Date"] = display["Date"].dt.strftime("%d.%m.%Y %H:%M UTC")
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.write("Keine kommenden Spiele gefunden.")

st.caption(
    "KickPredict AI ist ein Prognose-Prototyp. Datenabdeckung, "
    "Modellwahrscheinlichkeiten und Trefferquote können variieren. "
    "Es gibt keine Garantie für richtige Tipps."
)

