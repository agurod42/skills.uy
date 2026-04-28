# ASSE CLI

CLI experimental para entender y consultar flujos digitales vinculados a ASSE:
Agenda Web para reservas y Historia Clínica Digital / HCEN para lectura
read-only de historia clínica.

Las webs observadas usan GeneXus. Esta herramienta no usa GeneXus ni compila nada:
reproduce contratos HTTP/JSON/form-urlencoded que usa el frontend y parsea respuestas
HTML/JSON de sesiones reales.

## Estado

Prototipo:

- consulta reservas de Agenda Web con sesión local;
- lee timeline, visitas, vacunas y accesos de HCD/HCEN cuando hay sesión local;
- evita acciones destructivas por defecto.

## Uso local

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

asse agenda session login-browser
asse agenda reservas list

asse hcd session login-browser
asse hcd timeline
asse hcd visitas
asse hcd visita 1
asse hcd vacunas
asse hcd accesos
```

`login-browser` instala Playwright y Chromium automáticamente en el primer uso
si no están disponibles en el entorno Python actual.

Las sesiones se guardan separadas:

- `~/.asse-cli/agenda-session.json`
- `~/.asse-cli/hcd-session.json`

## Diseño

Capas:

- `genexus.py`: modelos de evento/respuesta y estado GeneXus.
- `client.py`: cliente HTTP compartido con cookies y sesión.
- `agenda_client.py`: cliente de Agenda Web.
- `hcd_client.py`: cliente de Historia Clínica Digital.
- `extract.py`: parsers de Agenda Web.
- `hcd_extract.py`: parsers de HCD/HCEN.
- `cli.py`: comandos de usuario.

## Seguridad

Los links a documentos clínicos y certificados se redactan por defecto. Usar
`--show-links` solo cuando se necesite ver el valor crudo.
