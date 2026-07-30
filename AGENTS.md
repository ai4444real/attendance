# Rebekko Webapps - Agent Notes

Questo repository contiene Rebekko Webapps, con focus attuale su Attendance,
import Zoom, normalizzazione presenze, analisi scuola e utilities.

## Regole operative

- Non lavorare direttamente sulla produzione.
- Il clone di lavoro dell'agente sul server deve essere separato da
  `/opt/rebekko/webapps`, che resta la produzione.
- Prima di modificare codice, controllare `git status --short`.
- Non cancellare o revertire modifiche non proprie senza richiesta esplicita.
- Non committare `.env`, runtime, virtualenv, backup o export con dati reali.
- Per modifiche manuali ai file usare patch piccole e verificabili.

## Struttura principale

- `backend/main.py`: entrypoint FastAPI e routing web/API.
- `backend/attendance_app/`: logica applicativa attendance.
- `backend/db/`: repository e accesso persistenza.
- `attendance/static/`: pagine e JS della UI attendance.
- `utilities/`: strumenti laterali, inclusi Classroom Manager e Smallinvoice.
- `sql/schema/`: evoluzioni schema PostgreSQL.
- `sql/queries/`: query operative/diagnostiche.
- `docs/` e `attendance/docs/`: documentazione di deploy e decisioni funzionali.

## Database

- La configurazione usa `DATABASE_URL` in `.env`.
- PostgreSQL e' il database applicativo.
- La persistenza deve restare isolata dietro repository in `backend/db/`.
- Non introdurre query sparse nel frontend.
- Gli script schema sono incrementali: se aggiungi tabelle o colonne, crea un
  nuovo file in `sql/schema/`.
- Prima di proporre operazioni distruttive sul DB, preparare una query di
  verifica o backup.

## Attendance

- I draft Zoom vengono importati e normalizzati nel database.
- Le correzioni devono essere applicabili e reversibili dove previsto.
- Gli alias servono a far convergere presenze apparentemente diverse.
- Le identita' stabili sono preparatorie per lesson set e report futuri.
- La visualizzazione ufficiale deve leggere dati consolidati, non rifare logica
  nel frontend.

## Deploy

- Deploy produzione: `/opt/rebekko/webapps/deploy.sh`.
- La documentazione operativa e' in `docs/deploy.md`.
- Il deploy esegue pull/install/restart/health check; verificare il file reale
  prima di cambiarne il comportamento.

## Test e verifiche

- Preferire test mirati quando si tocca la normalizzazione.
- Comandi utili:

```bash
python -m pytest attendance/tests
python -m pytest tests
```

Se i test non sono eseguibili nell'ambiente corrente, dichiararlo chiaramente.
