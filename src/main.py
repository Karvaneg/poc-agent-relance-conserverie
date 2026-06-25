"""Point d'entrée du POC : orchestration et affichage.

Enchaîne la récupération des factures impayées (Odoo, lecture seule), leur
classification par niveau de relance, la génération des messages via Claude, et
l'affichage du résultat en console.

Phase 1 : aucun envoi réel, aucune écriture dans Odoo.

Usage :
    python -m src.main                 # cycle complet (necessite des credits API)
    python -m src.main --dry-run       # tout sauf l'appel Claude (classification seule)
    python -m src.main --debug         # affiche les tracebacks complets en cas d'erreur
    python -m src.main --reference-date 2026-06-25
    python -m src.main --html          # ecrit aussi un rapport HTML (out/relances.html)
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path
from typing import Callable

from src.ai_generator import AiGenerator
from src.config import ConfigError, Settings, load_settings
from src.html_report import write_report
from src.models import Invoice
from src.odoo_client import OdooClient, OdooError
from src.relance_policy import RelanceLevel, relance_for
from src.results import RelanceResult

_DEFAULT_HTML_PATH = "out/relances.html"

logger = logging.getLogger(__name__)

_SEP = "─" * 64
_DSEP = "═" * 64


def _format_header(reference_date: datetime.date, total_echues: int, n_relance: int) -> str:
    return (
        f"{_DSEP}\n"
        f"  Agent de relance — conserverie-fde-2026\n"
        f"  Date de référence : {reference_date.isoformat()}   |   POC : aucun envoi réel\n"
        f"{_DSEP}\n\n"
        f"{total_echues} facture(s) impayée(s) échue(s) — {n_relance} à relancer (≥ J+7).\n"
    )


def _format_invoice_header(index: int, total: int, inv: Invoice, level: RelanceLevel, retard: int) -> str:
    return (
        f"\n{_SEP}\n"
        f"[{index}/{total}] {inv.name} · {inv.customer.name}\n"
        f"      Reste dû : {inv.amount_residual:.2f} {inv.currency}"
        f" · Échéance : {inv.invoice_date_due} · Retard : J+{retard}\n"
        f"      Niveau {level.level} — {level.label}\n"
        f"{_SEP}"
    )


class _PlainRenderer:
    """Rendu texte brut (comportement historique) — écrit via une fonction `out`.

    Reproduit à l'identique l'affichage d'origine ; sert de rendu par défaut et
    de cible pour les tests. Le contrat est partagé avec `RichRenderer`.
    """

    def __init__(self, out: Callable[[str], None]) -> None:
        self._out = out

    def header(self, today: datetime.date, total_echues: int, to_count: int, ignored: int) -> None:
        self._out(_format_header(today, total_echues, to_count))
        if ignored:
            self._out(f"({ignored} facture(s) échue(s) sous le seuil < J+7, ignorée(s).)\n")

    def invoice(self, index: int, total: int, inv: Invoice, level: RelanceLevel, retard: int) -> None:
        self._out(_format_invoice_header(index, total, inv, level, retard))

    def message(self, text: str) -> None:
        self._out(text)

    def dry_run(self) -> None:
        self._out("(génération IA ignorée — mode --dry-run)")

    def error(self, inv: Invoice, exc: Exception) -> None:
        self._out(f"[!] Génération impossible pour {inv.name} : {exc}")

    def footer(self) -> None:
        self._out(f"\n{_DSEP}")

    def html_written(self, path: object) -> None:
        self._out(f"\nRapport HTML écrit : {path}")


def run(
    settings: Settings,
    *,
    odoo_client: OdooClient | None = None,
    generator: AiGenerator | None = None,
    reference_date: datetime.date | None = None,
    generate: bool = True,
    out: Callable[[str], None] = print,
    html_path: Path | None = None,
    renderer: object | None = None,
) -> int:
    """Exécute un cycle de relance et affiche le résultat.

    Args:
        settings: Configuration validée.
        odoo_client: Client Odoo (injecté pour les tests).
        generator: Générateur IA (injecté pour les tests).
        reference_date: Date de référence pour le calcul des retards.
        generate: Si False, saute l'appel à Claude (mode dry-run).
        out: Fonction d'affichage du rendu texte brut (par défaut / tests).
        html_path: Si fourni, écrit aussi un rapport HTML à ce chemin.
        renderer: Rendu console à utiliser ; par défaut un `_PlainRenderer`
            écrivant via `out`. `main` y injecte un `RichRenderer` en terminal.

    Returns:
        Le nombre de factures à relancer.
    """
    today = reference_date or datetime.date.today()
    rnd = renderer if renderer is not None else _PlainRenderer(out)

    client = odoo_client or OdooClient(settings)
    client.connect()
    client.check_environment()

    invoices = [Invoice.from_odoo(record) for record in client.fetch_unpaid_invoices(today)]
    items = [(inv, relance_for(inv, today)) for inv in invoices]
    to_relance = [(inv, level) for inv, level in items if level is not None]
    ignored = len(items) - len(to_relance)

    rnd.header(today, len(items), len(to_relance), ignored)

    gen = generator if generator is not None else (AiGenerator(settings) if generate and to_relance else None)

    results: list[RelanceResult] = []
    for index, (inv, level) in enumerate(to_relance, start=1):
        retard = (today - inv.invoice_date_due).days if inv.invoice_date_due else 0
        rnd.invoice(index, len(to_relance), inv, level, retard)
        if not generate:
            rnd.dry_run()
            results.append(RelanceResult(inv, level, retard))
            continue
        try:
            message = gen.generate(inv, level, today)  # type: ignore[union-attr]
            rnd.message(message)
            results.append(RelanceResult(inv, level, retard, message=message))
        except Exception as exc:  # noqa: BLE001 - on isole l'echec d'une facture
            logger.error("Échec de génération pour %s", inv.name, exc_info=True)
            rnd.error(inv, exc)
            results.append(RelanceResult(inv, level, retard, error=str(exc)))

    rnd.footer()

    if html_path is not None:
        written = write_report(results, today, html_path, total_echues=len(items), ignored=ignored)
        rnd.html_written(written)

    return len(to_relance)


def _make_console_renderer(*, no_color: bool) -> object | None:
    """Choisit le rendu console : `RichRenderer` en terminal, sinon texte brut.

    Renvoie None (→ `_PlainRenderer`) si `--no-color`, si la sortie n'est pas un
    terminal (redirection/pipe), ou si `rich` n'est pas disponible.
    """
    if no_color or not sys.stdout.isatty():
        return None
    try:
        from src.console_report import RichRenderer
    except ImportError:
        return None
    return RichRenderer()


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI.

    Returns:
        Code de sortie (0 succès, 1 erreur de configuration ou d'accès Odoo).
    """
    parser = argparse.ArgumentParser(description="Agent de relance de factures impayées (POC).")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas appeler Claude (classification seule).")
    parser.add_argument("--debug", action="store_true", help="Afficher les tracebacks complets.")
    parser.add_argument("--reference-date", help="Date de référence YYYY-MM-DD (defaut : aujourd'hui).")
    parser.add_argument(
        "--html",
        nargs="?",
        const=_DEFAULT_HTML_PATH,
        default=None,
        metavar="CHEMIN",
        help=f"Écrire un rapport HTML partageable (défaut : {_DEFAULT_HTML_PATH}).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Désactiver l'affichage enrichi (rich) et forcer le texte brut.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    try:
        settings = load_settings()
        reference_date = (
            datetime.date.fromisoformat(args.reference_date) if args.reference_date else None
        )
        run(
            settings,
            reference_date=reference_date,
            generate=not args.dry_run,
            html_path=Path(args.html) if args.html else None,
            renderer=_make_console_renderer(no_color=args.no_color),
        )
        return 0
    except (ConfigError, OdooError) as exc:
        # Erreurs attendues : message clair, pas de traceback (sauf --debug).
        if args.debug:
            logger.exception("Erreur")
        print(f"\n[ERREUR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
