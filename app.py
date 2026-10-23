import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Öffentliche Fussballdaten von GitHub – kein API-Key notwendig
GITHUB_RAW = "https://raw.githubusercontent.com/openfootball/football.json/master"
DAYS_BACK = 30
SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

LEAGUES = {
    "Premier League 🇬🇧": "en.1.json",
    "La Liga 🇪🇸": "es.1.json",
    "Bundesliga 🇩🇪": "de.1.json",
    "Serie A 🇮🇹": "it.1.json",
    "Ligue 1 🇫🇷": "fr.1.json",
    "Champions League 🏆": None,
    "Europa League 🌍": None,
    "Super League 🇨🇭": None,
}

GREEN = "#4be0a0"
DARK = "#122238"
TEXT = "#f4f7fb"
MUTED = "#aebfd2"
GRID = "#293f58"

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] {
    background:linear-gradient(135deg,#07111f,#0b192a 55%,#102a36)!important;
    color:#f4f7fb!important;
}
[data-testid="stHeader"] {background:transparent!important;}
[data-testid="stSidebar"],[data-testid="stSidebar"]>div {background:#07111e!important;}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {color:#c2d0df;}
[data-testid="stMainBlockContainer"] {padding-top:1rem!important;}
.hero {padding:30px;border-radius:20px;background:linear-gradient(115deg,#142943,#12513f);border:1px solid #315b68;margin-bottom:22px;}
.hero h1 {font-size:42px;font-weight:850;color:#f4f7fb!important;}
.hero p {color:#d2e2ee!important;font-size:17px;}
.eyebrow {color:#63edaf!important;text-transform:uppercase;font-weight:800;letter-spacing:2px;font-size:12px;}
.panel {background:#122238;border:1px solid #293f58;border-radius:15px;padding:18px;margin-bottom:12px;}
.metric {background:linear-gradient(145deg,#152940,#101e31);border:1px solid #2b435e;border-radius:15px;padding:18px;min-height:115px;}
.metric-label {color:#aebfd2!important;font-size:13px;}
.metric-value {color:#5ce6a6!important;font-size:28px;font-weight:850;margin-top:5px;}
.muted {color:#aebfd2!important;font-size:13px;}
div.stButton>button,[data-testid="stDownloadButton"] button {background:#4be0a0!important;color:#07131c!important;border:0!important;border-radius:10px!important;font-weight:800!important;min-height:43px;}
[data-baseweb="select"]>div,[data-baseweb="input"]>div {background:#122238!important;color:#f4f7fb!important;border-color:#36516c!important;}
[data-baseweb="select"] *,[data-baseweb="input"] input {color:#f4f7fb!important;}
h1,h2,h3,h4,p,label {color:#f4f7fb;}
hr {border-color:#273d53!important;}
@media(max-width:768px) {.hero {padding:20px;}.hero h1 {font-size:32px;}}
</style>
""", unsafe_allow_html=True)


def metric(label, value, subtitle=""):
    st.markdown(f"""
    <div class="metric">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="muted">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def show_attribution():
    st.markdown(
        '<a href="https://github.com/openfootball/football.json" '
        'target="_blank" rel="noopener noreferrer">'
        'Fussballdaten: OpenFootball auf GitHub</a>',
        unsafe_allow_html=True,
    )


def outcome_chart(labels, values, title):
    colors = [GREEN, "#6bbf9a", "#328c6a"]
    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors[:len(labels)],
        text=[
            f"{v:.1f}%" if title == "Spielprognose" else str(int(v))
            for v in values
        ],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=DARK,
        font=dict(color=TEXT),
        margin=dict(l=20, r=25, t=55, b=45),
        height=350,
        showlegend=False,
        xaxis=dict(color=MUTED, gridcolor=GRID),
        yaxis=dict(color=MUTED, gridcolor=GRID, rangemode="tozero"),
    )
    st.plotly_chart(fig, use_container_width=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_matches(filename):
    """Lädt abgeschlossene Spiele aus öffentlichen OpenFootball-JSON-Dateien."""
    columns = [
        "Datum", "Heim", "Auswärts",
        "Tore_Heim", "Tore_Auswärts", "Saison", "Liga"
    ]

    if not filename:
        return pd.DataFrame(columns=columns), [
            "Für diesen Wettbewerb ist keine passende GitHub-Datei konfiguriert."
        ]

    rows = []
    errors = []
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=DAYS_BACK)

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "KickPredictAI/1.0 (public football data)"
        })

        for season in SEASONS:
            url = f"{GITHUB_RAW}/{season}/{filename}"

            try:
                response = session.get(url, timeout=15)

                if response.status_code == 404:
                    continue

                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, dict):
                    continue

                for match in payload.get("matches", []):
                    if not isinstance(match, dict):
                        continue

                    parsed_date = pd.to_datetime(
                        match.get("date"), utc=True, errors="coerce"
                    )

                    if pd.isna(parsed_date):
                        continue

                    if not (cutoff <= parsed_date.date() <= today):
                        continue

                    score = match.get("score") or {}
                    full_time = score.get("ft") if isinstance(score, dict) else None

                    if not isinstance(full_time, (list, tuple)) or len(full_time) != 2:
                        continue

                    if full_time[0] is None or full_time[1] is None:
                        continue

                    try:
                        home_score = int(full_time[0])
                        away_score = int(full_time[1])
                    except (TypeError, ValueError):
                        continue

                    home = match.get("team1")
                    away = match.get("team2")

                    if not home or not away:
                        continue

                    rows.append({
                        "Datum": parsed_date,
                        "Heim": str(home),
                        "Auswärts": str(away),
                        "Tore_Heim": home_score,
                        "Tore_Auswärts": away_score,
                        "Saison": int(season[:4]),
                        "Liga": filename,
                    })

            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{season}: {exc}")

    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Datum", "Heim", "Auswärts"]
        )
        df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors


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
        "form": matches,
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
        (0.65 * home["tore"] + 0.35 * home_all["tore"]) / league_home
    ) * (
        0.65 * away["gegentreffer"] + 0.35 * away_all["gegentreffer"]
    )

    expected_away = (
        (0.65 * away["tore"] + 0.35 * away_all["tore"]) / league_away
    ) * (
        0.65 * home["gegentreffer"] + 0.35 * home_all["gegentreffer"]
    )

    expected_home = max(0.15, min(4.0, expected_home))
    expected_away = max(0.15, min(4.0, expected_away))

    p_home = p_draw = p_away = 0.0
    scores = []

    for hg in range(11):
        for ag in range(11):
            prob = (
                poisson_probability(hg, expected_home)
                * poisson_probability(ag, expected_away)
            )
            scores.append((hg, ag, prob))

            if hg > ag:
                p_home += prob
            elif hg == ag:
                p_draw += prob
            else:
                p_away += prob

    total = p_home + p_draw + p_away

    if total <= 0:
        return None

    probabilities = [
        p_home / total,
        p_draw / total,
        p_away / total,
    ]

    labels = ["Heimsieg", "Unentschieden", "Auswärtssieg"]
    best = max(scores, key=lambda item: item[2])

    return {
        "home": probabilities[0],
        "draw": probabilities[1],
        "away": probabilities[2],
        "winner": labels[probabilities.index(max(probabilities))],
        "score": f"{best[0]} : {best[1]}",
        "expected_home": expected_home,
        "expected_away": expected_away,
    }


# ---------------- NAVIGATION ----------------
st.sidebar.markdown("## ⚽ KickPredict AI")
st.sidebar.caption("Deine Fussball-Analyseplattform")

page = st.sidebar.radio("Navigation", [
    "🏠 Home",
    "🔮 Spielprognose",
    "🧠 Team-Analyse",
    "📊 Statistiken",
    "📅 Ergebnisse",
    "ℹ️ Über uns",
])

st.sidebar.divider()
st.sidebar.markdown("**Erstellt von**")
st.sidebar.write("Tiago Faruk und Yigit")
st.sidebar.caption("Prognosen sind Schätzungen, keine Garantien.")


# ---------------- HOME ----------------
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
        metric("Datenquelle", "GitHub", "OpenFootball · öffentliche Daten")
    with b:
        metric("Prognose", "1X2", "Heim · Remis · Auswärts")
    with c:
        metric("Verfügbare Ligen", "5", "Europäische Topligen")

    st.markdown("### Entdecke die Plattform")

    a, b = st.columns(2)

    with a:
        st.markdown("""
        <div class="panel">
            <h3>🔮 Spielprognose</h3>
            Wahrscheinlichkeiten für mögliche Spielausgänge.
        </div>
        <div class="panel">
            <h3>📊 Statistiken</h3>
            Tore, Siege und Resultate auswerten.
        </div>
        """, unsafe_allow_html=True)

    with b:
        st.markdown("""
        <div class="panel">
            <h3>🧠 Team-Analyse</h3>
            Form sowie Heim- und Auswärtsleistung.
        </div>
        <div class="panel">
            <h3>📅 Ergebnisse</h3>
            Abgeschlossene Spiele filtern und exportieren.
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "Die Resultate stammen aus öffentlichen GitHub-Dateien. "
        "Eine bestimmte Prognose-Trefferquote wird nicht garantiert."
    )
    show_attribution()

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
        list(LEAGUES.keys())
    )

    left, right = st.columns([3, 1])

    with left:
        st.caption(
            f"Resultate der letzten {DAYS_BACK} Tage. "
            "Zwischenspeicherung: fünf Minuten."
        )

    with right:
        if st.button("🔄 Aktualisieren", use_container_width=True):
            load_matches.clear()
            st.rerun()

    if LEAGUES[league_name] is None:
        st.warning(
            f"{league_name} ist in dieser Version noch nicht "
            "mit einer passenden GitHub-Datendatei verbunden."
        )
        st.info(
            "Aktuell verfügbar: Premier League, La Liga, Bundesliga, "
            "Serie A und Ligue 1."
        )
        show_attribution()
        st.stop()

    try:
        with st.spinner("Lade Resultate von GitHub …"):
            df, errors = load_matches(LEAGUES[league_name])
    except Exception as exc:
        st.error(f"Die Daten konnten nicht geladen werden: {exc}")
        show_attribution()
        st.stop()

    if df.empty:
        st.warning(
            f"Für **{league_name}** wurden in den letzten "
            f"{DAYS_BACK} Tagen keine abgeschlossenen Spiele gefunden."
        )
        st.caption(
            "Die öffentliche Datei kann fehlen, keine aktuellen Resultate "
            "enthalten oder vorübergehend nicht erreichbar sein."
        )

        if errors:
            with st.expander("Technische Details"):
                st.write(errors[:5])

        show_attribution()
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))

    # ---------------- SPIELPROGNOSE ----------------
    if page == "🔮 Spielprognose":
        a, b, c = st.columns(3)

        with a:
            metric("Geladene Spiele", str(len(df)))
        with b:
            metric("Saisons", str(df["Saison"].nunique()))
        with c:
            metric(
                "Letztes Spiel",
                df["Datum"].max().strftime("%d.%m.%Y")
            )

        a, b = st.columns(2)

        with a:
            home_team = st.selectbox("Heimteam", teams)

        with b:
            away_options = [t for t in teams if t != home_team]
            away_team = st.selectbox("Auswärtsteam", away_options)

        if st.button("🚀 Prognose berechnen", use_container_width=True):
            result = predict_match(df, home_team, away_team)

            if result is None:
                st.error(
                    "Für diese Teams gibt es nicht genügend "
                    "Heim-/Auswärtsdaten in den geladenen Resultaten."
                )
            else:
                st.session_state["prediction"] = result
                st.session_state["prediction_teams"] = (
                    home_team, away_team
                )

        if "prediction" in st.session_state:
            result = st.session_state["prediction"]
            h, a = st.session_state["prediction_teams"]

            st.divider()
            st.subheader(f"{h} vs. {a}")

            x, y, z = st.columns(3)

            with x:
                metric("Heimsieg", f"{result['home'] * 100:.1f}%")
            with y:
                metric("Unentschieden", f"{result['draw'] * 100:.1f}%")
            with z:
                metric("Auswärtssieg", f"{result['away'] * 100:.1f}%")

            outcome_chart(
                ["Heimsieg", "Unentschieden", "Auswärtssieg"],
                [
                    result["home"] * 100,
                    result["draw"] * 100,
                    result["away"] * 100,
                ],
                "Spielprognose",
            )

            x, y = st.columns(2)

            with x:
                st.markdown("**Wahrscheinlichster Ausgang**")
                st.subheader(result["winner"])

            with y:
                st.markdown("**Geschätzter Spielstand**")
                st.subheader(result["score"])

            st.caption(
                f"Erwartete Tore: {result['expected_home']:.2f} – "
                f"{result['expected_away']:.2f}"
            )

            st.warning(
                "Statistische Schätzung, keine Garantie. "
                "Für diese Version werden Resultate der letzten "
                "30 Tage verwendet."
            )

    # ---------------- TEAM-ANALYSE ----------------
    elif page == "🧠 Team-Analyse":
        team = st.selectbox("Team auswählen", teams)

        overall = team_stats(df, team)
        home_stats = team_stats(df, team, "home")
        away_stats = team_stats(df, team, "away")

        if overall:
            a, b, c, d = st.columns(4)

            with a:
                metric("Spiele", str(overall["spiele"]))
            with b:
                metric("Ø Tore", f"{overall['tore']:.2f}")
            with c:
                metric("Ø Gegentore", f"{overall['gegentreffer']:.2f}")
            with d:
                metric(
                    "Punkte",
                    str(overall["punkte"]),
                    "Letzte 12 geladene Spiele",
                )

            st.markdown("### Letzte Spiele: Form")

            form = [
                "S" if r["Eigen"] > r["Gegner"]
                else "U" if r["Eigen"] == r["Gegner"]
                else "N"
                for _, r in overall["form"].iterrows()
            ]

            st.write(" – ".join(form))
            st.caption("S = Sieg · U = Unentschieden · N = Niederlage")

            comparison = pd.DataFrame({
                "Kategorie": ["Ø Tore", "Ø Gegentore", "Spiele"],
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

            st.markdown("### Heim- und Auswärtsvergleich")
            st.bar_chart(comparison.set_index("Kategorie"))

            with st.expander("Resultate dieses Teams"):
                games = df[
                    (df["Heim"] == team) | (df["Auswärts"] == team)
                ].copy()

                games["Datum"] = (
                    games["Datum"]
                    .dt.tz_convert("Europe/Zurich")
                    .dt.strftime("%d.%m.%Y")
                )

                st.dataframe(
                    games.sort_values("Datum", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )

    # ---------------- STATISTIKEN ----------------
    elif page == "📊 Statistiken":
        home_goals = int(df["Tore_Heim"].sum())
        away_goals = int(df["Tore_Auswärts"].sum())
        total_goals = home_goals + away_goals

        a, b, c, d = st.columns(4)

        with a:
            metric("Spiele", str(len(df)))
        with b:
            metric("Tore insgesamt", str(total_goals))
        with c:
            metric("Tore pro Spiel", f"{total_goals / len(df):.2f}")
        with d:
            metric(
                "Heimsiegquote",
                f"{(df['Tore_Heim'] > df['Tore_Auswärts']).mean() * 100:.1f}%"
            )

        hw = int((df["Tore_Heim"] > df["Tore_Auswärts"]).sum())
        dr = int((df["Tore_Heim"] == df["Tore_Auswärts"]).sum())
        aw = int((df["Tore_Heim"] < df["Tore_Auswärts"]).sum())

        outcome_chart(
            ["Heimsieg", "Unentschieden", "Auswärtssieg"],
            [hw, dr, aw],
            "Verteilung der Spielausgänge",
        )

        st.markdown("### Teams mit den meisten Toren")

        home_totals = df.groupby("Heim")["Tore_Heim"].sum()
        away_totals = df.groupby("Auswärts")["Tore_Auswärts"].sum()
        totals = home_totals.add(away_totals, fill_value=0)

        chart_df = (
            totals.sort_values(ascending=False)
            .head(10)
            .rename("Tore")
            .reset_index()
        )
        chart_df.columns = ["Team", "Tore"]

        fig = px.bar(
            chart_df.sort_values("Tore"),
            x="Tore",
            y="Team",
            orientation="h",
            color_discrete_sequence=[GREEN],
            text="Tore",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor=DARK,
            font=dict(color=TEXT),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Spiele nach Saison")

        summary = df.groupby("Saison").agg(
            Spiele=("Heim", "count"),
            Heimtore=("Tore_Heim", "sum"),
            Auswärtstore=("Tore_Auswärts", "sum"),
        )
        summary["Tore insgesamt"] = (
            summary["Heimtore"] + summary["Auswärtstore"]
        )

        st.dataframe(summary, use_container_width=True)

    # ---------------- ERGEBNISSE ----------------
    elif page == "📅 Ergebnisse":
        st.markdown("### Abgeschlossene Spiele durchsuchen")

        team_filter = st.selectbox(
            "Team filtern",
            ["Alle Teams"] + teams
        )

        years = sorted(df["Saison"].unique(), reverse=True)
        season_filter = st.selectbox(
            "Saison filtern",
            ["Alle Saisons"] + [str(y) for y in years]
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

        st.download_button(
            "⬇️ Ergebnisse als CSV exportieren",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name="kickpredict_ergebnisse.csv",
            mime="text/csv",
        )

    # ---------------- ÜBER UNS ----------------
    elif page == "ℹ️ Über uns":
        st.markdown("### Unsere Idee")

        st.write(
            "KickPredict AI ist ein Fussballanalyse-Projekt. "
            "Verfügbare Resultate werden ausgewertet, um statistische "
            "Schätzungen für mögliche Spielausgänge zu berechnen."
        )

        st.markdown("### Unsere Kategorien")
        st.write(
            "- Home: Übersicht und Einstieg\n"
            "- Spielprognose: Wahrscheinlichkeiten für 1X2\n"
            "- Team-Analyse: Form und Teamleistung\n"
            "- Statistiken: Tore und Spielausgänge\n"
            "- Ergebnisse: Resultate filtern und exportieren"
        )

        st.markdown("### Erstellt von")
        st.markdown("## Tiago Faruk und Yigit")

        st.info(
            "Die Prognosen sind statistische Schätzungen. "
            "Sie garantieren keine bestimmte Trefferquote."
        )

    show_attribution()

st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Football analytics")
