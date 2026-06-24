#!/usr/bin/env bash
#
# generate-ai-context.sh
#
# Genere le fichier de contexte canonique consomme par Claude Code :
#   .claude/skills/project-context.md
#
# Stack detectee a l'initialisation : Shell (fallback).
# Aucun marqueur de stack (package.json / pyproject.toml / requirements.txt /
# Cargo.toml) n'a ete trouve a la racine. Ce script est un point de depart
# MINIMAL a adapter quand la stack reelle du projet sera connue.
#
# Usage :
#   bash scripts/generate-ai-context.sh
#
set -euo pipefail

# Racine du projet = dossier parent de ce script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

OUTPUT_DIR=".claude/skills"
OUTPUT_FILE="${OUTPUT_DIR}/project-context.md"

# Exclusions imposees par le skill init-ai-workspace.
EXCLUDES=(node_modules .git dist build .claude coverage)

# Construit l'expression -prune de find a partir de la liste d'exclusions.
build_prune_expr() {
  local first=1
  for dir in "${EXCLUDES[@]}"; do
    if [[ ${first} -eq 1 ]]; then
      printf -- '-name %s' "${dir}"
      first=0
    else
      printf -- ' -o -name %s' "${dir}"
    fi
  done
}

# --- Arborescence -----------------------------------------------------------
# Liste les fichiers et dossiers en respectant les exclusions ci-dessus.
generate_tree() {
  find . \
    \( $(build_prune_expr) \) -prune -o -print \
    | LC_ALL=C sort \
    | sed 's|^\./||' \
    | grep -v '^\.$' || true
}

# --- Dependances ------------------------------------------------------------
# Stack shell : aucune source de dependances declaree.
# TODO: adapter cette fonction quand la stack reelle sera connue
#       (ex. lire package.json, pyproject.toml, Cargo.toml...).
generate_dependencies() {
  echo "_Aucune dependance detectee (stack Shell). Section a completer manuellement._"
}

# --- Fichiers de configuration racine --------------------------------------
# TODO: ajuster la liste des patterns selon la stack reelle du projet.
generate_config_files() {
  local found=0
  local f
  for f in Makefile .editorconfig .env.example docker-compose.yml Dockerfile *.config.*; do
    if [[ -e "${f}" ]]; then
      echo "- \`${f}\`"
      found=1
    fi
  done
  if [[ ${found} -eq 0 ]]; then
    echo "_Aucun fichier de configuration racine reconnu._"
  fi
}

# --- Generation -------------------------------------------------------------
mkdir -p "${OUTPUT_DIR}"

{
  echo "# Contexte projet"
  echo
  echo "> Fichier genere automatiquement par \`scripts/generate-ai-context.sh\`."
  echo "> **Ne pas editer a la main** : toute modification sera ecrasee a la prochaine generation."
  echo
  echo "- **Date de generation :** $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- **Stack detectee :** Shell (fallback — a adapter)"
  echo "- **Commande de test :** Non detecte"
  echo
  echo "## Dependances"
  echo
  generate_dependencies
  echo
  echo "## Fichiers de configuration racine"
  echo
  generate_config_files
  echo
  echo "## Arborescence"
  echo
  echo '```'
  generate_tree
  echo '```'
} > "${OUTPUT_FILE}"

echo "Contexte genere : ${OUTPUT_FILE}"
