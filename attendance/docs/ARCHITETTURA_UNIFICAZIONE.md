# Attendance: architettura unificata e backlog

## Scopo del documento

Questo file serve come riferimento condiviso per:

- chiarire cosa esiste oggi nel repository;
- dare un senso unico ai due tentativi fatti in momenti diversi;
- definire una direzione tecnica coerente;
- mantenere un backlog operativo iniziale.

Il principio guida e' questo:

- `adapter/` trasforma i report Zoom nel nostro formato normalizzato;
- la `root` dell'applicazione usa il formato normalizzato per fare analisi di presenza;
- in prospettiva il flusso non resta solo locale, ma salva i dati su un server Linux centrale.

## Stato attuale del repository

### 1. Modulo attendance: analisi presenze su formato "trackcc-like"

Nel modulo `attendance/` c'e' il frontend principale in `static/index.html`.
Il backend FastAPI che oggi lo serve sta invece nella root del workspace `webapps/`, in `backend/main.py`.

Oggi questa parte copre soprattutto:

- caricamento CSV di presenze gia' in formato semplificato;
- filtri per corso e studente;
- analisi aggregate;
- ragionamenti del tipo:
  - partecipazione sufficiente a un corso;
  - studenti inattivi nelle ultime lezioni;
  - esportazione del dataset filtrato.

Questa e' la parte da considerare come base per l'interfaccia di lavoro della persona che gestisce le presenze.

### 2. Adapter: prototipo Zoom -> formato normalizzato

In `adapter/` c'e' un prototipo separato che:

- legge i CSV Zoom dei partecipanti;
- ricompone le molteplici entrate/uscite di ogni persona;
- divide la lezione in prima parte / seconda parte;
- applica una regola di presenza basata su soglia;
- permette correzioni manuali;
- esporta un CSV normalizzato.

Questa e' la parte da considerare come base del processo di importazione Zoom.

### 3. Situazione attuale reale

Oggi le due funzionalita' convivono nello stesso repository ma non sono ancora un sistema unico:

- il formato prodotto dall'adapter non e' ancora il contratto ufficiale di sistema;
- non c'e' ancora una persistenza centrale;
- non c'e' ancora un workflow completo "importa -> salva -> analizza";
- l'infrastruttura server non e' ancora definita nel progetto.

## Modello concettuale desiderato

L'idea corretta e' trattare il sistema come due moduli distinti ma collegati.

### Modulo A: ingestione e normalizzazione

Responsabilita':

- caricare uno o piu' file Zoom;
- trasformarli nel formato interno;
- consentire eventuali correzioni manuali;
- inviare il risultato al server.

Utente tipico:

- persona operativa che importa i dati delle lezioni.

Output:

- record normalizzati coerenti e persistibili.

### Modulo B: analisi e reporting

Responsabilita':

- leggere i dati gia' normalizzati;
- mostrare storico, filtri e statistiche;
- supportare controlli amministrativi e didattici.

Utente tipico:

- persona che controlla presenze, frequenze, anomalie, soglie e assenze recenti.

Input:

- solo dati nel formato interno.

## Flusso operativo target

Il flusso desiderato e' questo:

1. L'operatore carica i file Zoom.
2. Il sistema li trasforma nel formato interno.
3. L'operatore controlla il risultato e, se serve, corregge casi dubbi.
4. Il sistema invia i record normalizzati al server.
5. Il server salva i record e gestisce i doppioni.
6. L'operatore delle presenze usa l'interfaccia di analisi sui dati gia' salvati.

Questo separa bene i ruoli:

- una persona importa e consolida;
- un'altra persona consulta e ragiona sui dati consolidati.

## Formato interno: direzione consigliata

Il repository oggi usa implicitamente almeno due forme di dato:

- formato root, vicino al vecchio mondo "trackcc";
- formato export dell'adapter, nato dal mondo Zoom.

Serve definire un **formato interno canonico**. La proposta pragmatica e':

- mantenere un record per `studente + corso + data lezione`;
- salvare anche i campi quantitativi che arrivano da Zoom;
- separare chiaramente i campi "calcolati" dai campi "manualmente corretti".

### Campi minimi consigliati del formato canonico

