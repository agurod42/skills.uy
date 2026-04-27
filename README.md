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

## Installing a skill

Symlink (or copy) a skill folder into your Claude skills directory:

```bash
ln -s "$PWD/skills/asse" ~/.claude/skills/asse
```

Then mention it in conversation — Claude will invoke it when the description matches.

## Contributing

New skills should target services, tools, or workflows that are specific to Uruguay (`.uy`). Keep each skill self-contained inside its folder.
