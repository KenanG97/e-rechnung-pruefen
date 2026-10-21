"""Baut die statische Website nach site/dist/ (für GitHub Pages, Netlify, Cloudflare Pages …).

    python site/build.py            # nutzt site/config.json
    python site/build.py --local    # Pyodide aus ./pyodide-local/ (Offline-Test)

Jede Seite ist echtes HTML (nicht per JavaScript nachgeladen) – genau das braucht Google.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
DIST = HERE / "dist"
CFG = json.loads((HERE / "config.json").read_text())
LOCAL = "--local" in sys.argv
VERSION = date.today().strftime("%Y%m%d")
TODAY = date.today().isoformat()
SITE = CFG["site_url"].rstrip("/") + "/"
BRAND = CFG["brand"]
imp = CFG["impressum"]
IMPRESSUM_OK = all(imp.get(k) for k in ("name", "strasse", "plz_ort", "email"))

LOGO = ('<svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><rect x="3" y="2" width="16" height="21" rx="2" '
        'fill="none" stroke="currentColor" stroke-width="2"/><path d="M7 8h8M7 12h8M7 16h4" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="19" cy="19" r="5.2" fill="var(--paper)" stroke="currentColor" stroke-width="2"/>'
        '<path d="M16.6 19.1l1.6 1.6 3-3.2" fill="none" stroke="currentColor" stroke-width="2"/></svg>')

NAV = [  # Werkzeuge (Kopfzeile)
    ("", "E-Rechnung prüfen"),
    ("kleinunternehmergrenze/", "Kleinunternehmer-Grenze"),
    ("grundpreis-gpsr-check/", "Shop-Check"),
    ("sepa-lastschrift-verein/", "SEPA für Vereine"),
    ("kanzlei/", "Pro-Lizenz"),
]
GUIDES = [  # Ratgeber (Fußzeile, „Weiterlesen“)
    ("xrechnung-oeffnen/", "XRechnung öffnen"),
    ("zugferd-pruefen/", "ZUGFeRD prüfen"),
    ("e-rechnung-vorsteuerabzug/", "E-Rechnung & Vorsteuerabzug"),
    ("rechnungsbetrug-iban/", "Rechnungsbetrug: IBAN geändert"),
    ("e-rechnung-kleinunternehmer/", "E-Rechnung für Kleinunternehmer"),
    ("kleinunternehmergrenze/", "Kleinunternehmergrenze 2026"),
    ("grundpreis-gpsr-check/", "Grundpreis & GPSR im Online-Shop"),
    ("sepa-lastschrift-verein/", "SEPA-Lastschrift für Vereine"),
]


def rel(depth: int) -> str:
    return "../" * depth


def page(path: str, title: str, description: str, body: str, *, schema: list | None = None,
         noindex: bool = False, tool: bool | str = False) -> None:
    depth = path.count("/")
    r = rel(depth)
    canonical = SITE + path
    nav = "".join(
        f'<a href="{r}{p}"{" aria-current=\"page\"" if p == path else ""}>{html.escape(n)}</a>' for p, n in NAV)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in (schema or []))
    analytics = (f'<script defer data-domain="{CFG["plausible_domain"]}" src="https://plausible.io/js/script.js"></script>'
                 if CFG.get("plausible_domain") else "")
    cfg_js = ""
    if tool:
        base = (r + "pyodide-local/") if LOCAL else CFG["pyodide_base"]
        cfg_js = ("<script>window.ERECHNUNG_CFG=" + json.dumps({
            "root": r, "pyodideBase": base, "version": VERSION,
            "pypdfWheel": PYPDF_WHEEL, "licensePublicKey": CFG.get("license_public_key", ""),
            "excelWheels": EXCEL_WHEELS,
        }) + f'</script><script defer src="{r}static/{tool if isinstance(tool, str) else 'app.js'}?v={VERSION}"></script>')
    doc = f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{f'<meta name="google-site-verification" content="{html.escape(CFG["google_verification"])}">' if CFG.get("google_verification") else ""}
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{canonical}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="de_DE">
<link rel="icon" href="{r}static/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{r}static/style.css?v={VERSION}">
{ld}{analytics}{cfg_js}
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="{r}">{LOGO}{html.escape(BRAND)}</a><nav aria-label="Hauptmenü">{nav}</nav></div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap"><nav aria-label="Ratgeber">{"".join(f'<a href="{r}{gp}">{html.escape(gn)}</a>' for gp, gn in GUIDES)}</nav><nav><a href="{r}impressum/">Impressum</a><a href="{r}datenschutz/">Datenschutz</a></nav>
<p>Automatisierte Plausibilitätsprüfung – keine Steuer- oder Rechtsberatung. Stand der Inhalte: {date.today():%m/%Y}.</p></div></footer>
</body>
</html>"""
    out = DIST / path / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    if not noindex:
        SITEMAP.append(canonical)


def cta(r: str, text="Rechnung jetzt kostenlos prüfen") -> str:
    return (f'<div class="cta-box"><p><b>Haben Sie eine E-Rechnung vor sich?</b></p>'
            f'<p>Datei ablegen, Ergebnis in Sekunden. Die Datei verlässt Ihren Rechner nicht.</p>'
            f'<a class="btn" href="{r}">{text}</a></div>')


def related(r: str, skip: str) -> str:
    items = [(p, n) for p, n in GUIDES if p != skip]
    return "<h2>Weiterlesen</h2><ul class=\"related\">" + "".join(f'<li><a href="{r}{p}">{n}</a></li>' for p, n in items) + "</ul>"


def faq_schema(qas):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas]}


def article_schema(path, title, desc):
    return {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
            "inLanguage": "de", "dateModified": TODAY, "mainEntityOfPage": SITE + path,
            "author": {"@type": "Organization", "name": BRAND}}


def faq_html(qas):
    return "<h2>Häufige Fragen</h2>" + "".join(f"<h3>{html.escape(q)}</h3><p>{html.escape(a)}</p>" for q, a in qas)


# ---------------------------------------------------------------- Startseite mit Werkzeug

