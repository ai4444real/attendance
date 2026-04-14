# Attendance

Repository per importazione, normalizzazione e analisi delle presenze.

Oggi contiene due moduli distinti ma complementari:

- `adapter/`: prototipo operativo per trasformare i report Zoom in un formato interno normalizzato;
- `static/`: frontend del modulo per consultare e analizzare dati di presenza gia' normalizzati o simili al vecchio formato TrackCC.

L'obiettivo del progetto e' unificare i due flussi in una pipeline semplice:

`Zoom -> formato interno -> salvataggio centrale -> analisi`

## Stato del progetto

Il repository non e' ancora un prodotto unico finito. E' una base reale di lavoro composta da:

- un frontend analitico gia' usabile;
- un adapter Zoom gia' usabile come prototipo avanzato;
- una documentazione di allineamento architetturale per guidare l'unificazione.

La direzione corrente e' descritta in [docs/ARCHITETTURA_UNIFICAZIONE.md](docs/ARCHITETTURA_UNIFICAZIONE.md).

## Moduli

### 1. Analisi presenze

Entry point:

- `static/index.html`

Nota:

- il backend FastAPI unico del workspace sta in `webapps/backend/main.py`, non dentro al modulo `attendance`.

Capacita' attuali:

- caricamento CSV lato browser;
- pulizia dati di presenza;
- filtri per corso e studente;
- evidenziazione studenti inattivi;
- export CSV filtrato.

### 2. Zoom adapter

Entry point:

- `adapter/index.html`

Capacita' attuali:

- parsing dei report CSV Zoom;
- ricostruzione dei segmenti join/leave;
- rilevazione automatica della pausa o split di meta' lezione;
- classificazione presenza per prima meta', seconda meta' o intera lezione;
- override manuale per casi dubbi;
- export CSV normalizzato.

## Struttura attuale

```text
attendance/
├── adapter/                    # Zoom -> formato interno
├── data/                       # File di lavoro e dataset storici usati finora
├── docs/                       # Documentazione tecnica e operativa
├── static/                     # Frontend analitico
└── README.md                   # Panoramica del repository
```

## Documentazione

- [docs/ARCHITETTURA_UNIFICAZIONE.md](docs/ARCHITETTURA_UNIFICAZIONE.md): direzione architetturale e backlog
- [docs/MIGRAZIONE_NORMALIZZAZIONE_PYTHON.md](docs/MIGRAZIONE_NORMALIZZAZIONE_PYTHON.md): piano incrementale di migrazione della logica Zoom in Python
- [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md): setup locale
- [docs/CLAUDE_INSTRUCTIONS.md](docs/CLAUDE_INSTRUCTIONS.md): note operative storiche del progetto
- [docs/README-SCRIPTS.txt](docs/README-SCRIPTS.txt): guida rapida agli script Windows

## Dataset e file di lavoro

La cartella `data/` contiene i file storici usati finora per sviluppo, prove e confronto tra formati.

Nota:

- i nuovi CSV sensibili non dovrebbero essere versionati automaticamente;
- il repository continua a ignorare i CSV nuovi tramite `.gitignore`;
- i file gia' tracciati restano presenti come base storica di riferimento.

## Avvio locale

### Windows

1. Dalla root `webapps/`, esegui `setup-local.bat` la prima volta.
2. Dalla root `webapps/`, avvia `start-server.bat`.
3. Apri `http://localhost:8080`.

### Manuale

```bash
cd webapps
pip install -r requirements.txt
python -m backend.main
```

## Principi di struttura

La struttura corrente segue un criterio semplice:

- root `webapps/` riservata al backend unico e alla configurazione condivisa;
- documentazione del modulo centralizzata in `docs/`;
- file di lavoro storici separati in `data/`;
- modulo `attendance` isolato per evitare ambiguita' quando arriveranno altre app.

Questo e' il punto di partenza per l'evoluzione 2026 del progetto: professionale, leggibile e senza introdurre complessita' gratuita.
