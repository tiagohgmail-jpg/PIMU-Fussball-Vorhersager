
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st


# =========================================================
# KICKPREDICT AI – Einstellungen
# =========================================================

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


# =========================================================
# DESIGN – gut lesbare Texte und klare Kontraste
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --background: #080d18;
    --panel: #111a2b;
    --panel-light: #19253a;
    --accent: #38e8a5;
    --text: #f5f7ff;
    --muted: #b9c5d8;
    --border: #2a3850;
}

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background: var(--background) !important;
    color: var(--text) !important;
}

[data-testid="stHeader"] {
    background: rgba(8, 13, 24, 0.96) !important;
}

[data-testid="stSidebar"] {
    background: #0d1423 !important;
    border-right: 1px solid var(--border);
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
label, h1, h2, h3, h4, p {
    color: var(--text) !important;
    opacity: 1 !important;
}

h1, h2, h3 {
    letter-spacing: -0.5px;
}

h1 {
    font-weight: 800 !important;
}

p, li {
    line-height: 1.65;
}

small, .muted {
    color: var(--muted) !important;
}

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background: var(--panel-light) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}

div[data-baseweb="select"] *,
input {
    color: var(--text) !important;
}

div[data-baseweb="popover"],
ul[data-testid="stSelectboxVirtualDropdown"] {
    background: var(--panel-light) !important;
}

[role="option"] {
    color: var(--text) !important;
    background: var(--panel-light) !important;
}

[role="option"]:hover {
    background: #263751 !important;
}

.stButton > button {
    background: var(--accent) !important;
    color: #06130e !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
    min-height: 44px;
}

.stButton > button p {
    color: #06130e !important;
    font-weight: 800 !important;
}

.stButton > button:hover {
    background: #75f5c2 !important;
    border: none !important;
}

.kp-hero {
    background: linear-gradient(120deg, #142c35, #14203a 60%, #172b36);
    border: 1px solid #2a4850;
    border-radius: 22px;
    padding: 34px;
    margin-bottom: 24px;
}

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

.kp-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 14px;
}

.kp-number {
    font-size: 27px;
    font-weight: 800;
    color: var(--accent) !important;
}

.kp-muted {
    color: var(--muted) !important;
    font-size: 13px;
}

.kp-footer {
    color: var(--muted) !important;
    text-align: center;
    padding: 25px 0;
    border-top: 1px solid var(--border);
    margin-top: 35px;
}

[data-testid="stAlert"] * {
    color: inherit;
}

