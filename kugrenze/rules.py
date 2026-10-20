"""Grenzen der Kleinunternehmerregelung und Auswertung.

Rechtsstand (zuletzt geprüft 10/2026):
AT – § 6 Abs. 1 Z 27 UStG 1994 idF Progressionsabgeltungsgesetz 2025:
     55.000 € BRUTTO (Gesamtumsatz); Überschreitung um höchstens 10 % (bis 60.500 €) -> Befreiung
     bleibt bis Jahresende, ab Folgejahr Regelbesteuerung; Überschreitung um mehr als 10 % ->
     Steuerpflicht ab dem Umsatz, mit dem die Toleranzgrenze überschritten wird.
     Wurde im Vorjahr 55.000 € überschritten, ist die Befreiung im laufenden Jahr nicht anwendbar.
DE – § 19 UStG idF Jahressteuergesetz 2024 (ab 1.1.2025):
     Vorjahr ≤ 25.000 € und laufendes Jahr ≤ 100.000 € (NETTO). Überschreiten der 100.000 € ->
     Regelbesteuerung ab dem Umsatz, mit dem die Grenze überschritten wird. Gründungsjahr:
     Grenze 25.000 €, Überschreiten -> Regelbesteuerung ab diesem Umsatz. Überschreiten der
     25.000 € in einem normalen Jahr -> im Folgejahr keine Kleinunternehmerregelung.
Kleinunternehmer stellen keine USt in Rechnung; Zahlungseingänge entsprechen daher dem Entgelt
(brutto = netto). Das gilt NICHT, wenn bereits Rechnungen mit USt gestellt wurden.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from .bankcsv import Transaction

D = Decimal
RULES = {
    "AT": {"name": "Österreich", "limit": D(55000), "tolerance": D(60500), "basis": "brutto",
           "law": "§ 6 Abs. 1 Z 27 UStG 1994 (Stand 2025/2026)"},
    "DE": {"name": "Deutschland", "limit": D(100000), "prior": D(25000), "founding": D(25000), "basis": "netto",
           "law": "§ 19 UStG (Stand ab 2025)"},
}

# Eingänge, die typischerweise KEIN Umsatz sind. Der Nutzer kann jede Entscheidung umstellen.
EXCLUDE_PATTERNS = [
    (r"\b(umbuchung|übertrag|uebertrag|eigenübertrag|eigenes konto|kontoübertrag|sparen|sparkonto|tagesgeld)\b", "Umbuchung zwischen eigenen Konten"),
    (r"\b(finanzamt|steuerrückzahlung|steuererstattung|arbeitnehmerveranlagung|einkommensteuer|bundeskasse)\b", "Steuererstattung"),
    (r"\b(svs|ögk|oegk|krankenkasse|sozialversicherung|aok|barmer|techniker krankenkasse)\b", "Sozialversicherung/Krankenkasse"),
    (r"\b(rückerstattung|rueckerstattung|erstattung|refund|storno|rücklastschrift|ruecklastschrift|retoure|gutschrift retour|chargeback)\b", "Rückerstattung/Storno"),
    (r"\b(darlehen|kredit|privateinlage|einlage|geschenk|taschengeld)\b", "Darlehen/Privateinlage"),
    (r"\b(zinsen|habenzinsen|zinsgutschrift|dividende|ertrag fonds|kupon)\b", "Zinsen/Kapitalerträge"),
    (r"\b(gehalt|lohn|bezüge|bezuege|pension|rente|gehaltszahlung)\b", "Gehalt/Pension (nicht selbständig)"),
    (r"\b(familienbeihilfe|kindergeld|kinderbetreuungsgeld|elterngeld|ams|arbeitsamt|arbeitslosengeld|wohnbeihilfe|bafög|stipendium)\b", "Sozialleistung"),
]
PLATFORM_PATTERN = r"\b(paypal|stripe|etsy|amazon|ebay|shopify|sumup|klarna|mollie|digistore|gumroad|lemon ?squeezy|airbnb|booking\.com|uber|wolt|lieferando|vinted|willhaben)\b"


def classify(tx: list[Transaction], own_names: list[str] | None = None) -> None:
    own = [n.strip().lower() for n in (own_names or []) if len(n.strip()) >= 3]
    for t in tx:
        hay = f"{t.counterparty} {t.text}".lower()
        t.tags = []
        if t.amount <= 0:
            t.include, t.reason = False, "Ausgang"
            continue
        t.include, t.reason = True, "Zahlungseingang"
        if own and any(n in hay for n in own):
            t.include, t.reason = False, "Überweisung von Ihnen selbst"
            continue
        for pat, why in EXCLUDE_PATTERNS:
            if re.search(pat, hay):
                t.include, t.reason = False, why
                break
        if t.include and re.search(PLATFORM_PATTERN, hay):
            t.tags.append("plattform")
            t.reason = "Plattform-Auszahlung – Umsatz ist der Betrag VOR Gebühren"


def _year_end(y: int) -> date:
    return date(y, 12, 31)


def _crossing(items: list[tuple[date, Decimal]], start: Decimal, limit: Decimal) -> Optional[tuple[date, Decimal]]:
    """Erster Eingang, mit dem die kumulierte Summe die Grenze ÜBERschreitet."""
    cum = start
    for d, a in items:
        cum += a
        if cum > limit:
            return d, cum
    return None


def _forecast(cum: Decimal, as_of: date, year: int, limit: Decimal) -> tuple[Decimal, Optional[date]]:
    start = date(year, 1, 1)
    days = (as_of - start).days + 1
    total = 366 if calendar.isleap(year) else 365
    if days <= 7 or cum <= 0:  # zu wenig Daten für eine seriöse Hochrechnung
        return cum, None
    rate = cum / D(days)
    proj = (rate * total).quantize(D("1"))
    hit = None
    if cum <= limit and proj > limit:
        hit = start + timedelta(days=int((limit / rate).to_integral_value()) )
    return proj, hit


def evaluate(tx: list[Transaction], country: str, year: int, *, prior_year_turnover: Optional[Decimal] = None,
             founding_year: bool = False, extra_turnover: Decimal = D(0), as_of: Optional[date] = None,
             charged_vat: bool = False) -> dict:
    r = RULES[country]
    items = sorted([(t.day, t.amount) for t in tx if t.include and t.day.year == year])
    prior_items = [t.amount for t in tx if t.include and t.day.year == year - 1]
    cum = sum((a for _, a in items), D(0)) + extra_turnover
    last = max((d for d, _ in items), default=None)
    if as_of is None:
        later = any(t.day.year > year for t in tx)
        as_of = _year_end(year) if later else (last or date(year, 1, 1))
    if prior_year_turnover is None and prior_items:
        covered = {t.day.month for t in tx if t.day.year == year - 1}
        if len(covered) >= 12:
            prior_year_turnover = sum(prior_items, D(0))
    monthly = [D(0)] * 12
    for d, a in items:
        monthly[d.month - 1] += a
    if extra_turnover:
        monthly[0] += extra_turnover

    res = {"country": country, "country_name": r["name"], "year": year, "law": r["law"], "basis": r["basis"],
           "turnover": cum, "as_of": as_of, "monthly": monthly, "prior_year_turnover": prior_year_turnover,
           "count": len(items), "notes": []}
    notes = res["notes"]
    if charged_vat:
        notes.append("Sie haben angegeben, bereits Rechnungen MIT Umsatzsteuer gestellt zu haben. Dann sind Zahlungseingänge "
                     "Bruttobeträge; in Deutschland zählt der Nettobetrag – Ergebnis entsprechend vorsichtig lesen.")
    if any("plattform" in t.tags for t in tx if t.include and t.day.year == year):
        notes.append("Es gibt Auszahlungen von Plattformen (PayPal, Etsy, Amazon …). Diese sind meist um Gebühren gekürzt. "
                     "Maßgeblich ist der Umsatz vor Gebühren – nehmen Sie die Summe aus dem Plattform-Bericht und tragen Sie die "
                     "Differenz als zusätzlichen Umsatz ein.")
    notes.append("Gezählt werden nur Zahlungseingänge auf diesem Konto. Barumsätze und andere Konten bitte als zusätzlichen Umsatz eintragen.")

    if country == "AT":
        limit, tol = r["limit"], r["tolerance"]
        res.update(limit=limit, tolerance=tol)
        proj, hit = _forecast(cum, as_of, year, limit) if items else (cum, None)
        res.update(forecast=proj, forecast_hit=hit)
        if prior_year_turnover is not None and prior_year_turnover > limit:
            res.update(status="rot", headline=f"Im Jahr {year} gilt die Kleinunternehmerbefreiung nicht.",
                       detail=f"Der Umsatz im Vorjahr ({_m(prior_year_turnover)} €) lag über {_m(limit)} €. "
                              "Sie müssen Umsatzsteuer in Rechnung stellen und abführen.")
            return res
        cross_tol = _crossing(items, extra_turnover, tol)
        if cross_tol:
            res.update(status="rot", crossed_on=cross_tol[0],
                       headline=f"Toleranzgrenze am {_d(cross_tol[0])} überschritten.",
                       detail=f"Mit dem Eingang vom {_d(cross_tol[0])} (Summe {_m(cross_tol[1])} €) ist die Toleranzgrenze von "
                              f"{_m(tol)} € überschritten. Ab diesem Umsatz ist Umsatzsteuer zu verrechnen. Rechnungen ab dann "
                              "müssen USt ausweisen – bestehende ggf. berichtigen. Steuerberatung einschalten.")
        elif cum > limit:
            cross = _crossing(items, extra_turnover, limit)
            res.update(status="gelb", crossed_on=cross[0] if cross else None,
                       headline=f"55.000 € überschritten – Befreiung gilt noch bis 31.12.{year}.",
                       detail=f"Sie liegen bei {_m(cum)} €, also innerhalb der 10-%-Toleranz (bis {_m(tol)} €). "
                              f"Ab 1.1.{year + 1} gilt die Regelbesteuerung. Weitere {_m(tol - cum)} € Umsatz in {year} "
                              "würden die sofortige Steuerpflicht auslösen.")
        else:
            res.update(status="gruen", headline=f"Noch {_m(limit - cum)} € bis zur Grenze.",
                       detail=f"Bisheriger Umsatz {year}: {_m(cum)} € von {_m(limit)} € (brutto)." +
                              (f" Im aktuellen Tempo erreichen Sie die Grenze voraussichtlich um den {_d(hit)}."
                               if hit and hit.year == year else ""))
            if hit and hit.year == year:
                res["status"] = "gelb"
        return res

    # Deutschland
    res.update(limit=r["limit"], prior_limit=r["prior"])
    if founding_year:
        lim = r["founding"]
        res["limit"] = lim
        proj, hit = _forecast(cum, as_of, year, lim) if items else (cum, None)
        res.update(forecast=proj, forecast_hit=hit)
        cross = _crossing(items, extra_turnover, lim)
        if cross:
            res.update(status="rot", crossed_on=cross[0], headline=f"Gründungsjahr: 25.000 € am {_d(cross[0])} überschritten.",
                       detail="Im Gründungsjahr endet die Kleinunternehmerregelung mit dem Umsatz, der 25.000 € überschreitet. "
                              "Ab diesem Umsatz Rechnungen mit Umsatzsteuer stellen; Steuerberatung einschalten.")
        else:
            res.update(status="gelb" if hit and hit.year == year else "gruen",
                       headline=f"Gründungsjahr: noch {_m(lim - cum)} € bis 25.000 €.",
                       detail=f"Umsatz bisher {_m(cum)} € (netto)." +
                              (f" Im aktuellen Tempo wird die Grenze um den {_d(hit)} erreicht." if hit and hit.year == year else ""))
        return res

    if prior_year_turnover is not None and prior_year_turnover > r["prior"]:
        res.update(status="rot", forecast=cum, forecast_hit=None, headline=f"Im Jahr {year} gilt die Kleinunternehmerregelung nicht.",
                   detail=f"Der Vorjahresumsatz ({_m(prior_year_turnover)} €) lag über {_m(r['prior'])} €.")
        return res
    proj, hit = _forecast(cum, as_of, year, r["limit"]) if items else (cum, None)
    res.update(forecast=proj, forecast_hit=hit)
    cross = _crossing(items, extra_turnover, r["limit"])
    if cross:
        res.update(status="rot", crossed_on=cross[0], headline=f"100.000 € am {_d(cross[0])} überschritten.",
                   detail="Ab dem Umsatz, mit dem 100.000 € überschritten werden, gilt sofort die Regelbesteuerung. "
                          "Rechnungen ab dann mit Umsatzsteuer stellen; Steuerberatung einschalten.")
    elif cum > r["prior"]:
        res.update(status="gelb", headline=f"25.000 € überschritten – ab {year + 1} keine Kleinunternehmerregelung.",
                   detail=f"Umsatz {year}: {_m(cum)} € (netto). Für {year} bleibt es bei der Befreiung, solange 100.000 € nicht "
                          f"überschritten werden (noch {_m(r['limit'] - cum)} €). Ab 1.1.{year + 1} gilt die Regelbesteuerung.")
    else:
        _, hit25 = _forecast(cum, as_of, year, r["prior"]) if items else (cum, None)
        res.update(status="gelb" if hit25 and hit25.year == year else "gruen",
                   headline=f"Noch {_m(r['prior'] - cum)} € bis 25.000 €.",
                   detail=f"Umsatz {year} bisher {_m(cum)} € (netto). Bleiben Sie in {year} unter 25.000 €, sind Sie auch "
                          f"{year + 1} Kleinunternehmer." +
                          (f" Im aktuellen Tempo überschreiten Sie 25.000 € um den {_d(hit25)} – dann ab {year + 1} Regelbesteuerung."
                           if hit25 and hit25.year == year else ""))
    return res


def _m(x) -> str:
    return f"{D(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _d(d: date) -> str:
    return d.strftime("%d.%m.%Y")
