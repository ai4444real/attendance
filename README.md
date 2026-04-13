# Rebekko Webapps

Contenitore delle webapp del progetto Rebekko.

## Applicazioni

- [attendance](attendance/README.md): importazione, normalizzazione e analisi delle presenze

## Root del workspace

Nella root di `webapps/` stanno solo gli elementi condivisi o di orchestrazione:

- backend FastAPI unico;
- configurazione ambiente;
- dipendenze Python;
- script di avvio locale;
- containerizzazione;
- documentazione generale del workspace.

## Struttura

```text
webapps/
├── attendance/               # Prima applicazione attiva
├── backend/
│   └── main.py               # Backend FastAPI unico
├── requirements.txt          # Dipendenze condivise
├── .env.example              # Template configurazione locale
├── setup-local.bat           # Setup ambiente locale
├── start-server.bat          # Avvio server locale
└── .gitignore
```

## Nota

L'attuale codice applicativo, la documentazione e i file di lavoro di `attendance` sono stati isolati nella cartella `attendance/` per preparare il repository all'arrivo di altri moduli.
