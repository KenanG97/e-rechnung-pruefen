/* Produktdaten-Check (Grundpreis + GPSR) – Python-Paket `shopcheck` per Pyodide im Browser. */
(() => {
  "use strict";
  const CFG = window.ERECHNUNG_CFG || {};
  const FREE = 25;
  const $ = (s, el = document) => el.querySelector(s);
  const input = $("#shop-file"); if (!input) return;
  const status = $("#shop-status"), out = $("#shop-out");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } } };
  let py = null, lastFile = null;

  const b64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
  async function isPro() {
    const key = store.get("erechnung_lizenz", "");
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
    status.textContent = "Prüfprogramm wird geladen (einmalig) …";
    if (!window.loadPyodide) await new Promise((res, rej) => { const s = document.createElement("script"); s.src = CFG.pyodideBase + "pyodide.js"; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
    const p = await window.loadPyodide({ indexURL: CFG.pyodideBase });
    for (const z of ["kugrenze.zip", "shopcheck.zip"]) p.unpackArchive(await (await fetch(CFG.root + "static/py/" + z + "?v=" + CFG.version)).arrayBuffer(), "zip");
    await p.runPythonAsync("from shopcheck import web as shop");
    status.textContent = ""; py = p; return p;
  }
  $("#shop-drop").addEventListener("pointerenter", () => loadPython().catch(() => {}), { once: true });
  $("#shop-drop").addEventListener("click", (e) => { if (e.target !== input) input.click(); });
  $("#shop-drop").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  $("#shop-drop").addEventListener("dragover", (e) => { e.preventDefault(); e.currentTarget.classList.add("over"); });
  $("#shop-drop").addEventListener("dragleave", (e) => e.currentTarget.classList.remove("over"));
  $("#shop-drop").addEventListener("drop", (e) => { e.preventDefault(); e.currentTarget.classList.remove("over"); if (e.dataTransfer.files[0]) run(e.dataTransfer.files[0]); });
  input.addEventListener("change", () => { if (input.files[0]) run(input.files[0]); input.value = ""; });

  async function run(file) {
    lastFile = file;
    let p; try { p = await loadPython(); } catch { status.textContent = "Das Prüfprogramm konnte nicht geladen werden. Bitte Seite neu laden."; return; }
    status.textContent = `Prüfe ${file.name} …`;
    const pro = await isPro();
    p.globals.set("_d", new Uint8Array(await file.arrayBuffer()));
    const j = JSON.parse(p.runPython(`shop.analyze(_d.to_py(), ${pro ? 0 : FREE})`));
    status.textContent = "";
    if (!j.ok) { out.innerHTML = `<section class="sheet"><span class="stamp rot">Nicht lesbar<small>Datei prüfen</small></span><h2>${esc(file.name)}</h2><p class="verdict">${esc(j.error)}</p></section>`; return; }
    render(j, pro, file.name);
    if (typeof window.plausible === "function") window.plausible("Shopcheck", { props: { n: j.summary.total } });
  }

  function render(j, pro, name) {
    const s = j.summary;
    const color = s.errors ? "rot" : (j.results.some((r) => r.findings.some((f) => f.severity === "warnung")) ? "gelb" : "gruen");
    const stamp = { rot: ["Abmahnrisiko", "nachbessern"], gelb: ["Prüfen", "Hinweise"], gruen: ["Geprüft", "ohne Befund"] }[color];
    const order = { fehler: 0, warnung: 1, info: 2 };
    const bad = j.results.filter((r) => r.findings.some((f) => f.severity !== "info"))
      .sort((a, b) => Math.min(...a.findings.map((f) => order[f.severity])) - Math.min(...b.findings.map((f) => order[f.severity])));
    const rows = bad.map((r) => `<tr><td>${esc(r.title)}${r.variant ? `<br><span class="muted">${esc(r.variant)}</span>` : ""}</td>
      <td class="n">${r.price ? Number(r.price).toLocaleString("de-DE", { style: "currency", currency: "EUR" }) : "–"}</td>
      <td>${r.findings.filter((f) => f.severity !== "info").map((f) => `<span class="${f.severity === "fehler" ? "" : "muted"}"><b>${esc(f.code)}</b> ${esc(f.message)}</span>`).join("<br>")}
      ${r.info.unit_price_text ? `<br><span class="muted">Richtig: ${esc(r.info.unit_price_text)}</span>` : ""}</td></tr>`).join("");
    out.innerHTML = `<section class="sheet" aria-live="polite">
      <span class="stamp ${color}">${stamp[0]}<small>${stamp[1]}</small></span>
      <h2>${esc(name)}</h2>
      <p class="muted">Erkannt: ${esc(j.mapping.Plattform)} · Name „${esc(j.mapping.Name)}“ · Preis „${esc(j.mapping.Preis)}“ · Hersteller „${esc(j.mapping["Hersteller/Marke"])}“ · Herstellerangaben: ${esc(j.mapping.Herstellerangaben)}</p>
      <p class="verdict">${s.errors ? `${s.errors} von ${s.products} Produkten mit Fehlern.` : `Keine Fehler in ${s.products} Produkten.`}</p>
      ${s.limited ? `<p class="note">Kostenlos werden die ersten ${FREE} von ${s.total} Produkten geprüft. Alle Produkte und den Export gibt es mit der <a href="../kanzlei/">Pro-Lizenz</a>.</p>` : ""}
      <dl class="figures">
        <div><dt>Geprüft</dt><dd>${s.products}</dd></div>
        <div><dt>Grundpreis fehlt/falsch</dt><dd>${s.grundpreis_missing}</dd></div>
        <div><dt>GPSR-Angaben fehlen</dt><dd>${s.gpsr_missing}</dd></div>
        <div><dt>Ohne Befund</dt><dd>${s.ok}</dd></div>
      </dl>
      ${rows ? `<div class="tbl"><table><thead><tr><th>Produkt</th><th class="n">Preis</th><th>Befund</th></tr></thead><tbody>${rows}</tbody></table></div>` : "<p>Alle geprüften Produkte sind in Ordnung.</p>"}
      <div class="actions"><button class="btn" type="button" id="shop-export">CSV mit berechneten Grundpreisen</button>
      <button class="btn ghost" type="button" onclick="window.print()">Bericht drucken / als PDF</button></div>
      <p class="muted">Automatisierte Prüfung, keine Rechtsberatung. Herstellerangaben, die Ihr Shop aus anderen Quellen anzeigt (Metafelder, Theme-Blöcke), sind im Export nicht enthalten und können als „fehlt“ erscheinen.</p>
    </section>`;
    $("#shop-export").addEventListener("click", async () => {
      if (!(await isPro())) { status.innerHTML = 'Der Export gehört zur <a href="../kanzlei/">Pro-Lizenz</a>. Lizenzschlüssel auf der <a href="../">Startseite</a> eingeben.'; return; }
      const csv = py.runPython("shop.export_fixed()");
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      a.download = name.replace(/\.csv$/i, "") + "_geprueft.csv"; document.body.appendChild(a); a.click(); setTimeout(() => a.remove(), 500);
    });
  }
})();
