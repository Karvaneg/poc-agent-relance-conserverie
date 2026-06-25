"""Rendu HTML autonome et interactif des relances — livrable partageable.

Produit un fichier `.html` sans dépendance externe (CSS + JS inline, aucune
ressource à charger), pensé pour être ouvert tel quel dans un navigateur ou
transmis par mail.

Deux niveaux de lecture, par enrichissement progressif :
  - **Sans JavaScript** (ou à l'impression) : un rapport statique complet,
    bandeau de synthèse + une carte par relance.
  - **Avec JavaScript** : un bouton « Lancer l'agent » rejoue les coulisses
    (séquence type terminal : connexion Odoo, analyse des retards,
    classification, rédaction IA), puis révèle les lettres une à une, le texte
    s'écrivant en direct (effet de frappe).

Le rendu est purement présentationnel : il consomme des `RelanceResult` déjà
calculés et n'effectue aucune I/O réseau. Les données sont « gravées » dans le
fichier — aucun appel API au moment où le destinataire l'ouvre.
"""

from __future__ import annotations

import datetime
import html
from collections import Counter
from pathlib import Path
from typing import Iterable

from src.results import RelanceResult

# Couleur d'accent par niveau de relance (badge + bordure de carte).
_LEVEL_COLORS: dict[int, str] = {
    1: "#2e7d32",  # vert  — rappel courtois
    2: "#ef6c00",  # orange — relance ferme
    3: "#c62828",  # rouge — mise en demeure
}
_NEUTRAL = "#607d8b"


def _money(amount: float, currency: str) -> str:
    """Formate un montant à la française : ``1 750,00 EUR``."""
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}".strip()


def _summary_band(results: list[RelanceResult]) -> str:
    """Construit le bandeau de synthèse (totaux et répartition par niveau)."""
    total = sum(r.invoice.amount_residual for r in results)
    currency = results[0].invoice.currency if results else ""
    by_level = Counter(r.level.level for r in results)
    chips = "".join(
        f'<span class="chip" style="background:{_LEVEL_COLORS.get(lvl, _NEUTRAL)}">'
        f"Niveau {lvl} · {count}</span>"
        for lvl, count in sorted(by_level.items())
    )
    return (
        '<section class="summary">'
        f'<div class="metric"><span class="num">{len(results)}</span>'
        '<span class="lbl">facture(s) à relancer</span></div>'
        f'<div class="metric"><span class="num">{_money(total, currency)}</span>'
        '<span class="lbl">en souffrance (reste dû)</span></div>'
        f'<div class="chips">{chips}</div>'
        "</section>"
    )


def _terminal(results: list[RelanceResult], total_echues: int, ignored: int) -> str:
    """Construit les lignes des « coulisses » (séquence type terminal).

    Le texte est présent en clair dans le DOM (lisible sans JavaScript) ; le
    script le retape ensuite avec un effet de frappe.
    """
    # (kind, texte, durée de « travail » simulée en ms avant le ✓ — 0 = aucune)
    lines: list[tuple[str, str, int]] = [
        ("ok", "Connexion à Odoo (lecture seule)", 900),
        ("info", f"{total_echues} facture(s) échue(s) impayée(s) récupérée(s)", 0),
        ("ok", "Analyse des retards de paiement", 700),
    ]
    for r in results:
        lines.append(
            (
                "item",
                f"{r.invoice.name}   J+{r.days_overdue}   "
                f"→ Niveau {r.level.level} ({r.level.label})",
                0,
            )
        )
    if ignored:
        lines.append(("info", f"{ignored} facture(s) sous le seuil J+7 ignorée(s)", 0))
    lines.append(("ok", "Rédaction des relances par l'IA (Claude)", 2600))

    rows = []
    for kind, text, work in lines:
        prefix = {"ok": "→ ", "info": "→ ", "item": "    "}[kind]
        suffix = " ✓" if kind == "ok" else ""
        rows.append(
            f'<div class="t-line t-{kind}" data-work="{work}">'
            f"{html.escape(prefix + text + suffix)}</div>"
        )
    return '<pre class="terminal" aria-label="Coulisses du traitement">' + "\n".join(rows) + "</pre>"


