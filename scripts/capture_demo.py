"""Génère des captures de l'agent en fonctionnement (pour la candidature / la démo).

Lance un cycle de relance réel (Odoo en lecture seule + API Claude) en enregistrant
la sortie console enrichie, puis l'exporte en **SVG** et **HTML** — un « screenshot »
de terminal propre et reproductible, sans capture manuelle. Le rapport HTML
interactif est produit au passage.

Artefacts écrits dans ``out/captures/`` (dossier ignoré par git) :
    - agent-console.svg   : rendu terminal coloré (panneaux par niveau + synthèse)
    - agent-console.html  : même rendu, en HTML
    - ../relances.html    : le rapport HTML interactif partageable

Usage :
    python scripts/capture_demo.py                      # date du jour
    python scripts/capture_demo.py --reference-date 2026-06-25
    python scripts/capture_demo.py --dry-run            # sans appel IA (gratuit)
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

# Permet `python scripts/capture_demo.py` depuis la racine du projet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console

from src.config import load_settings
from src.console_report import RichRenderer
from src.main import run

_CAPTURES_DIR = Path("out/captures")
_HTML_REPORT = Path("out/relances.html")
_TITLE = "Agent de relance — conserverie-fde-2026"


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture l'agent de relance en fonctionnement.")
    parser.add_argument("--reference-date", help="Date de référence YYYY-MM-DD (défaut : aujourd'hui).")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas appeler Claude (capture gratuite).")
    parser.add_argument("--width", type=int, default=100, help="Largeur du terminal capturé (défaut : 100).")
    args = parser.parse_args()

    reference_date = (
        datetime.date.fromisoformat(args.reference_date) if args.reference_date else None
    )

    # Console enregistreuse : force_terminal pour activer les couleurs hors TTY,
    # highlight=False pour neutraliser le surligneur automatique.
    console = Console(record=True, force_terminal=True, width=args.width, highlight=False)
    renderer = RichRenderer(console)

    settings = load_settings()
    # stream=False : on veut un rendu statique complet (le SVG est une image fixe).
    run(
        settings,
        reference_date=reference_date,
        generate=not args.dry_run,
        renderer=renderer,
        stream=False,
        html_path=_HTML_REPORT,
    )

    _CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = _CAPTURES_DIR / "agent-console.svg"
    html_path = _CAPTURES_DIR / "agent-console.html"
    console.save_svg(str(svg_path), title=_TITLE, clear=False)
    console.save_html(str(html_path), clear=False)

    print()
    print(f"✓ Capture SVG  : {svg_path.resolve()}")
    print(f"✓ Capture HTML : {html_path.resolve()}")
    print(f"✓ Rapport      : {_HTML_REPORT.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
