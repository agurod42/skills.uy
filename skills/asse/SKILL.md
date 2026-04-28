---
name: asse
description: Use this skill whenever the user wants to interact with ASSE (Administración de los Servicios de Salud del Estado, Uruguay) or related Uruguayan public-health digital services. Covers Agenda Web reservations at agendaweb.asse.uy, ASSE public links at asse.com.uy, Historia Clínica Digital / HCEN at historiaclinicadigital.gub.uy, captured HAR inspection, local browser sessions, reservation listing, and read-only clinical timeline/vaccines/access logs via the bundled asse-cli (Python). Trigger on mentions of "ASSE", "Agenda Web", "agendaweb.asse.uy", "asse.com.uy", "mis reservas", "historia clínica", "HCD", "HCEN", "mihcd", or Uruguayan public-health appointment/clinical-record workflows.
---

# ASSE — Agenda Web + Historia Clínica Digital

Skill for working with ASSE's Agenda Web (https://www.asse.com.uy, https://agendaweb.asse.uy) and Historia Clínica Digital / HCEN (https://historiaclinicadigital.gub.uy/mihcd/) via the bundled `asse-cli`.

The observed sites are built on GeneXus. `asse-cli` does not use GeneXus or compile anything — it reproduces the HTTP contracts the frontends use, plus parses HAR captures of real sessions.

## When to use

- User asks to list, inspect, or automate ASSE appointments / reservations.
- User shares a `.har` file from `www.asse.com.uy` or `agendaweb.asse.uy` and wants endpoints, GeneXus events, cookies, public links, or reservation rows extracted.
- User shares a `.har` file from `historiaclinicadigital.gub.uy` and wants clinical timeline, vaccine report, access logs, GeneXus events, cookies, or endpoints extracted.
- User wants to log in via browser and persist a session locally to query "Mis Reservas" without re-authenticating.
- User wants read-only access to Historia Clínica Digital after authenticating with ID Uruguay.

## Setup

The CLI lives at `skills/asse/` in this repo. Install it in editable mode:

```bash
cd skills/asse
python3.11 -m venv .venv
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
asse agenda har summary <file.har>
asse agenda har events <file.har>
asse agenda har public-links <file.har>
asse agenda har reservations <file.har>
asse agenda har appointment-flow <file.har>
asse agenda session login-url
asse agenda session login-browser
asse agenda session import-har-cookies <har>
asse agenda session show
asse agenda reservas list

asse hcd har summary <file.har>
asse hcd har events <file.har>
asse hcd har timeline <file.har>
asse hcd har vacunas <file.har>
asse hcd har accesos <file.har>
asse hcd session login-browser
asse hcd session import-har-cookies <har>
asse hcd session show
asse hcd timeline
asse hcd vacunas
asse hcd accesos
```

Sessions are stored separately by default; override with `--session <path>`.

- Agenda Web: `~/.asse-cli/agenda-session.json`
- HCD/HCEN: `~/.asse-cli/hcd-session.json`

## Architecture

- `har.py` — safe HAR loading + trace extraction.
- `genexus.py` — GeneXus event/response models and session state.
- `client.py` — shared HTTP client with cookies and session persistence.
- `agenda_client.py` — Agenda Web client.
- `hcd_client.py` — Historia Clínica Digital client.
- `extract.py` — HTML/HAR parsers for Agenda reservations and appointment flow.
- `hcd_extract.py` — HTML/HAR parsers for HCD timeline, vaccines, and access logs.
- `cli.py` — Typer entry point.

## Safety

- HARs typically contain cookies, identifiers, and personal data. **Never commit real HAR files** — `.gitignore` excludes `*.har` for that reason.
- Output that includes consultation codes is redacted by default; pass `--show-codes` only when the user explicitly wants the raw values.
- HCD HARs contain clinical data, identity tokens, and document URLs. Treat them as highly sensitive.
- HCD document/report links are redacted by default; pass `--show-links` only when the user explicitly wants raw URLs.
- The CLI avoids destructive actions by default (no cancellations, no bookings without explicit instruction).
- HCD support is read-only. Do not add privacy/permission mutation commands without explicit user request and separate review.

## How to drive this skill

1. If the user provides an Agenda HAR, start with `asse agenda har summary` and `asse agenda har reservations`.
2. If the user provides an HCD HAR, start with `asse hcd har summary`, then `asse hcd har timeline`, `asse hcd har vacunas`, or `asse hcd har accesos`.
3. If the user wants Agenda live data, check for `~/.asse-cli/agenda-session.json`. If absent, suggest `asse agenda session login-browser` or `asse agenda session import-har-cookies`.
4. If the user wants HCD live data, check for `~/.asse-cli/hcd-session.json`. If absent, suggest `asse hcd session login-browser` or `asse hcd session import-har-cookies`.
5. For Agenda reservation listings, use `asse agenda reservas list`. If the response says "Usuario no afiliado", the session is valid but the user lacks Mis Reservas access — surface that exact message rather than inferring a session failure.
6. For HCD access logs, prefer HAR extraction when possible: the live panel often loads through a signed K2BTools POST that cannot be recreated safely from a plain GET.
7. For new commands or flows the CLI does not yet cover, inspect the relevant HAR with `asse agenda har events`, `asse agenda har appointment-flow`, or `asse hcd har events` before implementing.
