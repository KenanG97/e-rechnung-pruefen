# App 1 – „E-Rechnung prüfen“: Konzept, Kosten, Monetarisierung

## 1. Die Nische – und warum sie echt ist

**Gesetzliche Lage (Deutschland, Wachstumschancengesetz):**
- Seit **1.1.2025** muss *jedes* inländische Unternehmen E-Rechnungen im B2B-Verkehr **empfangen** können, auch Kleinunternehmer nach § 19 UStG. Für das Empfangen gibt es keine Übergangsfrist.
- Ab **1.1.2027** müssen Unternehmen mit mehr als 800.000 € Vorjahresumsatz E-Rechnungen **versenden**. Ab **1.1.2028** gilt das für alle. Kleinunternehmer bleiben vom Versenden befreit (§ 34a UStDV).
- Nach dem BMF-Schreiben vom 15.10.2024 berechtigt nach Ablauf der Übergangsfristen grundsätzlich nur eine Rechnung im E-Rechnungsformat zum Vorsteuerabzug, wenn eine E-Rechnungspflicht besteht.
- Die ZUGFeRD-Profile MINIMUM und BASIC-WL gelten nicht als E-Rechnung, weil ihnen Pflichtangaben fehlen.

**Das eigentliche Problem:** Das *Erstellen* von E-Rechnungen ist schon gut abgedeckt (sevdesk, lexoffice und Generatoren mit Gratis-Stufen). Auf der *Empfangsseite* sehen kleine Betriebe dagegen eine XML-Datei, mit der sie nichts anfangen können. Kostenlose Viewer zeigen die Datei nur an. Was der Empfänger aber wirklich wissen muss, ist etwas anderes:

1. **Darf ich daraus Vorsteuer ziehen?** Das hängt an den Pflichtangaben nach § 14 Abs. 4 UStG und am zulässigen Profil.
2. **Stimmt der Betrag?** Also Positionen, Steuer, Brutto und Zahlbetrag.
3. **Ist die Rechnung echt?** Das häufigste Betrugsmuster sind geänderte Bankdaten. Die IHK warnt ausdrücklich davor.
4. **Habe ich die Rechnung schon bezahlt?** Dafür braucht es eine Duplikaterkennung.

**Positionierung:** „Der Rechnungsprüfer für den Posteingang.“ Das Tool ist kein Buchhaltungsprogramm und konkurriert deshalb nicht mit sevdesk & Co. Es ist die Prüfschicht *vor* dem Bezahlen.

**Zielgruppen, in Reihenfolge der Zahlungsbereitschaft:**
1. Buchhaltungsbüros und Steuerkanzleien, die Belege für viele Mandanten prüfen (Stapelprüfung, CSV)
2. Handwerksbetriebe und KMU ohne Buchhaltungssoftware mit E-Rechnungs-Import
3. Kleinunternehmer und Freelancer (Gratis-Stufe, Reichweite, SEO)

## 2. Was die App kann (MVP, fertig programmiert)

| Funktion | Gratis | Pro |
|---|---|---|
| XRechnung (UBL und CII) und ZUGFeRD/Factur-X-PDF lesbar darstellen | ✅ | ✅ |
| Erkennen, ob ein PDF überhaupt eine E-Rechnung ist; Profile MINIMUM/BASIC WL erkennen | ✅ | ✅ |
| Pflichtangaben-Check § 14 Abs. 4 UStG, Reverse Charge (§ 13b/§ 14a), Steuerbefreiungen | ✅ | ✅ |
| Rechnerische Prüfung (Positionen, USt je Satz, Brutto, Zahlbetrag, XRechnung-Drittforderungen) | ✅ | ✅ |
| IBAN-Prüfziffer, Prüfziffer der deutschen USt-IdNr., EU-USt-IdNr.-Format, Ausland-IBAN-Warnung | ✅ | ✅ |
| **IBAN-Wechsel-Alarm** und Duplikaterkennung über einen Verlauf | ✅ | ✅ |
| Prüfbericht als PDF, Positionen als CSV | ✅ | ✅ |
| Stapelprüfung | 3 Dateien | unbegrenzt |
| Sammel-CSV für Steuerberater/Excel | – | ✅ |

**Qualitätsnachweis:** Alle 72 offiziellen XRechnung-Testrechnungen der KoSIT (Koordinierungsstelle für IT-Standards) werden gelesen, ohne einen einzigen falschen „Fehler“. Gezielt manipulierte Rechnungen erkennt das Tool zuverlässig. Insgesamt gibt es 82 automatisierte Tests.

**Datenschutz als Verkaufsargument:** Dateien werden nur im Arbeitsspeicher verarbeitet. Der Verlauf liegt beim Nutzer (JSON-Download) und nicht auf dem Server.

## 3. Investitionsrechnung

