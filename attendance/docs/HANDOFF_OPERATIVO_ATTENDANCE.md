# Handoff Operativo Attendance

Documento corto per riprendere il lavoro senza dover rileggere tutta la storia della chat.

## Obiettivo del sistema

Pipeline desiderata:

1. import CSV Zoom grezzo
2. normalizzazione automatica
3. salvataggio nel database come `draft`
4. review lezione per lezione
5. correzioni persistite
6. `official` solo quando deciso esplicitamente

## Regole di dominio già decise

- L'unità di lavoro è la **lezione**, non il batch.
- Una lezione resta `draft` finché non viene marcata `official`.
- `ignored` significa “non lavorabile / non rilevante”, non “ufficiale”.
- I batch servono come contenitore operativo, ma lo stato vero è sulle lezioni.
- In UI si mostrano di default i batch che contengono ancora almeno una lezione draft non ignorata.

## Identità e alias

- Gli alias storici non stanno più solo in `attendance/config/identity_rules.json`.
- All'avvio vengono bootstrapati in `attendance_identity_aliases`.
- Gli alias nuovi creati dalla UI vanno nel database.
- `Unisci` deve restare **un solo gesto lato utente**.
- Il backend decide se registrare:
  - alias `full_name`
  - alias `email`

### Regola importante

- Alias ambigui globali sono pericolosi.
- Esempi da evitare come alias globale:
  - `Utente Zoom`
  - nomi troppo generici
  - device name generici
- In quei casi si usa override presenza sulla lezione, non alias identità.

## Rebuild lezione draft

Decisione forte già presa:

- la lesson draft **non si patcha**
- la lesson draft si **ricostruisce da zero**

Source of truth:

- `attendance_lesson_source_segments`
- marker correnti della lezione
- alias identità attivi
- review actions attive

Documentazione tecnica completa:

- `RICOSTRUZIONE_LEZIONE_DRAFT.md`

### Conseguenza pratica

- dopo `Unisci`, la lesson corrente deve ricostruirsi subito
- e deve restare coerente anche a refresh, restart o ricalcoli successivi

## Review actions

Le review actions vengono persistite subito nel DB.

Non sono “ufficializzazione”.

Modello corretto:

- import raw -> DB
- review action -> DB
- draft ricalcolato -> DB
- `official` -> cambio di stato della lezione

### Storico vs attivo

- nel DB si può tenere lo storico completo
- nel calcolo conta solo l'ultima action attiva per tipo

## Duplicati import

Regola già implementata:

- se una lesson con stessa chiave naturale esiste già, non viene importata

Chiave usata oggi:

- `course_name`
- `source_meeting_id`
- `lesson_date`

Comportamento desiderato:

- duplicate = riconosciute
- duplicate = riportate nel risultato import
- duplicate = **non persistite**

### Implicazione importante

Se un import contiene solo duplicati:

- non viene creato nessun batch

## Cancellazioni

È già possibile:

- cancellare una lesson da un batch
- cancellare un batch intero
- disattivare un alias dalla tabella alias

### Semantica

- cancellare una lesson elimina quella lesson e i suoi dati collegati
- non tocca le altre lesson equivalenti in altri batch
- disattivare un alias non cancella storia, lo rende inattivo

## Timezone

Decisione importante e recente:

- gli orari Zoom vanno interpretati come `Europe/Zurich`
- la correzione va fatta **una sola volta nel parser**
- non sparsa tra DB, UI e servizi

Fix già fatto:

- `backend/attendance_normalization/zoom_parser.py`
- `_parse_zoom_datetime(...)` restituisce datetime aware `Europe/Zurich`

### Conseguenza

- i nuovi import sono corretti
- i batch già salvati prima del fix restano offset e vanno reimportati se si vuole coerenza completa

## Origine record

La modal `Origine` serve come strumento di controllo, non come view decorativa.

Regola attuale:

- deve mostrare tutte le sorgenti raw confluite nella persona della lesson
- anche quando la stessa persona compare su più righe / email / record nascosti nei presenti

### Attenzione

- `Origine` è utile per capire cosa è arrivato da Zoom
- non va interpretata come “storia di tutte le correzioni”

## Casi già emersi e capiti

### Andrea Facchi

- stesso nome
- email diverse/sporche
- `Unisci` va interpretato come merge identità vero
- dopo il rebuild corretto, deve risultare una sola riga coerente

### Mihaela Colombo

- due email invertite, ma stessa persona
- `Origine` prima era incompleta
- la percentuale apparente “strana” si capisce solo vedendo tutte le sorgenti
- spesso il problema non è il calcolo ma la mancata unione identità

## UI: principi emersi

- lavorare su una lezione sola alla volta
- lista lezioni a sinistra, dettaglio al centro
- batch compatti, non protagonisti
- evitare rumore:
  - non mostrare i presenti nella tabella principale se sono già a posto
  - preferire percentuali a `minuti/minuti`
  - usare `official` per togliere dal rumore ciò che è già chiuso

## Cose che valgono ancora

- `attendance/import` è il punto di ingresso giusto
- `attendance/drafts` è la postazione operativa
- `attendance/aliases` è una view di controllo utile

## Quando NON usare alias

Non creare alias globale se:

- il nome è generico
- la label è ambigua
- sai la presenza corretta solo per conoscenza umana locale

In quei casi:

- usa override presenza sulla lezione specifica

## Note operative sul repo

- questo progetto vive dentro un repo più grande: `webapps`
- `git rev-parse --show-toplevel` punta al parent repo
- i commit/push avvengono lì, anche se lavori nella sottocartella `attendance`

### File locali da non toccare

- eventuali CSV in `attendance/data/` cancellati o lock temporanei dell'utente non vanno ripristinati né committati

## Deploy server

Flusso standard:

```bash
cd /opt/rebekko/webapps
./deploy.sh
```

`deploy.sh` già fa:

- `git pull --ff-only origin main`
- install requirements
- restart servizio
- health check con retry

## Migration SQL già esistenti

- `001_initial_schema.sql`
- `002_attendance_identity_aliases.sql`
- `003_attendance_identity_alias_types.sql`
- `004_attendance_lesson_source_segments.sql`

Quando si introduce una migration nuova:

- va applicata sul server
- e va verificato owner/grant coerente con `rebekko_app`

## Cosa controllare se “qualcosa non torna”

Ordine consigliato:

1. alias attivi in `attendance/aliases`
2. `Origine` della persona nella lesson
3. marker della lesson (`inizio`, `pausa`, `fine`, `threshold`)
4. se il problema è identity merge o ricalcolo draft
5. se il batch è stato importato prima o dopo fix importanti (soprattutto timezone)

## Regola finale

Se una correzione sembra “patch locale”, fermarsi.

Le parti delicate sono:

- identity merge
- rebuild draft
- timezone

Lì va cercata **la soluzione unica e coerente**, non il workaround.
