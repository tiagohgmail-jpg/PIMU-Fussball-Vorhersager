
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

# =====================================================
# KICKPREDICT AI
# =====================================================

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = "https://v3.football.api-sports.io"

LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Champions League": 2,
    "Conference League": 848,
}


# =====================================================
# DESIGN
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #080d18;
    --panel: #111a2b;
    --panel2: #19253a;
    --border: #2a3850;
    --white: #f5f7ff;
    --muted: #b9c5d8;
    --green: #38e8a5;
}

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background-color: var(--bg) !important;
    color: var(--white) !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"] {
    background: rgba(8,13,24,.95) !important;
}

[data-testid="stSidebar"] {
    background: #0d1423 !important;
    border-right: 1px solid var(--border);
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
h1, h2, h3, h4, label {
    color: var(--white) !important;
    opacity: 1 !important;
}

p, li { line-height: 1.65; }

.kp-card {
    background: var(--panel) !important;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 14px;
    color: var(--white) !important;
}

.kp-card * { color: var(--white) !important; }

.kp-number {
    color: var(--green) !important;
    font-size: 27px;
    font-weight: 800;
}

.kp-muted {
    color: var(--muted) !important;
    font-size: 13px;
}

.kp-hero {
    background: linear-gradient(120deg,#142c35,#14203a,#172b36);
    border: 1px solid #2a4850;
    border-radius: 22px;
    padding: 32px;
    margin-bottom: 24px;
}

.kp-hero h1 { color: #fff !important; }
.kp-hero p { color: #d5e1ef !important; }

.kp-tag {
    display: inline-block;
    color: #70f5bf !important;
    background: #17352f;
    border: 1px solid #285f4c;
    padding: 7px 12px;
    border-radius: 30px;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 14px;
}

/* Dropdown-Feld */
div[data-baseweb="select"] > div {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
}

div[data-baseweb="select"] > div * {
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
}

div[data-baseweb="select"] svg {
    fill: #111827 !important;
}

/* Eingabefelder */
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div {
    background: #fff !important;
    border: 1px solid #cbd5e1 !important;
}

div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea,
input, textarea {
    background: #fff !important;
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
    caret-color: #111827 !important;
}

input::placeholder, textarea::placeholder {
    color: #64748b !important;
    -webkit-text-fill-color: #64748b !important;
}

/* Dropdown-Auswahlliste */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[data-testid="stSelectboxVirtualDropdown"] {
    background: #fff !important;
    color: #111827 !important;
}

div[data-baseweb="popover"] *,
div[data-baseweb="menu"] *,
[role="option"] {
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
}

[role="option"] { background: #fff !important; }

[role="option"]:hover,
[aria-selected="true"] {
    background: #e2e8f0 !important;
    color: #111827 !important;
}

[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label {
    color: var(--white) !important;
}

.stButton > button {
    background: var(--green) !important;
    color: #06130e !important;
    border: none !important;
    border-radius: 10px !important;
    min-height: 44px;
    font-weight: 800 !important;
}

.stButton > button *,
.stButton > button p {
    color: #06130e !important;
    -webkit-text-fill-color: #06130e !important;
    font-weight: 800 !important;
}

.stButton > button:hover { background: #75f5c2 !important; }

[data-testid="stMetric"] {
    background: var(--panel) !important;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
}

[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
    color: var(--muted) !important;
}

[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    color: var(--green) !important;
}

hr { border-color: var(--border) !important; }

.kp-footer {
    color: var(--muted) !important;
    text-align: center;
    padding: 25px 0;
    border-top: 1px solid var(--border);
    margin-top: 35px;
}
.kp-footer * { color: var(--muted) !important; }
</style>
""", unsafe_allow_html=True)


# =====================================================
# DATEN LADEN: 2022 BIS ZUM AKTUELLEN JAHR
# =====================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_matches(league_id, api_key):
    headers = {"x-apisports-key": api_key}
    all_matches = []
    errors = []

    current_year = datetime.now(timezone.utc).year

    # Für europäische Ligen ist die Saison meist mit dem
    # Startjahr benannt. Deshalb werden alle Jahre geprüft.
    seasons = list(range(2022, current_year + 1))

    for season in seasons:
        try:
            response = requests.get(
                f"{API_URL}/fixtures",
                headers=headers,
                params={
                    "league": league_id,
                    "season": season,
                    "status": "FT",
                },
                timeout=25,
            )

            if response.status_code != 200:
                errors.append(
                    f"Saison {season}: HTTP {response.status_code}"
                )
                continue

            data = response.json()

            if data.get("errors"):
                errors.append(
                    f"Saison {season}: {data['errors']}"
                )
                continue

            for item in data.get("response", []):
                fixture = item.get("fixture", {})
                teams = item.get("teams", {})
                goals = item.get("goals", {})

                home = teams.get("home", {}).get("name")
                away = teams.get("away", {}).get("name")
                hg = goals.get("home")
                ag = goals.get("away")

                # Nur Spiele mit tatsächlichem Endresultat
                if (
                    home and away
                    and hg is not None
                    and ag is not None
                    and fixture.get("status", {}).get("short") == "FT"
                ):
                    all_matches.append({
                        "Datum": pd.to_datetime(
                            fixture.get("date"), utc=True
                        ),
                        "Heim": home,
                        "Auswärts": away,
                        "Tore_Heim": int(hg),
                        "Tore_Auswärts": int(ag),
                        "Saison": season,
                    })

        except requests.RequestException as exc:
            errors.append(f"Saison {season}: {exc}")

    df = pd.DataFrame(all_matches)

    if df.empty:
        return df, errors

    df = df.drop_duplicates(
        subset=["Datum", "Heim", "Auswärts"]
    )

    df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors


# =====================================================
# MODELL
# =====================================================

def weighted_average(values, dates, reference_date):
    values = np.asarray(values, dtype=float)
    dates = pd.to_datetime(dates, utc=True)

    age_days = (
        reference_date - dates
    ).dt.total_seconds().to_numpy() / 86400

    weights = np.exp(
        -np.maximum(age_days, 0) * math.log(2) / 240
    )

    if weights.sum() == 0:
        return float(np.mean(values))

    return float(np.average(values, weights=weights))


def team_statistics(df, team, venue, reference_date):
    if venue == "home":
        games = df[df["Heim"] == team].copy()
        scored_col = "Tore_Heim"
        conceded_col = "Tore_Auswärts"
    else:
        games = df[df["Auswärts"] == team].copy()
        scored_col = "Tore_Auswärts"
        conceded_col = "Tore_Heim"

    games = games.sort_values("Datum").tail(12)

    if len(games) < 3:
        return None

    return {
        "scored": weighted_average(
            games[scored_col], games["Datum"], reference_date
        ),
        "conceded": weighted_average(
            games[conceded_col], games["Datum"], reference_date
        ),
        "games": len(games),
    }


def poisson_probability(goals, expected):
    return (
        math.exp(-expected)
        * expected ** goals
        / math.factorial(goals)
    )


def predict_match(df, home_team, away_team):
    if home_team == away_team:
        raise ValueError("Bitte wähle zwei verschiedene Teams.")

    reference_date = df["Datum"].max() + pd.Timedelta(seconds=1)

    home_stats = team_statistics(
        df, home_team, "home", reference_date
    )
    away_stats = team_statistics(
        df, away_team, "away", reference_date
    )

    if home_stats is None or away_stats is None:
        raise ValueError(
            "Für mindestens ein Team gibt es zu wenige "
            "Heim- oder Auswärtsspiele."
        )

    avg_home = float(df["Tore_Heim"].mean())
    avg_away = float(df["Tore_Auswärts"].mean())

    if avg_home <= 0 or avg_away <= 0:
        raise ValueError("Die Ligadaten sind unvollständig.")

    home_attack = np.clip(
        home_stats["scored"] / avg_home, 0.45, 1.8
    )
    away_defence = np.clip(
        away_stats["conceded"] / avg_home, 0.45, 1.8
    )
    away_attack = np.clip(
        away_stats["scored"] / avg_away, 0.45, 1.8
    )
    home_defence = np.clip(
        home_stats["conceded"] / avg_away, 0.45, 1.8
    )

    expected_home = float(np.clip(
        avg_home * home_attack * away_defence, 0.15, 4.5
    ))
    expected_away = float(np.clip(
        avg_away * away_attack * home_defence, 0.15, 4.5
    ))

    home_win = draw = away_win = 0.0
    score_probs = []

    for hg in range(11):
        for ag in range(11):
            probability = (
                poisson_probability(hg, expected_home)
                * poisson_probability(ag, expected_away)
            )

            score_probs.append((hg, ag, probability))

            if hg > ag:
                home_win += probability
            elif hg == ag:
                draw += probability
            else:
                away_win += probability

    total = home_win + draw + away_win
    best_score = max(score_probs, key=lambda x: x[2])

    return {
        "home": home_win / total * 100,
        "draw": draw / total * 100,
        "away": away_win / total * 100,
        "expected_home": expected_home,
        "expected_away": expected_away,
        "score": f"{best_score[0]} : {best_score[1]}",
        "home_games": home_stats["games"],
        "away_games": away_stats["games"],
        "last_date": df["Datum"].max(),
    }


# =====================================================
# NAVIGATION
# =====================================================

with st.sidebar:
    st.markdown(
        '<div class="kp-tag">⚽ FOOTBALL INTELLIGENCE</div>',
        unsafe_allow_html=True,
    )
    st.markdown("## KickPredict AI")
    st.caption("Fussballprognosen mit Datenanalyse")
    st.divider()

    page = st.radio(
        "Navigation",
        ["Home", "Spielprognose", "Über uns"],
    )

    st.divider()
    st.caption("Erstellt von Tiago Faruk und Yigit")


# =====================================================
# HOME
# =====================================================

if page == "Home":
    st.markdown("""
    <div class="kp-hero">
        <div class="kp-tag">DEINE FUSSBALL-ANALYSE</div>
        <h1 style="font-size:42px;margin:0;">KickPredict AI</h1>
        <p style="font-size:18px;">
            Spiele analysieren. Wahrscheinlichkeiten verstehen.
            Fussball datenbasiert einschätzen.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Willkommen bei KickPredict")

    st.write(
        "KickPredict AI analysiert historische Spielergebnisse "
        "und berechnet Wahrscheinlichkeiten für Heimsieg, "
        "Unentschieden und Auswärtssieg."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="kp-card">
            <div class="kp-number">1X2</div>
            <b>Spielprognosen</b>
            <p class="kp-muted">Drei mögliche Spielausgänge vergleichen.</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="kp-card">
            <div class="kp-number">⚽</div>
            <b>Torberechnung</b>
            <p class="kp-muted">Erwartete Tore und Resultate einschätzen.</p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="kp-card">
            <div class="kp-number">📊</div>
            <b>Historische Daten</b>
            <p class="kp-muted">Spiele ab 2022 berücksichtigen.</p>
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "Die Prognosen sind Schätzungen. Eine bestimmte "
        "Trefferquote kann nicht garantiert werden."
    )


# =====================================================
# SPIELPROGNOSE
# =====================================================

elif page == "Spielprognose":
    st.title("⚽ Spielprognose")
    st.write(
        "Wähle eine Liga und zwei Teams, um eine Prognose "
        "auf Basis historischer Ergebnisse zu berechnen."
    )

    try:
        api_key = st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        api_key = ""

    if not api_key:
        st.error(
            "API-Schlüssel nicht gefunden. Öffne Streamlit "
            "Settings → Secrets und prüfe API_FOOTBALL_KEY."
        )
    else:
        selected_league = st.selectbox(
            "Liga auswählen", list(LEAGUES.keys())
        )

        if st.button(
            "📥 Daten aktualisieren",
            use_container_width=True,
        ):
            load_matches.clear()
            st.session_state.pop("prediction", None)
            st.rerun()

        with st.spinner(
            "Spiele ab 2022 bis zur neuesten verfügbaren Saison werden geladen..."
        ):
            matches, errors = load_matches(
                LEAGUES[selected_league], api_key
            )

        if errors:
            with st.expander("API-Meldungen anzeigen"):
                for error in errors:
                    st.write(error)

        if matches.empty:
            st.warning(
                "Keine Spieldaten erhalten. Prüfe deinen API-Zugang "
                "und ob die angefragten Saisons freigeschaltet sind."
            )
        else:
            first_date = matches["Datum"].min().strftime("%d.%m.%Y")
            last_date = matches["Datum"].max().strftime("%d.%m.%Y")

            st.markdown(
                f"""
                <div class="kp-card">
                    <b>{selected_league}</b>
                    <p class="kp-muted">
                        {len(matches)} abgeschlossene Spiele ·
                        {first_date} bis {last_date}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            teams = sorted(
                set(matches["Heim"]).union(set(matches["Auswärts"]))
            )

            col1, col2 = st.columns(2)

            with col1:
                home_team = st.selectbox(
                    "🏠 Heimteam", teams, key="home_team"
                )

            away_options = [
                team for team in teams if team != home_team
            ]

            with col2:
                away_team = st.selectbox(
                    "✈️ Auswärtsteam",
                    away_options,
                    key="away_team",
                )

            if st.button(
                "🔮 Prognose berechnen",
                use_container_width=True,
            ):
                try:
                    result = predict_match(
                        matches, home_team, away_team
                    )
                    st.session_state["prediction"] = {
                        "home_team": home_team,
                        "away_team": away_team,
                        "league": selected_league,
                        "result": result,
                    }
                except ValueError as exc:
                    st.error(str(exc))

            prediction = st.session_state.get("prediction")

            if (
                prediction
                and prediction["league"] == selected_league
                and prediction["home_team"] == home_team
                and prediction["away_team"] == away_team
            ):
                result = prediction["result"]

                st.divider()
                st.subheader("📊 Ergebnis der Analyse")
                st.markdown(f"### {home_team} vs. {away_team}")

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.metric("Heimsieg (1)", f"{result['home']:.1f}%")
                with c2:
                    st.metric("Unentschieden (X)", f"{result['draw']:.1f}%")
                with c3:
                    st.metric("Auswärtssieg (2)", f"{result['away']:.1f}%")

                st.markdown("#### Wahrscheinlichkeiten")

                st.progress(int(round(result["home"])))
                st.caption(f"1 · Heimsieg: {result['home']:.1f}%")

                st.progress(int(round(result["draw"])))
                st.caption(f"X · Unentschieden: {result['draw']:.1f}%")

                st.progress(int(round(result["away"])))
                st.caption(f"2 · Auswärtssieg: {result['away']:.1f}%")

                a, b, c = st.columns(3)

                with a:
                    st.markdown(
                        f"""
                        <div class="kp-card">
                            <div class="kp-muted">Erwartete Tore Heim</div>
                            <div class="kp-number">{result['expected_home']:.2f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with b:
                    st.markdown(
                        f"""
                        <div class="kp-card">
                            <div class="kp-muted">Erwartete Tore Auswärts</div>
                            <div class="kp-number">{result['expected_away']:.2f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with c:
                    st.markdown(
                        f"""
                        <div class="kp-card">
                            <div class="kp-muted">Wahrscheinlichstes Resultat</div>
                            <div class="kp-number">{result['score']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.caption(
                    f"Das Modell nutzt bis zu 12 Heimspiele von "
                    f"{home_team} und 12 Auswärtsspiele von "
                    f"{away_team}. Neuere Spiele werden stärker gewichtet."
                )

                st.warning(
                    "Die Werte sind statistische Schätzungen und "
                    "keine Garantie für den Spielausgang."
                )


# =====================================================
# ÜBER UNS
# =====================================================

elif page == "Über uns":
    st.title("Über KickPredict AI")

    st.markdown("""
    <div class="kp-hero">
        <div class="kp-tag">UNSER PROJEKT</div>
        <h1>Fussball trifft Datenanalyse.</h1>
        <p>
            KickPredict AI nutzt historische Spielergebnisse,
            um mögliche Fussballresultate statistisch einzuschätzen.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Was macht die Website?")
    st.write(
        "Die Website berechnet Wahrscheinlichkeiten für Heimsieg, "
        "Unentschieden und Auswärtssieg. Sie schätzt auch erwartete "
        "Tore und ein mögliches Resultat."
    )

    st.subheader("Wie funktioniert die Prognose?")
    st.write(
        "Das Modell vergleicht historische Tore der Teams und "
        "berücksichtigt Heim- und Auswärtsspiele. Neuere Spiele "
        "werden stärker gewichtet. Ein Poisson-Modell berechnet "
        "anschliessend die Wahrscheinlichkeiten."
    )

    st.subheader("Wer steckt dahinter?")
    st.markdown("""
    <div class="kp-card">
        <h3>Tiago Faruk und Yigit</h3>
        <p class="kp-muted">
            Entwicklung und Gestaltung von KickPredict AI.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "Die tatsächliche Trefferquote muss mit echten Ergebnissen "
        "getestet werden. Hohe Genauigkeit ist nicht garantiert."
    )


# =====================================================
# FOOTER
# =====================================================

st.markdown("""
<div class="kp-footer">
    <b>KickPredict AI</b><br>
    Erstellt von Tiago Faruk und Yigit<br>
    Fussballprognosen · Datenanalyse · 2026
</div>
""", unsafe_allow_html=True)
