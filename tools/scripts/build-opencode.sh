#!/usr/bin/env bash
set -euo pipefail

# Generates .opencode/commands/tools-*.md and .opencode/agents/*.md from the
# canonical Claude Code skills and agent definitions in tools/.
# Run from anywhere: ./tools/scripts/build-opencode.sh
#
# Unlike sdd/scripts/build-opencode.sh, which lists each skill and its inline
# files explicitly, this script discovers both. Skills are found by globbing
# skills/*/SKILL.md, and the files to inline are read out of each SKILL.md's
# own ${CLAUDE_SKILL_DIR} references. That means a new skill needs no edit
# here. The tradeoff is no control over inline order beyond the order the
# references appear in the skill.

shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PLUGIN_DIR")"
OUT_DIR="$REPO_ROOT/.opencode/commands"
AGENTS_OUT_DIR="$REPO_ROOT/.opencode/agents"

mkdir -p "$OUT_DIR" "$AGENTS_OUT_DIR"

# Helper: read the first value of a single-line frontmatter field, empty if absent
# Usage: frontmatter_field <file> <field>
frontmatter_field() {
  grep -m1 "^$2:" "$1" | sed "s/^$2: *//" || true
}

# Helper: map an internal model alias to an OpenCode provider-qualified string
map_model() {
  case "$1" in
    haiku) echo "anthropic/claude-haiku-4-5" ;;
    sonnet) echo "anthropic/claude-sonnet-5" ;;
    opus) echo "anthropic/claude-opus-5" ;;
    *) echo "anthropic/$1" ;;
  esac
}

# Helper: list the ${CLAUDE_SKILL_DIR} references in a SKILL.md, deduped, in
# the order they first appear. Prints one full reference per line; the caller
# strips the prefix with bash parameter expansion rather than sed, because BSD
# sed reads \{ \} as an interval expression and errors on the literal braces.
# The || true keeps an unmatched grep from aborting under set -e.
# Usage: inline_refs <skill_file>
inline_refs() {
  { grep -oE '\$\{CLAUDE_SKILL_DIR\}/[A-Za-z0-9_./-]+' "$1" || true; } \
    | awk '!seen[$0]++'
}

# Helper: convert a skill to an OpenCode command, inlining every file the
# skill references via ${CLAUDE_SKILL_DIR}.
# Usage: build_command <skill_dir>
build_command() {
  local skill_dir="$1"
  local skill_name output_name skill_file out_file
  skill_name="$(basename "$skill_dir")"
  output_name="tools-$skill_name"
  skill_file="$skill_dir/SKILL.md"
  out_file="$OUT_DIR/$output_name.md"

  if [[ ! -f "$skill_file" ]]; then
    echo "Warning: SKILL.md not found at $skill_file, skipping" >&2
    return
  fi

  local inline_files=() ref rel
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    rel="${ref#'${CLAUDE_SKILL_DIR}/'}"
    if [[ ! -f "$skill_dir/$rel" ]]; then
      echo "Warning: $skill_file references $rel, which does not exist, skipping skill" >&2
      return
    fi
    inline_files+=("$rel")
  done < <(inline_refs "$skill_file")

  {
    # Extract frontmatter (between first and second ---) and body (after second ---)
    # Using awk for reliable multi-line YAML frontmatter handling
    local frontmatter body
    frontmatter=$(awk '/^---$/{n++; next} n==1{print}' "$skill_file")
    body=$(awk '/^---$/{n++; next} n>=2{print}' "$skill_file")

    # Write frontmatter, keeping only fields OpenCode commands recognize
    # (description, agent, model, subtask). Drop name (filename determines
    # the command) and Claude-specific fields.
    echo "---"
    echo "$frontmatter" \
      | grep -v "^name:" \
      | grep -v "^allowed-tools:" \
      | grep -v "^disable-model-invocation:" \
      | grep -v "^  -"
    echo "---"
    echo ""

    # $ARGUMENTS carries over to OpenCode unchanged, so it is left alone here.

    # Replace ${CLAUDE_SKILL_DIR} references with inline content
    local f escaped_f
    for f in "${inline_files[@]+"${inline_files[@]}"}"; do
      escaped_f=$(echo "$f" | sed 's/[\/&]/\\&/g')
      body=$(echo "$body" | sed '/\${CLAUDE_SKILL_DIR}\/'"$escaped_f"'/{
        s/.*/## Inlined: '"$escaped_f"'/
        r '"$skill_dir/$f"'
      }')
    done

    echo "$body"
  } > "$out_file"

  echo "Generated: $out_file"
}

# Helper: convert a plugin agent definition (tools/agents/*.md) to an
# OpenCode subagent (.opencode/agents/*.md). maxTurns maps to OpenCode's
# `steps` (its documented "maximum number of agentic iterations" cap).
# `effort` has no equivalent: OpenCode's provider-parameter passthrough
# (e.g. reasoningEffort) is documented for OpenAI reasoning models, not
# verified for the Anthropic models map_model targets, so it is dropped
# rather than mapped to an unverified field.
# Usage: build_agent <agent_file>
build_agent() {
  local agent_file="$1"
  local base_name out_file
  base_name="$(basename "$agent_file" .md)"
  out_file="$AGENTS_OUT_DIR/$base_name.md"

  local description model effort max_turns disallowed_tools body
  description=$(frontmatter_field "$agent_file" description)
  model=$(frontmatter_field "$agent_file" model)
  effort=$(frontmatter_field "$agent_file" effort)
  max_turns=$(frontmatter_field "$agent_file" maxTurns)
  disallowed_tools=$(frontmatter_field "$agent_file" disallowedTools)
  body=$(awk '/^---$/{n++; next} n>=2' "$agent_file")

  {
    echo "---"
    echo "description: $description"
    echo "mode: subagent"
    echo "model: $(map_model "$model")"
    [[ -n "$max_turns" ]] && echo "steps: $max_turns"
    if [[ -n "$disallowed_tools" ]]; then
      echo "permission:"
      [[ "$disallowed_tools" == *"Edit"* ]] && echo "  edit: deny"
      [[ "$disallowed_tools" == *"Write"* ]] && echo "  write: deny"
    fi
    echo "---"
    echo ""
    echo "<!-- Dropped, no verified OpenCode equivalent for an Anthropic model: effort=$effort -->"
    echo ""
    echo "$body"
  } > "$out_file"

  echo "Generated: $out_file"
}

built=0

for agent_file in "$PLUGIN_DIR"/agents/*.md; do
  build_agent "$agent_file"
  built=$((built + 1))
done

for skill_dir in "$PLUGIN_DIR"/skills/*/; do
  build_command "${skill_dir%/}"
  built=$((built + 1))
done

if [[ "$built" == 0 ]]; then
  echo "Nothing to build: tools/ has no skills or agents yet."
fi
