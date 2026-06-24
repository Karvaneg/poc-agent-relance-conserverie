"""Accès en lecture seule à Odoo via XML-RPC.

Ce module encapsule toute la communication réseau avec Odoo. Il ne contient
aucune logique métier de relance (celle-ci vit dans `relance_policy.py`) ni
aucun appel à l'API Claude. Il expose la récupération des factures clients
impayées et échues, à partir du modèle standard `account.move`.

Le POC est strictement en lecture : aucune méthode n'écrit dans Odoo.
"""

from __future__ import annotations

import datetime
import logging
import xmlrpc.client
from typing import Any

from src.config import Settings

logger = logging.getLogger(__name__)

# Champs lus sur account.move (cf. hypothèses Odoo du brief, section 4).
INVOICE_FIELDS = [
    "id",
    "name",
    "partner_id",
    "amount_total",
    "amount_residual",
    "invoice_date",
    "invoice_date_due",
    "payment_state",
    "currency_id",
]


class OdooError(RuntimeError):
    """Levée pour toute erreur de connexion ou de requête Odoo."""


class OdooClient:
    """Client XML-RPC en lecture seule pour Odoo.

    La construction n'effectue aucune I/O ; appeler `connect()` avant toute
    autre méthode.

    Attributes:
        settings: Configuration applicative (URL, base, identifiants).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._uid: int | None = None
        self._common: xmlrpc.client.ServerProxy | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    # -- Connexion -----------------------------------------------------------

    def connect(self) -> None:
        """Authentifie le client auprès d'Odoo.

        Raises:
            OdooError: Si l'endpoint est injoignable ou l'authentification refusée.
        """
        url = self.settings.odoo_url
        try:
            self._common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
            uid = self._common.authenticate(
                self.settings.odoo_db,
                self.settings.odoo_login,
                self.settings.odoo_password,
                {},
            )
        except Exception as exc:  # noqa: BLE001 - on remonte un message clair
            raise OdooError(f"Connexion à Odoo impossible ({url}) : {exc}") from exc

        if not uid:
            raise OdooError(
                "Authentification Odoo refusée "
                f"(db={self.settings.odoo_db}, login={self.settings.odoo_login}). "
                "Vérifier les identifiants (login = email saisi à la création de la base)."
            )

        self._uid = uid
        self._models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        logger.info("Connecté à Odoo (db=%s, uid=%s)", self.settings.odoo_db, uid)

    def _execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        """Exécute un appel `execute_kw`, en validant que la connexion est établie."""
        if self._uid is None or self._models is None:
            raise OdooError("Client non connecté : appeler connect() d'abord.")
        try:
            return self._models.execute_kw(
                self.settings.odoo_db,
                self._uid,
                self.settings.odoo_password,
                model,
                method,
                list(args),
                kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise OdooError(f"Échec de l'appel Odoo {model}.{method} : {exc}") from exc

    # -- Validation des hypothèses ------------------------------------------

    def check_environment(self) -> None:
        """Vérifie que les hypothèses du brief sont satisfaites.

        Contrôle la présence du modèle `account.move` et des champs exploités,
        afin d'échouer tôt avec un message explicite plutôt que de laisser une
        erreur survenir en cours d'exécution.

        Raises:
            OdooError: Si le modèle ou un champ requis est absent (module
                `account` non installé, version Odoo incompatible…).
        """
        try:
            available = self._execute("account.move", "fields_get", [], {"attributes": []})
        except OdooError as exc:
            raise OdooError(
                "Modèle 'account.move' inaccessible : le module 'account' "
                "(Comptabilité/Facturation) est-il installé ?"
            ) from exc

        missing = [field for field in INVOICE_FIELDS if field not in available]
        if missing:
            raise OdooError(
                "Champs absents sur account.move : "
                + ", ".join(missing)
                + " (version Odoo incompatible avec les hypothèses du brief ?)."
            )
        logger.info("Environnement Odoo validé (account.move + champs requis présents).")

    # -- Lecture des factures ------------------------------------------------

    def fetch_unpaid_invoices(
        self, reference_date: datetime.date | None = None
    ) -> list[dict[str, Any]]:
        """Récupère les factures clients impayées et échues.

        Domaine appliqué (cf. brief section 4) :
        facture client (`out_invoice`) comptabilisée (`posted`), non soldée
        (`payment_state` ∈ {not_paid, partial}), d'échéance antérieure à la date
        de référence.

        Args:
            reference_date: Date servant de « aujourd'hui » pour le calcul de
                l'échéance. Par défaut, la date du jour.

        Returns:
            La liste des factures (dictionnaires des champs `INVOICE_FIELDS`),
            triées par échéance croissante (la plus ancienne d'abord).
        """
        today = (reference_date or datetime.date.today()).isoformat()
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("invoice_date_due", "<", today),
        ]
        invoices = self._execute(
            "account.move",
            "search_read",
            domain,
            fields=INVOICE_FIELDS,
            order="invoice_date_due asc",
        )
        logger.info("%d facture(s) impayée(s) échue(s) récupérée(s).", len(invoices))
        return invoices
