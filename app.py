import math
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "matches.csv"

st.set_page_config(page_title="KickPredict AI", page_icon="⚽", layout="wide")
st.title("⚽ KickPredict AI")
st.caption("Deine eigene Fussball-Prognose-Webapp · Version 1")

st.info(
    "Diese erste Version nutzt ein transparentes Poisson-Modell mit Heimvorteil und "
    "Teamstärke aus historischen Resultaten. Sie ist ein Startpunkt, keine Garantie "
    "für 60 % Trefferquote. Vorhersagen sind nur so gut wie die Daten."
)

def load_data():
    if CSV_PATH.exists():
        try:
            df = pd.read_csv(CSV_PATH)
            needed = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
            if needed.issubset(df.columns):
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
                df["FTHG"] = pd.to_numeric(df["FTHG"], errors="coerce")
                df["FTAG"] = pd.to_numeric(df["FTAG"], errors="coerce")
                df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
                return df.sort_values("Date")
        except Exception:
            pass
    return pd.DataFrame(columns=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])

def poisson_probs(lam, max_goals=10):
    probs = []
    for k in range(max_goals + 1):
        probs.append(math.exp(-lam) * (lam ** k) / math.factorial(k))
    total = sum(probs)
    return [p / total for p in probs]

def fit_team_rates(df, home, away, recent_n=8):
    # A simple, transparent model. Uses last matches from each team, plus league averages.
    league_home_avg = max(float(df["FTHG"].mean()), 0.15)
    league_away_avg = max(float(df["FTAG"].mean()), 0.15)

    home_matches = df[(df["HomeTeam"] == home) | (df["AwayTeam"] == home)].tail(recent_n)
    away_matches = df[(df["HomeTeam"] == away) | (df["AwayTeam"] == away)].tail(recent_n)

    def scored_conceded(matches, team):
        scored, conceded = [], []
        for _, r in matches.iterrows():
            if r["HomeTeam"] == team:
                scored.append(float(r["FTHG"]))
                conceded.append(float(r["FTAG"]))
            else:
                scored.append(float(r["FTAG"]))
                conceded.append(float(r["FTHG"]))
        return (sum(scored) / len(scored), sum(conceded) / len(conceded)) if scored else (None, None)

    hs, hc = scored_conceded(home_matches, home)
    as_, ac = scored_conceded(away_matches, away)

    # Blend team rates with competition averages to reduce overreaction to small samples.
    home_attack = 0.65 * (hs if hs is not None else league_home_avg) + 0.35 * league_home_avg
    home_defence = 0.65 * (hc if hc is not None else league_away_avg) + 0.35 * league_away_avg
    away_attack = 0.65 * (as_ if as_ is not None else league_away_avg) + 0.35 * league_away_avg
    away_defence = 0.65 * (ac if ac is not None else league_home_avg) + 0.35 * league_home_avg

    # Relative scoring strength, adjusted for home advantage.
    home_lambda = league_home_avg * (home_attack / league_home_avg) * (away_defence / league_home_avg)
    away_lambda = league_away_avg * (away_attack / league_away_avg) * (home_defence / league_away_avg)
    home_lambda *= 1.08
    away_lambda *= 0.94
    return max(0.15, min(home_lambda, 4.0)), max(0.15, min(away_lambda, 4.0))

def predict(df, home, away):
    lh, la = fit_team_rates(df, home, away)
    ph, pa = poisson_probs(lh), poisson_probs(la)
    p_home = p_draw = p_away = 0.0
    best_score, best_p = "1–1", -1
    for hg, p1 in enumerate(ph):
        for ag, p2 in enumerate(pa):
            p = p1 * p2
            if hg > ag:
                p_home += p
            elif hg == ag:
                p_draw += p
            else:
                p_away += p
            if p > best_p:
                best_p = p
                best_score = f"{hg}–{ag}"
    outcomes = {"1 (Heimsieg)": p_home, "X (Unentschieden)": p_draw, "2 (Auswärtssieg)": p_away}
    return outcomes, best_score, lh, la

df = load_data()
with st.sidebar:
    st.header("Daten")
    st.write("Geladene Spiele:", len(df))
    uploaded = st.file_uploader("Historische Resultate als CSV hochladen", type=["csv"])
    st.caption("CSV-Spalten: Date, HomeTeam, AwayTeam, FTHG, FTAG. Zum Beispiel aus Football-Data.co.uk.")
    if uploaded is not None:
        try:
            uploaded_df = pd.read_csv(uploaded)
            needed = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
            if needed.issubset(uploaded_df.columns):
                uploaded_df.to_csv(CSV_PATH, index=False)
                st.success("CSV gespeichert. Seite neu laden, falls die Daten noch nicht angezeigt werden.")
                st.rerun()
            else:
                st.error("Es fehlen Spalten. Benötigt: Date, HomeTeam, AwayTeam, FTHG, FTAG.")
        except Exception as e:
            st.error(f"CSV konnte nicht gelesen werden: {e}")

if df.empty:
    st.warning("Noch keine historischen Daten geladen. Lade links eine CSV-Datei mit den benötigten Spalten hoch.")
    st.markdown("""
    **So startest du:**
    1. Lade Resultatdaten einer Liga als CSV herunter.
    2. Stelle sicher, dass die Spalten `Date`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG` vorhanden sind.
    3. Lade die Datei links hoch.
    4. Wähle danach Heim- und Auswärtsteam.
    """)
else:
    teams = sorted(set(df["HomeTeam"].astype(str)) | set(df["AwayTeam"].astype(str)))
    c1, c2 = st.columns(2)
    with c1:
        home = st.selectbox("Heimteam", teams, index=0)
    with c2:
        away_choices = [t for t in teams if t != home]
        away = st.selectbox("Auswärtsteam", away_choices, index=0 if away_choices else None)

    if home == away:
        st.error("Bitte zwei verschiedene Teams wählen.")
    else:
        outcomes, score, lh, la = predict(df, home, away)
        st.subheader(f"Prognose: {home} – {away}")
        best = max(outcomes, key=outcomes.get)
        st.metric("Tipp der KI (1X2)", best, f"{outcomes[best]*100:.1f} % Modellwahrscheinlichkeit")
        cols = st.columns(3)
        for col, (name, prob) in zip(cols, outcomes.items()):
            col.metric(name, f"{prob*100:.1f} %")
        st.write(f"**Häufigstes genaues Resultat im Modell:** {score}")
        st.caption(f"Erwartete Tore (Modell): {home} {lh:.2f} · {away} {la:.2f}")
        st.bar_chart(pd.DataFrame({"Wahrscheinlichkeit (%)": [v*100 for v in outcomes.values()]}, index=list(outcomes.keys())))

st.divider()
st.subheader("Was diese Version kann – und was noch fehlt")
st.markdown("""
- **Kann:** aus hochgeladenen historischen Ergebnissen eine einfache 1X2-Wahrscheinlichkeit berechnen.
- **Noch nicht:** automatisch alle weltweiten Ligen und Spielpläne abrufen, Verletzungen oder Aufstellungen berücksichtigen.
- **Nächster Schritt:** Datenimport automatisieren, Ligen trennen und ein zeitlich sauberes Backtesting einbauen.
""")
