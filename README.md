# skills.uy

Claude skills for Uruguayan services and tools.

Each subdirectory of `skills/` is a self-contained [Claude skill](https://docs.claude.com/en/docs/claude-code/skills) — a `SKILL.md` (with `name` + `description` frontmatter that tells Claude when to use it) plus any supporting code, scripts, or reference docs.

## Skills

| Skill | Description |
|-------|-------------|
| [`asse`](skills/asse) | Interact with ASSE's Agenda Web (asse.com.uy / agendaweb.asse.uy) via the bundled `asse-cli` — inspect HAR captures, manage local sessions, and list reservations. |

## Layout

```
skills.uy/
└── skills/
    └── <skill-name>/
        ├── SKILL.md        # frontmatter + instructions Claude reads
        └── ...             # supporting code / scripts / references
```

## Installing

Clone the repo somewhere stable and run `./install.sh`. The script symlinks every `skills/*/` into `~/.claude/skills/`, so the skills appear in Claude Code on next session start.

```bash
git clone git@github.com:agurod42/skills.uy.git ~/Code/skills.uy
cd ~/Code/skills.uy
./install.sh
```

Re-run `./install.sh` after `git pull` or after adding a new skill — it's idempotent. Override the target with `CLAUDE_SKILLS_DIR=/some/other/path ./install.sh`.

Because skills are symlinked (not copied), editing a `SKILL.md` in this repo takes effect immediately.

## Contributing

New skills should target services, tools, or workflows that are specific to Uruguay (`.uy`). Keep each skill self-contained inside its folder.
