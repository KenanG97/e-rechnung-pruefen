# Livegang in ca. 15 Minuten (0 €)

## Variante A: GitHub mit Claude verbinden (am einfachsten)
claude.ai → Einstellungen → Connectors → GitHub verbinden. Danach kann Claude Repository und Website selbst anlegen und veröffentlichen.

## Variante B: selbst hochladen
1. **Konto anlegen** auf github.com (kostenlos). Der Benutzername steht später in der Adresse.
2. **Repository erstellen:** „New repository“ → Name `e-rechnung-pruefen` → **Public** → „Create“.
3. **Dateien hochladen:** „uploading an existing file“ → den *Inhalt* des entpackten Ordners hineinziehen (auch die Ordner `.github` und `site`) → „Commit changes“.
   - Ausgeblendete Ordner wie `.github` werden beim Ziehen am Mac manchmal ignoriert. In dem Fall in GitHub „Add file → Create new file“, als Name `.github/workflows/pages.yml` eingeben und den Inhalt der Datei einfügen.
4. **Pages einschalten:** Settings → Pages → Source: **GitHub Actions**.
5. Unter „Actions“ läuft der Bau (ca. 2 Min.). Danach ist die Seite unter `https://<benutzername>.github.io/e-rechnung-pruefen/` online.

**Vorher:** In `site/config.json` bei `plz_ort` Postleitzahl und Ort eintragen. Ohne vollständiges Impressum nicht veröffentlichen.

**Nie hochladen:** `lizenz_privat.pem`. Mit dieser Datei erzeugen Sie Lizenzschlüssel. Wer sie hat, kann beliebig viele Schlüssel erzeugen. Bewahren Sie sie offline auf (z. B. USB-Stick oder Passwortmanager).

## Bei Google anmelden (das Wichtigste für die Auffindbarkeit)
1. search.google.com/search-console → „Property hinzufügen“ → **URL-Präfix** → Ihre Seitenadresse.
2. Bestätigung per „HTML-Tag“: Den Tag an Claude schicken oder selbst in `site/build.py` im `<head>` einfügen.
3. Unter „Sitemaps“ `sitemap.xml` einreichen.
4. Unter „URL-Prüfung“ die Startseite und jede Ratgeberseite einmal mit „Indexierung beantragen“ einreichen.
5. Dasselbe bei **Bing Webmaster Tools**. Das geht schnell über „Aus Google Search Console importieren“. Bing liefert auch DuckDuckGo und Ecosia.

Rechnen Sie mit **Wochen bis Monaten**, bis Seiten ranken. Eine neue Domain ohne eingehende Links startet bei null.

## Später (optional, kostet ~10–15 €/Jahr)
Eine eigene Domain (z. B. `erechnung-pruefen.at` oder `.de`) wirkt vertrauenswürdiger und bündelt die Links. Bei GitHub Pages unter Settings → Pages → Custom domain eintragen und `site_url` in `config.json` anpassen.

## Lizenz verkaufen
1. Zahlung annehmen: anfangs einfach per Rechnung und Überweisung (Kanzleien zahlen so am liebsten). Später ein Zahlungslink über Stripe oder Lemon Squeezy.
2. Schlüssel erzeugen: `python site/lizenz.py neu kanzlei@beispiel.de 2027-12-31`
3. Den Schlüssel per E-Mail schicken. Der Kunde gibt ihn auf der Startseite unter „Lizenz eingeben“ ein.

**Vor dem ersten Verkauf:** Gewerbe anmelden (siehe Hinweise im Chat bzw. WKO-Gründerservice).
