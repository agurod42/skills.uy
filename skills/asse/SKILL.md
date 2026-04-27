---
name: asse
description: Use this skill whenever the user wants to interact with ASSE (Administración de los Servicios de Salud del Estado, Uruguay) — the public health service at asse.com.uy / agendaweb.asse.uy. Covers listing reservations ("mis reservas"), inspecting captured HAR traffic from the GeneXus-based Agenda Web, importing browser cookies into a local session, and driving the site via the bundled asse-cli (Python). Trigger on mentions of "ASSE", "Agenda Web", "agendaweb.asse.uy", "asse.com.uy", "mis reservas", or any Uruguayan public-health appointment workflow.
---

# ASSE — Agenda Web

Skill for working with ASSE's Agenda Web (https://www.asse.com.uy, https://agendaweb.asse.uy) via the bundled `asse-cli`.

The site is built on GeneXus. `asse-cli` does not use GeneXus or compile anything — it reproduces the HTTP/JSON contract the frontend uses, plus parses HAR captures of real sessions.

## When to use

- User asks to list, inspect, or automate ASSE appointments / reservations.
- User shares a `.har` file from `www.asse.com.uy` or `agendaweb.asse.uy` and wants endpoints, GeneXus events, cookies, public links, or reservation rows extracted.
- User wants to log in via browser and persist a session locally to query "Mis Reservas" without re-authenticating.

## Setup

The CLI lives at `skills/asse/` in this repo. Install it in editable mode:

```bash
cd skills/asse
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Optional browser-driven login (uses Playwright):

```bash
pip install -e ".[browser]"
playwright install chromium
```

After install the `asse` command is on PATH.

## Command surface

```
asse har summary <file.har>            # hosts/methods/statuses/endpoints counters
asse har events <file.har>             # GeneXus events + commands per object
asse har public-links <file.har>       # public links (default filter: agenda)
asse har reservations <file.har>       # reservation rows parsed from HAR
asse har appointment-flow <file.har>   # ordered booking flow steps
asse session login-url                 # discover Agenda Web login URL
asse session login-browser             # open browser, persist session.json
asse session import-har-cookies <har>  # seed session from a HAR capture
asse session show                      # dump current session (cookies redacted)
asse reservas list                     # list reservations using the active session
```

Sessions are stored at `~/.asse-cli/session.json` by default; override with `--session <path>`.

## Architecture

- `har.py` — safe HAR loading + trace extraction.
- `genexus.py` — GeneXus event/response models and session state.
- `client.py` — HTTP client with cookies, tokens, and state.
- `extract.py` — HTML/HAR parsers for reservations and appointment flow.
- `cli.py` — Typer entry point.

## Safety

- HARs typically contain cookies, identifiers, and personal data. **Never commit real HAR files** — `.gitignore` excludes `*.har` for that reason.
- Output that includes consultation codes is redacted by default; pass `--show-codes` only when the user explicitly wants the raw values.
- The CLI avoids destructive actions by default (no cancellations, no bookings without explicit instruction).

## How to drive this skill

1. If the user provides a HAR, start with `asse har summary` and `asse har reservations` to surface what's in it.
2. If the user wants live data, check for `~/.asse-cli/session.json`. If absent, suggest `asse session login-browser` (interactive) or `asse session import-har-cookies` (if they already have a HAR).
3. For reservation listings, use `asse reservas list`. If the response says "Usuario no afiliado", the session is valid but the user lacks Mis Reservas access — surface that exact message rather than inferring a session failure.
4. For new commands or flows the CLI does not yet cover, inspect a HAR with `asse har events` / `asse har appointment-flow` to understand the GeneXus event sequence before implementing.
