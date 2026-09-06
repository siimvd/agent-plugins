#!/usr/bin/env bash
set -euo pipefail

# Generates hermes/skills/tools-*/ from the canonical Claude Code skills in
# tools/skills/. Run from anywhere: ./tools/scripts/build-hermes.sh
#
# Same discovery shape as build-opencode.sh: skills are found by globbing
# skills/*/SKILL.md and the support files come from each SKILL.md's own
# ${CLAUDE_SKILL_DIR} references, so a new skill needs no edit here. The
# difference is that references are *copied* rather than inlined. Hermes
# substitutes ${HERMES_SKILL_DIR} and can read a support file on demand via
# skill_view(name, file_path), so inlining would throw away the token saving
# the reference exists for.
#
# Unlike .opencode/, the output of this script is committed. A Hermes tap
# installs by fetching paths from GitHub and cannot see local build output.

shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PLUGIN_DIR")"
PLUGIN_NAME="$(basename "$PLUGIN_DIR")"
MANIFEST="$PLUGIN_DIR/.claude-plugin/plugin.json"
OUT_ROOT="$REPO_ROOT/hermes/skills"

# Hermes truncates every skill description in its system-prompt index to
# SKILL_PROMPT_DESC_LIMIT (60) minus the "..." it appends. Anything longer is
# cut mid-phrase, so skills hand-author a hermes-description within budget.
DESC_LIMIT=57

# Hermes's own skill-name regex. The skill directory basename becomes a path
# component of the output tree, so this is also the path-traversal guard --
# see docs/learnings/mistakes/path-traversal-store-keys.md.
SKILL_NAME_RE='^[a-z0-9][a-z0-9._-]*$'

# Placeholders kept in variables so the substitutions below are plain literal
# text. BSD sed reads \{ \} as an interval expression and errors on the literal
# braces, so all rewriting here is bash parameter expansion, never sed.
CLAUDE_PLACEHOLDER='${CLAUDE_SKILL_DIR}'
HERMES_PLACEHOLDER='${HERMES_SKILL_DIR}'
CLAUDE_SUBST_NOTE='substituted automatically by Claude Code'
HERMES_SUBST_NOTE='substituted automatically by Hermes'

# Helper: read a top-level single-line frontmatter field, empty if absent.
# Usage: frontmatter_field <file> <field>
frontmatter_field() {
  grep -m1 "^$2:" "$1" | sed "s/^$2: *//" || true
}

# Helper: read the canonical description, which is written as a folded YAML
# scalar (`description: >-` plus indented continuation lines) in most skills
# and as a plain one-liner in others. Prints the value with the block indent
# stripped, line breaks preserved -- the destination is a markdown paragraph,
# where a wrapped line and a joined one render identically.
# Usage: canonical_description <skill_file>
canonical_description() {
  awk '
    /^---$/ { n++; if (n >= 2) exit; next }
    n != 1 { next }
    started {
      if ($0 ~ /^[ \t]/) { sub(/^[ \t]+/, ""); print; next }
      exit
    }
    /^description:/ {
      value = $0
      sub(/^description:[ \t]*/, "", value)
      started = 1
      # A plain one-liner is the whole value; a block indicator (>- | >) means
      # the value is in the indented lines that follow.
      if (value != "" && value !~ /^[|>][-+]?$/) { print value; exit }
    }
  ' "$1"
}

# Helper: print the skill body, everything after the closing --- of the
# frontmatter, with the blank line that follows it dropped so the generated
# file has exactly one. The n>=2 test runs before the counter is bumped, so a
# --- used as a horizontal rule inside the body survives.
# Usage: skill_body <skill_file>
skill_body() {
  awk 'n >= 2 && (NF || started) { started = 1; print } /^---$/ { n++ }' "$1"
}

# Helper: list the ${CLAUDE_SKILL_DIR} references in a SKILL.md, deduped, in
# the order they first appear. Prints one full reference per line; the caller
# strips the prefix with bash parameter expansion rather than sed, for the
# BSD-sed reason noted above. The || true keeps an unmatched grep from
# aborting under set -e.
# Usage: skill_refs <skill_file>
skill_refs() {
  { grep -oE '\$\{CLAUDE_SKILL_DIR\}/[A-Za-z0-9_./-]+' "$1" || true; } \
    | awk '!seen[$0]++'
}

