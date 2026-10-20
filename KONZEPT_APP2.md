# App 2 – Kleinunternehmer-Grenzwächter (AT & DE)

## Nische
- **Österreich:** Seit 2025 liegt die Kleinunternehmergrenze bei 55.000 € brutto. Bei bis zu 10 % Überschreitung (60.500 €) bleibt die Befreiung bis Jahresende bestehen. Darüber endet sie **sofort ab dem Umsatz, der die Toleranzgrenze überschreitet**.
- **Deutschland:** Seit 2025 gilt eine Vorjahresgrenze von 25.000 € und eine Grenze von 100.000 € im laufenden Jahr (jeweils netto). Wer die 100.000 € überschreitet, ist **sofort** regelbesteuert. Im Gründungsjahr gilt das schon ab 25.000 €.
- **Folge:** Wer die Grenze zu spät bemerkt, schuldet die Umsatzsteuer für Rechnungen, die er ohne USt gestellt hat. Die Kunden haben dann oft schon bezahlt, die Steuer geht also aus eigener Tasche.
- **Zielgruppe:** Hunderttausende Kleinunternehmer, Nebenerwerbs-Selbstständige und Online-Verkäufer (Etsy, Vinted, willhaben, Kleingewerbe).
- **Suchbegriffe:** „Kleinunternehmergrenze überschritten“, „Kleinunternehmerregelung 2026“, „Kleinunternehmergrenze Rechner“. Es gibt viel Suchvolumen und starke Konkurrenz, aber nur einfache Ein-Zahl-Rechner.

## Was die App anders macht
| | Übliche Rechner | Grenzwächter |
|---|---|---|
| Eingabe | eine Zahl | **Kontoauszug-CSV** jeder gängigen Bank, mehrere Konten |
| Ergebnis | über/unter | **Datum**, an dem die Grenze fällt, plus Hochrechnung bis Jahresende |
| Nicht-Umsätze | Nutzer muss selbst rechnen | erkennt Umbuchungen, Steuererstattungen, Rückerstattungen, Gehalt und Sozialleistungen automatisch; jede Buchung ist abwählbar |
| Plattformen | – | Warnung: PayPal-/Etsy-Auszahlungen sind netto nach Gebühren |
| Länder | meist nur eines | AT und DE inkl. Toleranzband, Vorjahresprüfung und Gründungsjahr |
| Datenschutz | teils Server | läuft lokal im Browser |

## Technik
- Reines Python-Paket `kugrenze/`:
  - `bankcsv.py` erkennt Zeichensatz, Trennzeichen, Kopfzeile, Soll/Haben-Spalten sowie deutsches und englisches Zahlenformat.
  - `rules.py` enthält Klassifikation, Grenzregeln und Prognose.
- Es läuft im Browser über Pyodide, auf derselben Website wie App 1 (Seite `/kleinunternehmergrenze/`). Eine Domain mit mehreren nützlichen Werkzeugen sammelt mehr Links und Vertrauen als zwei getrennte Seiten.
- **27 automatische Tests:** Bankformate im Stil von George, Sparkasse, N26 und Soll/Haben-Exporten, Grenzfälle auf den Cent genau (exakt 55.000 €, 60.500,01 €, 100.000,01 €), Vorjahr, Gründungsjahr und Browser-Brücke. Zusätzlich ein Test im echten Browser, Desktop und Mobil.

## Investition
**0 €**. Die App liegt auf derselben Website wie App 1, mit demselben kostenlosen Hosting und ohne Server.

## Monetarisierung (Annahmen)
Kleinunternehmer zahlen ungern für einen Rechner. Deshalb bleibt die App kostenlos und verdient indirekt:
1. **Affiliate-Links** zu Buchhaltungs- und Rechnungsprogrammen, genau im Moment „Sie werden bald umsatzsteuerpflichtig“. Mehrere Anbieter haben Partnerprogramme; Bedingungen und Provisionen müssen Sie bei Anmeldung prüfen. Solche Links müssen als Werbung gekennzeichnet sein.
2. **Vermittlung an Steuerberater** gegen Lead-Gebühr. Für den Nutzer ist die Steuerberatung beim Überschreiten der Grenze ohnehin der nächste Schritt.
3. **Traffic für App 1:** Wer regelbesteuert wird, bekommt Vorsteuer und braucht korrekte E-Rechnungen, die er dann mit App 1 prüft.

Ehrlich gesagt: Der Umsatz hängt vollständig von Google-Rankings ab. Realistisch sind die ersten Besucher nach 2–4 Monaten. Ohne eingehende Links bleibt es bei wenigen Besuchern.

## Ausbaustufen
- Erinnerung per E-Mail, wenn eine Grenze in Sicht ist (bräuchte einen kleinen Server, deshalb erst bei Nachfrage).
- Import von PayPal-, Etsy- und Stripe-Berichten (Bruttoumsatz statt Auszahlung).
- Österreich: Kleinunternehmerpauschalierung bei der Einkommensteuer sowie die SVS-Versicherungsgrenze (6.613,20 € für 2026 laut WKO; vor Einbau prüfen).
