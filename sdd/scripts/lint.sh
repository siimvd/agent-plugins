#!/usr/bin/env bash
set -uo pipefail

# Structural lint for the SDD plugin. Checks file existence, frontmatter
# shape, leftover paste markers, version consistency, and that
# build-opencode.sh is deterministic.
#
# This checks STRUCTURE, not BEHAVIOR. A clean run here means the plugin's
# files are internally consistent — it says nothing about whether a skill
# actually does the right thing when invoked. Use it as a fast pre-commit
# sanity check, not a substitute for exercising a skill for real.
#
# Run from the repo root: bash sdd/scripts/lint.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

FAIL=0
fail() { echo "FAIL: $1"; FAIL=1; }
pass() { echo "ok: $1"; }

# 1. Every SKILL.md has valid frontmatter with name and description
for f in sdd/skills/*/SKILL.md; do
  if ! head -1 "$f" | grep -q '^---$'; then
    fail "$f: missing frontmatter opening ---"
    continue
  fi
  fm=$(awk '/^---$/{n++; next} n==1' "$f")
  echo "$fm" | grep -q '^name:' || fail "$f: frontmatter missing 'name'"
  echo "$fm" | grep -q '^description:' || fail "$f: frontmatter missing 'description'"
done
pass "SKILL.md frontmatter checked"

# 2. Every \${CLAUDE_SKILL_DIR} reference resolves to a real file
for f in sdd/skills/*/SKILL.md; do
  skill_dir="$(dirname "$f")"
  while IFS= read -r ref; do
    [[ -z "$ref" ]] && continue
    rel="${ref#'${CLAUDE_SKILL_DIR}/'}"
    resolved="$skill_dir/$rel"
    [[ -f "$resolved" ]] || fail "$f: \${CLAUDE_SKILL_DIR} reference does not resolve: $ref -> $resolved"
  done < <(grep -oE '\$\{CLAUDE_SKILL_DIR\}/[A-Za-z0-9_./-]+' "$f")
done
pass "\${CLAUDE_SKILL_DIR} references checked"

# 3. No "[paste" markers remain in skill or agent content (not sdd/scripts/,
#    whose own source describes this very check)
if grep -rq '\[paste' sdd/skills/ sdd/agents/; then
  fail "found remaining [paste placeholder(s):"
  grep -rn '\[paste' sdd/skills/ sdd/agents/
else
  pass "no [paste placeholders"
fi

# 4. Every sdd/agents/*.md declares model, effort, maxTurns
for f in sdd/agents/*.md; do
  for field in model effort maxTurns; do
    grep -q "^${field}:" "$f" || fail "$f: missing '$field' in frontmatter"
  done
done
pass "agent definitions checked"

# 5. No stale version string across JSON manifests
current_version="$(grep -o '"version": *"[^"]*"' sdd/.claude-plugin/plugin.json | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
if [[ -z "$current_version" ]]; then
  fail "could not determine current version from sdd/.claude-plugin/plugin.json"
else
  while IFS= read -r jf; do
    v="$(grep -o '"version": *"[^"]*"' "$jf" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
    if [[ -n "$v" && "$v" != "$current_version" ]]; then
      fail "$jf: version $v does not match $current_version"
    fi
  done < <(find . -name "*.json" -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.opencode/*")
  pass "version strings checked against $current_version"
fi

# 6. build-opencode.sh output is byte-identical across two runs
tmp1="$(mktemp -d)"
tmp2="$(mktemp -d)"
./sdd/scripts/build-opencode.sh >/dev/null
cp -R .opencode/commands "$tmp1/commands"
[[ -d .opencode/agents ]] && cp -R .opencode/agents "$tmp1/agents"
./sdd/scripts/build-opencode.sh >/dev/null
cp -R .opencode/commands "$tmp2/commands"
[[ -d .opencode/agents ]] && cp -R .opencode/agents "$tmp2/agents"
if diff -rq "$tmp1" "$tmp2" >/dev/null; then
  pass "build-opencode.sh output deterministic"
else
  fail "build-opencode.sh output changed across two runs"
fi
rm -rf "$tmp1" "$tmp2"

echo
if [[ "$FAIL" == 1 ]]; then
  echo "lint FAILED"
  exit 1
fi
echo "lint OK"
