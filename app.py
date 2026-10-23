
import math
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

API_URL = "https://v3.football.api-sports.io"
START_YEAR = 2022

LEAGUES = {
    "Premier League 🇬🇧": 39,
    "La Liga 🇪🇸": 140,
    "Bundesliga 🇩🇪": 78,
    "Serie A 🇮🇹": 135,
    "Ligue 1 🇫🇷": 61,
    "Champions League 🏆": 2,
    "Europa League 🌍": 3,
    "Super League 🇨🇭": 207,
}

GREEN = "#4be0a0"
GREEN_LIGHT = "#85f3be"
DARK = "#122238"
DARKER = "#0b192a"
TEXT = "#f4f7fb"
MUTED = "#aebfd2"
GRID = "#293f58"

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- DESIGN ----------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f 0%, #0b192a 55%, #102a36 100%);
    color: #f4f7fb;
}
[data-testid="stSidebar"] {
    background: #07111e;
    border-right: 1px solid #21364b;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: #c2d0df;
}
.hero {
    padding: 30px;
    border-radius: 20px;
    background: linear-gradient(115deg, #142943, #12513f);
    border: 1px solid #315b68;
    margin-bottom: 22px;
}
.hero h1 {
    font-size: 42px;
    font-weight: 850;
    margin-bottom: 8px;
    color: #f4f7fb;
}
.hero p {
    color: #d2e2ee;
    font-size: 17px;
}
.eyebrow {
    color: #63edaf;
    text-transform: uppercase;
    font-weight: 800;
    letter-spacing: 2px;
    font-size: 12px;
}
.panel {
    background: #122238;
    border: 1px solid #293f58;
    border-radius: 15px;
    padding: 18px;
    margin-bottom: 12px;
}
.metric {
    background: linear-gradient(145deg, #152940, #101e31);
    border: 1px solid #2b435e;
    border-radius: 15px;
    padding: 18px;
    min-height: 115px;
}
.metric-label {
    color: #aebfd2;
    font-size: 13px;
}
.metric-value {
    color: #5ce6a6;
    font-size: 28px;
    font-weight: 850;
    margin-top: 5px;
}
.muted {
    color: #aebfd2;
    font-size: 13px;
}
div.stButton > button {
    background: #4be0a0;
    color: #07131c;
    border: 0;
    border-radius: 10px;
    font-weight: 800;
    min-height: 43px;
}
div.stButton > button:hover {
    background: #85f3be;
    color: #07131c;
}
hr {
    border-color: #273d53;
}
h1, h2, h3, h4, p, label {
    color: #f4f7fb;
}
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border: 1px solid #293f58;
    border-radius: 12px;
}
[data-testid="stAlert"] {
    background: #14263a;
    border: 1px solid #293f58;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)


# ---------- DUNKLE DIAGRAMME ----------
def dark_bar_chart(data, title=None, x_title=None, y_title=None,
                   horizontal=False, color=GREEN):
    """Erstellt ein Diagramm im dunklen KickPredict-Design."""
    if isinstance(data, pd.Series):
        chart_df = data.rename("Wert").reset_index()
        chart_df.columns = ["Kategorie", "Wert"]
    else:
        chart_df = data.reset_index()
        first_column = chart_df.columns[0]
        chart_df = chart_df.rename(columns={first_column: "Kategorie"})

    if horizontal:
        fig = px.bar(
            chart_df,
            x=chart_df.columns[-1],
            y="Kategorie",
            orientation="h",
            title=title,
            color_discrete_sequence=[color],
            text=chart_df.columns[-1],
        )
        fig.update_traces(
            texttemplate="%{text:.2f}",
            textposition="outside",
            cliponaxis=False,
            marker_line_width=0,
        )
    else:
        value_columns = [
            col for col in chart_df.columns if col != "Kategorie"
        ]
        fig = go.Figure()

        for i, column in enumerate(value_columns):
            series_color = GREEN if i == 0 else "#52a8ff"
            fig.add_trace(go.Bar(
                x=chart_df["Kategorie"],
                y=chart_df[column],
                name=str(column),
                marker_color=series_color,
                marker_line_width=0,
                text=chart_df[column],
                texttemplate="%{text:.2f}",
                textposition="outside",
                cliponaxis=False,
            ))

        fig.update_layout(barmode="group")

    fig.update_layout(
        title=dict(
            text=title or "",
            font=dict(color=TEXT, size=18),
            x=0.02,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=DARK,
        font=dict(
            family="Arial, sans-serif",
            color=TEXT,
            size=12,
        ),
        margin=dict(l=18, r=28, t=55 if title else 25, b=45),
        height=390,
        legend=dict(
            font=dict(color=TEXT),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title=x_title,
            color=MUTED,
            gridcolor=GRID,
            linecolor=GRID,
            tickfont=dict(color=MUTED),
            zerolinecolor=GRID,
        ),
        yaxis=dict(
            title=y_title,
            color=MUTED,
            gridcolor=GRID,
            linecolor=GRID,
            tickfont=dict(color=MUTED),
            zerolinecolor=GRID,
        ),
        hoverlabel=dict(
            bgcolor="#07111e",
            font_color=TEXT,
            bordercolor=GREEN,
        ),
    )

    st.plotly_chart(fig, use_container_width=True)


def dark_outcome_chart(labels, values, title):
    """Einheitliche grüne Ergebnisbalken mit Prozent- oder Zahlenwerten."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        marker=dict(
            color=[GREEN, "#6bbf9a", "#328c6a"][:len(labels)],
            line=dict(width=0),
        ),
        text=[
            f"{v:.1f}%" if title == "Spielprognose" else f"{v:,.0f}".replace(",", ".")
            for v in values
        ],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{x}: %{y:.1f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(color=TEXT, size=18), x=0.02),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=DARK,
        font=dict(color=TEXT, family="Arial, sans-serif"),
        margin=dict(l=18, r=25, t=55, b=45),
        height=360,
        showlegend=False,
        xaxis=dict(
            color=MUTED,
            gridcolor=GRID,
            linecolor=GRID,
            tickfont=dict(color=MUTED),
        ),
        yaxis=dict(
            color=MUTED,
            gridcolor=GRID,
            linecolor=GRID,
            rangemode="tozero",
        ),
        hoverlabel=dict(bgcolor="#07111e", font_color=TEXT),
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------- API ----------
def get_api_key():
    try:
        return st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        return ""


def api_get(endpoint, api_key, params=None, retries=3):
    headers = {"x-apisports-key": api_key}
    last_error = "Unbekannter Fehler"

    for attempt in range(retries + 1):
        try:
            response = requests.get(
                f"{API_URL}/{endpoint}",
                headers=headers,
                params=params or {},
                timeout=35,
            )

            if response.status_code == 429:
                last_error = "API-Limit erreicht (HTTP 429)."
                if attempt < retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        wait = int(retry_after)
                    except (ValueError, TypeError):
                        wait = min(15 * (2 ** attempt), 60)
                    time.sleep(max(5, min(wait, 90)))
                    continue
                raise RuntimeError(
                    last_error + " Bitte später erneut versuchen."
                )

            if response.status_code >= 500 and attempt < retries:
                time.sleep(4 * (attempt + 1))
                continue

            try:
                data = response.json()
            except ValueError:
                data = {}

            if response.status_code != 200:
                raise RuntimeError(
                    f"HTTP {response.status_code}: "
                    f"{data.get('errors', response.text[:200])}"
                )

            if isinstance(data, dict) and data.get("errors"):
                raise RuntimeError(str(data["errors"]))

            return data

        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"Verbindungsfehler: {last_error}")

    raise RuntimeError(last_error)


@st.cache_data(ttl=86400, show_spinner=False)
def load_available_seasons(league_id, api_key):
    data = api_get("leagues", api_key, {"id": int(league_id)})
    current_year = datetime.now(timezone.utc).year
    years = set()

    for entry in data.get("response", []):
        for season in entry.get("seasons", []):
            year = season.get("year")
            if year is not None:
                year = int(year)
                if START_YEAR <= year <= current_year:
                    years.add(year)

    if not years:
        raise RuntimeError("Keine verfügbaren Saisons ab 2022 gefunden.")

    return sorted(years)


@st.cache_data(ttl=86400, show_spinner=False)
def load_matches(league_id, api_key):
    all_matches = []
    errors = []
    seasons = load_available_seasons(league_id, api_key)
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

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
                hg = goals.get("home")
                ag = goals.get("away")

                if not home or not away or not fixture.get("date"):
                    continue

                date = pd.to_datetime(
                    fixture["date"], utc=True, errors="coerce"
                )

                if pd.isna(date) or date.date() > yesterday:
                    continue

                if status not in ("FT", "AET", "PEN"):
                    continue

                if hg is None or ag is None:
                    continue

                all_matches.append({
                    "Datum": date,
                    "Heim": home,
                    "Auswärts": away,
                    "Tore_Heim": int(hg),
                    "Tore_Auswärts": int(ag),
                    "Saison": season,
                })

        except Exception as exc:
            errors.append(f"Saison {season}: {exc}")

        if index < len(seasons) - 1:
            time.sleep(4)

    df = pd.DataFrame(all_matches)

    if df.empty:
        return df, errors, seasons

    df = df.drop_duplicates(
        subset=["Datum", "Heim", "Auswärts"]
    )
    df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors, seasons


# ---------- ANALYSEN ----------
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

    wins = int((matches["Eigen"] > matches["Gegner"]).sum())
    draws = int((matches["Eigen"] == matches["Gegner"]).sum())
    losses = int((matches["Eigen"] < matches["Gegner"]).sum())

    return {
        "spiele": len(matches),
        "tore": float(matches["Eigen"].mean()),
        "gegentreffer": float(matches["Gegner"].mean()),
        "siege": wins,
        "remis": draws,
        "niederlagen": losses,
        "punkte": wins * 3 + draws,
        "form": matches.sort_values("Datum"),
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

    expected_home = (
        (0.65 * home["tore"] + 0.35 * home_all["tore"])
        / league_home
        * (0.65 * away["gegentreffer"] + 0.35 * away_all["gegentreffer"])
    )
    expected_away = (
        (0.65 * away["tore"] + 0.35 * away_all["tore"])
        / league_away
        * (0.65 * home["gegentreffer"] + 0.35 * home_all["gegentreffer"])
    )

    expected_home = max(0.15, min(4.0, expected_home))
    expected_away = max(0.15, min(4.0, expected_away))

    p_home = p_draw = p_away = 0.0
    scorelines = []

    for hg in range(11):
        for ag in range(11):
            p = (
                poisson_probability(hg, expected_home)
                * poisson_probability(ag, expected_away)
            )
            scorelines.append((hg, ag, p))

            if hg > ag:
                p_home += p
            elif hg == ag:
                p_draw += p
            else:
                p_away += p

    total = p_home + p_draw + p_away
    if total <= 0:
        return None

    p_home /= total
    p_draw /= total
    p_away /= total

    if p_home >= p_draw and p_home >= p_away:
        winner = f"Heimsieg: {home_team}"
    elif p_away >= p_home and p_away >= p_draw:
        winner = f"Auswärtssieg: {away_team}"
    else:
        winner = "Unentschieden"

    best_score = max(scorelines, key=lambda x: x[2])

    return {
        "home": p_home,
        "draw": p_draw,
        "away": p_away,
        "winner": winner,
        "score": f"{best_score[0]} : {best_score[1]}",
        "expected_home": expected_home,
        "expected_away": expected_away,
    }


def metric(label, value, subtitle=""):
    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def form_string(stats):
    if not stats:
        return "Keine Daten"
    output = []
    for _, row in stats["form"].iterrows():
        if row["Eigen"] > row["Gegner"]:
            output.append("S")
        elif row["Eigen"] == row["Gegner"]:
            output.append("U")
        else:
            output.append("N")
    return " – ".join(output)


# ---------- NAVIGATION ----------
st.sidebar.markdown("## ⚽ KickPredict AI")
st.sidebar.caption("Deine Fussball-Analyseplattform")

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Home",
        "🔮 Spielprognose",
        "🧠 Team-Analyse",
        "📊 Statistiken",
        "📅 Ergebnisse",
        "ℹ️ Über uns",
    ],
)

st.sidebar.divider()
st.sidebar.markdown("**Erstellt von**")
st.sidebar.write("Tiago Faruk und Yigit")
st.sidebar.caption("Prognosen sind Schätzungen, keine Garantien.")

api_key = get_api_key()

if not api_key:
    st.error("API-Schlüssel fehlt. Bitte in Streamlit → Settings → Secrets eintragen.")
    st.code('API_FOOTBALL_KEY = "DEIN_API_SCHLUESSEL"')
    st.stop()


# ---------- HOME ----------
if page == "🏠 Home":
    st.markdown("""
    <div class="hero">
        <div class="eyebrow">Football intelligence</div>
        <h1>KickPredict AI</h1>
        <p>Fussball verstehen. Zahlen analysieren. Spiele einschätzen.</p>
    </div>
    """, unsafe_allow_html=True)

    a, b, c = st.columns(3)
    with a:
        metric("Daten ab", "2022", "Soweit über die API verfügbar")
    with b:
        metric("Prognose", "1X2", "Heimsieg · Remis · Auswärtssieg")
    with c:
        metric("Wettbewerbe", str(len(LEAGUES)), "Internationale Ligen")

    st.markdown("### Entdecke die Plattform")
    a, b = st.columns(2)

    with a:
        st.markdown("""
        <div class="panel">
            <h3>🔮 Spielprognose</h3>
            Vergleiche zwei Teams und berechne Wahrscheinlichkeiten
            für die drei möglichen Spielausgänge.
        </div>
        <div class="panel">
            <h3>📊 Statistiken</h3>
            Entdecke Tore, Resultate, Siege und Unentschieden
            in den geladenen Spielen.
        </div>
        """, unsafe_allow_html=True)

    with b:
        st.markdown("""
        <div class="panel">
            <h3>🧠 Team-Analyse</h3>
            Prüfe die letzten Leistungen sowie Heim- und Auswärtsform.
        </div>
        <div class="panel">
            <h3>📅 Ergebnisse</h3>
            Durchsuche die zuletzt geladenen abgeschlossenen Spiele.
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "Die Berechnungen basieren auf historischen Resultaten. "
        "Eine bestimmte Trefferquote wird nicht garantiert."
    )

else:
    st.markdown(f"""
    <div class="hero">
        <div class="eyebrow">KickPredict AI · Analytics</div>
        <h1>{page}</h1>
        <p>Fussballstatistiken und historische Resultate auf einen Blick.</p>
    </div>
    """, unsafe_allow_html=True)

    league_name = st.selectbox(
        "Wettbewerb auswählen",
        list(LEAGUES.keys()),
        key="league_choice",
    )
    league_id = LEAGUES[league_name]

    left, right = st.columns([3, 1])
    with left:
        st.caption("Daten werden zwischengespeichert, um API-Anfragen zu reduzieren.")
    with right:
        refresh = st.button("🔄 Aktualisieren", use_container_width=True)

    if refresh:
        load_matches.clear()
        load_available_seasons.clear()
        st.rerun()

    try:
        with st.spinner("Lade verfügbare Resultate …"):
            df, errors, seasons = load_matches(league_id, api_key)
    except Exception as exc:
        st.error(f"Daten konnten nicht geladen werden: {exc}")
        st.info("Warte bei API-Limits einige Minuten und versuche es erneut.")
        st.stop()

    if errors:
        with st.expander("API-Meldungen anzeigen"):
            for error in errors:
                st.warning(error)

    if df.empty:
        st.error("Keine abgeschlossenen Spiele verfügbar.")
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))

    # ---------- SPIELPROGNOSE ----------
    if page == "🔮 Spielprognose":
        a, b, c = st.columns(3)
        with a:
            metric("Geladene Spiele", f"{len(df):,}".replace(",", "."))
        with b:
            metric("Saisons", str(len(seasons)), f"{seasons[0]}–{seasons[-1]}")
        with c:
            metric("Letztes Spiel", df["Datum"].max().strftime("%d.%m.%Y"))

        col1, col2 = st.columns(2)
        with col1:
            home_team = st.selectbox("Heimteam", teams, key="predict_home")

        away_options = [t for t in teams if t != home_team]
        with col2:
            away_team = st.selectbox("Auswärtsteam", away_options, key="predict_away")

        if st.button("🚀 Prognose berechnen", use_container_width=True):
            result = predict_match(df, home_team, away_team)
            if result is None:
                st.error("Für diese Teams gibt es nicht genügend Daten.")
            else:
                st.session_state["prediction"] = result
                st.session_state["prediction_teams"] = (home_team, away_team)

        if "prediction" in st.session_state:
            result = st.session_state["prediction"]
            home_saved, away_saved = st.session_state["prediction_teams"]

            st.divider()
            st.subheader(f"{home_saved} vs. {away_saved}")

            a, b, c = st.columns(3)
            with a:
                metric("Heimsieg", f"{result['home'] * 100:.1f}%")
            with b:
                metric("Unentschieden", f"{result['draw'] * 100:.1f}%")
            with c:
                metric("Auswärtssieg", f"{result['away'] * 100:.1f}%")

            dark_outcome_chart(
                ["Heimsieg", "Unentschieden", "Auswärtssieg"],
                [
                    result["home"] * 100,
                    result["draw"] * 100,
                    result["away"] * 100,
                ],
                "Spielprognose",
            )

            a, b = st.columns(2)
            with a:
                st.markdown("**Wahrscheinlichster Ausgang**")
                st.subheader(result["winner"])
            with b:
                st.markdown("**Geschätzter Spielstand**")
                st.subheader(result["score"])

            st.caption(
                f"Geschätzte Tore: {result['expected_home']:.2f} – "
                f"{result['expected_away']:.2f}"
            )
            st.warning("Die Prognose ist eine Schätzung, keine Garantie.")

    # ---------- TEAM-ANALYSE ----------
    elif page == "🧠 Team-Analyse":
        team = st.selectbox("Team auswählen", teams, key="analysis_team")
        overall = team_stats(df, team)
        home_stats = team_stats(df, team, "home")
        away_stats = team_stats(df, team, "away")

        if overall:
            a, b, c, d = st.columns(4)
            with a:
                metric("Spiele analysiert", str(overall["spiele"]))
            with b:
                metric("Ø Tore", f"{overall['tore']:.2f}", "pro Spiel")
            with c:
                metric("Ø Gegentore", f"{overall['gegentreffer']:.2f}", "pro Spiel")
            with d:
                metric("Punkte", str(overall["punkte"]), "Letzte 12 Spiele")

            st.markdown("### Letzte Spiele: Form")
            st.write(form_string(overall))
            st.caption("S = Sieg · U = Unentschieden · N = Niederlage")

            st.markdown("### Heim- und Auswärtsvergleich")
            comparison = pd.DataFrame({
                "Kategorie": ["Ø erzielte Tore", "Ø Gegentore", "Spiele"],
                "Heim": [
                    home_stats["tore"] if home_stats else 0,
                    home_stats["gegentreffer"] if home_stats else 0,
                    home_stats["spiele"] if home_stats else 0,
                ],
                "Auswärts": [
                    away_stats["tore"] if away_stats else 0,
                    away_stats["gegentreffer"] if away_stats else 0,
                    away_stats["spiele"] if away_stats else 0,
                ],
            })

            dark_bar_chart(
                comparison,
                title="Heim- und Auswärtsvergleich",
                horizontal=True,
            )

            with st.expander("Letzte Resultate dieses Teams"):
                team_games = df[
                    (df["Heim"] == team) | (df["Auswärts"] == team)
                ].copy()
                team_games["Datum"] = (
                    team_games["Datum"]
                    .dt.tz_convert("Europe/Zurich")
                    .dt.strftime("%d.%m.%Y")
                )
                st.dataframe(
                    team_games.sort_values("Datum", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )

    # ---------- STATISTIKEN ----------
    elif page == "📊 Statistiken":
        home_goals = int(df["Tore_Heim"].sum())
        away_goals = int(df["Tore_Auswärts"].sum())
        total_goals = home_goals + away_goals

        a, b, c, d = st.columns(4)
        with a:
            metric("Spiele", f"{len(df):,}".replace(",", "."))
        with b:
            metric("Tore insgesamt", f"{total_goals:,}".replace(",", "."))
        with c:
            metric("Tore pro Spiel", f"{total_goals / len(df):.2f}")
        with d:
            metric(
                "Heimsiegquote",
                f"{(df['Tore_Heim'] > df['Tore_Auswärts']).mean() * 100:.1f}%",
            )

        st.markdown("### Verteilung der Spielausgänge")
        home_wins = int((df["Tore_Heim"] > df["Tore_Auswärts"]).sum())
        draws = int((df["Tore_Heim"] == df["Tore_Auswärts"]).sum())
        away_wins = int((df["Tore_Heim"] < df["Tore_Auswärts"]).sum())

        dark_outcome_chart(
            ["Heimsieg", "Unentschieden", "Auswärtssieg"],
            [home_wins, draws, away_wins],
            "Verteilung der Spielausgänge",
        )

        st.markdown("### Teams mit den meisten erzielten Toren")
        home_totals = df.groupby("Heim")["Tore_Heim"].sum()
        away_totals = df.groupby("Auswärts")["Tore_Auswärts"].sum()
        total_by_team = home_totals.add(away_totals, fill_value=0)
        top_teams = total_by_team.sort_values(ascending=False).head(10)

        top_df = top_teams.rename("Tore").reset_index()
        top_df.columns = ["Team", "Tore"]

        fig = px.bar(
            top_df.sort_values("Tore"),
            x="Tore",
            y="Team",
            orientation="h",
            text="Tore",
            color_discrete_sequence=[GREEN],
        )
        fig.update_traces(
            textposition="outside",
            marker_line_width=0,
            cliponaxis=False,
        )
        fig.update_layout(
            title=dict(
                text="Top 10 Teams nach Toren",
                font=dict(color=TEXT, size=18),
                x=0.02,
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor=DARK,
            font=dict(color=TEXT),
            margin=dict(l=18, r=35, t=55, b=30),
            height=450,
            xaxis=dict(color=MUTED, gridcolor=GRID, linecolor=GRID),
            yaxis=dict(color=MUTED, gridcolor=GRID, linecolor=GRID),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Spiele nach Saison")
        season_summary = df.groupby("Saison").agg(
            Spiele=("Heim", "count"),
            Tore_Heim=("Tore_Heim", "sum"),
            Tore_Auswärts=("Tore_Auswärts", "sum"),
        )
        season_summary["Tore insgesamt"] = (
            season_summary["Tore_Heim"] + season_summary["Tore_Auswärts"]
        )
        st.dataframe(season_summary, use_container_width=True)

    # ---------- ERGEBNISSE ----------
    elif page == "📅 Ergebnisse":
        st.markdown("### Abgeschlossene Spiele durchsuchen")

        team_filter = st.selectbox(
            "Team filtern",
            ["Alle Teams"] + teams,
            key="results_team",
        )

        season_filter = st.selectbox(
            "Saison filtern",
            ["Alle Saisons"] + [
                str(y) for y in sorted(df["Saison"].unique(), reverse=True)
            ],
            key="results_season",
        )

        results = df.copy()

        if team_filter != "Alle Teams":
            results = results[
                (results["Heim"] == team_filter)
                | (results["Auswärts"] == team_filter)
            ]

        if season_filter != "Alle Saisons":
            results = results[results["Saison"] == int(season_filter)]

        results["Datum"] = (
            results["Datum"]
            .dt.tz_convert("Europe/Zurich")
            .dt.strftime("%d.%m.%Y")
        )

        results["Resultat"] = (
            results["Tore_Heim"].astype(str)
            + " : "
            + results["Tore_Auswärts"].astype(str)
        )

        display = results[
            ["Datum", "Heim", "Resultat", "Auswärts", "Saison"]
        ].sort_values("Datum", ascending=False)

        st.caption(f"{len(display)} Spiele gefunden")
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
        )

        csv = display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Ergebnisse als CSV exportieren",
            data=csv,
            file_name="kickpredict_ergebnisse.csv",
            mime="text/csv",
        )

    # ---------- ÜBER UNS ----------
    elif page == "ℹ️ Über uns":
        st.markdown("### Unsere Idee")
        st.write(
            "KickPredict AI ist ein Fussballanalyse-Projekt, das historische "
            "Ergebnisse nutzt, um statistische Schätzungen für mögliche "
            "Spielausgänge zu berechnen."
        )

        st.markdown("### Unsere Kategorien")
        st.write(
            "- Home: Übersicht und Einstieg\n"
            "- Spielprognose: 1X2-Wahrscheinlichkeiten\n"
            "- Team-Analyse: Form, Tore und Heim-/Auswärtsleistung\n"
            "- Statistiken: Ausgänge, Tore und Saisonvergleiche\n"
            "- Ergebnisse: Resultate filtern und exportieren"
        )

        st.markdown("### Erstellt von")
        st.markdown("## Tiago Faruk und Yigit")

        st.info(
            "Die Daten stammen von API-Football. Welche Saisons verfügbar "
            "sind, hängt vom API-Zugang ab. Die Prognosen garantieren "
            "keine bestimmte Trefferquote."
        )

st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Football analytics")