def build_home():
    qas = [
        ("Wird meine Rechnung hochgeladen?",
         "Nein. Die Prüfung läuft vollständig in Ihrem Browser. Die Datei wird weder an uns noch an Dritte übertragen; "
         "Sie können die Seite nach dem Laden sogar offline nutzen."),
        ("Welche Formate werden unterstützt?",
         "XRechnung in beiden Syntaxen (UBL und UN/CEFACT CII) sowie ZUGFeRD 2.x und Factur-X als PDF mit eingebetteter XML. "
         "ZUGFeRD 1.0 ist seit 2025 keine zulässige E-Rechnung mehr und wird abgelehnt."),
        ("Ersetzt das die Prüfung durch meinen Steuerberater?",
         "Nein. Das Werkzeug findet formale und rechnerische Fehler, bevor Sie bezahlen oder buchen. Steuerliche Einzelfälle "
         "gehören zu Ihrer Steuerberatung."),
        ("Muss ich die Originaldatei aufbewahren?",
         "Ja. Aufzubewahren ist die E-Rechnung in ihrer ursprünglichen Form, also die XML-Datei bzw. das ZUGFeRD-PDF – "
         "ein Ausdruck oder dieser Prüfbericht ersetzt sie nicht."),
        ("Was kostet das?",
         "Die Einzelprüfung ist kostenlos. Für Buchhaltungsbüros und Kanzleien gibt es eine Lizenz für Stapelprüfung und Sammelexport."),
    ]
    body = f"""
<h1>E-Rechnung prüfen, bevor Sie bezahlen</h1>
<p class="lead">XRechnung oder ZUGFeRD ablegen und sofort sehen: Ist das überhaupt eine gültige E-Rechnung, fehlen Pflichtangaben für den Vorsteuerabzug, stimmen die Beträge – und hat der Lieferant plötzlich eine neue IBAN?</p>
<div id="drop" class="drop" role="button" tabindex="0" aria-describedby="drop-hint">
  <strong>Rechnung hier ablegen</strong>
  <span id="drop-hint">oder klicken, um .xml- oder .pdf-Dateien auszuwählen</span>
  <input id="file" type="file" accept=".xml,.pdf,application/xml,text/xml,application/pdf" multiple>
</div>
<ul class="trust"><li>Datei bleibt auf Ihrem Gerät</li><li>ohne Anmeldung</li><li>XRechnung, ZUGFeRD, Factur-X</li></ul>
<p id="status" role="status"></p>
<div id="batch" hidden class="sheet"><p><b><span id="batch-n">0</span> Rechnungen geprüft.</b> Alle als Tabelle für Excel oder den Steuerberater exportieren:</p>
<button class="btn" id="batch-csv" type="button">Sammel-CSV herunterladen</button>
<form id="pro" hidden class="no-print"><p class="muted">Der Sammelexport und Stapel mit mehr als 3 Dateien gehören zur <a href="kanzlei/">Kanzlei-Lizenz</a>.</p></form></div>
<div id="results"></div>

<div class="intro-content">
<h2>Was geprüft wird</h2>
<ul>
<li><b>Ist es eine echte E-Rechnung?</b> Eine gewöhnliche PDF ohne eingebettete Daten ist keine. Auch die ZUGFeRD-Profile MINIMUM und BASIC WL erfüllen die Anforderungen nicht, weil ihnen Pflichtangaben fehlen.</li>
<li><b>Pflichtangaben nach § 14 Abs. 4 UStG</b>: Namen und Anschriften, Steuernummer oder USt-IdNr., Rechnungsnummer, Datum, Leistung, Leistungszeitpunkt, Entgelt und Steuer je Satz. Fehlt etwas, ist Ihr Vorsteuerabzug in Gefahr.</li>
<li><b>Rechnerische Richtigkeit</b>: Positionen, Zu- und Abschläge, Steuer je Steuersatz, Brutto- und Zahlbetrag – auf den Cent.</li>
<li><b>Sonderfälle</b>: Reverse Charge mit Pflichthinweis, steuerfreie Umsätze mit Befreiungsgrund, innergemeinschaftliche Lieferungen, Leitweg-ID bei XRechnungen.</li>
<li><b>Schutz vor Rechnungsbetrug</b>: Prüfziffer der IBAN, ausländische IBAN bei inländischem Lieferanten und – über den Verlauf in Ihrem Browser – eine geänderte Bankverbindung gegenüber früheren Rechnungen sowie doppelt eingereichte Rechnungen.</li>
</ul>

<h2>Verlauf für den IBAN-Abgleich</h2>
<p>Damit eine geänderte Bankverbindung auffällt, merkt sich Ihr Browser zu jeder geprüften Rechnung Lieferant, Nummer, Betrag und IBAN – nicht die Datei. Den Verlauf können Sie sichern und auf einem anderen Gerät wieder einlesen.</p>
<div class="actions"><button class="btn ghost" id="hist-dl" type="button">Verlauf sichern</button>
<label class="btn ghost">Verlauf einlesen<input id="hist-up" type="file" accept=".json" hidden></label>
<button class="btn ghost" id="hist-clear" type="button">Verlauf löschen</button></div>

<h2>Lizenz eingeben</h2>
<form id="pro-form" class="actions"><label for="pro-key" class="muted" style="flex-basis:100%">Kanzlei-Lizenzschlüssel</label>
<input id="pro-key" autocomplete="off" style="flex:1;min-width:12rem;font:inherit;padding:.55rem;border:1.5px solid var(--ink-soft);border-radius:4px;background:var(--sheet);color:var(--ink)">
<button class="btn" type="submit" style="margin-top:0">Aktivieren</button></form>
<p id="pro-msg" class="muted" role="status"></p>

{faq_html(qas)}
</div>"""
    schema = [{
        "@context": "https://schema.org", "@type": "WebApplication", "name": BRAND, "url": SITE,
        "applicationCategory": "FinanceApplication", "operatingSystem": "Browser", "inLanguage": "de",
        "description": "XRechnung und ZUGFeRD kostenlos online prüfen: Pflichtangaben, Rechenfehler, IBAN-Betrug.",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
    }, faq_schema(qas)]
    page("", "E-Rechnung prüfen – XRechnung & ZUGFeRD kostenlos online prüfen",
         "XRechnung und ZUGFeRD kostenlos prüfen: Pflichtangaben für den Vorsteuerabzug, Rechenfehler, geänderte IBAN. "
         "Ohne Upload – die Datei bleibt in Ihrem Browser.", body, schema=schema, tool=True)


# ---------------------------------------------------------------- Ratgeber

def build_xrechnung():
    p = "xrechnung-oeffnen/"
    t = "XRechnung öffnen: So lesen Sie die XML-Datei (kostenlos)"
    d = "Eine XRechnung ist eine XML-Datei ohne Layout. So machen Sie sie lesbar, prüfen den Inhalt und bewahren sie richtig auf."
    qas = [
        ("Kann ich eine XRechnung mit dem Browser öffnen?",
         "Technisch ja, aber Sie sehen dann nur verschachtelten XML-Code. Lesbar wird sie erst mit einem Viewer, der die Felder als Rechnung darstellt."),
        ("Muss ich eine XRechnung ausdrucken?",
         "Nein. Ein Ausdruck ist nur eine Kopie. Aufbewahrungspflichtig ist die XML-Datei selbst, in unveränderter Form."),
        ("Was ist der Unterschied zwischen UBL und CII?",
         "Beides sind zulässige Syntaxen der XRechnung mit denselben Inhalten. UBL beginnt mit <Invoice>, CII mit <CrossIndustryInvoice>. Für Sie als Empfänger spielt das keine Rolle, solange Ihr Werkzeug beide liest."),
    ]
    body = f"""<article>
<h1>XRechnung öffnen und lesen</h1>
<p class="lead">Eine XRechnung sieht aus wie Programmcode, weil sie welcher ist: eine XML-Datei für Maschinen. Seit 2025 müssen Sie sie trotzdem annehmen können. So geht es ohne Software-Abo.</p>
<h2>Warum die Datei so seltsam aussieht</h2>
<p>Die XRechnung ist der deutsche Standard für strukturierte Rechnungen nach der europäischen Norm EN 16931. Sie enthält kein Layout, sondern nur Daten: Lieferant, Positionen, Steuersätze, Beträge und Bankverbindung, jeweils in einem fest definierten Feld. Das ist für Buchhaltungssoftware ideal, für Menschen ohne Hilfsmittel unlesbar.</p>
<p>Seit dem 1. Januar 2025 muss jedes Unternehmen in Deutschland solche Rechnungen im inländischen B2B-Geschäft empfangen können – auch Kleinunternehmer. Für den Empfang genügt nach Auffassung der Finanzverwaltung ein E-Mail-Postfach. Lesen und prüfen müssen Sie die Rechnung aber trotzdem.</p>
<h2>In drei Schritten zur lesbaren Rechnung</h2>
<ol>
<li><b>Datei speichern.</b> Legen Sie den Anhang (meist <code>.xml</code>) unverändert ab. Nicht umbenennen, nicht in Word öffnen und speichern.</li>
<li><b>In einem Viewer öffnen.</b> Ziehen Sie die Datei auf <a href="../">unser Prüfwerkzeug</a>. Sie sehen Lieferant, Positionen und Summen wie auf einer Papierrechnung – und zusätzlich, ob Pflichtangaben fehlen oder Beträge nicht stimmen.</li>
<li><b>Original archivieren.</b> Bewahren Sie die XML-Datei auf, nicht nur einen Ausdruck oder eine PDF-Ansicht. Für Buchungsbelege gilt seit 2025 eine Aufbewahrungsfrist von acht Jahren.</li>
</ol>
<div class="note"><p><b>Gut zu wissen:</b> Viele „XRechnung-Viewer“ zeigen die Datei nur an. Ob die Rechnung Ihren Vorsteuerabzug trägt, ob richtig gerechnet wurde oder ob die Bankverbindung plötzlich eine andere ist, sagen sie nicht. Genau das prüfen wir mit.</p></div>
<h2>Woran Sie eine XRechnung erkennen</h2>
<ul>
<li>Dateiendung <code>.xml</code>, oft wenige Kilobyte groß.</li>
<li>Im Inhalt stehen Begriffe wie <code>urn:xeinkauf.de:kosit:xrechnung</code> (Kennung der XRechnung) sowie <code>Invoice</code> oder <code>CrossIndustryInvoice</code>.</li>
<li>Rechnungen an Behörden enthalten eine <b>Leitweg-ID</b> im Feld Käuferreferenz.</li>
</ul>
<h2>Typische Probleme beim Empfang</h2>
<h3>„Die Datei lässt sich nicht öffnen“</h3>
<p>Oft wurde der E-Mail-Anhang beim Weiterleiten verändert oder als <code>.txt</code> gespeichert. Fordern Sie die Datei erneut an.</p>
<h3>„Ich habe nur eine PDF bekommen“</h3>
<p>Dann handelt es sich entweder um eine ZUGFeRD-Rechnung (PDF mit eingebetteter XML) oder um eine gewöhnliche PDF-Rechnung. Was davon vorliegt, klärt <a href="../zugferd-pruefen/">unser ZUGFeRD-Ratgeber</a>.</p>
<h3>„Die Beträge passen nicht“</h3>
<p>Auch maschinell erzeugte Rechnungen enthalten Fehler, etwa durch falsch gerundete Steuerbeträge oder vergessene Zuschläge. Das Prüfwerkzeug rechnet jede Summe nach.</p>
{cta('../', 'XRechnung jetzt öffnen')}
{faq_html(qas)}
{related('../', p)}
</article>"""
    page(p, t, d, body, schema=[article_schema(p, t, d), faq_schema(qas)])


