# Lesson Plan e programmazione scolastica

Stato: decisione progettuale per il prossimo sviluppo  
Data: 7 agosto 2026

## Obiettivo

Portare Lesson Plan e, progressivamente, la programmazione oggi gestita nella spreadsheet Google dentro Rebekko.

Il sistema deve aiutare a lavorare, non impedire una lezione perché manca una classificazione. Catalogo, piani e versioni servono alla qualità; la sessione operativa deve poter essere creata rapidamente anche con dati incompleti.

Attendance rimane autonomo in questa fase.

## Linguaggio del dominio

### Corso casa

Il corso che organizza la propria sequenza didattica, per esempio `Practitioner 2026`.

Per ora non distinguiamo tipo di corso, edizione, classe o coorte. Nel catalogo esiste semplicemente il corso.

### Unità didattica

La lezione astratta prevista nel programma del corso, per esempio `Autoipnosi Ericksoniana`.

Ha un titolo e un ordine nel corso. Può esistere senza piano di lezione e senza sessioni.

### Piano di lezione

Descrive come svolgere l'unità didattica: obiettivi, temi, tempi, metodi e strumenti. Il contenuto attuale di Lesson Plan resta valido e “segue” questo oggetto.

Il piano è opzionale e versionato.

### Sessione

L'evento concreto nel tempo: quella che nel linguaggio quotidiano chiamiamo “la lezione di stasera”.

Contiene data, orari, docenti, tutor, destinatari, cartella Drive, URL Zoom e stato operativo.

Nell'interfaccia possiamo continuare a chiamarla **lezione**. `Session` serve nel codice e nel database per evitare ambiguità.

## Modello dell'MVP

```text
Corso casa
└── Unità didattiche ordinate
    ├── Piano di lezione opzionale
    │   └── Versioni immutabili
    └── Sessioni
        ├── pianificate
        ├── erogate
        └── annullate

Sessioni non classificate
└── dati operativi validi, unità e corso da assegnare in seguito
```

Cardinalità iniziali:

- un corso ha molte unità didattiche;
- un'unità appartiene a un solo corso casa;
- un'unità ha zero o un piano;
- un piano ha una o più versioni;
- un'unità ha zero o più sessioni;
- una sessione importata può temporaneamente non avere un'unità e quindi neppure un corso.

Questa struttura rappresenta solo il catalogo dei corsi casa. Non tenta ancora di modellare tutti i corsi che partecipano a una sessione condivisa.

## Regole lazy

1. Un corso può esistere senza unità.
2. Un'unità può esistere senza piano.
3. Una sessione può essere pianificata o erogata senza piano.
4. Una sessione importata può restare senza corso e unità nella coda `Da classificare`.
5. Dati mancanti generano indicatori e filtri, non blocchi.
6. Da un corso deve essere possibile creare una lezione inserendo soltanto titolo e data: Rebekko crea insieme l'unità minima e la sessione.
7. Nessuna regola del catalogo blocca Attendance.

## Stati della sessione

| Stato | Significato |
|---|---|
| `planned` | Sessione prevista |
| `delivered` | Sessione avvenuta |
| `cancelled` | Sessione annullata |

Transizioni normali:

```text
planned ──> delivered
   │
   └──────> cancelled ──> planned
```

Una data passata non dimostra che la sessione sia stata erogata. Un import dalla spreadsheet crea quindi una sessione `planned`, salvo conferma esplicita.

Il ritorno da `delivered` richiede una correzione amministrativa tracciata.

## Versioni del piano

Le versioni sono snapshot immutabili.

- la prima scrittura crea la versione 1;
- una modifica reale crea la versione successiva;
- salvare contenuto identico non crea una versione;
- una sessione pianificata segue normalmente la versione corrente;
- quando passa a `delivered`, conserva la versione utilizzata;
- modifiche successive al piano non cambiano lo storico;
- una sessione erogata senza piano resta valida e senza versione.

Se una sessione viene confermata molto tempo dopo ed esistono più versioni, l'utente deve poter scegliere quella storicamente corretta.

## Sessioni condivise tra corsi

Una sessione del corso casa Practitioner può essere aperta anche a:

