# App 4 – SEPA-Lastschrift-Generator für Vereine

## Nische und Zeitpunkt
- **Formatwechsel November 2026:** Banken stellen auf ISO 20022 Version 2019 um. Für Lastschriften wird dann **pain.008.001.08** verlangt; das ältere pain.008.001.02 wird nicht mehr oder nur nach individueller Vereinbarung angenommen (laut Formatübersicht der HypoVereinsbank/UniCredit). Adressen müssen strukturiert oder hybrid sein, mindestens mit Ort und Land.
- **Zielgruppe:** Vereine in Österreich und Deutschland (Sport, Musik, Feuerwehr, Kultur), die Mitgliedsbeiträge einziehen. Oft erledigt das ein ehrenamtlicher Kassier mit einer Excel-Liste und einem alten Makro oder Tool, das noch das alte Format erzeugt.
- **Der Schmerz:** Die Bank lehnt die Datei ab, Beiträge kommen nicht herein, und der Kassier weiß nicht, warum.

## Lösung
Excel- oder CSV-Mitgliederliste laden, Vereinsdaten eingeben, und man erhält:
- eine gültige pain.008.001.08-Datei (getestet gegen das offizielle XSD-Schema)
- eine Fehlerliste: IBAN-Prüfziffer, doppelte Mandatsreferenzen, fehlende Mandatsdaten, zukünftige Mandatsdaten, Mandate älter als 36 Monate, Nicht-EWR-Konten ohne Adresse
- eine Prüfung des Einzugsdatums gegen den TARGET-Bankkalender sowie den Hinweis auf die 14-tägige Vorabankündigung
- fertige Texte für die Vorabankündigung (CSV für Serienbrief oder Serien-Mail)
- fehlerhafte Zeilen werden ausgelassen statt die ganze Datei zu blockieren

Die Datei entsteht im Browser. Namen und IBANs verlassen das Gerät nicht, was für Vereine datenschutzrechtlich wichtig ist.

**Technik:** Python-Paket `sepalast/`, erzeugt das XML mit der Standardbibliothek. Excel liest es über openpyxl (läuft ebenfalls im Browser).
**Tests:** 8 automatische Tests, darunter XSD-Validierung, Gläubiger-ID-Prüfziffer am offiziellen Bundesbank-Beispiel, TARGET-Feiertage, Excel-Import und Zeichensatz. Dazu ein Browser-Test mit Excel-Datei, Download und XSD-Prüfung der heruntergeladenen Datei.

## Investition
**0 €**, gleiche Website und gleiches Hosting.

## Monetarisierung (Annahmen)
- Kostenlos bis 25 Mitglieder. Das deckt sehr kleine Vereine ab und baut Reichweite und Vertrauen auf.
- **Pro-Lizenz 49 €/Jahr** für größere Vereine. Das ist dieselbe Lizenz wie für die anderen Werkzeuge. Vereinssoftware kostet typischerweise ein Mehrfaches; ein reiner Lastschrift-Generator muss günstig sein.
- **Vertrieb:** Landes-Sportverbände, Blasmusikverbände und Feuerwehrverbände haben Newsletter und Kassier-Schulungen. Ein kostenloses, datensparsames Werkzeug ist dort gut vermittelbar.

## Grenzen (ehrlich)
- Einzelne Banken haben Sonderregeln (Vorlaufzeiten, BIC-Pflicht, Zeichensatz). Die Seite empfiehlt, das bei der Bank zu klären.
- Mandatsverwaltung (wann wurde ein Mandat zuletzt genutzt?) ist nicht enthalten. Das Tool warnt nur bei sehr alten Mandatsdaten.
- B2B-Lastschriften (Firmenlastschrift) werden bewusst nicht unterstützt, nur die Basislastschrift CORE.

## Ausbaustufen
- Rücklastschriften-Import (camt.054) zum Abgleich.
- Überweisungen (pain.001.001.09) für Auszahlungen, etwa Übungsleiterpauschalen.
- Speicherbarer Vereinsstamm und Beitragsklassen (Kinder, Erwachsene, Familie).
