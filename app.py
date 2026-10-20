"""E-Rechnung Prüfen – Streamlit-Oberfläche.

Start lokal:   streamlit run app.py
Kostenlos hosten: Streamlit Community Cloud (GitHub-Repo verbinden, app.py wählen).

Datenschutz-Design: Dateien werden ausschließlich im Arbeitsspeicher der laufenden Sitzung
verarbeitet. Der Verlauf (für Duplikat- und IBAN-Wechsel-Erkennung) lebt nur in der Sitzung
und kann vom Nutzer als Datei heruntergeladen und später wieder geladen werden – auf dem
Server wird nichts dauerhaft gespeichert.
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from erechnung import ParseError, check_against_history, check_invoice, parse_bytes, summarize
from erechnung.export import de_date, eur, lines_csv, pdf_report, summary_row, to_csv
from erechnung.license import verify_key
from erechnung.model import PAYMENT_MEANS, TYPE_CODES, UNIT_CODES, VAT_CATEGORIES
from erechnung.store import file_hash

FREE_BATCH_LIMIT = 3

st.set_page_config(page_title="E-Rechnung prüfen – XRechnung & ZUGFeRD lesen", page_icon="🧾", layout="wide")

st.markdown("""
<style>
.badge {display:inline-block;padding:.35rem .8rem;border-radius:.5rem;font-weight:600;margin:.2rem 0 .8rem}
.rot {background:#f8d7da;color:#842029} .gelb {background:#fff3cd;color:#664d03} .gruen {background:#d1e7dd;color:#0f5132}
.small {font-size:.85rem;color:#6c757d}
</style>""", unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("history", [])
ss.setdefault("pro", False)
ss.setdefault("cache", {})  # hash -> Ergebnis, damit Reruns nicht neu (und gegen sich selbst) prüfen

# ---------------------------------------------------------------- Seitenleiste
with st.sidebar:
    st.header("🧾 E-Rechnung prüfen")
    st.write("XRechnung (XML) und ZUGFeRD/Factur-X (PDF) lesbar machen, auf Pflichtangaben und "
             "Rechenfehler prüfen, Prüfbericht als PDF.")
    st.divider()
    st.subheader("Verlauf")
    st.caption("Erkennt doppelte Rechnungen und **geänderte Bankverbindungen** von Lieferanten. "
               "Wird nicht auf dem Server gespeichert – laden Sie ihn herunter und beim nächsten Mal wieder hoch.")
    up_hist = st.file_uploader("Verlauf laden (.json)", type=["json"], key="hist_up")
    if up_hist is not None and not ss.get("hist_loaded"):
        try:
            ss.history = json.loads(up_hist.getvalue())
            ss.hist_loaded = True
            st.success(f"{len(ss.history)} Einträge geladen.")
        except Exception:
            st.error("Verlaufsdatei unlesbar.")
    st.download_button("Verlauf herunterladen", json.dumps(ss.history, ensure_ascii=False, indent=1),
                       file_name=f"erechnung-verlauf-{datetime.now():%Y%m%d}.json",
                       disabled=not ss.history, use_container_width=True)
    st.divider()
    st.subheader("Pro")
    if ss.pro:
        st.success(f"Pro aktiv ({ss.get('pro_email', '')})")
    else:
        st.caption(f"Kostenlos: bis zu {FREE_BATCH_LIMIT} Rechnungen gleichzeitig. "
                   "Pro: unbegrenzter Stapel, Sammel-CSV für Steuerberater/Excel.")
        key = st.text_input("Lizenzschlüssel", type="password")
        if key:
            ok, info = verify_key(key)
            if ok:
                ss.pro, ss.pro_email = True, info
                st.rerun()
            else:
                st.error(info)
    st.divider()
    st.markdown('<p class="small">Automatisierte Plausibilitätsprüfung, keine Steuerberatung. '
                'Originaldateien unverändert aufbewahren (GoBD).</p>', unsafe_allow_html=True)

# ---------------------------------------------------------------- Hauptbereich
st.title("E-Rechnung lesen & prüfen")
st.write("Seit 1.1.2025 muss jedes Unternehmen in Deutschland E-Rechnungen **empfangen** können – auch "
         "Kleinunternehmer. Laden Sie eine XRechnung (.xml) oder ZUGFeRD-Rechnung (.pdf) hoch.")

files = st.file_uploader("Rechnungen hier ablegen", type=["xml", "pdf"], accept_multiple_files=True)

if not files:
    with st.expander("Was wird geprüft?"):
        st.markdown("""
- **Lesbarkeit**: XRechnung & ZUGFeRD/Factur-X, beide Syntaxen (UBL und CII)
- **Ist es überhaupt eine E-Rechnung?** Gewöhnliche PDFs und ZUGFeRD-Profile MINIMUM/BASIC WL werden erkannt
- **Pflichtangaben nach § 14 Abs. 4 UStG** – Voraussetzung für Ihren Vorsteuerabzug
- **Rechnerische Richtigkeit**: Positionen, Steuerbeträge, Brutto, Zahlbetrag
- **Sonderfälle**: Reverse Charge, steuerfreie Umsätze, Kleinunternehmer
- **Betrugsschutz**: IBAN-Prüfziffer, Ausland-IBAN, **IBAN-Wechsel** gegenüber früheren Rechnungen, Duplikate
- **Export**: Prüfbericht als PDF, Positionen als CSV
""")
    st.stop()

if len(files) > FREE_BATCH_LIMIT and not ss.pro:
    st.warning(f"Kostenlos werden die ersten {FREE_BATCH_LIMIT} von {len(files)} Dateien geprüft. "
               "Für Stapelprüfung ohne Limit: Pro-Lizenz.")
    files = files[:FREE_BATCH_LIMIT]

results = []
for up in files:
    data = up.getvalue()
    try:
        inv = parse_bytes(data, up.name)
    except ParseError as exc:
        results.append((up.name, None, [], ("rot", str(exc))))
        continue
    inv._hash = file_hash(data)
    if inv._hash in ss.cache:
        findings, verdict = ss.cache[inv._hash]
    else:
        findings = check_against_history(inv, ss.history) + check_invoice(inv)
        verdict = summarize(findings)
        ss.cache[inv._hash] = (findings, verdict)
    results.append((up.name, inv, findings, verdict))
    if not any(h.get("hash") == inv._hash for h in ss.history):
        ss.history.append({
            "checked_at": datetime.now().isoformat(timespec="seconds"), "hash": inv._hash,
            "seller_name": inv.seller.name, "seller_vat": inv.seller.vat_id, "seller_tax": inv.seller.tax_number,
            "number": inv.number, "payable": str(inv.totals.payable or ""),
            "iban": inv.iban.replace(" ", "").upper(), "status": verdict[0],
        })

# Übersicht bei mehreren Dateien
if len(results) > 1:
    st.subheader("Übersicht")
    overview = [{
        "Datei": n, "Status": {"rot": "❌", "gelb": "⚠️", "gruen": "✅"}[v[0]],
        "Lieferant": i.seller.name if i else "–", "Nr.": i.number if i else "–",
        "Datum": de_date(i.issue_date) if i else "–",
        "Zahlbetrag": eur(i.totals.payable, i.currency) if i else "–",
    } for n, i, _, v in results]
    st.dataframe(pd.DataFrame(overview), hide_index=True, use_container_width=True)
    rows = [summary_row(i, v[0]) for _, i, _, v in results if i]
    if ss.pro:
        st.download_button("Sammel-CSV (Excel/Steuerberater)", to_csv(rows),
                           file_name=f"rechnungen-{datetime.now():%Y%m%d}.csv", mime="text/csv")
    else:
        st.caption("🔒 Sammel-CSV für alle Rechnungen: Pro")

for name, inv, findings, (color, text) in results:
    st.divider()
    if inv is None:
        st.subheader(f"📄 {name}")
        st.markdown(f'<div class="badge rot">Keine lesbare E-Rechnung</div>', unsafe_allow_html=True)
        st.write(text)
        continue

    title = TYPE_CODES.get(inv.type_code, "Rechnung")
    st.subheader(f"{title} {inv.number} – {inv.seller.name}")
    st.markdown(f'<div class="badge {color}">{text}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zahlbetrag", eur(inv.totals.payable, inv.currency))
    c2.metric("davon USt", eur(inv.totals.tax_total, inv.currency))
    c3.metric("Rechnungsdatum", de_date(inv.issue_date))
    c4.metric("Fällig", de_date(inv.due_date))

    tab_check, tab_inv, tab_pos = st.tabs(["Prüfergebnis", "Rechnung", "Positionen"])

    with tab_check:
        order = {"fehler": 0, "warnung": 1, "info": 2}
        if not findings:
            st.success("Keine Befunde.")
        for f in sorted(findings, key=lambda x: order[x.severity]):
            msg = f"**{f.code}** · {f.message}" + (f"  \n_{f.legal}_" if f.legal else "")
            {"fehler": st.error, "warnung": st.warning, "info": st.info}[f.severity](msg, icon=f.icon)

    with tab_inv:
        a, b = st.columns(2)
        for col, label, p in ((a, "Lieferant", inv.seller), (b, "Rechnungsempfänger", inv.buyer)):
            with col:
                st.markdown(f"**{label}**")
                st.write(p.name or "–")
                st.write(p.address.one_line() or "–")
                if p.vat_id:
                    st.write(f"USt-IdNr.: {p.vat_id}")
                if p.tax_number:
                    st.write(f"Steuernummer: {p.tax_number}")
                contact = " · ".join(x for x in (p.contact_name, p.contact_phone, p.contact_email) if x)
                if contact:
                    st.caption(contact)
        st.markdown("**Zahlung**")
        st.write(f"{PAYMENT_MEANS.get(inv.payment_means_code, inv.payment_means_code or '–')}"
                 f"{' · IBAN ' + inv.iban if inv.iban else ''}{' · BIC ' + inv.bic if inv.bic else ''}")
        if inv.payment_terms:
            st.caption(inv.payment_terms)
        leistung = de_date(inv.delivery_date) if inv.delivery_date else (
            f"{de_date(inv.period_start)} – {de_date(inv.period_end)}" if inv.period_start or inv.period_end else "–")
        st.write(f"**Leistungsdatum/-zeitraum:** {leistung}")
        if inv.buyer_reference:
            st.write(f"**Käuferreferenz / Leitweg-ID:** {inv.buyer_reference}")
        if inv.order_reference:
            st.write(f"**Bestellnummer:** {inv.order_reference}")
        if inv.notes:
            st.markdown("**Hinweise auf der Rechnung**")
            for n in inv.notes:
                st.caption(n)
        st.caption(f"Format: {inv.syntax} · {inv.container} · {inv.guideline}")

    with tab_pos:
        df = pd.DataFrame([{
            "Pos": ln.line_id, "Bezeichnung": ln.name,
            "Menge": float(ln.quantity) if ln.quantity is not None else None,
            "Einheit": UNIT_CODES.get(ln.unit, ln.unit),
            "Einzelpreis": eur(ln.unit_price, inv.currency), "Netto": eur(ln.net_amount, inv.currency),
            "USt": f"{ln.vat_category} {ln.vat_rate if ln.vat_rate is not None else ''} %",
        } for ln in inv.lines])
        st.dataframe(df, hide_index=True, use_container_width=True)
        t = inv.totals
        sums = [("Summe Positionen", t.line_total), ("Abschläge", t.allowance_total),
                ("Zuschläge", t.charge_total), ("Nettobetrag", t.tax_basis_total)]
        sums += [(f"USt {tb.rate or 0} % ({VAT_CATEGORIES.get(tb.category, tb.category)}) auf "
                  f"{eur(tb.basis, inv.currency)}", tb.amount) for tb in inv.taxes]
        sums += [("Bruttobetrag", t.grand_total), ("Bereits bezahlt", t.prepaid),
                 ("Drittforderungen", t.third_party), ("**Zahlbetrag**", t.payable)]
        for label, val in sums:
            if val is not None:
                l, r = st.columns([3, 1])
                l.markdown(label)
                r.markdown(f"<div style='text-align:right'>{eur(val, inv.currency)}</div>", unsafe_allow_html=True)

    d1, d2 = st.columns(2)
    d1.download_button("📄 Prüfbericht (PDF)", pdf_report(inv, findings, text),
                       file_name=f"Pruefbericht_{inv.number or name}.pdf", mime="application/pdf",
                       key=f"pdf_{inv._hash}", use_container_width=True)
    d2.download_button("📊 Positionen (CSV)", lines_csv(inv), file_name=f"Positionen_{inv.number or name}.csv",
                       mime="text/csv", key=f"csv_{inv._hash}", use_container_width=True)
