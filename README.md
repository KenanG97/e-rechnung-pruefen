# 🧾 Werkzeuge für Kleinunternehmer, Shops und Vereine

Vier Browser-Werkzeuge auf einer Website (Python via Pyodide, Hosting kostenlos auf GitHub Pages):

| App | Paket | Seite | Konzept |
|---|---|---|---|
| E-Rechnung prüfen | `erechnung/` | `/` | KONZEPT.md |
| Kleinunternehmer-Grenzwächter | `kugrenze/` | `/kleinunternehmergrenze/` | KONZEPT_APP2.md |
| Shop-Check Grundpreis & GPSR | `shopcheck/` | `/grundpreis-gpsr-check/` | KONZEPT_APP3.md |
| SEPA-Lastschrift für Vereine | `sepalast/` | `/sepa-lastschrift-verein/` | KONZEPT_APP4.md |


**Website (Browser-Version, empfohlen):** läuft komplett im Browser via Pyodide, Hosting kostenlos auf GitHub Pages – siehe **LIVEGANG.md** und **MARKETING.md**. Bauen: `python site/build.py`.

XRechnung & ZUGFeRD lesen, auf Pflichtangaben (§ 14 UStG) und Rechenfehler prüfen, Bankdaten-Betrug erkennen.
Konzept, Kosten und Monetarisierung: siehe **KONZEPT.md**.

## Streamlit-Variante (optional, z. B. als lokale Desktop-App)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Beispieldateien zum Ausprobieren liegen in `beispiele/` (darunter eine absichtlich fehlerhafte Rechnung).

## Kostenlos online stellen (Streamlit Community Cloud)
1. Diesen Ordner als Repository auf GitHub hochladen.
2. Auf share.streamlit.io mit GitHub anmelden → „New app“ → Repo wählen, Datei `app.py`.
3. Unter *Settings → Secrets* `LICENSE_SECRET = "..."` eintragen (langer Zufallswert, z. B. `python -c "import secrets;print(secrets.token_urlsafe(32))"`).
4. Fertig – Sie erhalten eine Adresse `https://<name>.streamlit.app`.

## Pro-Lizenzen verkaufen
Nach Zahlungseingang einen Schlüssel erzeugen und dem Kunden schicken:
```bash
LICENSE_SECRET="derselbe-wert" python -m erechnung.license neu kunde@firma.de 2027-12-31
```
Ohne Lizenzserver: Der Schlüssel ist signiert und enthält E-Mail und Ablaufdatum.

## Tests
```bash
git clone --depth 1 https://github.com/itplr-kosit/xrechnung-testsuite /tmp/xts
pip install pytest && python -m pytest -q tests
```

## Aufbau
| Datei | Zweck |
|---|---|
| `erechnung/parser.py` | UBL- & CII-Parser, ZUGFeRD-PDF-Extraktion, XXE-sicher |
| `erechnung/checks.py` | Pflichtangaben, Rechenprüfung, IBAN/USt-IdNr., Verlaufsvergleich |
| `erechnung/export.py` | PDF-Prüfbericht, CSV |
| `erechnung/license.py` | signierte Pro-Schlüssel |
| `app.py` | Streamlit-Oberfläche |

Hinweis: Automatisierte Plausibilitätsprüfung, keine Steuerberatung; ersetzt nicht die KoSIT-Validierung.
Testdaten unter `beispiele/` stammen aus der XRechnung-Testsuite der KoSIT (Apache-2.0).