# Helper: read "version" and "license" from a plugin manifest. Same grep-based
# reading as sdd/scripts/lint.sh, which these values are compared against.
# Usage: json_field <manifest> <field>
json_field() {
  grep -o "\"$2\": *\"[^\"]*\"" "$1" | head -1 | sed "s/.*: *\"//; s/\"$//"
}

# Helper: read author.name, which is nested and so cannot be grepped by key
# alone -- the manifest's top-level "name" would match first.
# Usage: json_author_name <manifest>
json_author_name() {
  awk '
    /"author"/ { in_author = 1 }
    in_author && match($0, /"name": *"[^"]*"/) {
      value = substr($0, RSTART, RLENGTH)
      sub(/^"name": *"/, "", value)
      sub(/"$/, "", value)
      print value
      exit
    }
  ' "$1"
}

# Helper: reject a skill directory name that is not a valid Hermes skill name.
# This is the single choke point where an on-disk name becomes a path component
# of the output tree, so it fails the whole run rather than skipping the skill:
# a name that can escape the tree is a bug to fix, not input to work around.
# Usage: validate_skill_name <name>
validate_skill_name() {
  if [[ ! "$1" =~ $SKILL_NAME_RE ]]; then
    echo "Error: skill directory name '$1' does not match $SKILL_NAME_RE" >&2
    echo "       Refusing to build: the name becomes a path under $OUT_ROOT/." >&2
    exit 1
  fi
}

# Helper: generate one Hermes skill directory from a canonical skill.
# Usage: build_skill <skill_dir>
build_skill() {
  local skill_dir="$1"
  local skill_name output_name skill_file out_dir out_file
  skill_name="$(basename "$skill_dir")"
  output_name="$PLUGIN_NAME-$skill_name"
  skill_file="$skill_dir/SKILL.md"
  out_dir="$OUT_ROOT/$output_name"
  out_file="$out_dir/SKILL.md"

  if [[ ! -f "$skill_file" ]]; then
    echo "Warning: SKILL.md not found at $skill_file, skipping" >&2
    return 1
  fi

  # The short description is hand-authored, not derived. A missing or
  # over-budget one is warned about and skipped here; sdd/scripts/lint.sh is
  # what turns it into a hard, repo-wide failure.
  local hermes_desc
  hermes_desc="$(frontmatter_field "$skill_file" hermes-description)"
  if [[ -z "$hermes_desc" ]]; then
    echo "Warning: $skill_file has no hermes-description, skipping skill" >&2
    return 1
  fi
  if [[ "${#hermes_desc}" -gt "$DESC_LIMIT" ]]; then
    echo "Warning: $skill_file hermes-description is ${#hermes_desc} characters, over the $DESC_LIMIT limit, skipping skill" >&2
    return 1
  fi

  # Collect the referenced support files. A dangling reference skips the whole
  # skill rather than shipping a broken one, matching build-opencode.sh.
  local ref_files=() ref rel
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    rel="${ref#"$CLAUDE_PLACEHOLDER/"}"
    # Second path choke point: a reference is written into the output path too,
    # so a traversing one would write outside the skill directory.
    if [[ "$rel" == /* || "$rel" == ".." || "$rel" == "../"* || "$rel" == *"/../"* || "$rel" == *"/.." ]]; then
      echo "Error: $skill_file references '$rel', which escapes the skill directory" >&2
      exit 1
    fi
    if [[ ! -f "$skill_dir/$rel" ]]; then
      echo "Warning: $skill_file references $rel, which does not exist, skipping skill" >&2
      return 1
    fi
    # Third path choke point: cp follows symlinks by default, so a symlinked
    # reference would copy its target's contents -- possibly from outside the
    # skill directory entirely -- into the committed output tree. Fail loud
    # rather than silently dereferencing or skipping, matching the traversal
    # check above.
    if [[ -L "$skill_dir/$rel" ]]; then
      echo "Error: $skill_file references '$rel', which is a symlink; refusing to copy" >&2
      exit 1
    fi
    # Fourth path choke point: -L and -f above only test the final path
    # component of $rel. A symlinked *intermediate* directory (e.g. $rel is
    # "subdir/file.txt" and "subdir" is a symlink to somewhere outside the
    # skill directory) is invisible to both checks -- the kernel follows it
    # before either test runs. Resolve the physical (symlink-free) directory
    # that actually holds the referenced file and require it stay inside the
    # skill directory, per the repo's allowlist-plus-realpath-containment
    # pattern for external-identifier-as-path bugs.
    local resolved_dir resolved_base
    resolved_dir="$(cd "$skill_dir/$(dirname "$rel")" 2>/dev/null && pwd -P)" || {
      echo "Error: $skill_file references '$rel', whose directory does not resolve" >&2
      exit 1
    }
    resolved_base="$(cd "$skill_dir" && pwd -P)"
    case "$resolved_dir" in
      "$resolved_base"|"$resolved_base"/*) ;;
      *)
        echo "Error: $skill_file references '$rel', which escapes the skill directory via a symlinked path component" >&2
        exit 1
        ;;
    esac
    ref_files+=("$rel")
  done < <(skill_refs "$skill_file")

  local body full_desc
  body="$(skill_body "$skill_file")"
  full_desc="$(canonical_description "$skill_file")"

  # The two rewrites Hermes needs: its own placeholder, and the sentence naming
  # the runtime that substitutes it.
  body="${body//$CLAUDE_PLACEHOLDER/$HERMES_PLACEHOLDER}"
  body="${body//$CLAUDE_SUBST_NOTE/$HERMES_SUBST_NOTE}"

  mkdir -p "$out_dir"

  {
    echo "---"
    echo "name: $output_name"
    echo "description: $hermes_desc"
    echo "version: $MANIFEST_VERSION"
    echo "author: $MANIFEST_AUTHOR"
    echo "license: $MANIFEST_LICENSE"
    echo "---"
    echo ""
    echo "$body"
    # The 57-character index entry decides whether Hermes loads the skill; the
    # full trigger list is what confirms the choice once it has. Appended
    # rather than spliced in after the H1, so the generator never parses the
    # body.
    echo ""
    echo "---"
    echo ""
    echo "## When to use this skill"
    echo ""
    echo "$full_desc"
  } > "$out_file"

  echo "Generated: $out_file"

  local f
  for f in "${ref_files[@]+"${ref_files[@]}"}"; do
    mkdir -p "$out_dir/$(dirname "$f")"
    cp -P "$skill_dir/$f" "$out_dir/$f"
    echo "Copied:    $out_dir/$f"
  done
}

skill_dirs=("$PLUGIN_DIR"/skills/*/)

if [[ "${#skill_dirs[@]}" == 0 ]]; then
  echo "Nothing to build: $PLUGIN_NAME/ has no skills yet."
  exit 0
fi

# Validate every name before touching the filesystem, so a bad one stops the
# run before any output is written or removed.
for skill_dir in "${skill_dirs[@]}"; do
  validate_skill_name "$(basename "${skill_dir%/}")"
done

if [[ ! -f "$MANIFEST" ]]; then
  echo "Error: manifest not found at $MANIFEST" >&2
  exit 1
fi

MANIFEST_VERSION="$(json_field "$MANIFEST" version)"
MANIFEST_AUTHOR="$(json_author_name "$MANIFEST")"
MANIFEST_LICENSE="$(json_field "$MANIFEST" license)"

for field in MANIFEST_VERSION MANIFEST_AUTHOR MANIFEST_LICENSE; do
  if [[ -z "${!field}" ]]; then
    echo "Error: $MANIFEST has no value for $field" >&2
    exit 1
  fi
done

# Clear stale output first, so a renamed or deleted skill does not linger in
# the committed tree. Scoped to this plugin's prefix, leaving other plugins'
# generated skills alone.
for stale_dir in "$OUT_ROOT"/"$PLUGIN_NAME"-*/; do
  rm -rf "${stale_dir%/}"
done

mkdir -p "$OUT_ROOT"

built=0
for skill_dir in "${skill_dirs[@]}"; do
  if build_skill "${skill_dir%/}"; then
    built=$((built + 1))
  fi
done

if [[ "$built" == 0 ]]; then
  echo "Nothing to build: no skill in $PLUGIN_NAME/ is ready for Hermes." >&2
fi
