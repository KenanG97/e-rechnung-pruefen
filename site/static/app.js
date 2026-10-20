/* E-Rechnung prüfen – läuft komplett im Browser.
   Die Prüflogik ist das Python-Paket `erechnung`, ausgeführt mit Pyodide (WebAssembly).
   Dateien werden nirgendwohin hochgeladen. */
(() => {
  "use strict";
  const CFG = window.ERECHNUNG_CFG || {};
  const FREE_LIMIT = 3;
  const $ = (s, el = document) => el.querySelector(s);
  const drop = $("#drop"), input = $("#file"), status = $("#status"), out = $("#results");
  if (!drop) return;

  let pyReady = null;
  let pro = null;
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* privat/gesperrt */ } },
  };
  let history = store.get("erechnung_verlauf", []);
  const batchRows = [];

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = (v, cur) => {
    if (v === null || v === undefined || v === "") return "–";
    const n = Number(v);
    return n.toLocaleString("de-DE", { style: "currency", currency: cur && cur.length === 3 ? cur : "EUR" });
  };
  const dd = (iso) => iso ? iso.slice(0, 10).split("-").reverse().join(".") : "–";

  function say(msg) { status.textContent = msg; }

  async function loadPython() {
    if (pyReady) return pyReady;
    pyReady = (async () => {
      say("Prüfprogramm wird geladen (einmalig, ca. 10 MB) …");
      if (!window.loadPyodide) {
        await new Promise((res, rej) => {
          const s = document.createElement("script");
          s.src = CFG.pyodideBase + "pyodide.js"; s.onload = res; s.onerror = () => rej(new Error("Pyodide nicht erreichbar"));
          document.head.appendChild(s);
        });
      }
      const py = await window.loadPyodide({ indexURL: CFG.pyodideBase });
      const fetchBuf = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(u + " " + r.status); return r.arrayBuffer(); };
      py.unpackArchive(await fetchBuf(CFG.root + "static/py/" + CFG.pypdfWheel), "wheel");
      py.unpackArchive(await fetchBuf(CFG.root + "static/py/erechnung.zip?v=" + CFG.version), "zip");
      await py.runPythonAsync("from erechnung.web import analyze");
      say("");
      return py;
    })();
    pyReady.catch(() => { pyReady = null; });
    return pyReady;
  }

  // Ab dem ersten Kontakt im Hintergrund laden, damit es beim Ablegen schon bereitsteht
  ["pointerenter", "focusin", "touchstart"].forEach((ev) => drop.addEventListener(ev, () => loadPython().catch(() => {}), { once: true, passive: true }));

  drop.addEventListener("click", (e) => { if (e.target !== input) input.click(); });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); handle([...e.dataTransfer.files]); });
  input.addEventListener("change", () => { handle([...input.files]); input.value = ""; });

  async function handle(files) {
    files = files.filter((f) => /\.(xml|pdf)$/i.test(f.name));
    if (!files.length) { say("Bitte eine .xml- oder .pdf-Datei wählen."); return; }
    if (files.length > FREE_LIMIT && !(await isPro())) {
      say(`Kostenlos werden ${FREE_LIMIT} Dateien gleichzeitig geprüft – die ersten ${FREE_LIMIT} von ${files.length}. Mehr mit der Kanzlei-Lizenz.`);
      files = files.slice(0, FREE_LIMIT);
    }
    let py;
    try { py = await loadPython(); }
    catch (err) { say("Das Prüfprogramm konnte nicht geladen werden. Bitte Internetverbindung prüfen und Seite neu laden."); return; }
    for (const f of files) {
      say(`Prüfe ${f.name} …`);
      if (f.size > 15 * 1024 * 1024) { render({ ok: false, name: f.name, error: "Datei ist größer als 15 MB." }); continue; }
      const bytes = new Uint8Array(await f.arrayBuffer());
      py.globals.set("_data", bytes); py.globals.set("_name", f.name); py.globals.set("_hist", JSON.stringify(history));
      let res;
      try { res = JSON.parse(py.runPython("analyze(_data.to_py(), _name, _hist)")); }
      catch (err) { res = { ok: false, name: f.name, error: "Interner Fehler beim Lesen: " + String(err).split("\n").slice(-2).join(" ") }; }
      if (res.ok) {
        if (!history.some((h) => h.hash === res.hash)) { history.push(res.history_record); history = history.slice(-2000); store.set("erechnung_verlauf", history); }
        batchRows.push(res.summary_row);
      }
      render(res);
    }
    say(files.length > 1 ? `${files.length} Dateien geprüft.` : "");
    updateBatch();
    if (typeof window.plausible === "function") window.plausible("Pruefung", { props: { n: files.length } });
  }

  const STAMP = { rot: ["Beanstanden", "vor Zahlung klären"], gelb: ["Prüfen", "Hinweise beachten"], gruen: ["Geprüft", "ohne Befund"] };

  function render(r) {
    const sec = document.createElement("section");
    sec.className = "sheet";
    sec.setAttribute("aria-live", "polite");
    if (!r.ok) {
      sec.innerHTML = `<span class="stamp rot">Keine E-Rechnung<small>nicht lesbar</small></span>
        <h2>${esc(r.name)}</h2><p class="verdict">${esc(r.error)}</p>
        <p class="muted">Eine gewöhnliche PDF-Rechnung ohne eingebettete Daten ist nach § 14 UStG keine E-Rechnung. Bitten Sie den Lieferanten um eine XRechnung oder ZUGFeRD-Datei (Profil EN 16931 oder höher).</p>`;
      out.prepend(sec); return;
    }
    const i = r.invoice, t = i.totals, cur = i.currency, v = r.verdict;
    const order = { fehler: 0, warnung: 1, info: 2 };
    const f = [...r.findings].sort((a, b) => order[a.severity] - order[b.severity]);
    const party = (p, label) => `<div><p class="muted">${label}</p><p><b>${esc(p.name) || "–"}</b></p><p>${esc([p.address.street, p.address.additional].filter(Boolean).join(", "))}</p>
      <p>${esc([p.address.postcode, p.address.city].filter(Boolean).join(" "))} ${esc(p.address.country)}</p>
      ${p.vat_id ? `<p>USt-IdNr. ${esc(p.vat_id)}</p>` : ""}${p.tax_number ? `<p>StNr. ${esc(p.tax_number)}</p>` : ""}</div>`;
    const leistung = i.delivery_date ? dd(i.delivery_date) : (i.period_start || i.period_end ? `${dd(i.period_start)} – ${dd(i.period_end)}` : "nicht angegeben");
    const rows = i.lines.map((l) => `<tr><td>${esc(l.line_id)}</td><td>${esc(l.name)}${l.description ? `<br><span class="muted">${esc(l.description)}</span>` : ""}</td>
      <td class="n">${l.quantity !== null ? Number(l.quantity).toLocaleString("de-DE") : ""} ${esc(l.unit_label)}</td><td class="n">${eur(l.unit_price, cur)}</td><td class="n">${eur(l.net_amount, cur)}</td><td class="n">${esc(l.vat_category)} ${l.vat_rate !== null ? Number(l.vat_rate).toLocaleString("de-DE") + " %" : ""}</td></tr>`).join("");
    const taxes = i.taxes.map((x) => `<tr><td colspan="4">USt ${x.rate !== null ? Number(x.rate).toLocaleString("de-DE") : 0} % (${esc(x.category_label)}) auf ${eur(x.basis, cur)}</td><td class="n" colspan="2">${eur(x.amount, cur)}</td></tr>`).join("");
    const id = "s" + r.hash.slice(0, 10);
    sec.id = id;
    sec.innerHTML = `
      <span class="stamp ${v.color}">${STAMP[v.color][0]}<small>${STAMP[v.color][1]}</small></span>
      <h2>${esc(i.type_label)} ${esc(i.number)}</h2>
      <p class="muted">${esc(i.seller.name)} · ${esc(r.name)}</p>
      <p class="verdict">${esc(v.text)}</p>
      <dl class="figures">
        <div><dt>Zahlbetrag</dt><dd>${eur(t.payable, cur)}</dd></div>
        <div><dt>davon USt</dt><dd>${eur(t.tax_total, cur)}</dd></div>
        <div><dt>Rechnungsdatum</dt><dd>${dd(i.issue_date)}</dd></div>
        <div><dt>Fällig</dt><dd>${dd(i.due_date)}</dd></div>
      </dl>
      <ul class="findings">${f.map((x) => `<li class="${x.severity}"><b>${esc(x.code)}</b> ${esc(x.message)}${x.legal ? `<span class="legal">${esc(x.legal)}</span>` : ""}</li>`).join("") || '<li class="info">Keine Befunde.</li>'}</ul>
      <details open><summary>Rechnung im Klartext</summary>
        <div class="parties">${party(i.seller, "Lieferant")}${party(i.buyer, "Rechnungsempfänger")}</div>
        <p><b>Leistungsdatum:</b> ${leistung}${i.buyer_reference ? ` · <b>Käuferreferenz/Leitweg-ID:</b> ${esc(i.buyer_reference)}` : ""}${i.order_reference ? ` · <b>Bestellnr.:</b> ${esc(i.order_reference)}` : ""}</p>
        <p><b>Zahlung:</b> ${esc(i.payment_label || "–")}${i.iban ? ` · IBAN ${esc(i.iban)}` : ""}${i.bic ? ` · BIC ${esc(i.bic)}` : ""}${i.payment_terms ? `<br><span class="muted">${esc(i.payment_terms)}</span>` : ""}</p>
        <div class="tbl"><table><thead><tr><th>Pos</th><th>Leistung</th><th class="n">Menge</th><th class="n">Einzelpreis</th><th class="n">Netto</th><th class="n">USt</th></tr></thead>
        <tbody>${rows}</tbody><tfoot>
          <tr><td colspan="4">Nettobetrag</td><td class="n" colspan="2">${eur(t.tax_basis_total, cur)}</td></tr>${taxes}
          <tr><td colspan="4">Bruttobetrag</td><td class="n" colspan="2">${eur(t.grand_total, cur)}</td></tr>
          ${t.prepaid ? `<tr><td colspan="4">Bereits bezahlt</td><td class="n" colspan="2">−${eur(t.prepaid, cur)}</td></tr>` : ""}
          ${t.third_party ? `<tr><td colspan="4">Drittforderungen</td><td class="n" colspan="2">${eur(t.third_party, cur)}</td></tr>` : ""}
          <tr><td colspan="4">Zahlbetrag</td><td class="n" colspan="2">${eur(t.payable, cur)}</td></tr></tfoot></table></div>
        ${i.notes.length ? `<p class="muted">${i.notes.map(esc).join("<br>")}</p>` : ""}
        <p class="muted">Format: ${esc(i.syntax)} · ${esc(i.container)} · ${esc(i.guideline)}</p>
      </details>
      <div class="actions">
        <button class="btn" type="button" data-print="${id}">Prüfbericht drucken / als PDF speichern</button>
        <button class="btn ghost" type="button" data-csv>Positionen als CSV</button>
      </div>`;
    sec.querySelector("[data-csv]").addEventListener("click", () => download(r.lines_csv, `Positionen_${i.number || "rechnung"}.csv`, "text/csv"));
    sec.querySelector("[data-print]").addEventListener("click", () => printOnly(sec));
    out.prepend(sec);
  }

  function printOnly(sec) {
    const others = [...out.children].filter((c) => c !== sec);
    others.forEach((c) => c.classList.add("no-print"));
    const d = sec.querySelector("details"); const wasOpen = d.open; d.open = true;
    window.print();
    d.open = wasOpen; others.forEach((c) => c.classList.remove("no-print"));
  }

  function download(text, name, type) {
    const blob = new Blob(["﻿" + text], { type: type + ";charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  function updateBatch() {
    const bar = $("#batch"); if (!bar) return;
    bar.hidden = batchRows.length < 2;
    $("#batch-n").textContent = batchRows.length;
  }
  $("#batch-csv")?.addEventListener("click", async () => {
    if (!(await isPro())) { $("#pro").hidden = false; $("#pro-key").focus(); return; }
    const head = Object.keys(batchRows[0]);
    const q = (s) => /[;"\n]/.test(s) ? `"${String(s).replace(/"/g, '""')}"` : String(s ?? "");
    download([head.join(";"), ...batchRows.map((r) => head.map((h) => q(r[h])).join(";"))].join("\r\n"), "rechnungen.csv", "text/csv");
  });

  // Verlauf
  $("#hist-dl")?.addEventListener("click", () => download(JSON.stringify(history, null, 1), "erechnung-verlauf.json", "application/json"));
  $("#hist-up")?.addEventListener("change", async (e) => {
    try { const d = JSON.parse(await e.target.files[0].text()); if (Array.isArray(d)) { const known = new Set(history.map((h) => h.hash)); history = history.concat(d.filter((h) => !known.has(h.hash))); store.set("erechnung_verlauf", history); say(`Verlauf: ${history.length} Einträge.`); } }
    catch { say("Die Verlaufsdatei ist nicht lesbar."); }
  });
  $("#hist-clear")?.addEventListener("click", () => { history = []; store.set("erechnung_verlauf", []); say("Verlauf gelöscht."); });

  // Lizenz: ECDSA-P-256-signiert, Prüfung mit öffentlichem Schlüssel im Browser
  const b64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
  async function verifyKey(key) {
    if (!CFG.licensePublicKey || !key || !key.includes(".")) return null;
    try {
      const [p, s] = key.trim().split(".");
      const pub = await crypto.subtle.importKey("spki", b64u(CFG.licensePublicKey), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
      const ok = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, pub, b64u(s), b64u(p));
      if (!ok) return null;
      const [email, until] = new TextDecoder().decode(b64u(p)).split("|");
      return until >= new Date().toISOString().slice(0, 10) ? { email, until } : null;
    } catch { return null; }
  }
  async function isPro() {
    if (pro !== null) return !!pro;
    pro = await verifyKey(store.get("erechnung_lizenz", ""));
    return !!pro;
  }
  $("#pro-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const k = $("#pro-key").value;
    const r = await verifyKey(k);
    if (r) { store.set("erechnung_lizenz", k); pro = r; $("#pro-msg").textContent = `Lizenz aktiv für ${r.email} bis ${dd(r.until)}.`; }
    else { $("#pro-msg").textContent = "Dieser Schlüssel ist ungültig oder abgelaufen."; }
  });
  isPro().then((ok) => { if (ok && $("#pro-msg")) $("#pro-msg").textContent = `Lizenz aktiv für ${pro.email} bis ${dd(pro.until)}.`; });
})();
