# KickPredict AI – Version 1

Eine erste Webapp für Fussball-1X2-Prognosen. Sie verwendet ein einfaches Poisson-Modell auf Basis historischer Resultate.

## Start auf Windows

1. Installiere Python 3.11 oder neuer von https://www.python.org/downloads/
2. Entpacke den Ordner.
3. Öffne PowerShell im Ordner `football_ai_v1`.
4. Führe diese Befehle aus:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Die Webapp öffnet sich normalerweise im Browser unter `http://localhost:8501`.

## Datenformat

Die CSV-Datei muss folgende Spalten enthalten:

- `Date`
- `HomeTeam`
- `AwayTeam`
- `FTHG` (Tore Heimteam)
- `FTAG` (Tore Auswärtsteam)

Du kannst Daten als CSV exportieren und links in der App hochladen. Nicht jede Datenquelle deckt alle Länder/Ligen ab. Prüfe Lizenz, Aktualität und Nutzungsbedingungen der Quelle.

## Wichtige Einschränkung

Diese Version ist ein Prototyp und **keine trainierte, verlässlich validierte KI**. Sie garantiert keine Trefferquote. Sie nutzt die letzten verfügbaren Resultate in der hochgeladenen Datei und eine einfache Poisson-Näherung. Für seriöse Auswertung müssen wir als nächsten Schritt ein Backtesting bauen, das nur Informationen verwendet, die vor dem jeweiligen Spiel bekannt waren.
