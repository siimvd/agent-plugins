#!/usr/bin/env bash
set -euo pipefail

# Generates .opencode/commands/ and .opencode/agents/ from the canonical
# Claude Code skills and agent definitions.
# Run from the repo root: ./sdd/scripts/build-opencode.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PLUGIN_DIR")"
OUT_DIR="$REPO_ROOT/.opencode/commands"
AGENTS_OUT_DIR="$REPO_ROOT/.opencode/agents"

mkdir -p "$OUT_DIR" "$AGENTS_OUT_DIR"

# Helper: convert a skill to an OpenCode command
# Usage: build_command <skill_dir> <output_name> <inline_files...>
build_command() {
  local skill_dir="$1"
  local output_name="$2"
  shift 2
  local inline_files=()
  if [[ $# -gt 0 ]]; then
    inline_files=("$@")
  fi

  local skill_file="$skill_dir/SKILL.md"
  local out_file="$OUT_DIR/$output_name.md"

  if [[ ! -f "$skill_file" ]]; then
    echo "Warning: SKILL.md not found at $skill_file, skipping" >&2
    return
  fi

  # Verify inline files exist
  for f in "${inline_files[@]+"${inline_files[@]}"}"; do
    if [[ ! -f "$skill_dir/$f" ]]; then
      echo "Warning: $f not found in $skill_dir, skipping" >&2
      return
    fi
  done

  {
    # Extract frontmatter (between first and second ---) and body (after second ---)
    # Using awk for reliable multi-line YAML frontmatter handling
    local frontmatter body
    frontmatter=$(awk '/^---$/{n++; next} n==1{print}' "$skill_file")
    body=$(awk '/^---$/{n++; next} n>=2{print}' "$skill_file")

    # Write frontmatter, keeping only fields OpenCode commands recognize
    # (description, agent, model, subtask) — drop name (filename determines
    # the command) and Claude-specific fields
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
    for f in "${inline_files[@]+"${inline_files[@]}"}"; do
      local escaped_f
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

# Helper: convert a plugin agent definition (sdd/agents/*.md) to an
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

for agent_file in "$PLUGIN_DIR"/agents/*.md; do
  build_agent "$agent_file"
done

# Build brainstorm command
build_command \
  "$PLUGIN_DIR/skills/brainstorm" \
  "sdd-brainstorm" \
  "mini-prd-template.md"

# Build plan command
build_command \
  "$PLUGIN_DIR/skills/plan" \
  "sdd-plan" \
  "spec-template.md" \
  "references/task-writing-guide.md"

# Build build command
build_command \
  "$PLUGIN_DIR/skills/build" \
  "sdd-build" \
  "references/review-triggers.md" \
  "references/agent-prompts.md"

# Build review command (no inline files needed)
build_command \
  "$PLUGIN_DIR/skills/review" \
  "sdd-review"

# Build finish command (no inline files needed)
build_command \
  "$PLUGIN_DIR/skills/finish" \
  "sdd-finish"

# Build setup command
build_command \
  "$PLUGIN_DIR/skills/setup" \
  "sdd-setup" \
  "agents-template.md" \
  "sdd-section.md"
