"""Tests du rendu HTML (build_html + write_report), sans réseau."""

from __future__ import annotations

import datetime

from src.html_report import build_html, write_report
from src.models import Customer, Invoice
from src.relance_policy import LEVELS
from src.results import RelanceResult

REF = datetime.date(2026, 6, 25)


def _invoice(name: str, customer: str, residual: float, due: str) -> Invoice:
    return Invoice(
        id=1,
        name=name,
        customer=Customer(id=1, name=customer),
        amount_total=residual,
        amount_residual=residual,
        invoice_date=None,
        invoice_date_due=datetime.date.fromisoformat(due),
        payment_state="not_paid",
        currency="EUR",
    )


def _results() -> list[RelanceResult]:
    return [
        RelanceResult(_invoice("FAC/2026/00004", "Épicerie Le Panier", 1750.0, "2026-06-17"),
                      LEVELS[1], 8, message="Bonjour, petit rappel courtois."),
        RelanceResult(_invoice("FAC/2026/00006", "Restaurant La Marée", 3200.0, "2026-05-21"),
                      LEVELS[3], 35, message="Mise en demeure formelle."),
    ]


def test_build_html_contient_synthese_et_cartes() -> None:
    html = build_html(_results(), REF)

    assert "<!DOCTYPE html>" in html
    assert "2026-06-25" in html
    # Synthèse : nombre et total reste dû (1750 + 3200 = 4950, format FR).
    assert "2" in html
    assert "4 950,00 EUR" in html
    # Cartes : références, clients, niveaux, messages.
    for ref in ("FAC/2026/00004", "FAC/2026/00006", "Épicerie Le Panier", "Restaurant La Marée"):
        assert ref in html
    assert "Niveau 1" in html and "Niveau 3" in html
    assert "rappel courtois" in html and "Mise en demeure formelle" in html


def test_build_html_echappe_le_contenu() -> None:
    res = [RelanceResult(_invoice("FAC/X", "Café <script>", 10.0, "2026-06-01"),
                         LEVELS[1], 24, message="A & B <b>gras</b>")]
    html = build_html(res, REF)

    # Le contenu utilisateur ne doit jamais apparaître non échappé...
    assert "Café <script>" not in html
    assert "<b>gras</b>" not in html
    # ...mais sous sa forme échappée.
    assert "&lt;script&gt;" in html
    assert "A &amp; B" in html
    assert "&lt;b&gt;gras&lt;/b&gt;" in html


def test_build_html_dry_run_sans_message() -> None:
    res = [RelanceResult(_invoice("FAC/Y", "Client", 10.0, "2026-06-01"), LEVELS[1], 24)]
    html = build_html(res, REF)

    assert "dry-run" in html


def test_write_report_cree_le_fichier(tmp_path) -> None:
    target = tmp_path / "sub" / "relances.html"
    written = write_report(_results(), REF, target)

    assert written == target
    assert target.exists()
    assert "<!DOCTYPE html>" in target.read_text(encoding="utf-8")