def build_zugferd():
    p = "zugferd-pruefen/"
    t = "ZUGFeRD-Rechnung prüfen: Echte E-Rechnung oder nur PDF?"
    d = "So erkennen Sie, ob eine PDF eine gültige ZUGFeRD-E-Rechnung ist – und warum die Profile MINIMUM und BASIC WL nicht genügen."
    qas = [
        ("Ist jede ZUGFeRD-Rechnung eine gültige E-Rechnung?",
         "Nein. Die Profile MINIMUM und BASIC WL enthalten nicht alle umsatzsteuerlichen Pflichtangaben und gelten deshalb nicht als E-Rechnung. Ab Profil BASIC (empfohlen: EN 16931/COMFORT) passt es."),
        ("Was gilt, wenn PDF und XML unterschiedliche Beträge zeigen?",
         "Maßgeblich ist der strukturierte XML-Teil. Abweichungen sollten Sie beim Lieferanten beanstanden, bevor Sie bezahlen."),
        ("Woran erkenne ich ZUGFeRD in einem PDF?",
         "Am eingebetteten Anhang, meist factur-x.xml oder zugferd-invoice.xml. Manche PDF-Programme zeigen ihn in der Seitenleiste unter Anhänge an."),
    ]
    body = f"""<article>
<h1>ZUGFeRD-Rechnung prüfen</h1>
<p class="lead">Eine ZUGFeRD-Rechnung sieht aus wie jede PDF – der entscheidende Teil steckt unsichtbar darin. Ob er da ist und ob er genügt, sehen Sie mit bloßem Auge nicht.</p>
<h2>Zwei Rechnungen in einer Datei</h2>
<p>ZUGFeRD (in Frankreich Factur-X) ist ein hybrides Format: eine normale PDF-Ansicht für Menschen und eine eingebettete XML-Datei für Maschinen. Steuerlich maßgeblich ist der strukturierte XML-Teil; dort müssen alle Pflichtangaben stehen. Weicht die PDF-Ansicht davon ab, gilt das als Problem, das Sie klären sollten.</p>
<h2>Drei Fälle, die Sie unterscheiden müssen</h2>
<ul>
<li><b>Gewöhnliche PDF ohne Anhang:</b> keine E-Rechnung. Während der Übergangsfristen bis Ende 2026 bzw. 2027 darf der Lieferant sie noch schicken; danach in der Regel nicht mehr.</li>
<li><b>ZUGFeRD mit Profil MINIMUM oder BASIC WL:</b> enthält eine XML, aber ohne Rechnungspositionen und vollständige Pflichtangaben. Das reicht nach dem BMF-Schreiben vom 15.10.2024 nicht für eine E-Rechnung.</li>
<li><b>ZUGFeRD ab Version 2.0.1 mit Profil BASIC, EN 16931 (COMFORT), EXTENDED oder XRECHNUNG:</b> zulässige E-Rechnung – vorausgesetzt, der Inhalt stimmt.</li>
</ul>
<div class="note"><p><b>Profil herausfinden:</b> Das Profil steht in der XML im Feld „GuidelineSpecifiedDocumentContextParameter“, z. B. <code>urn:cen.eu:en16931:2017</code> für EN 16931. Unser Werkzeug zeigt es an und warnt bei MINIMUM und BASIC WL.</p></div>
<h2>So prüfen Sie eine ZUGFeRD-Rechnung</h2>
<ol>
<li>Legen Sie die PDF auf <a href="../">das Prüfwerkzeug</a>.</li>
<li>Findet es keinen XML-Anhang, ist es eine gewöhnliche PDF-Rechnung.</li>
<li>Findet es einen Anhang, sehen Sie Profil, Pflichtangaben und Rechenergebnis – aus dem maßgeblichen XML-Teil, nicht aus der Ansicht.</li>
</ol>
<h2>Was Sie bei Fehlern tun</h2>
<p>Schreiben Sie dem Lieferanten konkret, was fehlt („Profil BASIC WL, bitte als EN 16931 senden“ oder „Leistungsdatum fehlt“). Der Prüfbericht lässt sich als PDF speichern und mitschicken. Zahlen Sie bei Rechenfehlern erst nach Korrektur.</p>
{cta('../', 'ZUGFeRD-PDF jetzt prüfen')}
{faq_html(qas)}
{related('../', p)}
</article>"""
    page(p, t, d, body, schema=[article_schema(p, t, d), faq_schema(qas)])


