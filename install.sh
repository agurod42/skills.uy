#!/usr/bin/env bash
# Symlink each skill in this repo into ~/.claude/skills/.
# Idempotent: re-run after `git pull` or after adding a new skill.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_dir="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

mkdir -p "$target_dir"

linked=0
for skill_path in "$repo_root"/skills/*/; do
  [ -d "$skill_path" ] || continue
  name="$(basename "$skill_path")"
  link="$target_dir/$name"

  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "skip  $name (a non-symlink already exists at $link)" >&2
    continue
  fi

  ln -snf "$skill_path" "$link"
  echo "link  $name -> $skill_path"
  linked=$((linked + 1))
done

echo
echo "Done. $linked skill(s) linked into $target_dir."
