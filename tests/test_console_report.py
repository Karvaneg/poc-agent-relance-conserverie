"""Tests du rendu console enrichi (RichRenderer), sans terminal réel."""

from __future__ import annotations

import datetime
import io

from rich.console import Console

from src.console_report import RichRenderer
from src.models import Customer, Invoice
from src.relance_policy import LEVELS

REF = datetime.date(2026, 6, 25)


def _invoice(name: str, customer: str, residual: float, due: str) -> Invoice:
    return Invoice(
        id=1, name=name, customer=Customer(id=1, name=customer),
        amount_total=residual, amount_residual=residual, invoice_date=None,
        invoice_date_due=datetime.date.fromisoformat(due),
        payment_state="not_paid", currency="EUR",
    )


def _render() -> str:
    buf = io.StringIO()
    # force_terminal pour activer le rendu rich ; width fixe pour un wrap stable.
    console = Console(file=buf, force_terminal=True, width=100, color_system=None)
    r = RichRenderer(console)

    r.header(REF, 5, 2, 3)
    inv1 = _invoice("FAC/2026/00004", "Épicerie Le Panier", 1750.0, "2026-06-17")
    r.invoice(1, 2, inv1, LEVELS[1], 8)
    r.message("Bonjour, rappel courtois.")
    inv2 = _invoice("FAC/2026/00006", "Restaurant La Marée", 3200.0, "2026-05-21")
    r.invoice(2, 2, inv2, LEVELS[3], 35)
    r.message("Mise en demeure formelle.")
    r.footer()
    r.html_written("out/relances.html")
    return buf.getvalue()


def test_rich_render_contient_les_elements_cles() -> None:
    out = _render()

    assert "Agent de relance" in out
    assert "2026-06-25" in out
    # Entête : compteurs.
    assert "5 facture" in out and "à relancer" in out
    # Panneaux : références, clients, messages.
    for ref in ("FAC/2026/00004", "Épicerie Le Panier", "Bonjour, rappel courtois."):
        assert ref in out
    assert "Mise en demeure formelle." in out
    # Synthèse + montant total (1750 + 3200 = 4950, format FR).
    assert "Synthèse" in out
    assert "4 950,00 EUR" in out
    assert "out/relances.html" in out


def test_rich_dry_run_affiche_la_mention() -> None:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=100, color_system=None)
    r = RichRenderer(console)
    r.invoice(1, 1, _invoice("FAC/X", "Client", 10.0, "2026-06-01"), LEVELS[1], 24)
    r.dry_run()

    assert "dry-run" in buf.getvalue()
