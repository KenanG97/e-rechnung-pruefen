/* SEPA-Lastschrift-Generator – Python-Paket `sepalast` per Pyodide im Browser. */
(() => {
  "use strict";
  const CFG = window.ERECHNUNG_CFG || {};
  const FREE = 25;
  const $ = (s, el = document) => el.querySelector(s);
  const form = $("#sepa"); if (!form) return;
  const status = $("#sepa-status"), out = $("#sepa-out");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = (v) => Number(v || 0).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
  const ls = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { } } };
  const FIELDS = ["name", "iban", "bic", "ci", "town", "country", "amount", "purpose"];
  const saved = ls.get("sepa_verein", {});
  FIELDS.forEach((f) => { if (saved[f]) form[f].value = saved[f]; });
  // Vorschlag Einzugsdatum: in 16 Tagen (Vorabankündigung 14 Tage + Puffer), Wochenende überspringen
  const d0 = new Date(); d0.setDate(d0.getDate() + 16); while ([0, 6].includes(d0.getDay())) d0.setDate(d0.getDate() + 1);
  form.date.value = d0.toISOString().slice(0, 10);
  let py = null, file = null;

  const b64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
  async function isPro() {
    const key = ls.get("erechnung_lizenz", "");
    if (!CFG.licensePublicKey || !key || !key.includes(".")) return false;
    try {
      const [p, s] = key.split(".");
      const pub = await crypto.subtle.importKey("spki", b64u(CFG.licensePublicKey), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
      if (!(await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, pub, b64u(s), b64u(p)))) return false;
      return new TextDecoder().decode(b64u(p)).split("|")[1] >= new Date().toISOString().slice(0, 10);
    } catch { return false; }
  }
  async function loadPython() {
    if (py) return py;
    status.textContent = "Generator wird geladen (einmalig) …";
    if (!window.loadPyodide) await new Promise((res, rej) => { const s = document.createElement("script"); s.src = CFG.pyodideBase + "pyodide.js"; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
    const p = await window.loadPyodide({ indexURL: CFG.pyodideBase });
    const get = async (n) => (await fetch(CFG.root + "static/py/" + n + "?v=" + CFG.version)).arrayBuffer();
    for (const w of CFG.excelWheels || []) p.unpackArchive(await get(w), "wheel");
    for (const z of ["kugrenze.zip", "sepalast.zip"]) p.unpackArchive(await get(z), "zip");
    await p.runPythonAsync("from sepalast import web as sepa");
    status.textContent = ""; py = p; return p;
  }
  form.addEventListener("pointerenter", () => loadPython().catch(() => {}), { once: true });
  $("#sepa-file").addEventListener("change", (e) => { file = e.target.files[0] || null; $("#sepa-fname").textContent = file ? file.name : ""; });
  $("#sepa-template").addEventListener("click", () => dl("﻿Vorname;Nachname;IBAN;BIC;Betrag;Mandatsreferenz;Mandatsdatum;Straße;PLZ;Ort;Land;E-Mail\r\n" +
    "Anna;Muster;AT611904300234573201;;45,00;MITGL-001;15.03.2024;Hauptstraße 1;6020;Innsbruck;AT;anna@example.at\r\n", "Mitgliederliste_Vorlage.csv", "text/csv"));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!file) { status.textContent = "Bitte zuerst die Mitgliederliste wählen."; return; }
    const cfg = Object.fromEntries(FIELDS.map((f) => [f, form[f].value.trim()]));
    ls.set("sepa_verein", cfg);
    cfg.date = form.date.value;
    let p; try { p = await loadPython(); } catch { status.textContent = "Der Generator konnte nicht geladen werden. Bitte Seite neu laden."; return; }
    const pro = await isPro();
    p.globals.set("_d", new Uint8Array(await file.arrayBuffer())); p.globals.set("_n", file.name); p.globals.set("_c", JSON.stringify(cfg));
    const j = JSON.parse(p.runPython(`sepa.run(_d.to_py(), _n, _c, ${pro ? 0 : FREE})`));
    render(j);
    if (typeof window.plausible === "function") window.plausible("SEPA", { props: { n: j.total || 0 } });
  });

  function dl(text, name, type) {
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: type + ";charset=utf-8" })); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  function render(j) {
    if (!j.ok) { out.innerHTML = `<section class="sheet"><span class="stamp rot">Nicht lesbar<small>Liste prüfen</small></span><h2>Mitgliederliste</h2><p class="verdict">${esc(j.error)}</p></section>`; return; }
    const hard = j.head.filter((h) => !h.startsWith("WARNUNG"));
    const bad = j.rows.filter((r) => r.errors.length);
    const color = hard.length || !j.count_ok ? "rot" : (bad.length || j.rows.some((r) => r.warnings.length) || j.head.length ? "gelb" : "gruen");
    const stamp = { rot: ["Nicht bereit", "Fehler beheben"], gelb: ["Bereit", "mit Hinweisen"], gruen: ["Bereit", "zum Hochladen"] }[color];
    const rows = j.rows.filter((r) => r.errors.length || r.warnings.length).map((r) => `<tr><td>${r.row}</td><td>${esc(r.name)}</td><td class="n">${r.amount ? eur(r.amount) : "–"}</td>
      <td>${r.errors.map((e) => `<b>${esc(e)}</b>`).join("<br>")}${r.errors.length && r.warnings.length ? "<br>" : ""}${r.warnings.map((w) => `<span class="muted">${esc(w)}</span>`).join("<br>")}</td></tr>`).join("");
    out.innerHTML = `<section class="sheet" aria-live="polite">
      <span class="stamp ${color}">${stamp[0]}<small>${stamp[1]}</small></span>
      <h2>Lastschrift ${esc(j.collection.split("-").reverse().join("."))}</h2>
      <p class="verdict">${j.xml ? `${j.count_ok} Lastschriften über ${eur(j.sum_ok)} – Datei ist fertig.` : "Die Datei kann noch nicht erstellt werden."}</p>
      ${j.limited ? `<p class="note">Kostenlos werden die ersten ${FREE} von ${j.total} Mitgliedern verarbeitet. Für größere Vereine: <a href="../kanzlei/">Pro-Lizenz</a>.</p>` : ""}
      ${j.head.length ? `<ul class="findings">${j.head.map((h) => `<li class="${h.startsWith("WARNUNG") ? "warnung" : "fehler"}">${esc(h.replace(/^WARNUNG: /, ""))}</li>`).join("")}</ul>` : ""}
      <dl class="figures"><div><dt>Mitglieder in der Liste</dt><dd>${j.total}</dd></div><div><dt>in der Datei</dt><dd>${j.count_ok}</dd></div>
        <div><dt>ausgelassen (Fehler)</dt><dd>${bad.length}</dd></div><div><dt>Summe</dt><dd>${eur(j.sum_ok)}</dd></div></dl>
      ${rows ? `<details ${bad.length ? "open" : ""}><summary>${bad.length} Fehler, ${j.rows.filter((r) => r.warnings.length).length} Hinweise</summary><div class="tbl"><table><thead><tr><th>Zeile</th><th>Name</th><th class="n">Betrag</th><th>Befund</th></tr></thead><tbody>${rows}</tbody></table></div></details>` : ""}
      <div class="actions">
        <button class="btn" type="button" id="sepa-xml" ${j.xml ? "" : "disabled"}>SEPA-Datei (XML) herunterladen</button>
        <button class="btn ghost" type="button" id="sepa-pre" ${j.xml ? "" : "disabled"}>Vorabankündigungen (CSV)</button>
      </div>
      <p class="muted">Format pain.008.001.08 (SEPA-Basislastschrift CORE). Laden Sie die Datei im Online-Banking (Business) unter „Datei hochladen“ / „SEPA-Datei einreichen“ hoch und prüfen Sie Summe und Anzahl in der Bankanzeige vor der Freigabe.</p>
    </section>`;
    if (j.xml) {
      $("#sepa-xml").addEventListener("click", () => dl(j.xml, `Lastschrift_${j.collection}.xml`, "application/xml"));
      $("#sepa-pre").addEventListener("click", () => dl(py.runPython("sepa.prenotifications()"), `Vorabankuendigung_${j.collection}.csv`, "text/csv"));
    }
  }
})();
