import math
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# KICKPREDICT AI – öffentliche Fussballdaten, kein API-Schlüssel
# ============================================================

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"

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

SEASONS = [
    "2026-27",
    "2025-26",
    "2024-25",
    "2023-24",
    "2022-23",
    "2021-22",
    "2020-21",
]

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide",
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg,#07111f,#0b192a 55%,#102a36);
    color:#f4f7fb;
}
[data-testid="stSidebar"] {
    background:#07111e;
}
[data-testid="stHeader"] {
    background:transparent;
}
.hero {
    padding:30px;
    border-radius:20px;
    background:linear-gradient(115deg,#142943,#12513f);
    border:1px solid #315b68;
    margin-bottom:22px;
}
.hero h1 {
    font-size:42px;
    font-weight:850;
    color:#f4f7fb;
}
.hero p {
    color:#d2e2ee;
    font-size:17px;
}
.eyebrow {
    color:#63edaf;
    text-transform:uppercase;
    font-weight:800;
    letter-spacing:2px;
    font-size:12px;
}
.metric {
    background:linear-gradient(145deg,#152940,#101e31);
    border:1px solid #2b435e;
    border-radius:15px;
    padding:18px;
    min-height:105px;
}
.metric-label {
    color:#aebfd2;
    font-size:13px;
}
.metric-value {
    color:#5ce6a6;
    font-size:27px;
    font-weight:850;
    margin-top:5px;
}
.panel {
    background:#122238;
    border:1px solid #293f58;
    border-radius:15px;
    padding:18px;
    margin-bottom:12px;
}
.muted {
    color:#aebfd2;
    font-size:13px;
}
div.stButton>button,
[data-testid="stDownloadButton"] button {
    background:#4be0a0;
    color:#07131c;
    border:0;
    border-radius:10px;
    font-weight:800;
    min-height:43px;
}
[data-baseweb="select"]>div,
[data-baseweb="input"]>div {
    background:#122238;
    color:#f4f7fb;
    border-color:#36516c;
}
h1,h2,h3,h4,p,label {
    color:#f4f7fb;
}
hr {
    border-color:#273d53;
}
</style>
""", unsafe_allow_html=True)


# -------------------- DESIGN --------------------

def hero(title, subtitle):
    st.markdown(f"""
    <div class="hero">
        <div class="eyebrow">KickPredict AI · Analytics</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def metric(label, value, subtitle=""):
    st.markdown(f"""
    <div class="metric">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="muted">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def attribution():
    st.markdown(
        "[Fussballdaten: OpenFootball auf GitHub]"
        "(https://github.com/openfootball/football.json)"
    )


# -------------------- DATEN LADEN --------------------

@st.cache_data(ttl=600, show_spinner=False)
def load_matches(filename):
    columns = [
        "Datum", "Heim", "Auswärts",
        "Tore_Heim", "Tore_Auswärts",
        "Saison", "Liga"
    ]

    if not filename:
        return pd.DataFrame(columns=columns), []

    rows = []
    errors = []
    session = requests.Session()
    session.headers.update({"User-Agent": "KickPredictAI/1.0"})

    for season in SEASONS:
        url = f"{BASE_URL}/{season}/{filename}"

        try:
            response = session.get(url, timeout=20)

            if response.status_code == 404:
                continue

            response.raise_for_status()
            payload = response.json()

            for match in payload.get("matches", []):
                date = pd.to_datetime(
                    match.get("date"),
                    errors="coerce",
                    utc=True
                )

                if pd.isna(date):
                    continue

                score = match.get("score") or {}
                ft = score.get("ft") if isinstance(score, dict) else None

                # Nur Spiele mit Endresultat verwenden.
                if not isinstance(ft, (list, tuple)) or len(ft) != 2:
                    continue

                if ft[0] is None or ft[1] is None:
                    continue

                home = match.get("team1")
                away = match.get("team2")

                if not home or not away:
                    continue

                try:
                    home_goals = int(ft[0])
                    away_goals = int(ft[1])
                except (ValueError, TypeError):
                    continue

                rows.append({
                    "Datum": date,
                    "Heim": str(home),
                    "Auswärts": str(away),
                    "Tore_Heim": home_goals,
                    "Tore_Auswärts": away_goals,
                    "Saison": season,
                    "Liga": filename,
                })

        except (requests.RequestException, ValueError, TypeError) as exc:
            errors.append(f"{season}: {exc}")

    session.close()

    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Datum", "Heim", "Auswärts"]
        )
        df = df.sort_values("Datum").reset_index(drop=True)

    return df, errors


# -------------------- TEAMSTATISTIKEN --------------------

def team_stats(df, team, venue=None, last_n=20):
    home = df[df["Heim"] == team].copy()
    away = df[df["Auswärts"] == team].copy()

    home["Eigen"] = home["Tore_Heim"]
    home["Gegner"] = home["Tore_Auswärts"]

    away["Eigen"] = away["Tore_Auswärts"]
    away["Gegner"] = away["Tore_Heim"]

    if venue == "home":
        games = home
    elif venue == "away":
        games = away
    else:
        games = pd.concat([home, away], ignore_index=True)

    games = games.sort_values("Datum").tail(last_n)

    if games.empty:
        return None

    wins = int((games["Eigen"] > games["Gegner"]).sum())
    draws = int((games["Eigen"] == games["Gegner"]).sum())
    losses = int((games["Eigen"] < games["Gegner"]).sum())

    return {
        "spiele": len(games),
        "tore": float(games["Eigen"].mean()),
        "gegentreffer": float(games["Gegner"].mean()),
        "siege": wins,
        "remis": draws,
        "niederlagen": losses,
        "punkte": wins * 3 + draws,
        "form": games,
    }


# -------------------- PROGNOSEMODELL --------------------

def poisson(goals, expected):
    expected = max(0.05, expected)
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
    ) * (
        0.65 * away["gegentreffer"]
        + 0.35 * away_all["gegentreffer"]
    )

    expected_away = (
        (0.65 * away["tore"] + 0.35 * away_all["tore"])
        / league_away
    ) * (
        0.65 * home["gegentreffer"]
        + 0.35 * home_all["gegentreffer"]
    )

    expected_home = max(0.15, min(4.5, expected_home))
    expected_away = max(0.15, min(4.5, expected_away))

    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    scores = []

    for hg in range(11):
        for ag in range(11):
            prob = poisson(hg, expected_home) * poisson(ag, expected_away)
            scores.append((hg, ag, prob))

            if hg > ag:
                p_home += prob
            elif hg == ag:
                p_draw += prob
            else:
                p_away += prob

    total = p_home + p_draw + p_away

    if total == 0:
        return None

    probabilities = [
        p_home / total,
        p_draw / total,
        p_away / total
    ]

    labels = ["Heimsieg", "Unentschieden", "Auswärtssieg"]
    best_score = max(scores, key=lambda item: item[2])

    return {
        "home": probabilities[0],
        "draw": probabilities[1],
        "away": probabilities[2],
        "winner": labels[probabilities.index(max(probabilities))],
        "score": f"{best_score[0]} : {best_score[1]}",
        "expected_home": expected_home,
        "expected_away": expected_away,
    }


def outcome_chart(labels, values, title):
    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=["#4be0a0", "#6bbf9a", "#328c6a"],
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
    ))

    fig.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#122238",
        font=dict(color="#f4f7fb"),
        height=350,
        margin=dict(l=20, r=20, t=55, b=40),
        yaxis=dict(gridcolor="#293f58", rangemode="tozero"),
        xaxis=dict(gridcolor="#293f58"),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------- NAVIGATION --------------------

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
st.sidebar.caption("Statistische Prognosen, keine Garantien.")


# -------------------- HOME --------------------

if page == "🏠 Home":
    hero(
        "KickPredict AI",
        "Fussball verstehen. Zahlen analysieren. Spiele einschätzen."
    )

    a, b, c = st.columns(3)

    with a:
        metric("Datenquelle", "GitHub", "Kostenlos und ohne API-Key")
    with b:
        metric("Prognose", "1X2", "Heimsieg · Remis · Auswärtssieg")
    with c:
        metric("Ligen", "5", "Europäische Topligen")

    st.markdown("### Entdecke die Plattform")

    a, b = st.columns(2)

    with a:
        st.markdown("""
        <div class="panel">
        <h3>🔮 Spielprognose</h3>
        Berechne Wahrscheinlichkeiten und mögliche Resultate.
        </div>
        <div class="panel">
        <h3>📊 Statistiken</h3>
        Entdecke Tore, Resultate und Teamvergleiche.
        </div>
        """, unsafe_allow_html=True)

    with b:
        st.markdown("""
        <div class="panel">
        <h3>🧠 Team-Analyse</h3>
        Analysiere Form sowie Heim- und Auswärtsleistung.
        </div>
        <div class="panel">
        <h3>📅 Ergebnisse</h3>
        Durchsuche Resultate und exportiere sie als CSV.
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "Die Website verwendet öffentlich verfügbare Daten. "
        "Eine bestimmte Trefferquote kann nicht garantiert werden."
    )

    attribution()


# -------------------- ALLE ANDEREN SEITEN --------------------

else:
    hero(page, "Fussballstatistiken und Resultate auf einen Blick.")

    league_name = st.selectbox(
        "Wettbewerb auswählen",
        list(LEAGUES.keys())
    )

    if st.button("🔄 Daten neu laden"):
        load_matches.clear()
        st.rerun()

    filename = LEAGUES[league_name]

    if filename is None:
        st.warning(
            "Dieser Wettbewerb ist noch nicht mit einer passenden "
            "Datendatei verbunden. Wähle eine der fünf verfügbaren Ligen."
        )
        st.stop()

    with st.spinner("Lade Fussballdaten von GitHub ..."):
        df, errors = load_matches(filename)

    if df.empty:
        st.error(
            "Es konnten keine abgeschlossenen Spiele geladen werden. "
            "Prüfe die Internetverbindung oder versuche es später erneut."
        )

        if errors:
            with st.expander("Technische Details"):
                st.code("\n".join(errors[:10]))

        attribution()
        st.stop()

    teams = sorted(set(df["Heim"]) | set(df["Auswärts"]))

    st.caption(
        f"{len(df)} abgeschlossene Spiele aus {df['Saison'].nunique()} "
        "Saisons geladen. Die Daten werden alle 10 Minuten aktualisiert."
    )

    # ---------------- SPIELPROGNOSE ----------------

    if page == "🔮 Spielprognose":
        a, b, c = st.columns(3)

        with a:
            metric("Geladene Spiele", str(len(df)))
        with b:
            metric("Teams", str(len(teams)))
        with c:
            metric("Saisons", str(df["Saison"].nunique()))

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
                    "Für diese Teams fehlen genügend Heim- oder "
                    "Auswärtsresultate."
                )
            else:
                st.session_state["prediction"] = result
                st.session_state["prediction_teams"] = (
                    home_team, away_team
                )

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

            outcome_chart(
                ["Heimsieg", "Unentschieden", "Auswärtssieg"],
                [
                    result["home"] * 100,
                    result["draw"] * 100,
                    result["away"] * 100,
                ],
                "Wahrscheinlichkeit der Spielausgänge",
            )

            a, b = st.columns(2)

            with a:
                st.markdown("**Wahrscheinlichster Ausgang**")
                st.subheader(result["winner"])

            with b:
                st.markdown("**Geschätzter Spielstand**")
                st.subheader(result["score"])

            st.caption(
                f"Erwartete Tore: {result['expected_home']:.2f} – "
                f"{result['expected_away']:.2f}"
            )

            st.warning(
                "Die Prognose basiert auf vergangenen Resultaten. "
                "Verletzungen, Aufstellungen und andere aktuelle Faktoren "
                "werden nicht automatisch berücksichtigt."
            )

    # ---------------- TEAM-ANALYSE ----------------

    elif page == "🧠 Team-Analyse":
        team = st.selectbox("Team auswählen", teams)
        stats = team_stats(df, team)

        if stats:
            a, b, c, d = st.columns(4)

            with a:
                metric("Spiele", str(stats["spiele"]))
            with b:
                metric("Ø Tore", f"{stats['tore']:.2f}")
            with c:
                metric("Ø Gegentore", f"{stats['gegentreffer']:.2f}")
            with d:
                metric("Punkte", str(stats["punkte"]))

            st.markdown("### Letzte Spiele")

            form = [
                "S" if row["Eigen"] > row["Gegner"]
                else "U" if row["Eigen"] == row["Gegner"]
                else "N"
                for _, row in stats["form"].iterrows()
            ]

            st.write(" – ".join(form))
            st.caption("S = Sieg · U = Unentschieden · N = Niederlage")

            home_stats = team_stats(df, team, "home")
            away_stats = team_stats(df, team, "away")

            comparison = pd.DataFrame({
                "Kategorie": ["Ø Tore", "Ø Gegentore"],
                "Heim": [
                    home_stats["tore"] if home_stats else 0,
                    home_stats["gegentreffer"] if home_stats else 0,
                ],
                "Auswärts": [
                    away_stats["tore"] if away_stats else 0,
                    away_stats["gegentreffer"] if away_stats else 0,
                ],
            })

            st.markdown("### Heim- und Auswärtsvergleich")
            st.bar_chart(comparison.set_index("Kategorie"))

    # ---------------- STATISTIKEN ----------------

    elif page == "📊 Statistiken":
        total_goals = int(
            df["Tore_Heim"].sum() + df["Tore_Auswärts"].sum()
        )

        home_wins = int(
            (df["Tore_Heim"] > df["Tore_Auswärts"]).sum()
        )
        draws = int(
            (df["Tore_Heim"] == df["Tore_Auswärts"]).sum()
        )
        away_wins = int(
            (df["Tore_Heim"] < df["Tore_Auswärts"]).sum()
        )

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
                f"{home_wins / len(df) * 100:.1f}%"
            )

        outcome_chart(
            ["Heimsieg", "Unentschieden", "Auswärtssieg"],
            [home_wins, draws, away_wins],
            "Spielausgänge",
        )

        home_totals = df.groupby("Heim")["Tore_Heim"].sum()
        away_totals = df.groupby("Auswärts")["Tore_Auswärts"].sum()
        totals = home_totals.add(away_totals, fill_value=0)

        top = totals.sort_values(ascending=False).head(10)
        chart_df = top.rename("Tore").reset_index()
        chart_df.columns = ["Team", "Tore"]

        fig = px.bar(
            chart_df.sort_values("Tore"),
            x="Tore",
            y="Team",
            orientation="h",
            color_discrete_sequence=["#4be0a0"],
        )

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#122238",
            font=dict(color="#f4f7fb"),
        )

        st.markdown("### Teams mit den meisten Toren")
        st.plotly_chart(fig, use_container_width=True)

    # ---------------- ERGEBNISSE ----------------

    elif page == "📅 Ergebnisse":
        team_filter = st.selectbox(
            "Team filtern",
            ["Alle Teams"] + teams
        )

        season_options = sorted(
            df["Saison"].unique().tolist(),
            reverse=True
        )

        season_filter = st.selectbox(
            "Saison",
            ["Alle Saisons"] + season_options
        )

        results = df.copy()

        if team_filter != "Alle Teams":
            results = results[
                (results["Heim"] == team_filter)
                | (results["Auswärts"] == team_filter)
            ]

        if season_filter != "Alle Saisons":
            results = results[results["Saison"] == season_filter]

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

        st.write(f"**{len(display)} Resultate gefunden**")
        st.dataframe(display, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Als CSV exportieren",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name="kickpredict_ergebnisse.csv",
            mime="text/csv",
        )

    # ---------------- ÜBER UNS ----------------

    elif page == "ℹ️ Über uns":
        st.markdown("### Unsere Idee")

        st.write(
            "KickPredict AI ist ein Fussballanalyse-Projekt, das "
            "vergangene Resultate statistisch auswertet, um mögliche "
            "Spielausgänge einzuschätzen."
        )

        st.markdown("### Unsere Kategorien")

        st.write("""
        - **Home:** Übersicht
        - **Spielprognose:** Wahrscheinlichkeiten für 1X2
        - **Team-Analyse:** Form und Leistung
        - **Statistiken:** Tore und Spielausgänge
        - **Ergebnisse:** Resultate und CSV-Export
        """)

        st.markdown("### Erstellt von")
        st.markdown("## Tiago Faruk und Yigit")

        st.info(
            "Die Prognosen sind Schätzungen und garantieren "
            "keine bestimmte Trefferquote."
        )

    attribution()


st.sidebar.divider()
st.sidebar.caption("KickPredict AI · Football Analytics")