- Assistenti Practitioner;
- Training Autogeno;
- Mentore Aziendale;
- altri gruppi.

Questa realtà è importante, ma non serve ancora strutturarla nel catalogo finché non attribuiamo presenze e costi ai diversi percorsi.

Nell'MVP la sessione conserva la lista ordinata dei destinatari così come arriva dalla spreadsheet. Il primo destinatario può suggerire il corso casa, ma non viene considerato automaticamente una verità.

Esempio:

```json
{
  "audiences": [
    "PRACTITIONER",
    "ASSISTENTI_PRACTITIONER",
    "MENTORE_AZIENDALE",
    "TRAINING_AUTOGENO"
  ]
}
```

Quando servirà, questa lista potrà evolvere in una relazione molti-a-molti tra sessioni e corsi. Non introduciamo ora iscrizioni, attribuzioni o contabilità.

## La spreadsheet attuale

La spreadsheet è il sistema operativo che ha permesso alla scuola di lavorare. Non è solo debito tecnico: è un prototipo validato del futuro registro sessioni.

Una riga rappresenta una sessione e contiene almeno:

| Spreadsheet | Dominio Rebekko |
|---|---|
| `lesson_id` | Identificativo esterno della sessione |
| `titolo_evento` | Titolo evento e possibile suggerimento del corso casa |
| `argomento` | Titolo sessione o suggerimento dell'unità didattica |
| `data`, `ora_inizio`, `ora_fine` | Pianificazione |
| `docenti`, `tutor` | Persone assegnate, inizialmente testuali |
| `destinatari` | Lista ordinata conservata senza interpretazione definitiva |
| `url_cartella` | Cartella Drive dei materiali |
| URL Zoom | Collegamento per partecipare |

Gli Apps Script pubblicano materiali su Classroom e creano eventi nei calendari. Rebekko dovrà progressivamente assumere queste responsabilità tramite servizi backend, senza un passaggio improvviso.

## Cosa conservare dell'esperienza spreadsheet

La futura interfaccia delle sessioni deve mantenere i vantaggi operativi realmente usati:

- vista tabellare compatta, una sessione per riga;
- ordinamento e filtri;
- ricerca;
- colori o badge di stato;
- modifica inline dei campi semplici;
- copia e incolla dove ragionevole;
- azioni massive;
- lavoro collaborativo con modifiche visibili;
- pagina di dettaglio soltanto per operazioni complesse.

Non dobbiamo ricostruire Google Sheets, ma neppure sostituirlo con una sequenza lenta di form.

## Transizione dalla spreadsheet

La sostituzione sarà progressiva:

1. **Lettura:** Rebekko legge la spreadsheet e mostra le sessioni senza scrivere.
2. **Import controllato:** Rebekko persiste le sessioni; la spreadsheet resta autorevole.
3. **Creazione pilota:** alcune sessioni nascono in Rebekko e vengono pubblicate su Google dal backend.
4. **Cambio di autorità:** Rebekko diventa autorevole; la spreadsheet rimane eventualmente come export o controllo.
5. **Dismissione Apps Script:** solo dopo avere coperto e verificato le automazioni reali.

Non manteniamo a lungo una sincronizzazione bidirezionale senza regole di conflitto.

Per ogni riga importata conserviamo:

- sistema sorgente;
- `lesson_id` esterno;
- payload originale;
- hash del contenuto;
- data dell'ultima sincronizzazione.

La coppia sorgente/ID rende l'import idempotente. L'hash segnala modifiche successive.

## Persistenza proposta

Nuovo dominio PostgreSQL separato da Attendance, con prefisso `school_`:

```text
school_courses
school_teaching_units
school_lesson_plans
school_lesson_plan_versions
school_sessions
school_session_status_history
```

Relazioni essenziali:

```text
school_courses.id
    └── school_teaching_units.course_id
            ├── school_lesson_plans.teaching_unit_id
            │       └── school_lesson_plan_versions.lesson_plan_id
            └── school_sessions.teaching_unit_id (nullable per import lazy)
```

Campi principali della sessione:

