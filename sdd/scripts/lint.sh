#!/usr/bin/env bash
set -uo pipefail

# Structural lint for the SDD plugin. Checks file existence, frontmatter
# shape, leftover paste markers, version consistency, and that
# build-opencode.sh is deterministic.
#
# This checks STRUCTURE, not BEHAVIOR. A clean run means the plugin's files
# are internally consistent — it says nothing about whether a skill does the
# right thing when invoked. It is a pre-commit sanity check, not a substitute
# for exercising a skill for real.
#
# Run from the repo root: bash sdd/scripts/lint.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

FAIL=0
fail() { echo "FAIL: $1"; FAIL=1; }
pass() { echo "ok: $1"; }

# 1. Every SKILL.md has valid frontmatter with name and description
for skill_file in sdd/skills/*/SKILL.md; do
  if ! head -1 "$skill_file" | grep -q '^---$'; then
    fail "$skill_file: missing frontmatter opening ---"
    continue
  fi
  frontmatter=$(awk '/^---$/{n++; next} n==1' "$skill_file")
  echo "$frontmatter" | grep -q '^name:' || fail "$skill_file: frontmatter missing 'name'"
  echo "$frontmatter" | grep -q '^description:' || fail "$skill_file: frontmatter missing 'description'"
done
pass "SKILL.md frontmatter checked"

# 2. Every \${CLAUDE_SKILL_DIR} reference resolves to a real file
for skill_file in sdd/skills/*/SKILL.md; do
  skill_dir="$(dirname "$skill_file")"
  while IFS= read -r ref; do
    resolved="$skill_dir/${ref#'${CLAUDE_SKILL_DIR}/'}"
    [[ -f "$resolved" ]] || fail "$skill_file: \${CLAUDE_SKILL_DIR} reference does not resolve: $ref -> $resolved"
  done < <(grep -oE '\$\{CLAUDE_SKILL_DIR\}/[A-Za-z0-9_./-]+' "$skill_file")
done
pass "\${CLAUDE_SKILL_DIR} references checked"

# 3. No "[paste" markers remain in skill or agent content. sdd/scripts/ is
#    excluded — this script's own source contains the marker it searches for.
if grep -rq '\[paste' sdd/skills/ sdd/agents/; then
  fail "found remaining [paste placeholder(s):"
  grep -rn '\[paste' sdd/skills/ sdd/agents/
else
  pass "no [paste placeholders"
fi

# 4. Every sdd/agents/*.md declares model, effort, maxTurns
for agent_file in sdd/agents/*.md; do
  for field in model effort maxTurns; do
    grep -q "^${field}:" "$agent_file" || fail "$agent_file: missing '$field' in frontmatter"
  done
done
pass "agent definitions checked"

# 5. No stale version string across JSON manifests
json_version() {
  grep -o '"version": *"[^"]*"' "$1" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
}
current_version="$(json_version sdd/.claude-plugin/plugin.json)"
if [[ -z "$current_version" ]]; then
  fail "could not determine current version from sdd/.claude-plugin/plugin.json"
else
  while IFS= read -r json_file; do
    version="$(json_version "$json_file")"
    if [[ -n "$version" && "$version" != "$current_version" ]]; then
      fail "$json_file: version $version does not match $current_version"
    fi
  done < <(find . -name "*.json" -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.opencode/*")
  pass "version strings checked against $current_version"
fi

# 6. build-opencode.sh output is byte-identical across two runs
snapshot_build() {
  ./sdd/scripts/build-opencode.sh >/dev/null
  cp -R .opencode/. "$1"
}
first_run="$(mktemp -d)"
second_run="$(mktemp -d)"
snapshot_build "$first_run"
snapshot_build "$second_run"
if diff -rq "$first_run" "$second_run" >/dev/null; then
  pass "build-opencode.sh output deterministic"
else
  fail "build-opencode.sh output changed across two runs"
fi
rm -rf "$first_run" "$second_run"

echo
if [[ "$FAIL" == 1 ]]; then
  echo "lint FAILED"
  exit 1
fi
echo "lint OK"
