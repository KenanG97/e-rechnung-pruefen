# App 3 – Shop-Check: Grundpreis (PAngV) & GPSR

## Nische
- **Grundpreis:** Seit der Neufassung der Preisangabenverordnung (28.05.2022) muss sich der Grundpreis auf 1 kg, 1 l, 1 m, 1 m² oder 1 m³ beziehen. Die 100-g-Option für Fertigpackungen ist entfallen, alte Shop-Daten sind deshalb oft falsch. Fehlende oder falsche Grundpreise sind ein Klassiker bei Abmahnungen.
- **GPSR (VO (EU) 2023/988, seit 13.12.2024):** Jedes Online-Angebot braucht Herstellername, Postanschrift und elektronische Adresse, bei Herstellern außerhalb der EU auch die verantwortliche Person in der EU, dazu Produktbild und Sicherheitshinweise. Abmahnungen von Mitbewerbern sind dokumentiert.
- **Zielgruppe:** kleine Shopify-, WooCommerce- und Etsy-Händler in DE und AT. Sie haben viele Produkte, keine Rechtsabteilung und echte Angst vor Abmahnungen.

## Lösung
Produkt-Export hochladen → Liste der betroffenen Artikel mit **fertig berechnetem Grundpreis**. Die Prüfung läuft im Browser, Shop-Daten verlassen den Rechner nicht.

**Technik:** Python-Paket `shopcheck/`
- **Formate:** erkennt Shopify (inkl. Varianten und eingebautem Einheitspreis), WooCommerce (deutsch und englisch), Etsy und allgemeine CSV-Dateien.
- **Füllmenge:** wird aus Titel, Variante und „Inhalt:“-Angaben gelesen, inkl. Mehrfachpackungen. Maße wie „30 x 40 cm“ werden bewusst nicht als Menge gewertet.
- **GPSR-Prüfung:** Hersteller, Anschrift, E-Mail/Web, Hinweis auf Nicht-EU-Herkunft ohne EU-Verantwortlichen, Bild, Sicherheitshinweise bei Risikoprodukten.
- **Tests:** 7 automatische Tests sowie ein Test im Browser auf Desktop und Mobil.

## Investition
**0 €**, gleiche Website und gleiches Hosting wie App 1 und 2.

## Monetarisierung (Annahmen)
- Kostenlos: bis 25 Produkte (reicht zum Ausprobieren und für Mini-Shops).
- **Pro-Lizenz 49 €/Jahr:** alle Produkte und Export der Produktliste mit berechneten Grundpreisen. Es ist dieselbe Lizenz wie für App 1.
- Händler sind die zahlungsfreudigste Zielgruppe der vier Apps: Eine einzige Abmahnung kostet ein Vielfaches.

## Grenzen (ehrlich)
- Herstellerangaben, die ein Shop über Metafelder oder Theme-Blöcke anzeigt, fehlen im Export. Dann meldet das Tool sie als fehlend, und der Nutzer wird darauf hingewiesen.
- Die Füllmengen-Erkennung arbeitet mit Mustern. Ungewöhnliche Schreibweisen werden eventuell nicht erkannt.
- Die österreichische Grundpreisauszeichnung (Preisauszeichnungsgesetz) kann im Detail abweichen. Die Prüfregeln folgen der strengeren deutschen PAngV.

## Ausbaustufen
- Shopify-App mit direktem Zugriff statt CSV (Shopify-Partnerkonto ist kostenlos; Verkauf über den App Store).
- Prüfung weiterer Abmahnklassiker: Lieferzeitangaben, „inkl. MwSt.“-Hinweis, Versandkostenhinweis, Textilkennzeichnung.
