# ASSE CLI

CLI experimental para entender y consultar flujos digitales vinculados a ASSE:
Agenda Web para reservas y Historia Clínica Digital / HCEN para lectura
read-only de historia clínica.

Las webs observadas usan GeneXus. Esta herramienta no usa GeneXus ni compila nada:
reproduce contratos HTTP/JSON/form-urlencoded que usa el frontend y parsea HTML/HARs
de sesiones reales.

## Estado

Prototipo:

- inspecciona HARs de `www.asse.com.uy`, `agendaweb.asse.uy` y
  `historiaclinicadigital.gub.uy`;
- extrae endpoints, eventos GeneXus, cookies, comandos y datos read-only;
- consulta reservas de Agenda Web con sesión local;
- lee timeline, vacunas y accesos de HCD/HCEN cuando hay sesión o HAR;
- evita acciones destructivas por defecto.

## Uso local

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

asse agenda har summary /Users/agurodriguez/Downloads/agendaweb.asse.uy.har
asse agenda har events /Users/agurodriguez/Downloads/agendaweb.asse.uy.har
asse agenda har public-links /Users/agurodriguez/Downloads/www.asse.com.uy.har
asse agenda har reservations /Users/agurodriguez/Downloads/agendaweb.asse.uy.har

asse hcd har timeline /Users/agurodriguez/Downloads/historiaclinicadigital.gub.uy.har
asse hcd har vacunas /Users/agurodriguez/Downloads/historiaclinicadigital.gub.uy.har
asse hcd har accesos /Users/agurodriguez/Downloads/historiaclinicadigital.gub.uy.har
```

Sesiones live:

```bash
asse agenda session login-browser
asse agenda reservas list

asse hcd session login-browser
asse hcd timeline
asse hcd vacunas
```

`login-browser` instala Playwright y Chromium automáticamente en el primer uso
si no están disponibles en el entorno Python actual.

Las sesiones se guardan separadas:

- `~/.asse-cli/agenda-session.json`
- `~/.asse-cli/hcd-session.json`

## Diseño

Capas:

- `har.py`: lectura segura de HAR y extracción de trazas/cookies.
- `genexus.py`: modelos de evento/respuesta y estado GeneXus.
- `client.py`: cliente HTTP compartido con cookies y sesión.
- `agenda_client.py`: cliente de Agenda Web.
- `hcd_client.py`: cliente de Historia Clínica Digital.
- `extract.py`: parsers de Agenda Web.
- `hcd_extract.py`: parsers de HCD/HCEN.
- `cli.py`: comandos de usuario.

## Seguridad

Los HAR pueden contener cookies, identificadores, tokens, datos clínicos y datos
personales. No commitear HAR reales.

Los links a documentos clínicos y certificados se redactan por defecto. Usar
`--show-links` solo cuando se necesite ver el valor crudo.
