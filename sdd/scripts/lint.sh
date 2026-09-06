#!/usr/bin/env bash
set -uo pipefail

# Structural lint for every plugin in this marketplace. Checks file
# existence, frontmatter shape, leftover paste markers, version consistency,
# and that each build-opencode.sh is deterministic.
#
# This checks STRUCTURE, not BEHAVIOR. A clean run means the plugins' files
# are internally consistent; it says nothing about whether a skill does the
# right thing when invoked. It is a pre-commit sanity check, not a substitute
# for exercising a skill for real.
#
# The plugin list is read from .claude-plugin/marketplace.json, so a new
# plugin is covered as soon as it is registered there.
#
# Run from the repo root: bash sdd/scripts/lint.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

shopt -s nullglob

FAIL=0
fail() { echo "FAIL: $1"; FAIL=1; }
pass() { echo "ok: $1"; }

# Plugin directories, read from the marketplace manifest's "source" fields.
PLUGINS=()
while IFS= read -r plugin_dir; do
  [[ -n "$plugin_dir" ]] || continue
  if [[ -d "$plugin_dir" ]]; then
    PLUGINS+=("$plugin_dir")
  else
    fail ".claude-plugin/marketplace.json: source '$plugin_dir' is not a directory"
  fi
done < <(grep -oE '"source": *"\./[A-Za-z0-9_-]+"' .claude-plugin/marketplace.json \
           | sed -E 's/.*"\.\/([A-Za-z0-9_-]+)"/\1/')

if [[ "${#PLUGINS[@]}" == 0 ]]; then
  fail "no plugins found in .claude-plugin/marketplace.json"
else
  pass "plugins discovered: ${PLUGINS[*]}"
fi

