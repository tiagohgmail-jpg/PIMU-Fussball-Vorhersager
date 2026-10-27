
    if st.button("Prognose berechnen"):
        result = predict_match(hist, home, away)
        if result:
            st.session_state["prediction_result"] = result
            st.session_state["prediction_pair"] = (home, away)
        else:
            st.error("Nicht genügend Daten.")

    if "prediction_result" in st.session_state:
        result = st.session_state["prediction_result"]
        saved_home, saved_away = st.session_state["prediction_pair"]
        st.subheader(f"{saved_home} vs. {saved_away}")

        a, b, c = st.columns(3)
        with a:
            metric("Heimsieg", f"{result['home'] * 100:.1f}%")
        with b:
            metric("Unentschieden", f"{result['draw'] * 100:.1f}%")
        with c:
            metric("Auswärtssieg", f"{result['away'] * 100:.1f}%")

        fig = go.Figure(go.Bar(
            x=["Heimsieg", "Unentschieden", "Auswärtssieg"],
            y=[result["home"] * 100, result["draw"] * 100, result["away"] * 100],
            marker_color=["#4be0a0", "#6bbf9a", "#328c6a"],
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#122238",
            font=dict(color="#f4f7fb"),
            yaxis_title="Wahrscheinlichkeit (%)",
            yaxis=dict(range=[0, 100]),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.write("Wahrscheinlichster Ausgang:", result["winner"])
        st.write("Geschätzter Spielstand:", result["score"])
        st.caption("Die Prozentwerte sind statistische Schätzungen und keine Garantie.")


# -------------------- TEAM-ANALYSE --------------------

elif page == "🧠 Team-Analyse":
    hero(
        "Team-Analyse",
        "Aktuelle Ligatabelle direkt aus football-data.org – Spiele, Punkte, Siege, Remis, Niederlagen und Tore.",
    )

    if not FOOTBALL_API_KEY:
        st.error("Der football-data.org API-Schlüssel fehlt. Ohne ihn kann die aktuelle Tabelle nicht geladen werden.")
        st.code('FOOTBALL_DATA_API_KEY = "DEIN_API_SCHLUESSEL"')
        st.stop()

    league = st.selectbox("Liga", list(LEAGUES), key="team_league")
    league_code = LEAGUES[league][0]

    with st.spinner("Aktuelle offizielle Tabelle wird geladen ..."):
        table, season, standings_error = league_standings(league_code)

    if standings_error:
        st.error("Die aktuelle Tabelle konnte nicht geladen werden.")
        st.warning(standings_error)
        st.info(
            "Die Tabelle wird absichtlich nicht aus historischen Resultaten geschätzt, "
            "damit keine falschen aktuellen Punkte oder Spielzahlen angezeigt werden. "
            "Prüfe deinen API-Schlüssel und ob dein football-data.org-Tarif Tabellenzugriff erlaubt."
        )
        st.stop()

    if not table:
        st.warning("Die Datenquelle hat für diese Liga keine Tabelle zurückgegeben.")
        st.stop()

    def team_name(entry):
        team_data = entry.get("team") or {}
        return team_data.get("name") or "Unbekanntes Team"

    table = sorted(table, key=lambda entry: entry.get("position", 999))
    table_rows = []
    for entry in table:
        team_data = entry.get("team") or {}
        table_rows.append({
            "Rang": entry.get("position", "–"),
            "Team": team_data.get("name", "Unbekannt"),
            "Spiele": entry.get("playedGames", 0),
            "S": entry.get("won", 0),
            "U": entry.get("draw", 0),
            "N": entry.get("lost", 0),
            "Tore": entry.get("goalsFor", 0),
            "Gegentore": entry.get("goalsAgainst", 0),
            "Tordifferenz": entry.get("goalDifference", 0),
            "Punkte": entry.get("points", 0),
        })

    season_info = ""
    if season:
        current_season = season.get("startDate", "")[:4]
        end_year = season.get("endDate", "")[:4]
        if current_season and end_year:
            season_info = f"Saison {current_season}/{end_year} · "
        elif season.get("id"):
            season_info = f"Saison-ID {season['id']} · "

    st.caption(
        f"{season_info}Quelle: football-data.org · Zuletzt angefragt: "
        f"{now_utc().astimezone().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    st.markdown("### 🏆 Aktuelle Ligatabelle")
    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 🔎 Team im Detail")
    names = [team_name(entry) for entry in table]
    selected_name = st.selectbox("Team auswählen", names, key="team_analysis_selected")
    selected = next(entry for entry in table if team_name(entry) == selected_name)
    team_data = selected.get("team") or {}

    a, b, c, d = st.columns(4)
    with a:
        metric("Tabellenrang", str(selected.get("position", "–")))
    with b:
        metric("Spiele", str(selected.get("playedGames", 0)))
    with c:
        metric("Punkte", str(selected.get("points", 0)))
    with d:
        metric("Tordifferenz", f"{selected.get('goalDifference', 0):+d}")

    a, b, c, d, e = st.columns(5)
    with a:
        metric("Siege", str(selected.get("won", 0)))
    with b:
        metric("Unentschieden", str(selected.get("draw", 0)))
    with c:
        metric("Niederlagen", str(selected.get("lost", 0)))
    with d:
        metric("Erzielte Tore", str(selected.get("goalsFor", 0)))
    with e:
        metric("Gegentore", str(selected.get("goalsAgainst", 0)))

    crest = team_data.get("crest")
    if crest:
        st.image(crest, width=72)

    st.caption(
        "Diese Werte stammen aus der aktuellen Ligatabelle und sind keine "
        "Durchschnittswerte aus alten OpenFootball-Daten. Die API aktualisiert "
        "ihre Daten; die Anzeige wird höchstens fünf Minuten zwischengespeichert."
    )


# -------------------- STATISTIKEN --------------------

elif page == "📊 Statistiken":
    hero("Statistiken", "Ligaweite Tore und Spielausgänge.")

    league = st.selectbox("Liga", list(LEAGUES), key="stats_league")
    hist = historical_data(LEAGUES[league][1])

    if hist.empty:
        st.warning("Keine Resultate verfügbar.")
        st.stop()

    total = len(hist)
    goals = int(hist["Tore_Heim"].sum() + hist["Tore_Auswärts"].sum())
    home_wins = int((hist["Tore_Heim"] > hist["Tore_Auswärts"]).sum())
    draws = int((hist["Tore_Heim"] == hist["Tore_Auswärts"]).sum())
    away_wins = int((hist["Tore_Heim"] < hist["Tore_Auswärts"]).sum())

    a, b, c = st.columns(3)
    with a:
        metric("Spiele", str(total))
    with b:
        metric("Tore insgesamt", str(goals))
    with c:
        metric("Tore pro Spiel", f"{goals / total:.2f}")

    fig = px.pie(
        names=["Heimsieg", "Unentschieden", "Auswärtssieg"],
        values=[home_wins, draws, away_wins],
        hole=0.5,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f4f7fb"),
    )
    st.plotly_chart(fig, use_container_width=True)


# -------------------- ÜBER UNS --------------------