| Posten | Start (Monat 0) | Laufend | Anmerkung |
|---|---|---|---|
| Hosting | **0 €** | 0 € | Streamlit Community Cloud (gratis, öffentliche App, schläft bei Inaktivität) |
| Code-Hosting | **0 €** | 0 € | GitHub (öffentliches oder privates Repo) |
| Domain | **0 €** | 0 € | zuerst `*.streamlit.app`; eigene Domain später ca. 10–15 €/Jahr |
| Zahlungsabwicklung | **0 €** | nur Gebühren pro Verkauf | z. B. Lemon Squeezy (Merchant of Record, erledigt die EU-USt) oder Stripe Payment Links; keine Fixkosten |
| Lizenzserver | **0 €** | 0 € | eingebaut: HMAC-signierte Schlüssel, ohne Datenbank |
| Impressum/Datenschutz | **0 €** | 0 € | kostenlose Generatoren |
| Gewerbe (AT) | ~0 € | – | **bitte prüfen**: Anmeldung beim Gewerbe bzw. über USP; Kleinunternehmerregelung beachten |
| **Summe** | **≈ 0 €** | **0 € fix** | Hauptinvestition ist Zeit für Vertrieb |

**Ab wann Kosten entstehen (bewusst aufgeschoben):**
- *EU-Hosting für zahlende B2B-Kunden.* Streamlit Cloud läuft nicht garantiert in der EU. Für Kanzleien ist das ein Einwand (DSGVO-Auftragsverarbeitung). Lösung: ein kleiner VPS in der EU (eine Größenordnung von einigen €/Monat) oder eine **lokale Desktop-Version** (dieselbe App, `streamlit run` bzw. als .exe paketiert, 0 € Hosting, maximale Vertraulichkeit).
- *Haftung:* Ein klarer Disclaimer ist eingebaut („keine Steuerberatung“). Ab nennenswertem Umsatz sollten Sie eine Vermögensschadenhaftpflicht erwägen.

## 4. Monetarisierung (Annahmen, nicht validiert)

| Plan | Preis-Vorschlag | Für wen |
|---|---|---|
| Gratis | 0 € | Kleinunternehmer, SEO-Reichweite |
| Pro | 4,90 €/Monat oder 39 €/Jahr | KMU, Handwerk |
| Kanzlei | 19 €/Monat oder 190 €/Jahr | Buchhaltungsbüros, Steuerkanzleien |

Zum Vergleich: Rechnungsprogramme mit E-Rechnung kosten ca. 10–19 €/Monat (z. B. kostenlose-erechnung.de Business 119 €/Jahr). Ein reiner Prüfer muss also deutlich darunter liegen.

**Beispielrechnung (rein illustrativ):** 40 Pro-Jahreskunden × 39 € + 10 Kanzleien × 190 € ≈ **3.460 €/Jahr** vor Gebühren und Steuern. Das ist ein Nebeneinkommen, kein Selbstläufer. Ob die Zahlen erreichbar sind, entscheidet allein der Vertrieb.

**Kritische Einschätzung:**
- *Gegenargument:* Gratis-Viewer existieren bereits, und Buchhaltungssoftware wird das Lesen ohnehin integrieren. Das Zeitfenster ist **2025–2028**, danach wird das Thema Standard.
- *Verteidigung:* Die Differenzierung liegt im **Prüfen** (Vorsteuer-Risiko, Betrug, Duplikate), nicht im Anzeigen. Der wahrscheinlichste zahlende Kanal sind Kanzleien und Buchhalter, nicht Endkunden.
- *Validierung vor weiterer Arbeit:* Sprechen Sie mit 10 Buchhaltern oder Kanzleien. Wenn keiner sagt „das würde ich zahlen“, sollte die Erweiterung nicht weiterverfolgt werden.

## 5. Go-to-Market (0 €)
1. Deployen (siehe README), Impressum und Datenschutz ergänzen.
2. SEO: 5–10 Ratgeberseiten zu Suchbegriffen wie „XRechnung öffnen“, „ZUGFeRD prüfen“, „E-Rechnung Vorsteuerabzug Pflichtangaben“ und „IBAN geändert Rechnung Betrug“.
3. Direkt anschreiben: Buchhaltungsbüros und Bilanzbuchhalter (Verbände, LinkedIn, XING) mit einem Pilot-Angebot (3 Monate Kanzlei-Plan gratis gegen Feedback).
4. Präsenz in Foren und Communitys, in denen Kleinunternehmer die Frage „wie öffne ich diese XML?“ stellen.

## 6. Ausbaustufen (erst nach Validierung)
1. **Offizielle KoSIT-Validierung** (Schematron) als Pro-Funktion. Der Validator ist Open Source (Java) und lässt sich als zweiter Prozess anbinden.
2. **E-Mail-Postfach-Import:** eine eigene Adresse wie `rechnungen@…`, an die automatisch geprüft wird.
3. **USt-IdNr.-Live-Abfrage** über die EU-VIES-Schnittstelle (kostenlos).
4. **DATEV-Buchungsstapel-Export** für Kanzleien.
5. **Österreich-Modul** (ebInterface, E-Rechnung an den Bund).
