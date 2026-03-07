#!/usr/bin/env bash
set -euo pipefail

# Generates .opencode/commands/ from canonical Claude Code skills.
# Run from the repo root: ./sdd/scripts/build-opencode.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PLUGIN_DIR")"
OUT_DIR="$REPO_ROOT/.opencode/commands"

mkdir -p "$OUT_DIR"

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

    # Write frontmatter, stripping Claude-specific fields
    echo "---"
    echo "$frontmatter" \
      | grep -v "^allowed-tools:" \
      | grep -v "^disable-model-invocation:" \
      | grep -v "^  -"
    echo "---"
    echo ""

    # Replace $ARGUMENTS with $IDEA for OpenCode
    body=$(echo "$body" | sed 's/\$ARGUMENTS/\$IDEA/g')

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