- `source_system`: es. `zoom`, `trackcc_legacy`
- `source_file_name`
- `source_import_batch_id`
- `source_meeting_id`
- `course_name`
- `lesson_date`
- `lesson_start_at`
- `lesson_end_at`
- `student_first_name`
- `student_last_name`
- `student_email`
- `presence_status`
- `minutes_first_half`
- `minutes_second_half`
- `duration_first_half`
- `duration_second_half`
- `total_minutes`
- `segment_count`
- `calculated_presence_status`
- `manual_override_presence_status`
- `notes`
- `created_at`
- `updated_at`

### Stati presenza consigliati

Per non rompere il lavoro gia' fatto, ha senso tenere questi valori:

- `presente`
- `prima_meta`
- `seconda_meta`
- `assente`

Se in futuro servira' compatibilita' piu' stretta con TrackCC, potremo aggiungere una mappatura derivata invece di sporcare il modello base.

## Doppioni: approccio iniziale

Non serve decidere tutto ora, ma serve una regola iniziale semplice.

Chiave di unicita' proposta, da verificare sul campo:

- `source_system`
- `source_meeting_id`
- `course_name`
- `lesson_date`
- `student_email`

Fallback se manca l'email:

- `student_first_name`
- `student_last_name`
- `lesson_date`
- `course_name`

Politica iniziale suggerita:

- se arriva lo stesso record identico, ignorarlo;
- se arriva un record con stessa chiave ma contenuti diversi, segnalarlo come conflitto;
- non sovrascrivere in automatico una correzione manuale gia' salvata.

## Architettura target consigliata

La proposta piu' sensata, senza overengineering, e':

- frontend web unico;
- backend Python leggero;
- PostgreSQL sul server Linux;
- upload/import via API HTTP;
- analisi lette dal database, non da CSV locali.

### Componenti

#### 1. Frontend

Due aree funzionali nella stessa applicazione:

- area `Import Zoom`
- area `Analisi Presenze`

All'inizio possono anche restare due pagine separate, pur condividendo server e backend.

#### 2. Backend Python

Responsabilita':

- ricevere i record normalizzati;
- validare il payload;
- salvare su PostgreSQL;
- esporre endpoint per query e filtri;
- in seguito gestire autenticazione e audit minimo.

FastAPI e' gia' presente nel progetto e resta una scelta sensata.

#### 3. PostgreSQL

Responsabilita':

- persistenza centrale;
- controllo unicita';
- base per analisi multi-sessione e multi-operatore.

#### 4. Server Linux Infomaniak

Responsabilita':

- ospitare backend e database;
- diventare il punto centrale dei dati;
- convivere con n8n senza confondere i ruoli.

## Proposta di evoluzione concreta

### Fase 1: allineamento del modello

Obiettivo:

- decidere il formato interno ufficiale;
- decidere la semantica degli stati presenza;
- chiarire che il root non lavora piu' su CSV "casuali", ma su record canonici.

Output atteso:

- schema dati condiviso;
- mapping chiaro da Zoom al formato interno.

### Fase 2: consolidamento dell'adapter

Obiettivo:

- trasformare `adapter/` da prototipo standalone a modulo di importazione ufficiale.

Attivita':

- pulire naming e output;
- fissare il formato del CSV export;
- aggiungere un invio API al server oltre al download CSV;
- mantenere la possibilita' di review manuale prima del salvataggio.

### Fase 3: backend con persistenza

Obiettivo:

- far smettere al sistema di dipendere da file locali per lavorare sullo storico.

Attivita':

- schema PostgreSQL;
- endpoint di ingestione;
- gestione import batch;
- deduplica base;
- endpoint lettura per dashboard e filtri.

### Fase 4: migrazione dell'analisi

Obiettivo:

- far leggere alla UI della root i dati da PostgreSQL invece che solo da CSV caricati localmente.

Attivita':

- adattare frontend e servizio dati;
- mantenere opzionalmente il caricamento CSV locale solo come funzione di emergenza o debug.

### Fase 5: rifinitura operativa

Obiettivo:

- rendere il sistema usabile da due persone con ruoli distinti.

Attivita':