def build_vorsteuer():
    p = "e-rechnung-vorsteuerabzug/"
    t = "E-Rechnung & Vorsteuerabzug: Checkliste der Pflichtangaben (§ 14 UStG)"
    d = "Welche Angaben eine E-Rechnung enthalten muss, damit Sie die Vorsteuer ziehen dürfen – als Checkliste mit Sonderfällen wie Reverse Charge."
    qas = [
        ("Verliere ich den Vorsteuerabzug bei einem Formatfehler?",
         "Nicht automatisch – entscheidend sind vor allem vollständige und richtige Pflichtangaben. Fehlen diese, ist die Rechnung nicht ordnungsgemäß und der Vorsteuerabzug gefährdet, auch wenn das Format technisch stimmt. Lassen Sie fehlerhafte Rechnungen berichtigen."),
        ("Ab wann zählt für den Vorsteuerabzug nur noch die E-Rechnung?",
         "Nach Ablauf der Übergangsfristen – für die meisten Unternehmen ab 2027 bzw. 2028 – berechtigt im B2B-Inland grundsätzlich nur noch eine E-Rechnung zum Vorsteuerabzug, soweit eine E-Rechnungspflicht besteht."),
        ("Gibt es Ausnahmen?",
         "Ja, etwa Kleinbetragsrechnungen bis 250 Euro brutto und Fahrausweise. Für sie gelten vereinfachte Pflichtangaben, und sie sind von der E-Rechnungspflicht ausgenommen."),
    ]
    items = [
        ("Name und Anschrift des Lieferanten", "Nr. 1"), ("Name und Anschrift des Leistungsempfängers (also Ihre)", "Nr. 1"),
        ("Steuernummer oder USt-IdNr. des Lieferanten", "Nr. 2"), ("Ausstellungsdatum", "Nr. 3"),
        ("Fortlaufende, einmalige Rechnungsnummer", "Nr. 4"), ("Menge und Art der Lieferung bzw. Umfang und Art der Leistung", "Nr. 5"),
        ("Zeitpunkt der Lieferung oder Leistung (oder Leistungszeitraum)", "Nr. 6"),
        ("Entgelt nach Steuersätzen aufgeschlüsselt, inkl. vereinbarter Entgeltminderungen", "Nr. 7"),
        ("Steuersatz und Steuerbetrag – oder Hinweis auf die Steuerbefreiung", "Nr. 8"),
    ]
    rows = "".join(f"<tr><td>{a}</td><td>§ 14 Abs. 4 {b} UStG</td></tr>" for a, b in items)
    body = f"""<article>
<h1>E-Rechnung und Vorsteuerabzug: die Pflichtangaben</h1>
<p class="lead">Die Vorsteuer aus einer Eingangsrechnung dürfen Sie nur ziehen, wenn die Rechnung ordnungsgemäß ist. Mit der E-Rechnung ändert sich das Format – die Pflichtangaben bleiben dieselben.</p>
<h2>Checkliste nach § 14 Abs. 4 UStG</h2>
<div class="tbl"><table><thead><tr><th>Angabe</th><th>Rechtsgrundlage</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>Bei einer E-Rechnung müssen diese Angaben im <b>strukturierten Teil</b> stehen. Ein Verweis auf eine angehängte PDF genügt nicht.</p>
<h2>Sonderfälle, die oft schiefgehen</h2>
<h3>Reverse Charge (§ 13b UStG)</h3>
<p>Schuldet der Leistungsempfänger die Steuer, muss die Rechnung den Hinweis „Steuerschuldnerschaft des Leistungsempfängers“ enthalten (§ 14a Abs. 5 UStG). Sie melden die Steuer dann selbst an und können sie – sofern berechtigt – zugleich als Vorsteuer abziehen.</p>
<h3>Steuerfreie Umsätze</h3>
<p>Wird keine Umsatzsteuer berechnet, braucht es einen Hinweis auf den Grund der Befreiung. In der E-Rechnung steht dafür ein eigenes Feld (Befreiungsgrund).</p>
<h3>Innergemeinschaftliche Lieferungen</h3>
<p>Hier müssen die USt-IdNr. von Lieferant und Abnehmer auf der Rechnung stehen (§ 14a Abs. 3 UStG).</p>
<h3>Rechnungen von Kleinunternehmern</h3>
<p>Kleinunternehmer weisen keine Umsatzsteuer aus. Aus ihren Rechnungen gibt es folglich keine Vorsteuer.</p>
<h2>Rechenfehler sind keine Kleinigkeit</h2>
<p>Ist der Steuerbetrag falsch berechnet, können Sie höchstens die gesetzlich geschuldete Steuer abziehen – im Zweifel muss die Rechnung berichtigt werden. Unser Werkzeug rechnet Steuer je Satz, Summen und Zahlbetrag automatisch nach.</p>
<div class="note"><p>Diese Übersicht ersetzt keine Steuerberatung. Sie hilft, offensichtliche Mängel zu erkennen, bevor Sie buchen und bezahlen.</p></div>
{cta('../', 'Pflichtangaben jetzt prüfen')}
{faq_html(qas)}
{related('../', p)}
</article>"""
    page(p, t, d, body, schema=[article_schema(p, t, d), faq_schema(qas)])


def build_betrug():
    p = "rechnungsbetrug-iban/"
    t = "Rechnungsbetrug: Geänderte IBAN auf der Rechnung erkennen"
    d = "Neue Bankverbindung auf einer Lieferantenrechnung? So funktioniert die Masche, woran Sie sie erkennen und was Sie vor der Zahlung tun sollten."
    qas = [
        ("Ist eine neue IBAN immer Betrug?",
         "Nein, Firmen wechseln tatsächlich die Bank. Eine Änderung sollte aber nie allein auf Grundlage der Rechnung oder einer E-Mail übernommen werden. Bestätigen Sie sie über einen Ihnen bekannten Kontaktweg."),
        ("Schützt die E-Rechnung vor Betrug?",
         "Nicht von selbst. Auch eine formal korrekte XRechnung kann manipulierte Bankdaten enthalten, wenn das E-Mail-Postfach des Absenders kompromittiert wurde."),
        ("Was tun, wenn ich schon überwiesen habe?",
         "Sofort Ihre Bank kontaktieren und einen Rückruf der Zahlung versuchen, Anzeige bei der Polizei erstatten und den echten Lieferanten informieren."),
    ]
    body = f"""<article>
<h1>Geänderte IBAN auf der Rechnung: So erkennen Sie Rechnungsbetrug</h1>
<p class="lead">Die Rechnung sieht echt aus, Betrag und Leistung stimmen – nur das Konto ist ein anderes. Genau so funktioniert eine der verbreitetsten Betrugsmaschen gegen Unternehmen.</p>
<h2>So läuft die Masche</h2>
<p>Täter verschaffen sich Zugang zum E-Mail-Verkehr zwischen Lieferant und Kunde, fangen echte Rechnungen ab und tauschen die Bankverbindung aus. Die IHK warnt ausdrücklich vor diesem Vorgehen. Oft folgt eine plausible Begründung („Wir haben die Bank gewechselt“), manchmal sogar ein gefälschter Brief.</p>
<p>Weil Rechnungsnummer, Beträge und Ansprechpartner echt sind, fällt der Tausch beim schnellen Freigeben kaum auf.</p>
<h2>Warnzeichen</h2>
<ul>
<li>Die IBAN unterscheidet sich von früheren Rechnungen desselben Lieferanten.</li>
<li>Das Länderkürzel der IBAN passt nicht zum Sitz des Lieferanten (z. B. ein deutsches Unternehmen mit litauischem Konto).</li>
<li>Die IBAN hat eine ungültige Prüfziffer – ein Hinweis auf Tippfehler oder Manipulation.</li>
<li>Druck zur schnellen Zahlung oder ungewöhnliche Begleit-E-Mails.</li>
</ul>
<h2>Automatisch prüfen</h2>
<p><a href="../">Unser Prüfwerkzeug</a> merkt sich in Ihrem Browser zu jedem Lieferanten die bisherigen IBANs. Taucht eine neue auf, erscheint eine deutliche Warnung. Zusätzlich prüft es Prüfziffer und Länderkennung und erkennt doppelt eingereichte Rechnungsnummern. Die Rechnung selbst verlässt dabei Ihren Rechner nicht.</p>
<h2>Was Sie vor der Zahlung tun sollten</h2>
<ol>
<li>Neue Bankdaten nie ungeprüft übernehmen.</li>
<li>Beim Lieferanten über eine bekannte Telefonnummer rückfragen – nicht über Kontaktdaten aus der Rechnung oder E-Mail.</li>
<li>Bankdatenänderungen im Vier-Augen-Prinzip freigeben.</li>
<li>Eine geänderte IBAN im Lieferantenstamm erst nach Bestätigung speichern.</li>
</ol>
{cta('../', 'Rechnung auf IBAN-Wechsel prüfen')}
{faq_html(qas)}
{related('../', p)}
</article>"""
    page(p, t, d, body, schema=[article_schema(p, t, d), faq_schema(qas)])