def _card(result: RelanceResult) -> str:
    """Construit la carte d'une facture (entête + message ou état)."""
    inv = result.invoice
    color = _LEVEL_COLORS.get(result.level.level, _NEUTRAL)
    due = inv.invoice_date_due.isoformat() if inv.invoice_date_due else "—"

    if result.message:
        body = f'<div class="message">{html.escape(result.message)}</div>'
    elif result.error:
        body = f'<div class="message error">⚠ Génération impossible : {html.escape(result.error)}</div>'
    else:
        body = '<div class="message muted">(message non généré — mode dry-run)</div>'

    return (
        f'<article class="card" style="border-left-color:{color}">'
        '<header class="card-head">'
        f'<div><span class="ref">{html.escape(inv.name)}</span>'
        f'<span class="cust">{html.escape(inv.customer.name)}</span></div>'
        f'<span class="badge" style="background:{color}">Niveau {result.level.level}'
        f" · {html.escape(result.level.label)}</span>"
        "</header>"
        '<div class="meta">'
        f'<span><strong>{_money(inv.amount_residual, inv.currency)}</strong> dus</span>'
        f"<span>Échéance : {due}</span>"
        f"<span>Retard : J+{result.days_overdue}</span>"
        "</div>"
        f"{body}"
        "</article>"
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relances — conserverie-fde-2026</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         background: #f4f6f8; color: #1c2733; line-height: 1.5; }
  .wrap { max-width: 880px; margin: 0 auto; padding: 32px 20px 64px; }
  header.top h1 { margin: 0 0 4px; font-size: 1.6rem; }
  header.top .sub { color: #607d8b; font-size: .9rem; }

  .hero { display: none; flex-direction: column; align-items: center; gap: 10px;
          background: #fff; border-radius: 12px; padding: 36px 24px; margin: 24px 0;
          box-shadow: 0 1px 3px rgba(0,0,0,.08); text-align: center; }
  .hero p { margin: 0; color: #607d8b; }
  .btn { cursor: pointer; border: 0; border-radius: 999px; padding: 13px 30px;
         font-size: 1rem; font-weight: 700; color: #fff; background: #1565c0;
         box-shadow: 0 2px 8px rgba(21,101,192,.35); transition: transform .08s, background .2s; }
  .btn:hover { background: #0d47a1; }
  .btn:active { transform: scale(.97); }
  .btn:disabled { opacity: .5; cursor: default; }
  .controls { display: flex; gap: 10px; justify-content: center; margin: 8px 0 0; }
  .btn-light { background: #eceff1; color: #37474f; box-shadow: none; font-size: .85rem;
               padding: 7px 16px; }
  .btn-light:hover { background: #cfd8dc; }
  [hidden] { display: none !important; }

  .terminal { background: #0f1722; color: #cfe3f5; border-radius: 12px;
              padding: 18px 20px; margin: 24px 0; font-size: .86rem; line-height: 1.7;
              font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
              white-space: pre-wrap; overflow-wrap: anywhere; box-shadow: 0 1px 3px rgba(0,0,0,.2); }
  .t-line { margin: 0; min-height: 1.7em; }
  .t-ok { color: #8be59a; }
  .t-info { color: #9fb3c8; }
  .t-item { color: #ffd9a0; }
  .typing::after { content: "▋"; margin-left: 1px; animation: blink 1s steps(2) infinite; }
  @keyframes blink { 50% { opacity: 0; } }
  .spin { color: #ffd9a0; }

  .summary { display: flex; flex-wrap: wrap; gap: 24px; align-items: center;
             background: #fff; border-radius: 12px; padding: 20px 24px; margin: 24px 0;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .metric { display: flex; flex-direction: column; }
  .metric .num { font-size: 1.5rem; font-weight: 700; }
  .metric .lbl { color: #607d8b; font-size: .8rem; }
  .chips { display: flex; gap: 8px; margin-left: auto; flex-wrap: wrap; }
  .chip, .badge { color: #fff; border-radius: 999px; padding: 3px 12px;
                  font-size: .78rem; font-weight: 600; white-space: nowrap; }
  .card { background: #fff; border-radius: 12px; border-left: 5px solid #ccc;
          padding: 18px 22px; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .card-head .ref { font-weight: 700; margin-right: 10px; }
  .card-head .cust { color: #455a64; }
  .meta { display: flex; flex-wrap: wrap; gap: 18px; color: #546e7a;
          font-size: .85rem; margin: 10px 0 14px; }
  .message { white-space: pre-wrap; background: #fafbfc; border: 1px solid #eceff1;
             border-radius: 8px; padding: 14px 16px; font-size: .92rem; min-height: 1.4em; }
  .message.muted, .muted { color: #90a4ae; }
  .message.error { background: #fff3f3; border-color: #ffcdd2; color: #c62828; }
  footer { margin-top: 32px; color: #90a4ae; font-size: .78rem; text-align: center; }

  /* Mode interactif : le script masque le contenu statique et révèle le bouton. */
  body.js .hero { display: flex; }
  body.js .terminal, body.js .summary, body.js .card { display: none; }
  body.js .terminal.on, body.js .summary.on { display: block; }
  body.js .summary.on { display: flex; }
  body.js .card.on { display: block; opacity: 0; transform: translateY(10px);
                     transition: opacity .4s ease, transform .4s ease; }
  body.js .card.on.show { opacity: 1; transform: none; }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Agent de relance — conserverie-fde-2026</h1>
    <div class="sub">Date de référence : __REFDATE__ · POC : aucun envoi réel · généré le __GENAT__</div>
  </header>

  <div class="hero">
    <p>Démonstration : l'agent lit les factures impayées dans Odoo, classe les retards et rédige les relances.</p>
    <button class="btn" id="play">▶ Lancer l'agent</button>
    <div class="controls">
      <button class="btn btn-light" id="skip" hidden>⏭ Tout afficher</button>
      <button class="btn btn-light" id="replay" hidden>↻ Rejouer</button>
    </div>
  </div>

  __TERMINAL__
  __SUMMARY__
  __CARDS__

  <footer>Rapport généré automatiquement — relances rédigées par l'IA, à relire avant tout envoi.</footer>
</div>

<script>
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;  // accessibilité : on laisse le rapport statique complet.

  // --- Réglages de rythme (ms) — ajustables d'un coup d'œil ---------------
  var TERM_CHAR   = 30;   // frappe d'une ligne de terminal (par caractère)
  var TERM_PAUSE  = 480;  // pause entre deux lignes de terminal
  var MSG_CHAR    = 16;   // frappe du texte d'une lettre (par caractère)
  var BEFORE_CARDS = 700; // pause après le terminal, avant les lettres
  var BEFORE_MSG  = 450;  // pause entre l'apparition d'une carte et sa rédaction
  var AFTER_MSG   = 550;  // pause après chaque lettre
  var SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

  var body = document.body;
  var playBtn = document.getElementById("play");
  var skipBtn = document.getElementById("skip");
  var replayBtn = document.getElementById("replay");
  var terminal = document.querySelector(".terminal");
  var summary = document.querySelector(".summary");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
  var termLines = Array.prototype.slice.call(document.querySelectorAll(".t-line"));

  // Enrichissement progressif : on passe en mode interactif et on met le texte de côté.
  body.classList.add("js");
  function stash(el) { el.dataset.text = el.textContent; el.textContent = ""; }
  termLines.forEach(stash);
  cards.forEach(function (c) { var m = c.querySelector(".message"); if (m) stash(m); });

  var running = false, skipFlag = false;
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, skipFlag ? 0 : ms); }); };

  function typeInto(el, text, perTick) {
    el.classList.add("typing");
    var i = 0;
    return new Promise(function (resolve) {
      function tick() {
        if (skipFlag) { el.textContent = text; el.classList.remove("typing"); return resolve(); }
        i += 1;
        el.textContent = text.slice(0, i);
        if (i >= text.length) { el.classList.remove("typing"); return resolve(); }
        setTimeout(tick, perTick);
      }
      tick();
    });
  }

  // Affiche un spinner animé pendant `ms`, comme un appel réseau en cours.
  function workPause(el, base, ms) {
    if (skipFlag || ms <= 0) { el.textContent = base + " ✓"; return Promise.resolve(); }
    el.textContent = base + " ";
    var span = document.createElement("span");
    span.className = "spin";
    el.appendChild(span);
    var f = 0;
    var id = setInterval(function () { span.textContent = SPIN_FRAMES[f++ % SPIN_FRAMES.length]; }, 90);
    return new Promise(function (resolve) {
      setTimeout(function () {
        clearInterval(id);
        el.textContent = base + " ✓";
        resolve();
      }, ms);
    });
  }

  function revealAllInstantly() {
    terminal && terminal.classList.add("on");
    termLines.forEach(function (l) { l.textContent = l.dataset.text; });
    summary && summary.classList.add("on");
    cards.forEach(function (c) {
      c.classList.add("on", "show");
      var m = c.querySelector(".message");
      if (m) m.textContent = m.dataset.text;
    });
  }

  async function play() {
    if (running) return;
    running = true; skipFlag = false;
    playBtn.disabled = true; replayBtn.hidden = true; skipBtn.hidden = false;

    // Réinitialise (utile au rejeu).
    terminal && terminal.classList.remove("on");
    termLines.forEach(function (l) { l.textContent = ""; l.classList.remove("typing"); });
    summary && summary.classList.remove("on");
    cards.forEach(function (c) { c.classList.remove("on", "show");
      var m = c.querySelector(".message"); if (m) { m.textContent = ""; } });

    terminal && terminal.classList.add("on");
    for (var k = 0; k < termLines.length; k++) {
      var line = termLines[k];
      var full = line.dataset.text || "";
      var work = parseInt(line.dataset.work || "0", 10);
      if (work > 0) {
        // Étape « travail » : on tape le libellé sans le ✓, on patiente, puis on valide.
        var base = full.replace(/ ✓\s*$/, "");
        await typeInto(line, base, TERM_CHAR);
        await workPause(line, base, work);
      } else {
        await typeInto(line, full, TERM_CHAR);
      }
      await sleep(TERM_PAUSE);
    }
    await sleep(BEFORE_CARDS);

    summary && summary.classList.add("on");
    for (var j = 0; j < cards.length; j++) {
      var card = cards[j];
      card.classList.add("on");
      void card.offsetWidth;            // force le reflow pour l'anim d'entrée
      card.classList.add("show");
      await sleep(BEFORE_MSG);
      var msg = card.querySelector(".message");
      if (msg && msg.dataset.text) { await typeInto(msg, msg.dataset.text, MSG_CHAR); }
      await sleep(AFTER_MSG);
    }

    running = false; skipFlag = false;
    playBtn.disabled = false; skipBtn.hidden = true; replayBtn.hidden = false;
  }

  playBtn.addEventListener("click", play);
  replayBtn.addEventListener("click", play);
  skipBtn.addEventListener("click", function () {
    if (!running) return;
    skipFlag = true; revealAllInstantly();
  });
})();
</script>
</body>
</html>
"""


def build_html(
    results: list[RelanceResult],
    reference_date: datetime.date,
    *,
    total_echues: int | None = None,
    ignored: int = 0,
) -> str:
    """Assemble le document HTML complet (statique + interactif) à partir des résultats.

    Args:
        results: Les relances à présenter (peut être vide).
        reference_date: Date de référence affichée dans l'entête.
        total_echues: Nombre total de factures échues récupérées (pour les
            coulisses). Par défaut : ``len(results) + ignored``.
        ignored: Nombre de factures échues sous le seuil J+7 (coulisses).

    Returns:
        Le document HTML sous forme de chaîne.
    """
    if total_echues is None:
        total_echues = len(results) + ignored
    cards = "\n".join(_card(r) for r in results) or '<p class="muted">Aucune facture à relancer.</p>'
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        _TEMPLATE.replace("__REFDATE__", reference_date.isoformat())
        .replace("__GENAT__", generated_at)
        .replace("__TERMINAL__", _terminal(results, total_echues, ignored))
        .replace("__SUMMARY__", _summary_band(results))
        .replace("__CARDS__", cards)
    )


def write_report(
    results: Iterable[RelanceResult],
    reference_date: datetime.date,
    path: Path,
    *,
    total_echues: int | None = None,
    ignored: int = 0,
) -> Path:
    """Écrit le rapport HTML sur disque (crée le dossier parent au besoin).

    Args:
        results: Les relances à présenter.
        reference_date: Date de référence affichée dans l'entête.
        path: Chemin du fichier de sortie.
        total_echues: Nombre total de factures échues (coulisses).
        ignored: Nombre de factures sous le seuil J+7 (coulisses).

    Returns:
        Le chemin écrit (pour affichage à l'appelant).
    """
    results = list(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        build_html(results, reference_date, total_echues=total_echues, ignored=ignored),
        encoding="utf-8",
    )
    return path