- schermata import;
- schermata analisi;
- cronologia import;
- segnalazione conflitti o record dubbi;
- eventuale autenticazione minima.

## Backlog iniziale

### A. Decisioni funzionali da confermare

- Definire il nome ufficiale del formato interno.
- Confermare che gli stati ufficiali siano `presente`, `prima_meta`, `seconda_meta`, `assente`.
- Confermare se la "prima parte" e' sempre concettualmente meta' lezione oppure se in alcuni corsi va gestita in modo diverso.
- Confermare se i docenti e tutor vanno esclusi dall'import Zoom o solo dall'analisi.
- Confermare se il record canonico deve essere per singola lezione o per singolo meeting Zoom.

### B. Backlog applicativo

- Creare una documentazione tecnica del formato interno con esempi reali.
- Rendere l'output dell'adapter il formato canonico, oppure mapparlo esplicitamente al formato canonico.
- Rendere espliciti nella UI della `Gestione presenze` i due marker temporali: `inizio effettivo` (blu, da cui parte il calcolo percentuale) e `pausa/split` (giallo, che divide prima e seconda parte della lezione).
- Aggiungere endpoint `POST /api/imports/zoom-normalized`.
- Aggiungere endpoint `GET /api/attendance`.
- Aggiungere endpoint `GET /api/courses`.
- Aggiungere endpoint `GET /api/students`.
- Salvare i batch di import con metadata minimi.
- Gestire deduplica e conflitti.
- Portare l'analisi della root a usare il backend.
- Mantenere export CSV dalla UI per controllo umano.

### C. Backlog database

- Installare PostgreSQL sul server Linux.
- Creare database dedicato all'applicazione.
- Definire tabella `attendance_records`.
- Definire tabella `import_batches`.
- Aggiungere indici su corso, data, email, meeting id.
- Definire una unique key pragmatica per i doppioni.
- Preparare backup e dump periodici.

### D. Backlog server Linux

- Installare Python runtime e virtual environment.
- Installare PostgreSQL.
- Preparare utente di sistema dedicato all'app.
- Configurare variabili ambiente.
- Mettere il backend dietro reverse proxy.
- Definire servizio `systemd` per l'app Python.
- Valutare se tenere PostgreSQL sullo stesso host di n8n o separarlo piu' avanti.
- Definire una strategia di log minima.

### E. Backlog qualita'

- Creare qualche CSV di test anonimo o minimizzato.
- Scrivere test sul parser Zoom.
- Scrivere test sulle regole presenza.
- Scrivere test sulla deduplica.
- Testare casi sporchi: email mancanti, nomi varianti, piu' segmenti, meeting doppi, import ripetuti.

## Scelte tecniche consigliate adesso

Per evitare dispersione, le scelte migliori in questa fase mi sembrano:

- tenere **FastAPI** come backend unico;
- tenere **PostgreSQL** come storage centrale;
- trattare `adapter/` come base da integrare, non da buttare;
- trattare la UI in `static/` come base dell'area analitica;
- non automatizzare ancora il recupero Zoom: prima consolidare formato, persistenza e flusso umano;
- introdurre automazione solo dopo che il flusso manuale e' stabile.

## Rischi principali

- unire troppo presto UI, logica di import e logica di analisi senza prima fissare il modello dati;
- non decidere subito la regola di unicita' dei record;
- perdere la distinzione tra dato calcolato e correzione manuale;
- cercare di modellare tutto subito come prodotto finito invece di chiudere prima il flusso base.

## Definizione pratica del prossimo passo

Il prossimo passo sensato non e' ancora "deployare tutto", ma:

1. fissare il formato interno canonico;
2. definire lo schema PostgreSQL minimo;
3. decidere come l'adapter inviera' i dati al backend;
4. poi preparare il server Linux.

## Nota finale

La lettura piu' corretta del repository, oggi, e' questa:

- non c'e' un solo prodotto finito;
- ci sono due semi-strumenti con una logica compatibile;
- il lavoro da fare e' trasformarli in una pipeline unica:
  - Zoom -> normalizzazione -> salvataggio server -> analisi.

Questo documento va considerato una base di lavoro e non una specifica definitiva.
