# poc-agent-relance-conserverie

POC d'un agent IA (Claude via l'API Anthropic) qui automatise les **relances de factures impayées** pour une PME comptable équipée d'Odoo.

**Phase 1 (périmètre actuel) :** Odoo 17 tourne en local (Docker), un agent Python récupère les factures clients impayées et échues via XML-RPC, les classe par niveau de relance, génère un message personnalisé avec Claude, et **affiche** le résultat. **Aucun envoi réel, aucune écriture dans Odoo.**

> Documents de référence : [`.claude/skills/project-brief.md`](.claude/skills/project-brief.md) (le _quoi_) et [`.claude/skills/working-rules.md`](.claude/skills/working-rules.md) (le _comment travailler_).

---

## 1. Prérequis

| Outil         | Version   | Notes                                                               |
| ------------- | --------- | ------------------------------------------------------------------- |
| Docker Engine | récent    | Avec le plugin **Docker Compose v2** (`docker compose`, sans tiret) |
| Python        | **3.11+** | Pour l'agent (Phase B)                                              |
| WSL2          | (Windows) | Lancer Docker Desktop avec l'intégration WSL2 activée               |

Vérifier l'installation :

```bash
docker --version
docker compose version
python3 --version
```

> **WSL2 :** travaillez dans le système de fichiers Linux (`~/...`), **pas** dans `/mnt/c/...`. Les volumes Docker utilisés ici sont des volumes nommés (pas de bind-mount Windows), ce qui évite les problèmes de permissions et de performances. **Clonez le repo dans le home Linux WSL2** (ex. `~/poc-agent-relance`), pas dans `/mnt/c/...` (chemins Windows lents sur Docker → lag I/O, timeouts possibles).

```bash
# ✅ BON (dans le home Linux WSL2)
cd ~
git clone <url> poc-agent-relance
cd poc-agent-relance
docker compose -f docker/docker-compose.yml up -d

# ❌ MAUVAIS (depuis un chemin Windows monté)
cd /mnt/c/Users/.../poc-agent-relance   # lag I/O, timeouts possibles
docker compose -f docker/docker-compose.yml up -d
```

---

## 2. Setup Odoo (Docker)

Depuis la racine du projet :

```bash
docker compose -f docker/docker-compose.yml up -d
```

Cela démarre deux conteneurs : `conserverie_postgres` (PostgreSQL 15) et `conserverie_odoo` (Odoo 17). Odoo n'accepte les connexions qu'une fois Postgres sain (`healthcheck`).

Suivre le démarrage :

```bash
docker compose -f docker/docker-compose.yml logs -f odoo
```

Quand le log affiche `HTTP service (werkzeug) running on ...`, ouvrir :

> **http://localhost:8069**

> ⏳ Odoo peut afficher ce message **avant** d'être 100 % prêt côté UI. Si le Database Manager n'apparaît pas (page blanche ou timeout), attendre ~10 s de plus et **rafraîchir** la page.

### Création de la base

Au premier lancement, Odoo affiche le **Database Manager**. Renseigner :

| Champ              | Valeur                                                      |
| ------------------ | ----------------------------------------------------------- |
| Master Password    | (au choix — mot de passe maître Odoo)                       |
| Database Name      | **`conserverie`** (doit correspondre à `ODOO_DB` du `.env`) |
| Email              | **`admin`**                                                 |
| Password           | **`admin`**                                                 |
| Language / Country | Français / France                                           |
| **Demo data**      | ☑️ **cocher « Load demonstration data »**                   |

Cliquer sur **Create database**. Odoo initialise la base (~1 min) puis ouvre la session `admin` / `admin`.

> ℹ️ Les données de démo s'activent **ici**, via la case à cocher — il n'existe pas de variable d'environnement Docker pour ça.

### Configuration de l'agent

Préparer le fichier d'environnement de l'agent (Phase B) :

```bash
cp .env.example .env
# puis editer .env : renseigner ANTHROPIC_API_KEY (les valeurs Odoo conviennent par defaut)
```

---

## 3. Validation du setup

Avant d'écrire l'agent, vérifier que l'environnement est conforme aux hypothèses du brief :

