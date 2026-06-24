# Collaboration avec Claude Code — journal de bord du POC

> Récit **curaté** de la construction du POC _agent de relance de factures impayées_
> (Odoo 17 → Claude), que j'ai **piloté** en binôme avec **Claude Code** (Anthropic).
> Ce document met en avant **ma démarche** : comment j'ai cadré, itéré, revu et
> arbitré — l'IA jouant le rôle d'un copilote senior que je dirige et challenge.

---

## 1. Ma façon de piloter la collaboration

Plutôt que de déléguer en bloc, j'ai **encadré le travail par des règles que j'ai
fait écrire puis affinées**, versionnées dans le dépôt
(`.claude/skills/project-brief.md`, `.claude/skills/working-rules.md`). Les principes
que j'ai imposés :

- **« Montre-moi avant de lancer »** — j'exige une validation de ma part avant toute
  action qui modifie l'état (fichier, commande, commit). Je revois chaque livrable.
- **Une étape à la fois** — j'ai fait construire l'agent **module par module**, en
  **validant chacun** avant d'autoriser le suivant.
- **Git à ma main** — j'ai défini le workflow : `main` stable, `dev` comme base de
  travail, **toute fonctionnalité sur une branche issue de `dev`**, commits atomiques.
- **Sécurité non négociable** — secrets dans un `.env` gitignoré, jamais en dur.
- **Périmètre tenu** — Odoo en **lecture seule** ; aucune dérive hors scope.

---

## 2. Mes itérations sur les fondations

Avant toute ligne de code, j'ai **itéré en profondeur sur les deux documents de
cadrage**, en demandant des ajouts précis passe après passe. Quelques exemples de
mes apports successifs :

- **Anticipation Phase 2** (SMTP, écriture Odoo, scheduler, dashboard) pour donner sa
  cohérence au design dès le départ.
- **Données de test** explicitées (6 factures, variantes payée/partielle/échue).
- **Gestion des erreurs** : `try/except` explicites, `exc_info=True`, pas de traceback
  brut côté utilisateur.
- **Validation d'une nouvelle dépendance** (stdlib d'abord, `pip show`, maintenance).
- **Validation au démarrage** : faire échouer tôt si une hypothèse Odoo n'est pas tenue.
- **Conventions de commit** illustrées par des exemples **BON / MAUVAIS**.
- **Format de remontée des blocages** (erreur → contexte → hypothèse → piste).

> Ces itérations montrent que **j'ai apporté la connaissance métier et le niveau
> d'exigence** ; l'IA a rédigé, mais le cap et la précision venaient de moi.

---

## 3. Ce que j'ai repéré et arbitré

La collaboration a eu de la valeur parce que **je n'ai rien pris pour argent
comptant** : j'ai relu, questionné, et plusieurs fois c'est **moi qui ai détecté
l'anomalie** avant de demander une investigation.

| Ce que j'ai repéré / demandé                                                                                                    | Ce qui en a découlé                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **« C'est bizarre, moi j'ai 4 factures non payées »** — j'ai remarqué un écart entre l'affichage Odoo et le résultat de l'agent | Investigation → les données de démo créaient des doublons → **j'ai décidé** de passer à un seed contrôlé et reproductible |
| **Incohérence « minimum 5 / liste de 6 »** dans la doc, repérée à la relecture                                                  | Correction immédiate                                                                                                      |
| **Choix de nommer les fichiers** pour éviter une collision avec le contexte auto-généré                                         | Organisation propre du `.claude/skills/`                                                                                  |
| **Décision du workflow Git** (création des branches `init` puis `dev`, règle « toujours brancher depuis `dev` »)                | Historique lisible, `main` protégée                                                                                       |
| **Cadrage du périmètre et de la deadline** (démo à courte échéance)                                                             | Priorisation : aller au plus court vers une démo présentable                                                              |

En parallèle, j'ai **tenu compte des alertes du copilote** quand elles étaient
justifiées et **tranché** : modèle Claude obsolète → bascule sur `claude-sonnet-4-6` ;
bug Odoo `KeyError: ir.http` → correction `POSTGRES_DB=postgres` ; confusion
abonnement Pro / crédits API → clarification. À chaque fois, **la décision était la
mienne**, prise sur la base d'un diagnostic argumenté.

---

## 4. Les étapes livrées

| Phase       | Contenu                                          | Mon rôle                     |
| ----------- | ------------------------------------------------ | ---------------------------- |
| **Cadrage** | Workspace, workflow Git, 2 docs de référence     | Direction + itérations       |
| **Phase A** | Infra Docker Odoo 17 + PostgreSQL 15 (WSL2)      | Validation à chaque fichier  |
| **Phase B** | Agent Python modulaire, **20 tests**             | Revue module par module      |
| **Phase C** | Génération des relances via l'API Claude         | Validation du flux et du ton |
| **Phase D** | README, **seed reproductible**, scénario de démo | Recette finale               |

**Architecture** que j'ai validée : I/O (Odoo, Claude) isolée dans des modules dédiés,
**logique métier de relance pure et testée** — d'où une suite de tests rapide et fiable.

---

## 5. Ce que cette collaboration démontre (de ma part)

- **Esprit critique** : je relis, je challenge, je détecte les incohérences.
- **Rigueur de pilotage** : validation continue, avancement maîtrisé, périmètre tenu.
- **Connaissance métier** : ce sont mes exigences qui ont façonné le cadrage et les
  règles.
- **Bon usage de l'IA** : je m'en sers comme d'un accélérateur encadré, pas d'une
  boîte noire — je garde la main sur les décisions.

---

## 6. Résultat

Un POC **fonctionnel et présentable** : Odoo 17 conteneurisé, un agent Python qui
récupère les factures impayées échues, les classe par niveau de relance et génère des
messages personnalisés via Claude — testé, documenté, reproductible. Le seul prérequis
restant pour la génération _live_ est l'ajout de crédits API (la chaîne complète tourne
déjà en mode `--dry-run`).

_Collaboration : Marie Le Carvennec × Claude Code (Anthropic)._
