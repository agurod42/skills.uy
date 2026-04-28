---
name: asse
description: Use this skill whenever the user wants to interact with ASSE (Administración de los Servicios de Salud del Estado, Uruguay) or related Uruguayan public-health digital services. Covers Agenda Web reservations at agendaweb.asse.uy, ASSE public links at asse.com.uy, Historia Clínica Digital / HCEN at historiaclinicadigital.gub.uy, local browser sessions, reservation listing, and read-only clinical timeline/visits/vaccines/access logs via the bundled asse-cli (Python). Trigger on mentions of "ASSE", "Agenda Web", "agendaweb.asse.uy", "asse.com.uy", "mis reservas", "historia clínica", "HCD", "HCEN", "mihcd", or Uruguayan public-health appointment/clinical-record workflows.
---

# ASSE — Agenda Web + Historia Clínica Digital

Skill for working with ASSE's Agenda Web (https://www.asse.com.uy, https://agendaweb.asse.uy) and Historia Clínica Digital / HCEN (https://historiaclinicadigital.gub.uy/mihcd/) via the bundled `asse-cli`.

The observed sites are built on GeneXus. `asse-cli` does not use GeneXus or compile anything — it reproduces the HTTP contracts the frontends use and parses live session responses.

## When to use

- User asks to list, inspect, or automate ASSE appointments / reservations.
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

Browser-driven login auto-installs Playwright and Chromium on first use. To preinstall manually:

```bash
pip install -e ".[browser]"
playwright install chromium
```

After install the `asse` command is on PATH.

## Command surface

```
asse agenda session login-url
asse agenda session login-browser
asse agenda session show
asse agenda reservas list

asse hcd session login-browser
asse hcd session show
asse hcd timeline
asse hcd visitas
asse hcd visita 1
asse hcd vacunas
asse hcd accesos
```

Sessions are stored separately by default; override with `--session <path>`.

- Agenda Web: `~/.asse-cli/agenda-session.json`
- HCD/HCEN: `~/.asse-cli/hcd-session.json`

## Architecture

- `genexus.py` — GeneXus event/response models and session state.
- `client.py` — shared HTTP client with cookies and session persistence.
- `agenda_client.py` — Agenda Web client.
- `hcd_client.py` — Historia Clínica Digital client.
- `extract.py` — HTML/JSON parsers for Agenda reservations.
- `hcd_extract.py` — HTML/JSON parsers for HCD timeline, visits, vaccines, and access logs.
- `cli.py` — Typer entry point.

## Safety

- Output that includes consultation codes is redacted by default; pass `--show-codes` only when the user explicitly wants the raw values.
- HCD document/report links are redacted by default; pass `--show-links` only when the user explicitly wants raw URLs.
- The CLI avoids destructive actions by default (no cancellations, no bookings without explicit instruction).
- HCD support is read-only. Do not add privacy/permission mutation commands without explicit user request and separate review.

## How to drive this skill

1. If the user wants Agenda data, check for `~/.asse-cli/agenda-session.json`. If absent, suggest `asse agenda session login-browser`.
2. If the user wants HCD data, check for `~/.asse-cli/hcd-session.json`. If absent, suggest `asse hcd session login-browser`.
3. For Agenda reservation listings, use `asse agenda reservas list`. If the response says "Usuario no afiliado", the session is valid but the user lacks Mis Reservas access — surface that exact message rather than inferring a session failure.
4. For HCD timeline/visits/vaccines, use `asse hcd timeline`, `asse hcd visitas`, `asse hcd visita N`, and `asse hcd vacunas`.
5. For HCD access logs, use `asse hcd accesos`. If the live panel cannot be parsed, explain that the signed K2BTools POST is not yet supported.