- [ ] Les deux conteneurs tournent :
  ```bash
  docker compose -f docker/docker-compose.yml ps
  ```
- [ ] Odoo répond sur http://localhost:8069 et la session `admin` / `admin` fonctionne.
- [ ] La base **`conserverie`** existe (visible dans le Database Manager : `/web/database/manager`).
- [ ] Le module **`account` (Comptabilité / Facturation)** est installé : menu **Apps** → retirer le filtre « Apps » → chercher _Invoicing/Accounting_ → **Install** si absent (le module fournit le modèle `account.move`).
- [ ] Des factures clients de démo sont présentes : menu **Comptabilité → Clients → Factures**.
- [ ] **Au moins 1 facture client de démo existe.** Si la liste est vide, la base a probablement été créée **sans** cocher « Load demonstration data » : revenir au Database Manager (`/web/database/manager`), **supprimer** la base `conserverie`, puis la **recréer en cochant « Demo data »** (étape 2).

---

## 4. Données de test

Le POC est en **lecture seule**. Pour valider toute la chaîne (filtrage + classification + génération) avant la démo, créer **au moins 6 factures** couvrant les variantes du brief §4. Les factures « à relancer » sont réparties sur **2 clients** pour un rendu réaliste.

| #   | Client   | État / paiement            | Échéance | Attendu par l'agent                    |
| --- | -------- | -------------------------- | -------- | -------------------------------------- |
| 1   | Client A | Brouillon (`draft`)        | —        | **ignorée** (non comptabilisée)        |
| 2   | Client A | Payée (`paid`)             | —        | **ignorée**                            |
| 3   | Client B | Payée (`paid`)             | —        | **ignorée**                            |
| 4   | Client A | Impayée échue              | **J+8**  | relance **niveau 1** (courtois)        |
| 5   | Client B | Impayée échue              | **J+20** | relance **niveau 2** (ferme)           |
| 6   | Client B | Partiellement payée, échue | **J+35** | relance **niveau 3** (mise en demeure) |

> Calcul du retard : `aujourd'hui − date d'échéance`. Pour obtenir un retard précis (J+8, J+20, J+35), fixer la **date d'échéance** de la facture en conséquence (champ _Date d'échéance_ / `invoice_date_due`).

**Création d'une facture** (rappel) : Comptabilité → Clients → Factures → **Nouveau** → choisir le client, ajouter une ligne, définir la **date d'échéance**, puis **Confirmer** (passe en `posted`). Pour une facture « payée », utiliser **Enregistrer un paiement** ; pour « partiellement payée », enregistrer un paiement d'un montant inférieur au total.

> Pour la démo Phase 1 (1-2 semaines), la **création manuelle via l'UI suffit**. Pour rendre la démo **reproductible**, ces données pourront être scriptées plus tard via un stub `docker/fixtures/create_invoices.py` (optionnel en Phase A, utile en Phase B) :
>
> ```bash
> # (Phase B — a venir)
> python docker/fixtures/create_invoices.py --env .env
> ```

---

## 5. Commandes utiles

```bash
# Démarrer / arrêter (sans perdre les données)
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml stop

# Logs
docker compose -f docker/docker-compose.yml logs -f odoo
docker compose -f docker/docker-compose.yml logs -f postgres

# État des conteneurs
docker compose -f docker/docker-compose.yml ps

# Arrêt + suppression des conteneurs (les volumes/données SURVIVENT)
docker compose -f docker/docker-compose.yml down

# ⚠️ RESET COMPLET : supprime conteneurs ET volumes (base Odoo + Postgres effacées)
docker compose -f docker/docker-compose.yml down -v
```

> Après un `down -v`, tout est remis à zéro : il faudra recréer la base `conserverie` et les données de test (étapes 2 à 4).

---

## 6. Lancement du POC

> 🚧 **Phase B (à venir).** L'agent Python n'est pas encore implémenté.
>
> Une fois développé, le lancement ressemblera à :
>
> ```bash
> python -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt
> python -m src.main
> ```
>
> L'agent lira `.env`, se connectera à Odoo en XML-RPC, récupérera les factures impayées échues, les classera (niveaux 1/2/3) et affichera les messages de relance générés par Claude. Cette section sera complétée à la fin de la Phase B.
