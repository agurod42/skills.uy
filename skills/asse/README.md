# ASSE CLI

CLI experimental para entender y automatizar flujos de Agenda Web de ASSE.

La web observada en los HAR usa GeneXus. Esta herramienta no usa GeneXus ni compila nada
GeneXus: reproduce el contrato HTTP/JSON que usa el frontend.

## Estado

Primer prototipo:

- inspecciona HAR de `www.asse.com.uy` y `agendaweb.asse.uy`;
- extrae endpoints, eventos GeneXus, cookies y comandos;
- modela sesión y estado GeneXus para implementar comandos reales;
- evita acciones destructivas por defecto.

## Uso local

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

asse har summary /Users/agurodriguez/Downloads/agendaweb.asse.uy.har
asse har events /Users/agurodriguez/Downloads/agendaweb.asse.uy.har
asse har public-links /Users/agurodriguez/Downloads/www.asse.com.uy.har
```

## Diseño

Capas:

- `har.py`: lectura segura de HAR y extracción de trazas.
- `genexus.py`: modelos de evento/respuesta y estado GeneXus.
- `client.py`: cliente HTTP con cookies, tokens y estado.
- `cli.py`: comandos de usuario.

## Seguridad

Los HAR pueden contener cookies, identificadores y datos personales. No commitear HAR reales.