hr {
    border-color: var(--border) !important;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# DATEN LADEN
# =========================================================

@st.cache_data(ttl=21600, show_spinner=False)
def load_matches(league_id, api_key):
    all_matches = []
    errors = []

    headers = {"x-apisports-key": api_key}

    for season in [2024, 2023, 2022]:
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
                home_goals = goals.get("home")
                away_goals = goals.get("away")

                if (
                    home
                    and away
                    and home_goals is not None
                    and away_goals is not None
                ):
                    all_matches.append({
                        "Datum": pd.to_datetime(
                            fixture.get("date"), utc=True
                        ),
                        "Heim": home,
                        "Auswärts": away,
                        "Tore_Heim": int(home_goals),
                        "Tore_Auswärts": int(away_goals),
                        "Saison": season,
                    })

        except requests.RequestException as exc:
            errors.append(f"Saison {season}: {exc}")

    df = pd.DataFrame(all_matches)

    if df.empty:
        return df, errors

    df = df.drop_duplicates(
        subset=["Datum", "Heim", "Auswärts"]
    ).sort_values("Datum")

    return df, errors


# =========================================================
# MODELL – GEWICHTETE TEAMSTATISTIK
# =========================================================

def weighted_average(values, dates, reference_date):
    values = np.asarray(values, dtype=float)

    dates = pd.to_datetime(dates, utc=True)
    age_days = (
        reference_date - dates
    ).dt.total_seconds().to_numpy() / 86400

    # Neuere Spiele erhalten mehr Gewicht.
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

    scored = weighted_average(
        games[scored_col], games["Datum"], reference_date
    )
    conceded = weighted_average(
        games[conceded_col], games["Datum"], reference_date
    )

    return {
        "scored": scored,
        "conceded": conceded,
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
        raise ValueError("Die Liga-Daten sind unvollständig.")

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

    home_win = 0.0
    draw = 0.0
    away_win = 0.0
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

    if total <= 0:
        raise ValueError("Die Berechnung ist fehlgeschlagen.")

    home_win = home_win / total * 100
    draw = draw / total * 100
    away_win = away_win / total * 100

    most_likely = max(score_probs, key=lambda item: item[2])

    return {
        "home": home_win,
        "draw": draw,
        "away": away_win,
        "expected_home": expected_home,
        "expected_away": expected_away,
        "score": f"{most_likely[0]} : {most_likely[1]}",
        "home_games": home_stats["games"],
        "away_games": away_stats["games"],
        "last_date": df["Datum"].max(),
    }


# =========================================================
# KOPFZEILE UND NAVIGATION
# =========================================================

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
        label_visibility="visible",
    )

    st.divider()
    st.caption("Erstellt von Tiago Faruk und Yigit")


# =========================================================
# HOME
# =========================================================

if page == "Home":
    st.markdown("""
    <div class="kp-hero">
        <div class="kp-tag">DEINE FUSSBALL-ANALYSE</div>
        <h1 style="font-size:42px; margin:0;">
            KickPredict AI
        </h1>
        <p style="font-size:18px; color:#d5e1ef !important;">
            Daten analysieren. Spiele besser einschätzen.
            Fussball verstehen.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Willkommen bei KickPredict")

    st.write(
        "KickPredict AI analysiert historische Spielergebnisse "
        "und berechnet daraus Wahrscheinlichkeiten für "
        "Heimsieg, Unentschieden und Auswärtssieg."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="kp-card">
            <div class="kp-number">1X2</div>
            <b>Spielprognosen</b>
            <p class="kp-muted">
                Drei mögliche Ausgänge eines Spiels vergleichen.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="kp-card">
            <div class="kp-number">⚽</div>
            <b>Torberechnung</b>
            <p class="kp-muted">
                Erwartete Tore und mögliches Resultat anzeigen.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="kp-card">
            <div class="kp-number">📊</div>
            <b>Datenanalyse</b>
            <p class="kp-muted">
                Frühere Spiele als Grundlage nutzen.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "Die Prognosen sind Schätzungen und keine sicheren "
        "Ergebnisse. Die Genauigkeit muss mit echten "
        "Spielresultaten getestet werden."
    )

    if st.button("⚽ Jetzt Spiele analysieren", use_container_width=True):
        st.session_state["page_jump"] = True
        st.rerun()


# =========================================================
# SPIELPROGNOSE
# =========================================================

elif page == "Spielprognose":
    st.title("⚽ Spielprognose")
    st.write(
        "Wähle eine Liga und zwei Teams. KickPredict berechnet "
        "anschliessend die Wahrscheinlichkeiten."
    )

    try:
        api_key = st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        api_key = ""

    if not api_key:
        st.error(
            "Der API-Schlüssel fehlt. Füge in Streamlit unter "
            "Settings → Secrets deinen API_FOOTBALL_KEY ein."
        )
    else:
        selected_league = st.selectbox(
            "Liga auswählen",
            list(LEAGUES.keys()),
        )

        league_id = LEAGUES[selected_league]

        if st.button("📥 Ligadaten laden", use_container_width=True):
            st.cache_data.clear()

        with st.spinner("Historische Spielergebnisse werden geladen..."):
            matches, errors = load_matches(league_id, api_key)

        if errors:
            with st.expander("Details zu Datenmeldungen"):
                for error in errors:
                    st.write(error)

        if matches.empty:
            st.warning(
                "Keine verwendbaren Daten erhalten. Prüfe deinen "
                "API-Schlüssel und die verfügbaren Saisons."
            )
        else:
            min_date = matches["Datum"].min().strftime("%d.%m.%Y")
            max_date = matches["Datum"].max().strftime("%d.%m.%Y")

            st.markdown(
                f"""
                <div class="kp-card">
                    <b>{selected_league}</b>
                    <p class="kp-muted">
                        {len(matches)} historische Spiele ·
                        Datenzeitraum {min_date} bis {max_date}
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
                    "🏠 Heimteam",
                    teams,
                    index=0,
                    key="home_team",
                )

            with col2:
                away_options = [team for team in teams if team != home_team]
                away_team = st.selectbox(
                    "✈️ Auswärtsteam",
                    away_options,
                    index=0,
                    key="away_team",
                )

            if st.button("🔮 Prognose berechnen", use_container_width=True):
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
                and prediction["home_team"] in teams
                and prediction["away_team"] in teams
            ):
                result = prediction["result"]

                st.divider()
                st.subheader("📊 Ergebnis der Analyse")
                st.markdown(
                    f"### {prediction['home_team']} vs. "
                    f"{prediction['away_team']}"
                )

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
                            <div class="kp-number">
                                {result['expected_home']:.2f}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with b:
                    st.markdown(
                        f"""
                        <div class="kp-card">
                            <div class="kp-muted">Erwartete Tore Auswärts</div>
                            <div class="kp-number">
                                {result['expected_away']:.2f}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with c:
                    st.markdown(
                        f"""
                        <div class="kp-card">
                            <div class="kp-muted">Wahrscheinlichstes Resultat</div>
                            <div class="kp-number">
                                {result['score']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.caption(
                    "Grundlage: bis zu 12 jüngste verfügbare Heimspiele "
                    "und Auswärtsspiele je Team. Die Daten können veraltet "
                    "sein; das Modell garantiert keine Trefferquote."
                )

                st.warning(
                    "Hinweis: Die Prozentwerte sind Modellschätzungen, "
                    "keine Gewinnchancen und keine Garantie für das Resultat."
                )


# =========================================================
# ÜBER UNS
# =========================================================

elif page == "Über uns":
    st.title("Über KickPredict AI")

    st.markdown("""
    <div class="kp-hero">
        <div class="kp-tag">UNSER PROJEKT</div>
        <h1>Fussball trifft Datenanalyse.</h1>
        <p style="color:#d5e1ef !important;">
            KickPredict AI ist ein Projekt, das historische
            Fussballresultate nutzt, um mögliche Spielausgänge
            besser einzuschätzen.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Was macht die Website?")

    st.write(
        "Die Website berechnet Wahrscheinlichkeiten für Heimsieg, "
        "Unentschieden und Auswärtssieg. Zusätzlich schätzt sie die "
        "erwarteten Tore und zeigt ein mögliches Resultat an."
    )

    st.subheader("Wie funktioniert die Prognose?")

    st.write(
        "Das Modell vergleicht historische Tore der Teams und "
        "berücksichtigt dabei Heim- und Auswärtsspiele. Neuere "
        "Spiele werden stärker gewichtet. Daraus werden mit einem "
        "Poisson-Modell Wahrscheinlichkeiten berechnet."
    )

    st.subheader("Wer steckt dahinter?")

    st.markdown("""
    <div class="kp-card">
        <h3>Tiago Faruk und Yigit</h3>
        <p class="kp-muted">
            Entwicklung und Gestaltung des Projekts KickPredict AI.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Unsere Ziele")

    st.write(
        "Wir möchten eine übersichtliche Fussballanalyse anbieten "
        "und das Modell mit mehr Daten und Tests laufend verbessern."
    )

    st.info(
        "Transparenz: Eine hohe Trefferquote ist nicht garantiert. "
        "Die Leistung muss anhand vergangener Spiele überprüft werden."
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("""
<div class="kp-footer">
    <b>KickPredict AI</b><br>
    Erstellt von Tiago Faruk und Yigit<br>
    <span>Fussballprognosen · Datenanalyse · 2026</span>
</div>
""", unsafe_allow_html=True)
