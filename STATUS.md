# État d'avancement — POC agent de relance

> Récapitulatif de ce qui est livré et de ce qui reste à faire.
> Dernière mise à jour : 2026-06-25.

---

## ✅ Fait

### Infrastructure (Phase A)
- `docker-compose.yml` : **Odoo 17 + PostgreSQL 15** (réseau dédié, volumes nommés, healthcheck, `platform: linux/amd64` pour WSL2).
- Base **`conserverie`** créée sans données de démo + **seed reproductible** (`docker/fixtures/create_invoices.py`) : 2 clients, 6 factures (brouillon, 2 payées, J+8 / J+20 / J+35).

### Agent Python (Phases B & C)
- Modules : `config`, `odoo_client` (XML-RPC, **lecture seule**), `models`, `relance_policy`, `ai_generator` (Claude), `main`.
- Classification du retard **J+7 / J+15 / J+30 → niveaux 1 / 2 / 3**.
- Génération des relances via l'**API Claude** (`claude-sonnet-4-6`), ton adapté au niveau, prompt **sans historique inventé** (fix #8).
- **31 tests pytest** (logique de relance, mapping, prompt, orchestration, rendus rich/HTML, streaming).
- CLI : `--dry-run` (sans appel IA), `--debug`, `--reference-date`, `--html [chemin]`, `--no-color`, `--no-stream`.

### Démo visuelle (A / B / C)
- **A — Console enrichie (`rich`)** : un panneau coloré par niveau (vert/orange/rouge) contenant le message, tableau de synthèse + total reste dû. Rendu injectable (`_PlainRenderer` conserve le texte brut historique) ; `rich` activé en terminal, repli auto sinon (`--no-color`).
- **B — Streaming « rédaction en direct »** : génération token par token (`generate_stream` + `rich.live`), active par défaut (`--no-stream` pour l'éteindre). **Validée en run live réel.**
- **C — Rapport HTML interactif** (`--html`, défaut `out/relances.html`) : fichier autonome **partageable** (CSS + JS inline). Bouton « Lancer l'agent » qui rejoue les coulisses (terminal animé : Odoo, analyse des retards, classification, rédaction IA) puis écrit les lettres une à une (effet de frappe). Rapport statique complet **sans JS** ; respecte `prefers-reduced-motion`. `out/` est gitignoré.

### Documentation & Git
- `README.md` (setup, exécution, dépannage, crédits API), `COLLABORATION.md`, `CLAUDE.md` + workspace context **Python**.
- Dépôt **GitHub public**, historique en **12 PR**, tags **`v0.1-demo`** et **`v0.1.1-demo`** sur `main` (fix prompt #8 promu via #10).

### Démo
- **Run live de bout en bout validé** : 3 relances générées (en streaming), ton différencié, montants/dates exacts (reste dû, pas le total) ; livrable `out/relances.html` régénéré avec le vrai contenu.

---

## 🔜 Reste à faire

### Court terme
- [x] ~~Promouvoir le fix prompt (PR #8) de `dev` → `main`~~ — fait (#10, tag `v0.1.1-demo`).
- [ ] Promouvoir la **démo visuelle (A/B/C)** de `dev` → `main` quand souhaité ; option : tag `v0.2-demo`.
- [ ] Ajouter ta **vraie clé Anthropic** dans `.env` sur la machine de démo (déjà fait sur la machine de dev).

### Phase 2 (hors périmètre actuel)
- [ ] **Envoi réel** des relances (SMTP).
- [ ] **Écriture dans Odoo** : tracer l'historique des relances (`account.move.line` / champ dédié) → permettrait au prompt de s'appuyer sur l'**historique réel** (lève la limite à l'origine du fix #8).
- [ ] **Scheduler** : exécution automatique périodique.
- [ ] **Dashboard web** de suivi.

### Industrialisation (nice to have)
- [ ] **CI GitHub Actions** : `pytest` sur chaque push/PR.
- [ ] Config **lint/format** (`black` + `ruff`).
- [ ] Gestion **multi-devise / multi-société**.
- [ ] Tests d'intégration Odoo automatisés (aujourd'hui validés manuellement via XML-RPC).

---

## ⚠️ Limites connues (assumées pour le POC)
- **Lecture seule** côté Odoo : aucun envoi, aucune écriture.
- **Pas de suivi d'historique** des relances : le niveau découle uniquement du retard.
- **Crédits API** Anthropic requis pour la génération (facturation à l'usage, distincte de l'abonnement Claude Pro).
