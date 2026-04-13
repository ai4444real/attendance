# Rebekko Webapps

Contenitore delle webapp del progetto Rebekko.

## Applicazioni

- [attendance](attendance/README.md): importazione, normalizzazione e analisi delle presenze
- [docs/DEPLOY_UBUNTU_SERVER.md](docs/DEPLOY_UBUNTU_SERVER.md): runbook del deploy su server Ubuntu
- [infra/caddy/Caddyfile.example](infra/caddy/Caddyfile.example): esempio di routing pubblico con Caddy

## Root del workspace

Nella root di `webapps/` stanno solo gli elementi condivisi o di orchestrazione:

- backend FastAPI unico;
- configurazione ambiente;
- dipendenze Python;
- script di avvio locale;
- script di deploy;
- configurazione infrastrutturale condivisa;
- containerizzazione eventuale;
- documentazione generale del workspace.

## Struttura

```text
webapps/
├── attendance/               # Prima applicazione attiva
├── backend/
│   └── main.py               # Backend FastAPI unico
├── docs/
│   └── DEPLOY_UBUNTU_SERVER.md
├── infra/
│   └── caddy/
│       └── Caddyfile.example # Routing pubblico di riferimento
├── assets/
│   ├── brand/                # Logo e asset visivi globali
│   └── styles/brand.css      # Palette colore condivisa
├── requirements.txt          # Dipendenze condivise
├── .env.example              # Template configurazione locale
├── deploy.sh                 # Deploy one-command sul server Ubuntu
├── setup-local.bat           # Setup ambiente locale
├── start-server.bat          # Avvio server locale
└── .gitignore
```

## Nota

L'attuale codice applicativo, la documentazione e i file di lavoro di `attendance` sono stati isolati nella cartella `attendance/` per preparare il repository all'arrivo di altri moduli.