def build_kleinunternehmer():
    p = "e-rechnung-kleinunternehmer/"
    t = "E-Rechnung für Kleinunternehmer: Empfangen ja, senden nein"
    d = "Was Kleinunternehmer nach § 19 UStG bei der E-Rechnung wirklich müssen: Empfangspflicht seit 2025, Befreiung beim Versand, Archivierung."
    qas = [
        ("Muss ich als Kleinunternehmer E-Rechnungen empfangen können?",
         "Ja. Seit dem 1. Januar 2025 müssen alle inländischen Unternehmen E-Rechnungen empfangen können, Kleinunternehmer eingeschlossen. Ein E-Mail-Postfach reicht dafür aus."),
        ("Muss ich als Kleinunternehmer E-Rechnungen schreiben?",
         "Nein. Kleinunternehmer sind von der Pflicht zur Ausstellung von E-Rechnungen befreit (§ 34a UStDV). Freiwillig dürfen sie welche ausstellen."),
        ("Brauche ich dafür eine kostenpflichtige Software?",
         "Nein. Zum Lesen und Prüfen genügt ein kostenloser Viewer. Wichtig ist, die Originaldatei unverändert aufzubewahren."),
    ]
    body = f"""<article>
<h1>E-Rechnung für Kleinunternehmer</h1>
<p class="lead">Kleinunternehmer müssen keine E-Rechnungen schreiben. Empfangen müssen sie sie trotzdem – und das betrifft fast jeden, der bei Großhändlern, Plattformen oder Dienstleistern einkauft.</p>
<h2>Was gilt</h2>
<ul>
<li><b>Empfangen:</b> Pflicht seit 1.1.2025, ohne Übergangsfrist. Ein E-Mail-Postfach genügt.</li>
<li><b>Ausstellen:</b> dauerhaft befreit nach § 34a UStDV. Papier- oder PDF-Rechnungen bleiben für Sie zulässig.</li>
<li><b>Aufbewahren:</b> Eingehende E-Rechnungen im Originalformat archivieren (XML bzw. ZUGFeRD-PDF), unveränderbar und maschinell auswertbar.</li>
</ul>
<h2>Warum Sie eingehende Rechnungen trotzdem prüfen sollten</h2>
<p>Als Kleinunternehmer haben Sie keinen Vorsteuerabzug – aber Sie bezahlen jede Rechnung. Rechenfehler, doppelt gestellte Rechnungen und manipulierte Bankverbindungen kosten Sie bares Geld. <a href="../">Das kostenlose Prüfwerkzeug</a> zeigt die Rechnung lesbar an und warnt bei genau diesen Problemen.</p>
<h2>So richten Sie den Empfang in zehn Minuten ein</h2>
<ol>
<li>Eine eigene Adresse wie <code>rechnungen@ihre-firma.de</code> anlegen oder einen Ordner im bestehenden Postfach.</li>
<li>Lieferanten diese Adresse mitteilen.</li>
<li>Eingehende XML- und ZUGFeRD-Dateien mit dem Prüfwerkzeug öffnen.</li>
<li>Originaldateien in einem Archivordner bzw. Ihrer Buchhaltungslösung ablegen.</li>
</ol>
{cta('../')}
{faq_html(qas)}
{related('../', p)}
</article>"""
    page(p, t, d, body, schema=[article_schema(p, t, d), faq_schema(qas)])


def build_kanzlei():
    p = "kanzlei/"
    t = "Pro-Lizenz: Stapelprüfung, alle Produkte, Export"
    d = "Pro-Lizenz für E-Rechnung prüfen und den Shop-Check: unbegrenzte Stapelprüfung, Sammelexport, alle Produkte – ohne Upload."
    mail = CFG.get("kontakt_email") or imp.get("email")
    contact = (f'<a class="btn" href="mailto:{html.escape(mail)}?subject=Pro-Lizenz">Lizenz anfragen</a>' if mail else "")
    body = f"""<article>
<h1>Pro-Lizenz</h1>
<p class="lead">Die Werkzeuge sind für Einzelfälle kostenlos. Wer regelmäßig viele Rechnungen oder Produkte prüft, schaltet mit einer Lizenz alle Grenzen frei.</p>
<h2>Was freigeschaltet wird</h2>
<ul>
<li><b>E-Rechnung prüfen:</b> Stapelprüfung ohne Begrenzung (kostenlos: 3 Dateien je Durchgang) und Sammelexport als CSV – Lieferant, Nummer, Datum, Netto, USt, Brutto, IBAN, Status.</li>
<li><b>Shop-Check:</b> alle Produkte statt der ersten 25 und Export der Produktliste mit berechneten Grundpreisen und Prüfergebnis.</li>
<li><b>SEPA für Vereine:</b> beliebig viele Mitglieder statt 25.</li>
</ul>
<h2>Preise</h2>
<div class="tbl"><table><thead><tr><th>Lizenz</th><th>Für</th><th class="n">pro Jahr</th></tr></thead><tbody>
<tr><td>Pro</td><td>Online-Shops, Selbstständige, Vereine</td><td class="n">49 €</td></tr>
<tr><td>Kanzlei</td><td>Buchhaltungsbüros, Steuerkanzleien (je Standort)</td><td class="n">{html.escape(CFG.get('kanzlei_preis_jahr', ''))}</td></tr>
</tbody></table></div>
<p class="muted">Preise zzgl. gesetzlicher Umsatzsteuer, falls anfallend. Pilotkunden testen drei Monate kostenlos gegen ehrliches Feedback.</p>
<h2>Datenschutz</h2>
<p>Alle Prüfungen laufen im Browser. Rechnungen, Kontoauszüge und Produktdaten werden nicht an uns übertragen.</p>
{contact}
</article>"""
    page(p, t, d, body, schema=[article_schema(p, t, d)])


