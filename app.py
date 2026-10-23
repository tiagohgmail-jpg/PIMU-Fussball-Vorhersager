
import math
import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

SPORTSCORE_URL = "https://sportscore.com/api/widget/matches/"

LEAGUES = {
    "Premier League 🇬🇧": "Premier League",
    "La Liga 🇪🇸": "La Liga",
    "Bundesliga 🇩🇪": "Bundesliga",
    "Serie A 🇮🇹": "Serie A",
    "Ligue 1 🇫🇷": "Ligue 1",
    "Champions League 🏆": "Champions League",
    "Europa League 🌍": "Europa League",
    "Super League 🇨🇭": "Swiss Super League",
}

GREEN = "#4be0a0"
GREEN_LIGHT = "#85f3be"
DARK = "#122238"
DARKER = "#07111e"
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
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background: linear-gradient(135deg,#07111f 0%,#0b192a 55%,#102a36 100%) !important;
    color: #f4f7fb !important;
}
[data-testid="stHeader"],
[data-testid="stHeader"] > div,
header[data-testid="stHeader"] {
    background: transparent !important;
    background-color: #07111f !important;
    color: #f4f7fb !important;
}
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stDeployButton"] {
    background: transparent !important;
}
.stApp > header,
.stApp header,
[data-testid="stAppViewContainer"] > header {
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stMainBlockContainer"] {
    padding-top: 1rem !important;
}
[data-testid="stSidebar"] {
    background: #07111e !important;
    border-right: 1px solid #21364b;
}
[data-testid="stSidebar"] > div {
    background: #07111e !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
    color: #c2d0df;
}
.hero {
    padding: 30px;
    border-radius: 20px;
    background: linear-gradient(115deg,#142943,#12513f);
    border: 1px solid #315b68;
    margin-bottom: 22px;
}
.hero h1 {
    font-size: 42px;
    font-weight: 850;
    margin-bottom: 8px;
    color: #f4f7fb !important;
}
.hero p {
    color: #d2e2ee !important;
    font-size: 17px;
}
.eyebrow {
    color: #63edaf !important;
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
    background: linear-gradient(145deg,#152940,#101e31);
    border: 1px solid #2b435e;
    border-radius: 15px;
    padding: 18px;
    min-height: 115px;
}
.metric-label {
    color: #aebfd2 !important;
    font-size: 13px;
}
.metric-value {
    color: #5ce6a6 !important;
    font-size: 28px;
    font-weight: 850;
    margin-top: 5px;
}
.muted {
    color: #aebfd2 !important;
    font-size: 13px;
}
div.stButton > button {
    background: #4be0a0 !important;
    color: #07131c !important;
    border: 0 !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
    min-height: 43px;
}
div.stButton > button:hover {
    background: #85f3be !important;
    color: #07131c !important;
}
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div {
    background-color: #122238 !important;
    color: #f4f7fb !important;
    border-color: #36516c !important;
}
[data-baseweb="select"] *,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
    color: #f4f7fb !important;
}
[data-baseweb="popover"],
[data-baseweb="menu"] {
    background-color: #122238 !important;
}
h1, h2, h3, h4, h5, p, label {
    color: #f4f7fb;
}
.stMarkdown,
.stCaption,
[data-testid="stCaptionContainer"] {
    color: #c2d0df;
}
hr {
    border-color: #273d53 !important;
}
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border: 1px solid #293f58;
    border-radius: 12px;
}
[data-testid="stAlert"] {
    background: #14263a !important;
    border: 1px solid #293f58 !important;
    border-radius: 12px;
    color: #f4f7fb !important;
}
[data-testid="stDownloadButton"] button {
    background: #4be0a0 !important;
    color: #07131c !important;
    border: 0 !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label {
    color: #d6e2ef !important;
}
@media (max-width: 768px) {
    .hero { padding: 20px; }
    .hero h1 { font-size: 32px; }
    [data-testid="stMainBlockContainer"] {
        padding-top: 0.5rem !important;
    }
}
</style>
""", unsafe_allow_html=True)


# ---------- DIAGRAMME ----------
def dark_bar_chart(
    data,
    title=None,
    x_title=None,
    y_title=None,
    horizontal=False,
    color=GREEN,
):
    if isinstance(data, pd.Series):
        chart_df = data.rename("Wert").reset_index()
        chart_df.columns = ["Kategorie", "Wert"]
    else:
        chart_df = data.copy().reset_index(drop=True)
        if "Kategorie" not in chart_df.columns:
            chart_df = chart_df.rename(
                columns={chart_df.columns[0]: "Kategorie"}
            )

    value_columns = [
        column for column in chart_df.columns
        if column != "Kategorie"
    ]
    fig = go.Figure()
    colors = [GREEN, "#2e9b72", GREEN_LIGHT, "#26785d"]

    for i, column in enumerate(value_columns):
        fig.add_trace(go.Bar(
            x=chart_df["Kategorie"] if horizontal else chart_df[column],
            y=chart_df[column] if horizontal else chart_df["Kategorie"],
            orientation="h" if horizontal else "v",
            name=str(column),
            marker_color=(
                colors[i % len(colors)]
                if len(value_columns) > 1 else color
            ),
            marker_line_width=0,
            text=chart_df[column],
            texttemplate="%{text:.2f}",
            textposition="outside",
            cliponaxis=False,
        ))

    fig.update_layout(
        title=dict(
            text=title or "",
            font=dict(color=TEXT, size=18),
            x=0.02,
        ),
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=DARK,
        font=dict(family="Arial, sans-serif", color=TEXT, size=12),
        margin=dict(l=18, r=40, t=55 if title else 25, b=45),
        height=390,
        legend=dict(font=dict(color=TEXT), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(
            title=x_title, color=MUTED, gridcolor=GRID,
            linecolor=GRID, tickfont=dict(color=MUTED),
            zerolinecolor=GRID,
        ),
        yaxis=dict(
            title=y_title, color=MUTED, gridcolor=GRID,
            linecolor=GRID, tickfont=dict(color=MUTED),
            zerolinecolor=GRID,
        ),
        hoverlabel=dict(
            bgcolor="#07111e", font_color=TEXT, bordercolor=GREEN
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


def dark_outcome_chart(labels, values, title):
    fig = go.Figure()
    colors = [GREEN, "#6bbf9a", "#328c6a"]

    formatted_values = [
        f"{value:.1f}%" if title == "Spielprognose"
        else f"{value:,.0f}".replace(",", ".")
        for value in values
    ]

    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        marker=dict(
            color=colors[:len(labels)],
            line=dict(width=0),
        ),
        text=formatted_values,
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
            color=MUTED, gridcolor=GRID, linecolor=GRID,
            tickfont=dict(color=MUTED),
        ),
        yaxis=dict(
            color=MUTED, gridcolor=GRID, linecolor=GRID,
            rangemode="tozero",
        ),
        hoverlabel=dict(bgcolor="#07111e", font_color=TEXT),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------- SPORTSCORE API ----------
@st.cache_data(ttl=300, show_spinner=False)
def load_sportscore_matches():
    response = requests.get(
        SPORTSCORE_URL,
        params={"sport": "football", "limit": 50},
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        raise RuntimeError("Ungültige Antwort von SportScore.")

    matches = data.get("matches", [])
    if not isinstance(matches, list):
        raise RuntimeError("SportScore hat keine gültige Spieleliste geliefert.")

    rows = []

    for match in matches:
        if not isinstance(match, dict):
            continue

        home = match.get("home")
        away = match.get("away")
        status = str(match.get("status", "")).lower()
        match_time = match.get("time")

        if not home or not away or not match_time:
            continue

        if status not in ("finished", "ft", "aet", "pen"):
            continue

        hg = match.get("home_score")
        ag = match.get("away_score")

        if hg is None or ag is None:
            continue

        date = pd.to_datetime(match_time, utc=True, errors="coerce")
        if pd.isna(date):
            continue

        try:
            hg = int(hg)
            ag = int(ag)
        except (ValueError, TypeError):
            continue

        rows.append({
            "Datum": date,
            "Heim": str(home),
            "Auswärts": str(away),
            "Tore_Heim": hg,
            "Tore_Auswärts": ag,
            "Saison": int(date.year),
            "Liga": str(match.get("competition") or "Unbekannt"),
        })

    columns = [
        "Datum", "Heim", "Auswärts", "Tore_Heim",
        "Tore_Auswärts", "Saison", "Liga",
    ]
    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Datum", "Heim", "Auswärts"]
        )
        df = df.sort_values("Datum").reset_index(drop=True)

    return df


def load_matches(league_name=None):
    df = load_sportscore_matches()
    errors = []

    if df.empty:
        return df, errors, []

    # Liga-Namen der API sind nicht immer einheitlich.
    # Deshalb wird nur gefiltert, wenn die Bezeichnung passt.
    expected = LEAGUES.get(league_name, "")
    if expected:
        league_values = df["Liga"].fillna("").astype(str)
        matching = df[
            league_values.str.contains(
                expected, case=False, regex=False
            )
        ].copy()

        # Keine falschen Resultate vortäuschen, wenn die Liga
        # in der aktuellen API-Antwort nicht vorkommt.
        df = matching

    seasons = sorted(
        int(year) for year in df["Saison"].dropna().unique()
    )
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
        metric("Datenquelle", "SportScore", "Öffentliche Fussballdaten")
    with b:
        metric("Prognose", "1X2", "Heimsieg · Remis · Auswärtssieg")
    with c:
        metric("Wettbewerbe", str(len(LEAGUES)), "Verfügbare Auswahl")

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
            Durchsuche die geladenen abgeschlossenen Spiele.
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "Die Berechnungen basieren auf den Resultaten, die SportScore "
        "zur Verfügung stellt. Eine bestimmte Trefferquote wird nicht garantiert."
    )

else:
    st.markdown(f"""
    <div class="hero">
        <div class="eyebrow">KickPredict AI · Analytics</div>
        <h1>{page}</h1>
        <p>Fussballstatistiken und Resultate auf einen Blick.</p>
    </div>
    """, unsafe_allow_html=True)

    league_name = st.selectbox(
        "Wettbewerb auswählen",
        list(LEAGUES.keys()),
        key="league_choice",
    )

    left, right = st.columns([3, 1])
    with left:
        st.caption(
            "Daten werden fünf Minuten zwischengespeichert, "
            "um API-Anfragen zu reduzieren."
        )
    with right:
        refresh = st.button("🔄 Aktualisieren", use_container_width=True)

    if refresh:
        load_sportscore_matches.clear()
        st.rerun()

    try:
        with st.spinner("Lade Resultate von SportScore …"):
            df, errors, seasons = load_matches(league_name)
    except Exception as exc:
        st.error(f"Daten konnten nicht geladen werden: {exc}")
        st.info(
            "Prüfe deine Internetverbindung oder versuche es später erneut."
        )
        st.stop()

    if df.empty:
        st.warning(
            f"SportScore hat in der aktuellen Antwort keine abgeschlossenen "
            f"Spiele für **{league_name}** geliefert. Wähle einen anderen "
            "Wettbewerb oder versuche es später erneut."
        )
        st.markdown(
            '<a href="https://sportscore.com/" rel="dofollow">'
            'Powered by SportScore</a>',
            unsafe_allow_html=True,
        )
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))

    # ---------- SPIELPROGNOSE ----------
    if page == "🔮 Spielprognose":
        a, b, c = st.columns(3)
        with a:
            metric("Geladene Spiele", f"{len(df):,}".replace(",", "."))
        with b:
            metric("Saisons/Jahre", str(len(seasons)))
        with c:
            metric("Letztes Spiel", df["Datum"].max().strftime("%d.%m.%Y"))

        col1, col2 = st.columns(2)
        with col1:
            home_team = st.selectbox("Heimteam", teams, key="predict_home")

        away_options = [team for team in teams if team != home_team]
        with col2:
            away_team = st.selectbox(
                "Auswärtsteam", away_options, key="predict_away"
            )

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
                metric(
                    "Ø Gegentore",
                    f"{overall['gegentreffer']:.2f}",
                    "pro Spiel",
                )
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

        st.markdown("### Spiele nach Jahr")
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
            "Jahr filtern",
            ["Alle Jahre"] + [
                str(year)
                for year in sorted(df["Saison"].unique(), reverse=True)
            ],
            key="results_season",
        )

        results = df.copy()

        if team_filter != "Alle Teams":
            results = results[
                (results["Heim"] == team_filter)
                | (results["Auswärts"] == team_filter)
            ]

        if season_filter != "Alle Jahre":
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
        st.dataframe(display, use_container_width=True, hide_index=True)

        csv_data = display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Ergebnisse als CSV exportieren",
            data=csv_data,
            file_name="kickpredict_ergebnisse.csv",
            mime="text/csv",
        )

    # ---------- ÜBER UNS ----------
    elif page == "ℹ️ Über uns":
        st.markdown("### Unsere Idee")
        st.write(
            "KickPredict AI ist ein Fussballanalyse-Projekt, das verfügbare "
            "Resultate nutzt, um statistische Schätzungen für mögliche "
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
            "Die Datenquelle ist SportScore. Die verfügbaren Spiele hängen "
            "von der aktuellen API-Antwort ab. Die Prognosen garantieren "
            "keine bestimmte Trefferquote."
        )

# ---------- SPORTSCORE HINWEIS ----------
st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Football analytics")
st.markdown(
    '<a href="https://sportscore.com/" rel="dofollow">'
    'Powered by SportScore</a>',
    unsafe_allow_html=True,
)
