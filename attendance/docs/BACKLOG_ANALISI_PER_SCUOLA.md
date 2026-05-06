# Backlog Analisi Per Scuola

Catalogo delle funzionalita' da portare nel sistema nuovo per l'uso amministrativo/didattico della scuola.

## Fonte corretta letta

La sorgente giusta non e' `attendance/adapter`.

La URL `/attendance/view` risponde a:

- `attendance/static/index.html`

Quindi questo backlog deriva da quello che fa davvero la view attuale:

- `attendance/static/index.html`
- `attendance/static/courses-config.js`

## Scopo della view attuale

La view attuale lavora su un dataset gia' “scolastico”, simile a un registro presenze consolidato.

Non e' una view di pulizia Zoom.

Fa soprattutto queste cose:

- carica un CSV “attendance data”
- pulisce i record vuoti
- filtra e analizza corsi / studenti / staff
- calcola presenze per soglia esame
- esporta i risultati filtrati

## Funzionalita' osservate nella view attuale

### 1. Import dataset scuola

Funzionalita' esistenti:

- upload file CSV
- nome file caricato visibile
- stato di caricamento
- pulizia record con `Check-in status` vuoto

### 2. Statistiche globali iniziali

Funzionalita' esistenti:

- record totali
- record validi
- record vuoti rimossi
- corsi unici
- conteggi unici separati per:
  - studenti
  - docenti
  - tutor

Nota:

La distinzione studenti/docenti/tutor oggi nasce da convenzioni nel nome:

- `(DOCENTE)`
- `(TUTOR)`

### 3. Filtro per tipo persona

Funzionalita' esistenti:

- mostra/nasconde:
  - studenti
  - docenti
  - tutor
- click rapido sulle card filtro

Questa funzione e' molto utile per la scuola e va mantenuta.

### 4. Filtro per corso

Funzionalita' esistenti:

- select corso
- vista focalizzata su un corso specifico

### 5. Filtro per studente

Funzionalita' esistenti:

- select studente
- dettaglio di uno studente dentro un corso

### 6. Toggle “Mostra anche assenti”

Funzionalita' esistenti:

- possibilità di escludere gli assenti dalla tabella

Questa e' una funzione piccola ma utile.

### 7. Evidenzia studenti inattivi

Funzionalita' esistenti:

- checkbox per attivare highlight inattivi
- numero configurabile di ultime lezioni da controllare
- logica:
  - studente senza presenze nelle ultime N lezioni
  - oppure con sole assenze nelle ultime N lezioni

Questa funzione va backloggata esplicitamente: e' un valore reale per la scuola.

### 8. Tabella risultati

Funzionalita' esistenti:

- corso
- data
- studente
- stato presenza
- percentuale / informazione di frequenza
- badge ruolo
- highlight inattivi

### 9. Summary per studente nel corso

Funzionalita' esistenti:

- lezioni partecipate
- eventuale breakdown:
  - presenze regolari
  - correzione manuale / adjustment
- totale lezioni corso
- percentuale presenza
- soglia richiesta
- esito:
  - puo' fare esame
  - soglia non raggiunta

Questo e' uno dei pezzi piu' importanti da riportare.

### 10. Summary per corso

Funzionalita' esistenti:

- nome corso
- descrizione corso
- lezioni svolte
- totale lezioni previsto
- soglia richiesta
- numero studenti iscritti
- corso aperto vs corso con totale lezioni definito

### 11. Configurazione corsi

La view attuale usa una configurazione esterna per corso.

Concetti osservati:

- `totalLessons`
- `attendanceThreshold`
- `description`
- `active`
- `adjustments` per singolo studente

Questo e' un pezzo strutturale, non cosmetico.

### 12. Regole di presenza scuola

La view attuale traduce gli stati presenza in punteggio:

- assente = `0`
- uscito = `0.5`
- presente = `1`

Questa logica non e' la stessa della pulizia Zoom.

Questa e' logica di **analisi scuola** e va modellata separatamente.

### 13. Export CSV filtrato

Funzionalita' esistenti:

- export del dataset filtrato corrente
- campi export semplici:
  - `Class name`
  - `Date`
  - `First name`
  - `Last name`
  - `Check-in status`

Questa e' una funzione minima, ma serve.

## Traduzione in backlog per il sistema nuovo

## Fase 1 — Fondazione analitica su dati `official`

### A. Nuova area “Analisi scuola”

Creare una nuova area separata dal workflow `drafts`.

Vincolo:

