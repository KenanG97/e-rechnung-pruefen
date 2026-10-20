/* Kleinunternehmer-Grenzwächter – Python (Paket `kugrenze`) läuft per Pyodide im Browser. */
(() => {
  "use strict";
  const CFG = window.ERECHNUNG_CFG || {};
  const $ = (s, el = document) => el.querySelector(s);
  const form = $("#kug"); if (!form) return;
  const status = $("#kug-status"), out = $("#kug-out");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = (v) => Number(v || 0).toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const eur2 = (v) => Number(v || 0).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
  const dd = (iso) => iso ? iso.slice(0, 10).split("-").reverse().join(".") : "–";
  const store = { get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { } } };

  // Land vorauswählen: Österreich bei de-AT, sonst Deutschland
  const savedCountry = store.get("kug_land", (navigator.language || "").toLowerCase() === "de-at" ? "AT" : "DE");
  form.country.value = savedCountry;
  const yearSel = form.year;
  const thisYear = new Date().getFullYear();
  const setYears = (years) => {
    const ys = [...new Set([thisYear, thisYear - 1, ...(years || [])])].sort((a, b) => b - a);
    const cur = Number(yearSel.value) || thisYear;
    yearSel.innerHTML = ys.map((y) => `<option${y === cur ? " selected" : ""}>${y}</option>`).join("");
  };
  setYears([]);
  form.ownname.value = store.get("kug_name", "");
  const syncCountry = () => { $("#kug-founding-wrap").hidden = form.country.value !== "DE"; };
  syncCountry();

  let py = null, hasData = false;
  async function loadPython() {
    if (py) return py;
    status.textContent = "Rechner wird geladen (einmalig) …";
    if (!window.loadPyodide) {
      await new Promise((res, rej) => { const s = document.createElement("script"); s.src = CFG.pyodideBase + "pyodide.js"; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
    }
    const p = await window.loadPyodide({ indexURL: CFG.pyodideBase });
    const r = await fetch(CFG.root + "static/py/kugrenze.zip?v=" + CFG.version);
    p.unpackArchive(await r.arrayBuffer(), "zip");
    await p.runPythonAsync("from kugrenze import web as kug");
    status.textContent = "";
    py = p; return p;
  }
  form.addEventListener("pointerenter", () => loadPython().catch(() => {}), { once: true });

  $("#kug-file").addEventListener("change", async (e) => {
    const files = [...e.target.files]; e.target.value = "";
    if (!files.length) return;
    let p; try { p = await loadPython(); } catch { status.textContent = "Der Rechner konnte nicht geladen werden. Bitte Seite neu laden."; return; }
    store.set("kug_name", form.ownname.value);
    for (const f of files) {
      p.globals.set("_d", new Uint8Array(await f.arrayBuffer())); p.globals.set("_n", form.ownname.value);
      const j = JSON.parse(p.runPython("kug.load(_d.to_py(), _n)"));
      if (!j.ok) { status.textContent = `${f.name}: ${j.error}`; continue; }
      hasData = true;
      setYears(j.years);
      status.textContent = `${f.name}: ${j.added} Buchungen gelesen (Spalten: Datum = „${j.mapping.Datum}“, Betrag = „${j.mapping.Betrag}“).`;
    }
    $("#kug-reset").hidden = !hasData;
    calc();
  });
  $("#kug-reset").addEventListener("click", async () => { const p = await loadPython(); p.runPython("kug.reset()"); hasData = false; out.innerHTML = ""; $("#kug-reset").hidden = true; status.textContent = "Kontodaten entfernt."; });

  form.addEventListener("input", (e) => { if (e.target.name === "country") { store.set("kug_land", form.country.value); syncCountry(); } });
  form.addEventListener("change", (e) => { if (e.target.type !== "file" && (hasData || form.extra.value)) calc(); });
  form.addEventListener("submit", (e) => { e.preventDefault(); calc(); });

  const STAMP = { rot: ["Grenze überschritten", "jetzt handeln"], gelb: ["Achtung", "Grenze in Sicht"], gruen: ["Im Rahmen", "Kleinunternehmer"] };

  async function calc() {
    let p; try { p = await loadPython(); } catch { status.textContent = "Der Rechner konnte nicht geladen werden."; return; }
    const args = [form.country.value, Number(form.year.value), form.prior.value, form.founding.checked, form.extra.value, form.vat.checked];
    p.globals.set("_a", p.toPy(args));
    const j = JSON.parse(p.runPython("kug.run(*_a)"));
    render(j);
    if (typeof window.plausible === "function") window.plausible("Grenzcheck", { props: { land: args[0] } });
  }

  function chart(r) {
    const W = 640, H = 220, padL = 56, padB = 26, padT = 14, padR = 10;
    const months = r.monthly; let cum = 0; const pts = months.map((m) => (cum += m));
    const lines = [{ v: r.limit, label: r.country === "AT" ? "55.000 € Grenze" : (r.limit === 25000 ? "25.000 € Grenze" : "100.000 € Grenze") }];
    if (r.tolerance) lines.push({ v: r.tolerance, label: "60.500 € Toleranz" });
    if (r.country === "DE" && r.limit === 100000) lines.push({ v: 25000, label: "25.000 € (Folgejahr)" });
    const maxV = Math.max(cum, r.forecast || 0, ...lines.map((l) => l.v)) * 1.08;
    const x = (i) => padL + (i + 1) * (W - padL - padR) / 12, y = (v) => padT + (H - padT - padB) * (1 - v / maxV);
    const asOfM = r.as_of ? Number(r.as_of.slice(5, 7)) : 12;
    const path = pts.slice(0, asOfM).map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
    const fc = r.forecast && asOfM < 12 ? `<path d="M${x(asOfM - 1)},${y(pts[asOfM - 1])}L${x(11)},${y(r.forecast)}" stroke="var(--ink-soft)" stroke-dasharray="5 5" fill="none" stroke-width="2"/>
      <text x="${x(11) - 4}" y="${y(r.forecast) - 6}" text-anchor="end" font-size="12" fill="var(--ink-soft)">Hochrechnung ${eur(r.forecast)}</text>` : "";
    const mn = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Kumulierter Umsatz ${r.year}: ${eur(cum)}" style="width:100%;height:auto;margin:.4rem 0 1rem">
      ${lines.map((l) => `<line x1="${padL}" x2="${W - padR}" y1="${y(l.v)}" y2="${y(l.v)}" stroke="var(--red)" stroke-width="1.2" stroke-dasharray="${l.label.includes("Toleranz") || l.label.includes("Folgejahr") ? "2 3" : "0"}"/>
        <text x="${l.label.includes("Grenze") ? padL + 4 : W - padR - 4}" y="${y(l.v) - 4}" text-anchor="${l.label.includes("Grenze") ? "start" : "end"}" font-size="12" fill="var(--red)">${l.label}</text>`).join("")}
      <path d="${path}" stroke="var(--ink)" stroke-width="2.6" fill="none" stroke-linejoin="round"/>${fc}
      ${pts.slice(0, asOfM).map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="var(--ink)"><title>${mn[i]}: ${eur(v)}</title></circle>`).join("")}
      ${mn.map((m, i) => `<text x="${x(i)}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--ink-soft)">${m}</text>`).join("")}
      <text x="${padL - 8}" y="${y(0)}" text-anchor="end" font-size="12" fill="var(--ink-soft)">0</text>
      <line x1="${padL}" x2="${W - padR}" y1="${y(0)}" y2="${y(0)}" stroke="var(--rule)"/>
    </svg>`;
  }

  function render(j) {
    const r = j.result; const st = STAMP[r.status];
    const tx = j.transactions.filter((t) => t.day.startsWith(String(r.year)));
    const rows = tx.map((t) => `<tr${t.include ? "" : ' class="muted"'}><td><input type="checkbox" data-i="${t.i}" ${t.include ? "checked" : ""} aria-label="Eingang vom ${dd(t.day)} zählen"></td>
      <td>${dd(t.day)}</td><td>${esc(t.party)}<br><span class="muted">${esc(t.text)}</span></td><td class="n">${eur2(t.amount)}</td><td>${esc(t.reason)}</td></tr>`).join("");
    out.innerHTML = `<section class="sheet" aria-live="polite">
      <span class="stamp ${r.status}">${st[0]}<small>${st[1]}</small></span>
      <h2>${esc(r.country_name)} · ${r.year}</h2>
      <p class="verdict">${esc(r.headline)}</p><p>${esc(r.detail)}</p>
      <dl class="figures">
        <div><dt>Umsatz ${r.year} (${esc(r.basis)})</dt><dd>${eur(r.turnover)}</dd></div>
        <div><dt>Grenze</dt><dd>${eur(r.limit)}</dd></div>
        <div><dt>Hochrechnung Jahresende</dt><dd>${r.count ? eur(r.forecast) : "–"}</dd></div>
        <div><dt>Stand</dt><dd>${dd(r.as_of)}</dd></div>
      </dl>
      ${chart(r)}
      <ul class="findings">${r.notes.map((n) => `<li class="info">${esc(n)}</li>`).join("")}<li class="info">Rechtsgrundlage: ${esc(r.law)}. Automatisierte Berechnung, keine Steuerberatung.</li></ul>
      ${rows ? `<details><summary>${tx.length} Zahlungseingänge in ${r.year} – Auswahl prüfen</summary>
        <p class="muted">Haken entfernen bei allem, was kein Umsatz ist (z. B. private Überweisungen). Erkannte Nicht-Umsätze sind bereits abgewählt.</p>
        <div class="tbl"><table><thead><tr><th>Zählt</th><th>Datum</th><th>Von</th><th class="n">Betrag</th><th>Einordnung</th></tr></thead><tbody>${rows}</tbody></table></div></details>` : ""}
      <div class="actions"><button class="btn" type="button" id="kug-print">Ergebnis drucken / als PDF</button></div>
    </section>`;
    out.querySelectorAll("input[data-i]").forEach((cb) => cb.addEventListener("change", async () => {
      const p = await loadPython(); p.runPython(`kug.toggle(${Number(cb.dataset.i)}, ${cb.checked ? "True" : "False"})`);
      const open = out.querySelector("details")?.open; await calc(); if (open) out.querySelector("details").open = true;
    }));
    $("#kug-print").addEventListener("click", () => window.print());
  }
})();
