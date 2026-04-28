# asse-cli (npm wrapper)

Wrapper de npm para [`asse-cli`](https://pypi.org/project/asse-cli/) (paquete Python).

> **Requiere Python 3.11+ y `pip` instalados en el sistema.** El `postinstall` corre `pip install --user asse-cli`.

## Instalación

```bash
npm install -g asse-cli
asse --help
```

O sin instalar:

```bash
npx asse-cli --help
```

Comandos principales:

```bash
asse agenda session login-browser
asse agenda reservas list
asse hcd session login-browser
asse hcd timeline
asse hcd visitas
asse hcd visita 1
asse hcd vacunas
```

## Variables de entorno

- `ASSE_SKIP_POSTINSTALL=1` — saltea el `pip install` automático.