def build_kug():
    p = "kleinunternehmergrenze/"
    t = "Kleinunternehmergrenze 2026 prüfen – Rechner mit Kontoauszug (AT & DE)"
    d = ("Kleinunternehmergrenze überschritten? Kontoauszug als CSV laden und sehen, wann 55.000 € (Österreich) bzw. "
         "25.000/100.000 € (Deutschland) erreicht werden. Kostenlos, ohne Upload.")
    qas = [
        ("Wie hoch ist die Kleinunternehmergrenze in Österreich?",
         "Seit 2025 liegt sie bei 55.000 Euro Bruttoumsatz im Jahr. Wird sie um höchstens 10 % überschritten (bis 60.500 Euro), "
         "bleibt die Befreiung bis Jahresende bestehen und endet mit dem Folgejahr. Bei mehr als 10 % endet sie sofort mit dem Umsatz, "
         "der die Toleranzgrenze überschreitet."),
        ("Wie hoch ist die Kleinunternehmergrenze in Deutschland?",
         "Seit 2025 gilt: Der Umsatz im Vorjahr darf 25.000 Euro und im laufenden Jahr 100.000 Euro nicht übersteigen (jeweils netto). "
         "Wer im laufenden Jahr 100.000 Euro überschreitet, ist ab diesem Umsatz sofort regelbesteuert. Im Gründungsjahr gilt die "
         "Grenze von 25.000 Euro."),
        ("Zählt jede Überweisung auf meinem Konto als Umsatz?",
         "Nein. Umbuchungen zwischen eigenen Konten, Steuererstattungen, Darlehen, Rückerstattungen oder Gehalt sind kein Umsatz. Der "
         "Rechner erkennt typische Fälle und Sie können jeden Eingang selbst an- oder abwählen."),
        ("Was ist mit PayPal-, Etsy- oder Amazon-Auszahlungen?",
         "Plattformen zahlen meist den Betrag nach Abzug ihrer Gebühren aus. Für die Grenze zählt aber der Umsatz vor Gebühren. "
         "Nehmen Sie dafür die Summe aus dem Plattform-Bericht."),
        ("Werden meine Kontodaten hochgeladen?",
         "Nein. Die Berechnung läuft in Ihrem Browser. Der Kontoauszug verlässt Ihr Gerät nicht."),
    ]
    body = f"""
<h1>Kleinunternehmergrenze prüfen</h1>
<p class="lead">Laden Sie Ihren Kontoauszug als CSV. Der Rechner zählt Ihre Einnahmen Tag für Tag zusammen, zeigt, wie viel Spielraum bleibt, und wann Sie im aktuellen Tempo die Grenze erreichen.</p>
<form id="kug" class="sheet" style="display:grid;gap:.9rem">
  <fieldset style="border:0;padding:0;margin:0;display:flex;gap:1.2rem;flex-wrap:wrap"><legend class="muted" style="padding:0">Steuerland</legend>
    <label><input type="radio" name="country" value="AT"> Österreich (55.000 € brutto)</label>
    <label><input type="radio" name="country" value="DE"> Deutschland (25.000/100.000 € netto)</label></fieldset>
  <label>Jahr <select name="year" style="font:inherit;padding:.3rem"></select></label>
  <div>
    <label class="btn" style="margin:0">Kontoauszug (CSV) wählen<input id="kug-file" type="file" accept=".csv,.txt,text/csv" multiple hidden></label>
    <button class="btn ghost" type="button" id="kug-reset" hidden style="margin:0 0 0 .4rem">Kontodaten entfernen</button>
    <p class="muted" style="margin:.4rem 0 0">Funktioniert mit den CSV-Exporten der meisten Banken (z. B. George, Raiffeisen, Bank Austria, Sparkasse, ING, N26). Mehrere Konten nacheinander laden.</p>
  </div>
  <label>Ihr Name (optional, damit Überweisungen an sich selbst nicht als Umsatz zählen)<br><input name="ownname" autocomplete="name" style="width:100%;font:inherit;padding:.5rem;border:1.5px solid var(--ink-soft);border-radius:4px;background:var(--sheet);color:var(--ink)"></label>
  <label>Weitere Umsätze in diesem Jahr, z. B. bar oder auf anderen Konten (€)<br><input name="extra" inputmode="decimal" placeholder="0" style="width:12rem;font:inherit;padding:.5rem;border:1.5px solid var(--ink-soft);border-radius:4px;background:var(--sheet);color:var(--ink)"></label>
  <label>Umsatz im Vorjahr (€, falls nicht im Kontoauszug)<br><input name="prior" inputmode="decimal" placeholder="leer = aus Kontoauszug" style="width:12rem;font:inherit;padding:.5rem;border:1.5px solid var(--ink-soft);border-radius:4px;background:var(--sheet);color:var(--ink)"></label>
  <label id="kug-founding-wrap"><input type="checkbox" name="founding"> Dieses Jahr ist mein Gründungsjahr</label>
  <label><input type="checkbox" name="vat"> Ich habe bereits Rechnungen mit Umsatzsteuer gestellt</label>
  <div><button class="btn" type="submit" style="margin:0">Berechnen</button></div>
  <p id="kug-status" class="muted" role="status" style="margin:0"></p>
</form>
<div id="kug-out"></div>
<div class="intro-content">
<h2>Die Grenzen auf einen Blick</h2>
<div class="tbl"><table><thead><tr><th></th><th>Österreich</th><th>Deutschland</th></tr></thead><tbody>
<tr><td>Grenze</td><td>55.000 € brutto im Jahr</td><td>Vorjahr 25.000 €, laufendes Jahr 100.000 € (netto)</td></tr>
<tr><td>Toleranz</td><td>bis 10 % (60.500 €): Befreiung bis Jahresende</td><td>keine</td></tr>
<tr><td>Sofortige Steuerpflicht</td><td>ab dem Umsatz über 60.500 €</td><td>ab dem Umsatz über 100.000 € (Gründungsjahr: über 25.000 €)</td></tr>
<tr><td>Folgejahr</td><td>Regelbesteuerung, wenn 55.000 € überschritten</td><td>Regelbesteuerung, wenn 25.000 € überschritten</td></tr>
<tr><td>Rechtsgrundlage</td><td>§ 6 Abs. 1 Z 27 UStG 1994</td><td>§ 19 UStG</td></tr>
</tbody></table></div>
<h2>Warum das Datum so wichtig ist</h2>
<p>Seit 2025 kann die Befreiung in beiden Ländern <b>mitten im Jahr</b> enden. Ab dem Umsatz, der die Grenze überschreitet, müssen Sie Umsatzsteuer in Rechnung stellen. Wer das zu spät merkt, schuldet die Steuer trotzdem – oft aus eigener Tasche, weil die Kunden bereits bezahlt haben. Deshalb zeigt der Rechner nicht nur eine Summe, sondern den Tag, an dem die Grenze fällt, und eine Hochrechnung bis Jahresende.</p>
<h2>Was nicht zum Umsatz zählt</h2>
<ul><li>Umbuchungen zwischen Ihren eigenen Konten</li><li>Steuererstattungen und Sozialleistungen</li><li>Darlehen, Privateinlagen, Geschenke</li><li>Rückerstattungen und Stornos</li><li>Gehalt aus einer Anstellung</li>
<li>In Österreich außerdem Hilfsgeschäfte wie der Verkauf von Betriebsvermögen; in Deutschland der Verkauf von Wirtschaftsgütern des Anlagevermögens</li></ul>
<div class="note"><p>Der Rechner ist eine Hilfe zur Selbstkontrolle, keine Steuerberatung. Bei Grenzfällen – etwa Umsätzen aus mehreren Tätigkeiten oder grenzüberschreitenden Leistungen – lohnt sich eine Rückfrage bei Ihrer Steuerberatung.</p></div>
{faq_html(qas)}
<h2>Weiterlesen</h2><ul class="related"><li><a href="../e-rechnung-kleinunternehmer/">E-Rechnung für Kleinunternehmer</a></li><li><a href="../">E-Rechnung prüfen</a></li></ul>
</div>"""
    schema = [{"@context": "https://schema.org", "@type": "WebApplication", "name": "Kleinunternehmer-Grenzrechner",
               "url": SITE + p, "applicationCategory": "FinanceApplication", "operatingSystem": "Browser", "inLanguage": "de",
               "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}}, faq_schema(qas)]
    page(p, t, d, body, schema=schema, tool="kug.js")


def build_shop():
    p = "grundpreis-gpsr-check/"
    t = "Grundpreis & GPSR prüfen: Produktdaten-Check für Online-Shops"
    d = ("Shopify-, WooCommerce- oder Etsy-Export hochladen: fehlende oder falsche Grundpreise (PAngV) und fehlende "
         "Herstellerangaben nach GPSR finden – bevor die Abmahnung kommt. Kostenlos, ohne Upload.")
    qas = [
        ("Wann brauche ich einen Grundpreis?",
         "Wenn Sie Verbrauchern Ware nach Gewicht, Volumen, Länge oder Fläche anbieten – also z. B. 500 g Honig, 0,75 l Öl oder "
         "10 m Band. Der Grundpreis muss sich seit Mai 2022 auf 1 kg, 1 l, 1 m, 1 m² oder 1 m³ beziehen."),
        ("Darf ich den Grundpreis noch pro 100 g angeben?",
         "Für Fertigpackungen nicht mehr. Die frühere Ausnahme für Waren bis 250 g ist mit der Neufassung der Preisangabenverordnung "
         "zum 28.05.2022 entfallen."),
        ("Welche Herstellerangaben verlangt die GPSR im Online-Shop?",
         "Name bzw. Marke, Postanschrift und eine elektronische Adresse des Herstellers. Sitzt der Hersteller außerhalb der EU, "
         "zusätzlich Name und Anschrift der verantwortlichen Person in der EU. Dazu kommen Produktbild, Angaben zur Identifizierung "
         "und Warn- bzw. Sicherheitshinweise."),
        ("Wie bekomme ich die CSV-Datei aus meinem Shop?",
         "Shopify: Produkte → Exportieren → CSV für Excel. WooCommerce: Produkte → Exportieren. Etsy: Shop-Manager → Einstellungen → "
         "Optionen → Daten herunterladen. Andere Shops: jeder Produkt-Export mit Name und Preis funktioniert."),
        ("Werden meine Produktdaten hochgeladen?",
         "Nein. Die Prüfung läuft vollständig in Ihrem Browser."),
    ]
    body = f"""
<h1>Grundpreis & GPSR: Produktdaten prüfen</h1>
<p class="lead">Fehlende Grundpreise und fehlende Herstellerangaben gehören zu den häufigsten Abmahngründen im Online-Handel. Laden Sie Ihren Produkt-Export und sehen Sie in Sekunden, welche Artikel betroffen sind – mit dem richtigen Grundpreis gleich dazu.</p>
<div id="shop-drop" class="drop" role="button" tabindex="0" aria-describedby="shop-hint">
  <strong>Produkt-Export (CSV) hier ablegen</strong>
  <span id="shop-hint">Shopify, WooCommerce, Etsy oder jeder andere Export mit Name und Preis</span>
  <input id="shop-file" type="file" accept=".csv,.txt,text/csv">
</div>
<ul class="trust"><li>Daten bleiben auf Ihrem Gerät</li><li>{25} Produkte kostenlos</li><li>Grundpreis wird gleich berechnet</li></ul>
<p id="shop-status" role="status" class="muted"></p>
<div id="shop-out"></div>
<div class="intro-content">
<h2>Was geprüft wird</h2>
<h3>Grundpreis nach § 4 PAngV</h3>
<ul>
<li>Füllmenge wird aus Titel, Variante oder Angaben wie „Inhalt: 250 ml“ erkannt – auch Mehrfachpackungen wie „3 x 50 g“.</li>
<li>Fehlt der Grundpreis, berechnet das Werkzeug ihn: 9,90 € für 500 g → 19,80 € / 1 kg.</li>
<li>Vorhandene Grundpreise werden nachgerechnet; Angaben pro 100 g oder 100 ml werden als unzulässig markiert.</li>
<li>Bei Shopify wird die eingebaute Grundpreis-Einstellung (Einheitspreis) mitgeprüft.</li>
<li>Ausnahmen: unter 10 g/ml und Füllmenge genau 1 kg/l. Maße wie „30 x 40 cm“ bei Postern werden nicht als Verkaufsmenge gewertet.</li>
</ul>
<h3>Herstellerangaben nach Art. 19 GPSR</h3>
<ul>
<li>Hersteller bzw. Marke vorhanden?</li>
<li>Postanschrift und E-Mail oder Website des Herstellers in den Produktdaten?</li>
<li>Hinweise auf einen Hersteller außerhalb der EU ohne verantwortliche Person in der EU?</li>
<li>Produktbild vorhanden? Bei Spielzeug, Elektrogeräten, Kerzen, Kosmetik u. Ä.: Sicherheitshinweise in der Beschreibung?</li>
</ul>
<div class="note"><p>Viele Shops zeigen Herstellerangaben über Metafelder oder Theme-Blöcke an, die nicht im Export stehen. Dann erscheint „Angaben nicht gefunden“, obwohl Ihr Shop korrekt ist – prüfen Sie in diesem Fall stichprobenartig die Produktseite.</p></div>
<h2>Was kostet eine Abmahnung?</h2>
<p>Abmahnungen von Mitbewerbern sind mit Anwaltskosten und einer strafbewehrten Unterlassungserklärung verbunden; bei einem zweiten Verstoß wird die vereinbarte Vertragsstrafe fällig. Fehlende Grundpreise und Herstellerangaben lassen sich automatisiert finden – deshalb sind sie beliebte Ziele.</p>
{faq_html(qas)}
{related('../', p)}
</div>"""
    schema = [{"@context": "https://schema.org", "@type": "WebApplication", "name": "Grundpreis- & GPSR-Check",
               "url": SITE + p, "applicationCategory": "BusinessApplication", "operatingSystem": "Browser", "inLanguage": "de",
               "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}}, faq_schema(qas)]
    page(p, t, d, body, schema=schema, tool="shop.js")


def build_sepa():
    p = "sepa-lastschrift-verein/"
    t = "SEPA-Lastschrift für Vereine: XML-Datei aus Excel erstellen (pain.008, 2026)"
    d = ("Mitgliedsbeiträge per SEPA-Lastschrift einziehen: Excel- oder CSV-Mitgliederliste laden, Fehler finden, "
         "Bankdatei im neuen Format pain.008.001.08 erstellen. Kostenlos, ohne Upload.")
    inp = 'style="width:100%;font:inherit;padding:.5rem;border:1.5px solid var(--ink-soft);border-radius:4px;background:var(--sheet);color:var(--ink)"'
    qas = [
        ("Was ändert sich 2026 bei SEPA-Lastschriftdateien?",
         "Banken stellen auf die ISO-20022-Version 2019 um. In Deutschland akzeptieren viele Banken für Lastschriften ab November 2026 "
         "nur noch pain.008.001.08; das ältere pain.008.001.02 wird dann nicht mehr oder nur nach Vereinbarung angenommen. In Österreich "
         "gelten bankindividuelle Termine – fragen Sie Ihre Bank. "
         "Adressen müssen, wenn angegeben, strukturiert oder hybrid sein – mindestens mit Ort und Land."),
        ("Was brauche ich, um Mitgliedsbeiträge per Lastschrift einzuziehen?",
         "Eine Gläubiger-Identifikationsnummer (in Österreich bei der Oesterreichischen Nationalbank, in Deutschland bei der "
         "Bundesbank), ein unterschriebenes SEPA-Mandat jedes Mitglieds mit Mandatsreferenz und Datum, eine Inkassovereinbarung "
         "mit Ihrer Bank und ein Online-Banking mit Datei-Upload."),
        ("Muss ich die Mitglieder vorher informieren?",
         "Ja, mit einer Vorabankündigung (Pre-Notification) grundsätzlich 14 Kalendertage vor dem Einzug, sofern keine kürzere Frist "
         "vereinbart ist. Der Generator erstellt die Texte dafür gleich mit."),
        ("Brauche ich den BIC?",
         "Für Konten im Europäischen Wirtschaftsraum nicht – die IBAN genügt. Bei Konten etwa in der Schweiz oder in Großbritannien "
         "sollten BIC und die Adresse des Zahlers angegeben werden."),
        ("Werden die Mitgliederdaten hochgeladen?",
         "Nein. Die Datei wird in Ihrem Browser erzeugt. Namen und IBANs verlassen Ihr Gerät nicht."),
    ]
    body = f"""
<h1>SEPA-Lastschrift für Vereine</h1>
<p class="lead">Mitgliederliste aus Excel laden, Fehler sehen, Bankdatei herunterladen – im neuen Format <b>pain.008.001.08</b> (ISO 20022, Version 2019), auf das die Banken umstellen – in Deutschland vielfach mit Stichtag November 2026.</p>
<form id="sepa" class="sheet" style="display:grid;gap:.9rem;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr))">
  <label>Name des Vereins<br><input name="name" required autocomplete="organization" {inp}></label>
  <label>IBAN des Vereinskontos<br><input name="iban" required {inp}></label>
  <label>Gläubiger-ID<br><input name="ci" required placeholder="z. B. AT12ZZZ00000000001" {inp}></label>
  <label>BIC (optional)<br><input name="bic" {inp}></label>
  <label>Ort des Vereins (optional)<br><input name="town" {inp}></label>
  <label>Land (optional, z. B. AT)<br><input name="country" maxlength="2" {inp}></label>
  <label>Einzugsdatum<br><input name="date" type="date" required {inp}></label>
  <label>Betrag, falls nicht in der Liste (€)<br><input name="amount" inputmode="decimal" {inp}></label>
  <label style="grid-column:1/-1">Verwendungszweck<br><input name="purpose" placeholder="Mitgliedsbeitrag 2027" {inp}></label>
  <div style="grid-column:1/-1">
    <label class="btn" style="margin:0">Mitgliederliste wählen (Excel oder CSV)<input id="sepa-file" type="file" accept=".xlsx,.xlsm,.csv,.txt" hidden></label>
    <span id="sepa-fname" class="muted" style="margin-left:.5rem"></span>
    <p class="muted" style="margin:.4rem 0 0">Benötigte Spalten: Name (oder Vorname/Nachname), IBAN, Betrag, Mandatsreferenz, Mandatsdatum. Optional: BIC, Straße, PLZ, Ort, Land, E-Mail. <button type="button" id="sepa-template" class="btn ghost" style="margin:0 0 0 .3rem;padding:.2rem .6rem">Vorlage herunterladen</button></p>
  </div>
  <div style="grid-column:1/-1"><button class="btn" type="submit" style="margin:0">Prüfen und Datei erstellen</button>
  <p id="sepa-status" class="muted" role="status" style="margin:.4rem 0 0"></p></div>
</form>
<div id="sepa-out"></div>
<div class="intro-content">
<h2>Was geprüft wird</h2>
<ul>
<li>IBAN-Prüfziffer jedes Mitglieds und des Vereinskontos, Format des BIC</li>
<li>Gläubiger-ID samt Prüfziffer</li>
<li>Mandatsreferenz vorhanden, eindeutig, höchstens 35 zulässige Zeichen; Mandatsdatum nicht in der Zukunft; Hinweis bei Mandaten älter als 36 Monate</li>
<li>Einzugsdatum ist ein Bankarbeitstag (TARGET-Kalender) und nicht zu kurzfristig; Erinnerung an die 14-tägige Vorabankündigung</li>
<li>Konten außerhalb des EWR (z. B. Schweiz): Adresse des Zahlers vorhanden</li>
<li>Umlaute und Sonderzeichen werden in den SEPA-Zeichensatz übertragen (ü → ue, ß → ss)</li>
</ul>
<p>Fehlerhafte Zeilen werden nicht in die Datei übernommen, sondern aufgelistet – so lehnt die Bank nicht die ganze Datei ab.</p>
<h2>So geht es danach weiter</h2>
<ol>
<li>Vorabankündigungen versenden (Texte als CSV, z. B. für den Serienbrief).</li>
<li>Die XML-Datei im Business-Online-Banking hochladen und Anzahl sowie Summe vor der Freigabe vergleichen.</li>
<li>Rücklastschriften der folgenden Tage abgleichen und die Liste aktualisieren.</li>
</ol>
<div class="note"><p>Der Generator ersetzt nicht die Vereinbarung mit Ihrer Bank. Fragen Sie dort nach, ob pain.008.001.08 bereits angenommen wird und welche Vorlaufzeit gilt.</p></div>
{faq_html(qas)}
{related('../', p)}
</div>"""
    schema = [{"@context": "https://schema.org", "@type": "WebApplication", "name": "SEPA-Lastschrift-Generator für Vereine",
               "url": SITE + p, "applicationCategory": "FinanceApplication", "operatingSystem": "Browser", "inLanguage": "de",
               "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}}, faq_schema(qas)]
    page(p, t, d, body, schema=schema, tool="sepa.js")


def build_legal():
    if IMPRESSUM_OK:
        lines = [imp["name"], imp["strasse"], imp["plz_ort"], imp.get("land", "")]
        extra = "".join(f"<p>{lbl}: {html.escape(imp[k])}</p>" for k, lbl in (
            ("uid", "UID-Nummer"), ("gewerbe", "Gewerbe"), ("behoerde", "Gewerbebehörde")) if imp.get(k))
        body = (f"<h1>Impressum</h1><p>Angaben gemäß § 5 ECG und § 25 MedienG (Österreich) bzw. § 5 DDG (Deutschland)</p>"
                f"<p>{'<br>'.join(html.escape(x) for x in lines if x)}</p><p>E-Mail: {html.escape(imp['email'])}</p>{extra}"
                "<p>Verbraucherstreitbeilegung: Wir sind nicht verpflichtet und nicht bereit, an Streitbeilegungsverfahren vor einer "
                "Verbraucherschlichtungsstelle teilzunehmen.</p>")
    else:
        body = ("<h1>Impressum</h1><p><b>Platzhalter:</b> Bitte in <code>site/config.json</code> unter „impressum“ Name, Anschrift "
                "und E-Mail eintragen. Ohne Impressum darf die Seite nicht veröffentlicht werden.</p>")
    page("impressum/", "Impressum", "Impressum", body, noindex=True)
    who = html.escape(f"{imp['name']}, {imp['strasse']}, {imp['plz_ort']}, {imp['email']}") if IMPRESSUM_OK else "[Name, Anschrift, E-Mail]"
    ana = ("<h2>Reichweitenmessung</h2><p>Wir nutzen Plausible Analytics, eine cookielose Statistik ohne personenbezogene Profile. "
           "Erfasst werden u. a. aufgerufene Seite, Herkunftsseite, Browsertyp und Land, ohne Speicherung der IP-Adresse.</p>"
           if CFG.get("plausible_domain") else "")
    body = f"""<h1>Datenschutzerklärung</h1>
<h2>Verantwortlicher</h2><p>{who}</p>
<h2>Ihre Rechnungsdateien</h2><p>Hochgeladene Rechnungen werden <b>ausschließlich lokal in Ihrem Browser</b> verarbeitet. Sie werden nicht an unsere oder fremde Server übertragen. Der Prüfverlauf (Lieferant, Rechnungsnummer, Betrag, IBAN, Prüfzeitpunkt) wird im lokalen Speicher Ihres Browsers abgelegt und kann jederzeit über „Verlauf löschen“ entfernt werden.</p>
<h2>Hosting</h2><p>Die Website wird über GitHub Pages (GitHub Inc., USA) ausgeliefert. Beim Aufruf verarbeitet der Anbieter technisch notwendige Verbindungsdaten wie IP-Adresse und Zeitpunkt (Art. 6 Abs. 1 lit. f DSGVO). GitHub ist unter dem EU-US Data Privacy Framework zertifiziert.</p>
<h2>Eingebundene Dienste</h2><p>Schriftarten werden von Google Fonts, das Prüfprogramm (Pyodide) von jsDelivr geladen. Dabei wird Ihre IP-Adresse an diese Anbieter übermittelt. Rechnungsinhalte werden nicht übertragen.</p>
{ana}
<h2>Ihre Rechte</h2><p>Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit und Widerspruch sowie auf Beschwerde bei einer Aufsichtsbehörde (in Österreich: Datenschutzbehörde, dsb.gv.at).</p>"""
    page("datenschutz/", "Datenschutzerklärung", "Datenschutz", body, noindex=True)


# ---------------------------------------------------------------- Ablauf

def main():
    global PYPDF_WHEEL, SITEMAP, EXCEL_WHEELS
    SITEMAP = []
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "static" / "py").mkdir(parents=True)
    for f in ("style.css", "app.js", "kug.js", "shop.js", "sepa.js"):
        shutil.copy(HERE / "static" / f, DIST / "static" / f)
    (DIST / "static" / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26" style="color:#1D2B4F"><style>:root{--paper:#fff}</style>'
        + LOGO.split(">", 1)[1])
    wheels = sorted((HERE / "static" / "py").glob("pypdf-*.whl"))
    PYPDF_WHEEL = wheels[-1].name
    shutil.copy(wheels[-1], DIST / "static" / "py" / PYPDF_WHEEL)
    EXCEL_WHEELS = []
    for pat in ("et_xmlfile-*.whl", "openpyxl-*.whl"):
        w = sorted((HERE / "static" / "py").glob(pat))[-1]
        shutil.copy(w, DIST / "static" / "py" / w.name)
        EXCEL_WHEELS.append(w.name)
    with zipfile.ZipFile(DIST / "static" / "py" / "erechnung.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for py in sorted((ROOT / "erechnung").glob("*.py")):
            if py.name in ("store.py", "license.py"):
                continue  # serverseitig, im Browser nicht nötig
            z.write(py, f"erechnung/{py.name}")
    for pkg in ("kugrenze", "shopcheck", "sepalast"):
        with zipfile.ZipFile(DIST / "static" / "py" / f"{pkg}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for py in sorted((ROOT / pkg).glob("*.py")):
                z.write(py, f"{pkg}/{py.name}")
    if LOCAL:
        shutil.copytree(HERE.parent / "pyodide-local", DIST / "pyodide-local")
    build_home(); build_xrechnung(); build_zugferd(); build_vorsteuer(); build_betrug()
    build_kleinunternehmer(); build_kanzlei(); build_kug(); build_shop(); build_sepa(); build_legal()
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in SITEMAP) + "</urlset>\n")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}sitemap.xml\n")
    (DIST / ".nojekyll").write_text("")
    (DIST / "404.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=./">'
                                   '<title>Seite nicht gefunden</title><a href="./">Zur Startseite</a>')
    print(f"Gebaut: {len(SITEMAP)} indexierbare Seiten -> {DIST}")
    if not IMPRESSUM_OK:
        print("WARNUNG: Impressum unvollständig – vor Veröffentlichung site/config.json ausfüllen!")
        if "--release" in sys.argv:
            sys.exit("ABBRUCH: Ohne vollständiges Impressum wird nicht veröffentlicht.")
    if "IHR-GITHUB-NAME" in SITE:
        print("WARNUNG: site_url in config.json ist noch ein Platzhalter.")


if __name__ == "__main__":
    main()
