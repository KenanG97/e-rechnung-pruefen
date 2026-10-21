# Marketing-Plan für „E-Rechnung prüfen“ (0 € Budget)

## Ehrliche Ausgangslage
- „Finanzen“ als Suchbegriff ist nicht erreichbar. Dort ranken Banken, Vergleichsportale und Medien mit Millionen-Budgets.
- Erreichbar sind **konkrete Fragen**, die Menschen genau dann googeln, wenn sie eine XML-Rechnung vor sich haben. Diese Suchenden haben das Problem *jetzt*, deshalb sind sie wertvoller als breiter Traffic.
- Bei „XRechnung öffnen“ ist die Konkurrenz stark (sevdesk, norman, b2brouter und andere). Bessere Chancen haben Begriffe, die bisher kaum jemand bedient:

| Seite | Hauptbegriff | Warum Chancen |
|---|---|---|
| Startseite | „E-Rechnung prüfen“, „XRechnung prüfen online“ | Konkurrenz zeigt meist nur an, prüft nicht |
| /rechnungsbetrug-iban/ | „Rechnung IBAN geändert Betrug“ | Kaum Tools, hoher Schmerz |
| /zugferd-pruefen/ | „ZUGFeRD MINIMUM gültig“, „ZUGFeRD Profil prüfen“ | Nischenfrage, wenig gute Antworten |
| /e-rechnung-vorsteuerabzug/ | „E-Rechnung Vorsteuerabzug Pflichtangaben“ | Steuerseiten erklären, keine prüft |
| /e-rechnung-kleinunternehmer/ | „E-Rechnung Kleinunternehmer empfangen“ | Großes Volumen, starke Konkurrenz, guter Einstieg |

**USP für jeden Text:** „Die Datei verlässt Ihren Rechner nicht.“ Das kann fast kein Wettbewerber sagen.

## Woche 1: Fundament
1. Seite online stellen, Google Search Console und Bing einrichten (siehe LIVEGANG.md).
2. **Eingehende Links**, der wichtigste Rankingfaktor. Kostenlose und seriöse Quellen sind:
   - das eigene GitHub-Repository (README verlinkt die Seite)
   - ein Eintrag bei **awesome-Listen** auf GitHub zu E-Invoicing/ZUGFeRD (Pull Request)
   - ein Hinweis im ZUGFeRD-/XRechnung-Umfeld, z. B. in Diskussionen der Open-Source-Projekte, wo ein Viewer gefragt ist (nur wenn es zur Frage passt)
   - Ihr LinkedIn- und XING-Profil

## Woche 2–4: Direkter Vertrieb an Kanzleien (der eigentliche Umsatzhebel)
Ziel: **10 Gespräche, 3 Pilotkanzleien**. Kleine Kanzleien und selbstständige Bilanzbuchhalter in Deutschland finden Sie über die Online-Verzeichnisse der Steuerberaterkammern, über LinkedIn und über Google Maps.

**E-Mail-Vorlage** (persönlich anpassen, *einzeln* versenden, keine Massenmails):

> Betreff: E-Rechnungen Ihrer Mandanten vor dem Buchen prüfen
>
> Guten Tag Frau/Herr …,
>
> seit 2025 bekommen Ihre Mandanten XRechnungen und ZUGFeRD-PDFs. Viele davon sind formal fehlerhaft (falsches ZUGFeRD-Profil, fehlendes Leistungsdatum, Rundungsfehler), und das fällt oft erst bei der Buchung auf.
>
> Ich habe dafür ein kleines Prüfwerkzeug gebaut: Dateien ablegen, und es zeigt Pflichtangaben nach § 14 UStG, Rechenfehler und geänderte Bankverbindungen. Die Prüfung läuft komplett im Browser, Mandantendaten verlassen Ihren Rechner also nicht.
>
> Ich suche drei Kanzleien, die es drei Monate kostenlos nutzen und mir ehrlich sagen, was fehlt. Hätten Sie 15 Minuten für einen kurzen Blick?
>
> [Link] · Keno Benedetto

Rechtlich: Eine einzelne, sachliche B2B-E-Mail an eine öffentlich angegebene Geschäftsadresse ist in AT/DE eine Grauzone. Bei Kanzleien in Deutschland wäre ein **Anruf oder eine LinkedIn-Nachricht** rechtlich sicherer. Massen-E-Mails ohne Einwilligung sind unzulässig.

## Laufend: Fragen beantworten, wo sie gestellt werden
Wo: Gründer- und Selbstständigen-Foren, Reddit (r/selbststaendig, r/Finanzen nur wenn es dort passt), Facebook-Gruppen für Kleinunternehmer, die Community-Bereiche von Buchhaltungssoftware.

Regeln, damit es nicht als Spam gilt (sonst schadet es mehr als es nützt):
- Zuerst die Frage vollständig beantworten, dann erst den Link erwähnen.
- Immer offenlegen: „Disclaimer: Das Tool ist von mir.“
- Höchstens ein Beitrag pro Thread, nie Copy-Paste.

**Antwortvorlage:**
> Eine XRechnung ist reine XML, deshalb sieht sie im Browser aus wie Code. Aufheben müssen Sie die XML-Datei selbst (nicht nur einen Ausdruck), 8 Jahre. Zum Lesen reicht ein Viewer. Ich habe einen gebaut, der zusätzlich Pflichtangaben und Rechnung prüft und warnt, wenn sich die IBAN des Lieferanten geändert hat. Er läuft lokal im Browser: [Link]. (Disclaimer: von mir, kostenlos.)

## Messen
- Google Search Console: Welche Suchbegriffe bringen Impressionen? Für die besten Begriffe den Text ausbauen.
- Optional: Plausible (cookielos, ab ca. 9 $/Monat, deshalb anfangs weglassen) oder einfach die Search-Console-Daten nutzen.

## Abbruchkriterium
Wenn nach 3 Monaten **keine** Kanzlei zahlen will, verfolgen Sie das Projekt nicht weiter. Die Seite kann dann trotzdem gratis online bleiben.

## Kanäle für App 2–4
- **Kleinunternehmer-Grenze:** Saisonaler Höhepunkt ist Oktober bis Januar (Jahresende, Planung). Antworten in Gründer- und Selbstständigen-Foren auf die Frage „Grenze überschritten, was jetzt?“
- **Shop-Check:** Etsy- und Shopify-Händlergruppen, Händlerforen. Aufhänger: „Abmahnung wegen Grundpreis oder GPSR? Vorher prüfen.“
- **SEPA für Vereine:** Der Formatwechsel im **November 2026** ist ein aktueller Aufhänger, deshalb jetzt handeln. Kurzer Hinweistext an Landes-Sportverbände, Blasmusik- und Feuerwehrverbände sowie Gemeindezeitungen: „Kostenloser Generator für das neue Lastschriftformat, Daten bleiben am eigenen PC.“