- deve leggere solo dati `official`
- non deve essere una UI di correzione

### B. Dataset scuola derivato dai dati official

Serve una proiezione coerente dei dati attendance per uso scuola.

Campi minimi:

- corso
- data lezione
- nome canonico
- cognome / nome visualizzato
- email
- stato finale
- eventuale ruolo

### C. Ruoli persona

Funzionalita' da decidere bene:

- studenti
- docenti
- tutor

Nel legacy il ruolo viene inferito dal nome.

Nel sistema nuovo va valutato se:

- tenerlo come convenzione temporanea
- oppure renderlo un attributo vero

## Fase 2 — Summary globale

### D. Statistiche globali

Portare una summary iniziale simile all'attuale:

- record totali
- record validi
- corsi unici
- studenti unici
- docenti unici
- tutor unici

### E. Filtri globali

Funzionalita' richieste:

- filtro corso
- filtro studente
- filtro tipo persona
- toggle mostra assenti

## Fase 3 — Analisi corso

### F. Summary per corso

Portare:

- lezioni svolte
- totale lezioni previsto
- soglia richiesta
- descrizione corso
- numero studenti iscritti / comparsi
- distinzione:
  - corso aperto
  - corso con percorso strutturato

### G. Configurazione corso

Serve una casa chiara per:

- totale lezioni
- soglia esame
- descrizione
- attivo / non attivo

Questo oggi vive in `courses-config.js`.

Nel nuovo sistema va backloggato come configurazione persistita o almeno centralizzata.

## Fase 4 — Analisi studente

### H. Summary per studente nel corso

Da riportare:

- lezioni partecipate
- percentuale presenza
- soglia richiesta
- puo' fare esame / non puo' fare esame

### I. Breakdown frequenza

Da riportare:

- presenze regolari
- eventuali correzioni / adjustment

Questo punto e' importante per audit amministrativo.

## Fase 5 — Regole scuola

### L. Punteggio stati presenza

Serve un modulo esplicito per la logica scuola.

Regola osservata oggi:

- `assente = 0`
- `uscito = 0.5`
- `presente = 1`

Domande backlog da chiarire:

- `prima_meta` e `seconda_meta` nel sistema nuovo scuola come si mappano?
- valgono `0.5` entrambe?
- `presente` resta `1`?
- eventuali override devono influenzare direttamente questa metrica?

### M. Soglia esame

Regola osservata oggi:

- `attendanceThreshold`
- confronto su percentuale finale

Questa regola va riportata in modo dichiarativo, non sparso.

## Fase 6 — Inattivi

### N. Rilevazione studenti inattivi

Portare esplicitamente:

- checkbox o filtro dedicato
- numero di ultime lezioni configurabile
- highlight degli inattivi

Definizione osservata oggi:

- nessuna presenza nelle ultime N lezioni
- oppure solo assenze nelle ultime N lezioni

Questa e' una funzione molto utile lato scuola.

## Fase 7 — Export

### O. Export filtrato

Funzionalita' richiesta:

- export del sottoinsieme corrente
- coerente con i filtri attivi

### P. Export per uso amministrativo

Possibili export da backloggare:

- per corso
- per studente
- per esame / idoneita'

## Fase 8 — Decisioni tecniche da prendere

### Q. Dove vive la configurazione corsi?

Oggi:

- `attendance/static/courses-config.js`

Da decidere:

- file config temporaneo
- tabella DB
- UI admin futura

### R. Come gestire gli adjustment?

Oggi esistono adjustment manuali per studente/corso.

Da decidere:

- mantenerli come concetto
- oppure ricondurli solo a correzioni/override attendance gia' fatte a monte

### S. Come mappare i ruoli?

Oggi i ruoli vengono dedotti dai nomi.

Da decidere:

- continuare cosi' in prima fase
- oppure introdurre un modello vero

## Priorita' consigliata

### Priorita' 1

- nuova area `Analisi scuola`
- summary globale
- filtri base
- summary corso
- summary studente
- logica soglia esame
- export filtrato

### Priorita' 2

- inattivi
- adjustment espliciti
- configurazione corsi persistita

### Priorita' 3

- export piu' ricchi
- strumenti amministrativi piu' evoluti

## Vincolo forte

La nuova analisi scuola deve partire da dati `official`.

Non deve dipendere da:

- draft
- marker temporanei
- operazioni di pulizia ancora in corso

Il flusso corretto resta:

1. Zoom grezzo
2. pulizia / review / official
3. analisi scuola