# Collect every skill and agent file across all plugins. nullglob makes an
# empty skills/ or a missing agents/ contribute nothing rather than a literal
# unexpanded glob, so a scaffold plugin with no skills yet is valid.
# Empty arrays are expanded as ${arr[@]+"${arr[@]}"} throughout, because this
# script runs under `set -u` on bash 3.2, where a bare "${arr[@]}" on an empty
# array is an unbound-variable error.
SKILL_FILES=()
AGENT_FILES=()
for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
  for f in "$plugin_dir"/skills/*/SKILL.md; do SKILL_FILES+=("$f"); done
  for f in "$plugin_dir"/agents/*.md; do AGENT_FILES+=("$f"); done
done

# 1. Every SKILL.md has valid frontmatter with name and description
for skill_file in ${SKILL_FILES[@]+"${SKILL_FILES[@]}"}; do
  if ! head -1 "$skill_file" | grep -q '^---$'; then
    fail "$skill_file: missing frontmatter opening ---"
    continue
  fi
  frontmatter=$(awk '/^---$/{n++; next} n==1' "$skill_file")
  echo "$frontmatter" | grep -q '^name:' || fail "$skill_file: frontmatter missing 'name'"
  echo "$frontmatter" | grep -q '^description:' || fail "$skill_file: frontmatter missing 'description'"
done
pass "SKILL.md frontmatter checked"

# 2. Every \${CLAUDE_SKILL_DIR} or \${CLAUDE_PLUGIN_ROOT} reference resolves to a real file.
#    \${CLAUDE_SKILL_DIR} is the skill's own directory; \${CLAUDE_PLUGIN_ROOT} is the whole
#    plugin's directory (two levels up: skills/<skill>/SKILL.md -> plugin root).
for skill_file in ${SKILL_FILES[@]+"${SKILL_FILES[@]}"}; do
  skill_dir="$(dirname "$skill_file")"
  plugin_dir="$(dirname "$(dirname "$skill_dir")")"
  while IFS= read -r ref; do
    resolved="$skill_dir/${ref#'${CLAUDE_SKILL_DIR}/'}"
    [[ -f "$resolved" ]] || fail "$skill_file: \${CLAUDE_SKILL_DIR} reference does not resolve: $ref -> $resolved"
  done < <(grep -oE '\$\{CLAUDE_SKILL_DIR\}/[A-Za-z0-9_./-]+' "$skill_file")
  while IFS= read -r ref; do
    resolved="$plugin_dir/${ref#'${CLAUDE_PLUGIN_ROOT}/'}"
    [[ -f "$resolved" ]] || fail "$skill_file: \${CLAUDE_PLUGIN_ROOT} reference does not resolve: $ref -> $resolved"
  done < <(grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9_./-]+' "$skill_file")
done
pass "\${CLAUDE_SKILL_DIR}/\${CLAUDE_PLUGIN_ROOT} references checked"

# 3. No "[paste" markers remain in skill or agent content. Only skills/ and
#    agents/ are scanned, never scripts/: this script's own source contains
#    the marker it searches for.
PASTE_SCAN=()
for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
  for d in "$plugin_dir/skills" "$plugin_dir/agents"; do
    [[ -d "$d" ]] && PASTE_SCAN+=("$d")
  done
done
if [[ "${#PASTE_SCAN[@]}" == 0 ]]; then
  pass "no skill or agent content to scan for [paste placeholders"
elif grep -rq '\[paste' "${PASTE_SCAN[@]}"; then
  fail "found remaining [paste placeholder(s):"
  grep -rn '\[paste' "${PASTE_SCAN[@]}"
else
  pass "no [paste placeholders"
fi

# 4. Every <plugin>/agents/*.md declares model, effort, maxTurns
for agent_file in ${AGENT_FILES[@]+"${AGENT_FILES[@]}"}; do
  for field in model effort maxTurns; do
    grep -q "^${field}:" "$agent_file" || fail "$agent_file: missing '$field' in frontmatter"
  done
done
pass "agent definitions checked"

# 5. Each plugin's own version matches its marketplace.json entry.
#    Plugins version independently, so this compares each plugin against its
#    own entry rather than holding every manifest to one repo-wide version.
json_version() {
  grep -o '"version": *"[^"]*"' "$1" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
}

# Read the "version" of a named marketplace entry. Callers pass the plugin
# directory, which assumes a plugin's directory name matches its "name" in the
# manifest. If the two ever diverge the lookup finds nothing and fails loudly
# rather than passing silently. Relies on "version" appearing after "name"
# within an entry, which is how the manifest is written.
marketplace_version() {
  awk -v want="$1" '
    $0 ~ "\"name\": *\"" want "\"" { in_entry = 1; next }
    in_entry && match($0, /"version": *"[^"]*"/) {
      v = substr($0, RSTART, RLENGTH)
      gsub(/.*: *"|"$/, "", v)
      print v
      exit
    }
  ' .claude-plugin/marketplace.json
}

for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
  manifest="$plugin_dir/.claude-plugin/plugin.json"
  if [[ ! -f "$manifest" ]]; then
    fail "$plugin_dir: missing .claude-plugin/plugin.json"
    continue
  fi
  plugin_version="$(json_version "$manifest")"
  entry_version="$(marketplace_version "$plugin_dir")"
  if [[ -z "$plugin_version" ]]; then
    fail "$manifest: could not determine version"
  elif [[ -z "$entry_version" ]]; then
    fail ".claude-plugin/marketplace.json: no version for plugin '$plugin_dir'"
  elif [[ "$plugin_version" != "$entry_version" ]]; then
    fail "$plugin_dir: plugin.json version $plugin_version does not match marketplace.json entry $entry_version"
  else
    pass "$plugin_dir version consistent ($plugin_version)"
  fi
done

# 6. Codex manifests: each plugin's .codex-plugin/plugin.json version must
#    match its .claude-plugin/plugin.json version, and every plugin must be
#    listed in .agents/plugins/marketplace.json. If Codex's own bundled
#    validator is installed locally, run it too. Both are skipped cleanly
#    when absent, since the validator lives outside the repo, at $HOME/.codex.
codex_marketplace_plugin_names() {
  awk '
    /"plugins": *\[/ { in_plugins = 1 }
    in_plugins && match($0, /"name": *"[^"]*"/) {
      v = substr($0, RSTART, RLENGTH)
      gsub(/.*: *"|"$/, "", v)
      print v
    }
  ' "$1"
}

CODEX_MARKETPLACE=".agents/plugins/marketplace.json"
if [[ ! -f "$CODEX_MARKETPLACE" ]]; then
  fail "$CODEX_MARKETPLACE: missing"
else
  CODEX_LISTED="$(codex_marketplace_plugin_names "$CODEX_MARKETPLACE")"
  for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
    codex_manifest="$plugin_dir/.codex-plugin/plugin.json"
    if [[ ! -f "$codex_manifest" ]]; then
      fail "$plugin_dir: missing .codex-plugin/plugin.json"
      continue
    fi
    codex_version="$(json_version "$codex_manifest")"
    claude_version="$(json_version "$plugin_dir/.claude-plugin/plugin.json")"
    if [[ -z "$codex_version" ]]; then
      fail "$codex_manifest: could not determine version"
    elif [[ "$codex_version" != "$claude_version" ]]; then
      fail "$plugin_dir: .codex-plugin/plugin.json version $codex_version does not match .claude-plugin/plugin.json version $claude_version"
    fi
    if ! echo "$CODEX_LISTED" | grep -qx "$plugin_dir"; then
      fail "$plugin_dir: not listed in $CODEX_MARKETPLACE"
    fi
  done
  pass "Codex manifests checked"
fi

CODEX_VALIDATOR="$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py"
if [[ -f "$CODEX_VALIDATOR" ]] && command -v python3 >/dev/null 2>&1; then
  for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
    validator_log="$(mktemp)"
    if ! python3 "$CODEX_VALIDATOR" "$plugin_dir" >"$validator_log" 2>&1; then
      fail "$plugin_dir: Codex plugin validator failed:"
      cat "$validator_log"
    fi
    rm -f "$validator_log"
  done
  pass "Codex plugin validator checked (found at $CODEX_VALIDATOR)"
else
  pass "Codex plugin validator not found locally, skipped"
fi

# 7. Every plugin's build-opencode.sh output is byte-identical across two runs.
#    All plugins write into the same .opencode/ tree, so the snapshot is taken
#    after running every build script, and compared across two full passes.
BUILD_SCRIPTS=()
for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
  [[ -x "$plugin_dir/scripts/build-opencode.sh" ]] && BUILD_SCRIPTS+=("$plugin_dir/scripts/build-opencode.sh")
done

if [[ "${#BUILD_SCRIPTS[@]}" == 0 ]]; then
  pass "no build-opencode.sh scripts to check"
else
  snapshot_build() {
    for build_script in "${BUILD_SCRIPTS[@]}"; do
      "./$build_script" >/dev/null || fail "$build_script: exited non-zero"
    done
    cp -R .opencode/. "$1"
  }
  first_run="$(mktemp -d)"
  second_run="$(mktemp -d)"
  snapshot_build "$first_run"
  snapshot_build "$second_run"
  if diff -rq "$first_run" "$second_run" >/dev/null; then
    pass "build-opencode.sh output deterministic (${#BUILD_SCRIPTS[@]} script(s))"
  else
    fail "build-opencode.sh output changed across two runs"
    diff -rq "$first_run" "$second_run"
  fi
  rm -rf "$first_run" "$second_run"
fi

# 8. No IBAN-shaped tokens in committed plugin content. The finance plugin
#    handles account data, and the repo is public, so a pasted bank line or a
#    fixture built from a real statement must not survive a commit. Scanned
#    paths are skills/, toolkit/ and README.md per plugin, never scripts/,
#    which holds this pattern's own source.
#    Word boundaries are written as explicit non-alphanumeric context rather
#    than \b, which BSD grep does not support.
IBAN_PATTERN='(EE[0-9]{18})|((^|[^A-Za-z0-9])[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}([^A-Za-z0-9]|$))'
IBAN_SCAN=()
for plugin_dir in ${PLUGINS[@]+"${PLUGINS[@]}"}; do
  for t in "$plugin_dir/skills" "$plugin_dir/toolkit" "$plugin_dir/README.md"; do
    [[ -e "$t" ]] && IBAN_SCAN+=("$t")
  done
done
if [[ "${#IBAN_SCAN[@]}" == 0 ]]; then
  pass "no plugin content to scan for IBAN-shaped tokens"
elif grep -rqE "$IBAN_PATTERN" "${IBAN_SCAN[@]}"; then
  fail "found IBAN-shaped token(s) in plugin content:"
  grep -rnE "$IBAN_PATTERN" "${IBAN_SCAN[@]}"
else
  pass "no IBAN-shaped tokens in plugin content"
fi

echo
if [[ "$FAIL" == 1 ]]; then
  echo "lint FAILED"
  exit 1
fi
echo "lint OK"