- `teaching_unit_id` opzionale;
- titolo;
- data e orari pianificati/reali;
- stato;
- docenti e tutor testuali;
- destinatari JSON;
- URL Drive e Zoom;
- sorgente e ID esterno;
- payload e hash della sorgente;
- versione del piano utilizzata, opzionale;
- audit di creazione e modifica.

SQL solo nei repository `backend/db/`; versionamento e transizioni nei servizi del dominio scolastico.

## Confine con Attendance

Attendance continua a registrare una presenza osservata come:

```text
persona + lezione Attendance
```

Il nome Zoom, per esempio `PRACTITIONER 2026-08-07`, non determina il corso al quale attribuire la presenza dello studente.

Gli insiemi didattici restano la soluzione incrementale per i report:

```text
lezione Attendance ── N insiemi
studente ──────────── N insiemi
```

Non assumiamo ora che un insieme didattico sia necessariamente un corso del catalogo.

In futuro Attendance potrà collegarsi opzionalmente a una sessione Rebekko. Solo allora valuteremo corsi partecipanti, iscrizioni e attribuzione della stessa presenza a uno o più percorsi.

## Sequenza di implementazione

### 1. Fotografare il sistema esistente

- inventariare colonne, valori e convenzioni della spreadsheet;
- leggere gli Apps Script e annotare trigger, operazioni Google, errori e retry;
- raccogliere alcuni esempi reali e anonimizzati per i test.

Output: mapping confermato della riga-sessione e lista delle automazioni da sostituire.

### 2. Fondazione del dominio

- migration incrementale per le tabelle `school_*`;
- repository per corsi, unità, piani/versioni e sessioni;
- servizi per versionamento e stati;
- test delle invarianti.

### 3. Primo vertical slice

Realizzare integralmente questo flusso:

> creare un corso, creare un'unità, aggiungere il piano versione 1, pianificare una sessione e marcarla erogata congelando la versione.

Attendance e Google non sono coinvolti.

### 4. Import spreadsheet in sola lettura

- adapter per leggere le righe;
- vista tabellare in Rebekko;
- anteprima di import e rilevazione duplicati;
- coda `Da classificare`;
- nessuna scrittura verso Google.

### 5. Migrare Lesson Plan

- sostituire la persistenza filesystem con API/database;
- mantenere import/export JSON;
- mantenere identiche anteprima e stampa;
- collegare l'editor alle unità didattiche e alle versioni.

### 6. Programmazione operativa

- creazione rapida delle sessioni;
- vista griglia con filtri e modifiche rapide;
- Drive, Zoom, docenti, tutor e destinatari;
- storico degli stati.

### 7. Sostituire gradualmente gli Apps Script

- prima un'automazione a basso rischio;
- stato di sincronizzazione visibile per ogni sessione;
- retry espliciti e idempotenti;
- estensione a Calendar, Classroom e Drive solo dopo verifica sul campo.

## Criteri di accettazione iniziali

Il primo rilascio utile è concluso quando:

1. corsi, unità, piani e sessioni vivono in PostgreSQL;
2. i piani sono versionati e lo storico erogato non cambia;
3. una lezione urgente può essere creata in pochi secondi senza piano;
4. le sessioni importate possono restare da classificare;
5. la lista destinatari viene conservata senza imporre un modello prematuro;
6. JSON, anteprima e stampa di Lesson Plan continuano a funzionare;
7. Rebekko mostra una vista tabellare utilizzabile delle sessioni;
8. la spreadsheet e gli Apps Script non vengono dismessi prima della sostituzione verificata;
9. Attendance continua a funzionare senza catalogo e senza collegamenti obbligatori.

## Decisioni rinviate

- corsi partecipanti come relazioni strutturate;
- iscrizioni degli studenti;
- attribuzione delle presenze ai corsi;
- costi e ripartizione economica della sessione;
- equivalenza tra insiemi didattici e corsi;
- tipi di corso, edizioni, classi e coorti;
- anagrafica strutturata di docenti e aule;
- sincronizzazione bidirezionale completa con Google;
- confronto visuale tra versioni del piano.

Questi punti non devono essere risolti per iniziare. Il modello conserva i dati necessari e lascia aperta l'estensione senza imporla oggi.
