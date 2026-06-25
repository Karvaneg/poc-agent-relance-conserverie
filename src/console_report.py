"""Rendu console enrichi (rich) — pour une démo terminal lisible et colorée.

Alternative au rendu texte brut de `main`. Affiche un entête, un panneau par
relance (bordure colorée selon le niveau : vert / orange / rouge) contenant le
message, puis un tableau de synthèse. Le contrat (méthodes appelées par
`main.run`) est volontairement identique à celui du rendu brut, de sorte que
l'un ou l'autre soit injectable sans toucher à la logique.

Aucune I/O réseau : ce module ne fait qu'afficher des `RelanceResult` calculés
en amont.
"""

from __future__ import annotations

import datetime
from collections import Counter
from contextlib import contextmanager
from typing import Callable, Iterator

from rich import box
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.models import Invoice
from src.relance_policy import LEVELS, RelanceLevel

# Style rich par niveau de relance (bordure de panneau + libellés du tableau).
_LEVEL_STYLE: dict[int, str] = {1: "green", 2: "dark_orange", 3: "red"}
_NEUTRAL = "grey50"


def _money(amount: float, currency: str) -> str:
    """Formate un montant à la française : ``1 750,00 EUR``."""
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}".strip()


class RichRenderer:
    """Rendu console coloré via `rich`. Accumule les compteurs pour la synthèse."""

    def __init__(self, console: Console | None = None) -> None:
        # highlight=False : on neutralise le surligneur auto de rich (qui
        # colorerait au hasard mots et nombres) ; le balisage explicite reste actif.
        self.console = console or Console(highlight=False)
        self._counts: Counter[int] = Counter()
        self._total = 0.0
        self._currency = ""
        self._pending: tuple[int, int, Invoice, RelanceLevel, int] | None = None

    def header(
        self,
        today: datetime.date,
        total_echues: int,
        to_count: int,
        ignored: int,
    ) -> None:
        self.console.print()
        self.console.rule("[bold]Agent de relance — conserverie-fde-2026[/]")
        self.console.print(
            f"Date de référence : {today.isoformat()}   ·   POC : aucun envoi réel",
            style="dim",
        )
        line = f"{total_echues} facture(s) échue(s) impayée(s) — [bold]{to_count}[/] à relancer (≥ J+7)"
        if ignored:
            line += f"   ·   {ignored} ignorée(s) (< J+7)"
        self.console.print(line)

    def invoice(
        self,
        index: int,
        total: int,
        inv: Invoice,
        level: RelanceLevel,
        retard: int,
    ) -> None:
        self._pending = (index, total, inv, level, retard)
        self._counts[level.level] += 1
        self._total += inv.amount_residual
        self._currency = inv.currency

    def _make_panel(self, body: Text, *, style: str) -> Panel:
        assert self._pending is not None
        index, total, inv, level, retard = self._pending
        title = f"[{index}/{total}] {escape(inv.name)} · {escape(inv.customer.name)}"
        subtitle = (
            f"Niveau {level.level} — {escape(level.label)}  ·  "
            f"{_money(inv.amount_residual, inv.currency)} dus  ·  J+{retard}"
        )
        return Panel(
            body,
            title=title,
            subtitle=subtitle,
            title_align="left",
            subtitle_align="left",
            border_style=style,
            padding=(1, 2),
        )

    def _panel(self, body: Text, *, style: str) -> None:
        self.console.print()
        self.console.print(self._make_panel(body, style=style))

    def message(self, text: str) -> None:
        assert self._pending is not None
        level = self._pending[3]
        self._panel(Text(text), style=_LEVEL_STYLE.get(level.level, _NEUTRAL))

    @contextmanager
    def message_stream(self) -> Iterator[Callable[[str], None]]:
        """Affiche un panneau qui se remplit en direct au fil du streaming.

        Cède un callback `feed(delta)` ; chaque fragment reçu agrandit le texte
        du panneau, redessiné en place via `rich.live.Live`. Le dernier état
        reste affiché à la sortie du contexte.
        """
        assert self._pending is not None
        level = self._pending[3]
        style = _LEVEL_STYLE.get(level.level, _NEUTRAL)
        buf: list[str] = []
        self.console.print()
        with Live(self._make_panel(Text(""), style=style), console=self.console,
                  refresh_per_second=16, transient=False) as live:
            def feed(delta: str) -> None:
                buf.append(delta)
                live.update(self._make_panel(Text("".join(buf)), style=style))
            yield feed

    def dry_run(self) -> None:
        self._panel(Text("(génération IA ignorée — mode --dry-run)", style="dim italic"), style=_NEUTRAL)

    def error(self, inv: Invoice, exc: Exception) -> None:
        self._panel(Text(f"Génération impossible : {exc}", style="red"), style="red")

    def footer(self) -> None:
        table = Table(box=box.SIMPLE, title="Synthèse", title_style="bold", title_justify="left")
        table.add_column("Niveau")
        table.add_column("Libellé")
        table.add_column("Nb", justify="right")
        for lvl in sorted(self._counts):
            style = _LEVEL_STYLE.get(lvl, _NEUTRAL)
            table.add_row(f"[{style}]Niveau {lvl}[/]", LEVELS[lvl].label, str(self._counts[lvl]))
        self.console.print()
        self.console.print(table)
        total_n = sum(self._counts.values())
        self.console.print(
            f"[bold]{total_n}[/] relance(s)  ·  "
            f"[bold]{_money(self._total, self._currency)}[/] en souffrance (reste dû)"
        )

    def html_written(self, path: object) -> None:
        self.console.print(f"\n📄 Rapport HTML écrit : [cyan]{path}[/]")
