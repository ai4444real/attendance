# Attendance: ricostruzione corretta della singola lezione draft

## Scopo

Questo documento definisce **LA** soluzione per il rebuild di una singola lezione draft.

Il problema da evitare e' questo:

- si crea o modifica una regola di identita' (`Unisci`);
- la UI dice che la lezione e' stata aggiornata;
- ma il draft della lezione resta incoerente:
  - doppioni ancora presenti;
  - percentuali assurde;
  - una riga nuova piu' una vecchia superstite;
  - review action agganciate a righe che non esistono piu'.

La regola guida e':

- una lezione draft **non si patcha**
- una lezione draft si **ricostruisce da zero**

## Decisione chiave

La source of truth del rebuild **non** puo' essere `attendance_lesson_participants`.

Quella tabella e':

- una proiezione derivata;
- gia' influenzata da merge precedenti;
- gia' influenzata da review action;
- quindi non e' abbastanza affidabile per una ricostruzione robusta.

La source of truth del rebuild deve essere il livello piu' grezzo persistito per quella lezione:

- segmenti originali persistiti;
- identita' originali osservate;
- marker correnti della lezione;
- threshold corrente;
- review action persistite.

## Modello corretto

Per una singola lezione esistono tre strati distinti:

### 1. Dati grezzi di lezione

Sono i dati "come arrivano da Zoom", o il piu' vicino possibile:

- nomi osservati;
- email osservate;
- segmenti temporali;
- meeting start/end originali.

Questi dati non vanno riscritti a ogni correzione.

### 2. Regole e correzioni

Sono i fatti che influenzano il rebuild:

- alias identita';
- marker (`effective_start`, `break_point`, `effective_end`);
- threshold;
- manual override presenza;
- stato `ignored` / `official`.

Queste informazioni vanno persistite separatamente.

### 3. Proiezione draft corrente

E' il risultato calcolato della lezione:

- partecipanti aggregati;
- minuti prima/seconda meta';
- stato presenza;
- summary finale;
- diagnostica.

Questo strato puo' essere distrutto e ricreato in ogni momento.

## Regola operativa fondamentale

Ogni volta che una correzione cambia la struttura della lezione, il sistema deve fare:

1. leggere i dati grezzi della lezione;
2. leggere tutte le regole/correzioni attive;
3. ricostruire la lezione da zero;
4. sostituire integralmente la proiezione draft corrente.

Non:

- aggiornare qualche riga;
- cancellarne una parte;
- lasciare sopravvivenze "comode".

## Casi che devono usare il rebuild completo

### A. `Unisci`

`Unisci` e' il caso piu' delicato.

Per la singola lezione corrente deve voler dire:

- salva la regola identita' nel DB;
- rigenera la lezione draft completa;
- al termine deve esistere **una sola identita' finale coerente**.

Se restano due `Andrea Facchi`, il rebuild ha fallito.

### B. Cambio marker

Se si cambia:

- inizio utile;
- pausa;
- fine utile;

serve rigenerare i minuti a partire dai segmenti grezzi.

### C. Cambio threshold

Qui il rebuild puo' essere piu' leggero, ma concettualmente resta una ricostruzione della proiezione:

- i minuti restano uguali;
- cambiano gli stati presenza.

### D. Manual override presenza

Qui i minuti non cambiano.
Ma il valore finale mostrato e la summary si aggiornano sulla proiezione draft.

## Algoritmo corretto del rebuild

Per una singola lezione:

1. carica i dati grezzi della lezione
2. carica alias identita' attivi
3. carica marker correnti
4. carica threshold corrente
5. carica review action correnti
6. applica le regole identita' ai segmenti grezzi
7. raggruppa i segmenti per identita' finale
8. calcola i minuti sulle meta' usando i marker correnti
9. determina lo stato presenza calcolato
10. applica eventuali manual override presenza
11. ricostruisce summary e diagnostica
12. sostituisce integralmente la proiezione draft della lezione

## Sostituzione integrale: significato preciso

Sostituire integralmente significa:

- il set finale dei partecipanti draft della lezione deve essere esattamente quello ricostruito;
- nessuna riga vecchia puo' restare "appesa";
- nessun partecipante puo' sopravvivere se non esiste nel risultato ricostruito.

Regola verificabile:

- se il rebuild produce `34` identita' finali,
- `attendance_lesson_participants` per quella `lesson_id` deve finire con `34` righe.

Non `35`.
Non `34 + un residuo`.

## Review action: principio corretto

Le review action devono restare storico di audit.

Pero', durante il rebuild:

- il sistema non deve "fidarsi" delle vecchie righe partecipante;
- deve applicare le action allo stato ricostruito.

In particolare:

- `set_threshold_ratio`: si applica alla lezione
- `set_effective_start`: si applica alla lezione
- `set_break_point`: si applica alla lezione
- `set_effective_end`: si applica alla lezione
- `set_manual_presence_status`: si applica all'identita' finale corrente
- `clear_manual_presence_status`: rimuove l'override su quell'identita'

## Problema aperto importante

Le action che oggi puntano a `participant_id` sono fragili.

Perche':

- il `participant_id` puo' cambiare o sparire dopo un merge identita'

La soluzione robusta futura e':

- introdurre una chiave identita' stabile per la lezione
  oppure
- introdurre una chiave persona stabile a livello dominio

Finche' non esiste quella chiave, ogni rebuild che cambia il set partecipanti deve avere una logica esplicita di remap.

## Implicazione di schema

Per fare bene il rebuild serve separare in modo netto:

- dati grezzi lezione
- proiezione draft lezione

La direzione consigliata e' introdurre una tabella dedicata, per esempio:

- `attendance_lesson_source_segments`

o struttura equivalente.

Questa tabella deve contenere:

- `lesson_id`
- nome osservato
- email osservata
- join time
- leave time
- eventuale raw identity key

La proiezione finale continua invece a stare in:

- `attendance_lesson_participants`

## Stato attuale del progetto

Oggi il sistema conserva abbastanza informazione da tentare un rebuild, ma non ha ancora la forma ideale.

In particolare:

- stiamo ancora reusando parti della proiezione corrente come base di rebuild;
- questo espone a incoerenze nei casi sporchi.

Quindi la soluzione definitiva non e' "aggiungere una toppa al merge".
La soluzione definitiva e':

- formalizzare il livello source della lezione;
- rifare il rebuild sulla source;
- trattare `attendance_lesson_participants` come puro output.

## Decisione finale

La soluzione corretta da implementare e':

- rebuild totale della singola lezione draft;
- basato su dati grezzi persistiti;
- con regole e review action applicate sopra;
- con sostituzione integrale del draft finale.

Da evitare:

- patch incrementali sulle righe partecipante;
- merge "furbi" che lasciano residui;
- uso della proiezione draft come base logica del rebuild.

## Prossimo lavoro corretto

Ordine consigliato:

1. mappare con precisione il livello source gia' persistito oggi;
2. decidere se basta o se serve tabella source dedicata;
3. introdurre il rebuild totale della lesson su quella source;
4. solo dopo semplificare `Unisci`, marker e review action sopra quel motore.

Questa e' la base per non farci uccidere dal rebuild.
