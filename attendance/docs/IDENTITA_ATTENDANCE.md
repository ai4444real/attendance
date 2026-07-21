# Identita Attendance

Questo documento spiega il ragionamento che ha portato al modello attuale delle
identita nel dominio attendance.

## Problema

Le presenze arrivano da sorgenti operative:

- Zoom
- correzioni manuali
- presenze manuali
- in futuro QR form o import analoghi

Queste sorgenti non garantiscono una vera anagrafica studenti. Lo stesso
studente puo comparire come:

- nome completo con email
- stesso nome senza email
- email diversa
- nome abbreviato o sporco
- device name

Non vogliamo pero obbligare l'utente a registrare prima uno studente in una
anagrafica. Il sistema deve continuare a funzionare anche solo con dati
osservati.

## Decisione centrale

La lezione e' la sorgente osservata.

L'identita e' la persona stabile derivata dalle lezioni.

Quindi:

- `attendance_lesson_participants` conserva cosa e' stato osservato e
  normalizzato in una lezione.
- `attendance_identities` consolida quelle osservazioni in persone stabili.
- Le funzionalita future come insiemi didattici e report scuola dovranno
  puntare all'identita stabile, non a stringhe nome/email.

## Cosa non deve cambiare

Il merge delle presenze nella singola lezione non deve essere riscritto adesso.

Il meccanismo gia stabile resta:

1. import o rebuild lezione
2. applicazione alias attivi
3. calcolo partecipanti della lezione
4. merge locale dei partecipanti compatibili
5. salvataggio dei partecipanti normalizzati

Questo meccanismo e' delicato e ha gia risolto molti casi reali. L'introduzione
di `identity_id` non deve cambiare i calcoli della lezione.

## Alias

Gli alias sono correzioni operative:

```text
quando vedi X, trattalo come Y
```

Oggi vivono in:

```text
attendance_identity_aliases
```

La tabella contiene ancora:

- `canonical_full_name`
- `canonical_email`
- `alias_type`
- `alias_full_name`
- `normalized_alias_key`
- `is_active`

Questi campi restano per compatibilita con il codice esistente.

Abbiamo aggiunto:

```text
identity_id
```

Questo collega l'alias alla persona stabile in `attendance_identities`, ma non
sostituisce ancora i campi canonical usati dal merge lezioni.

## Identita

La tabella:

```text
attendance_identities
```

ha ora un id stabile:

```text
id
```

e mantiene anche una chiave tecnica:

```text
identity_key
```

La `identity_key` serve per riconoscere e aggiornare le righe in modo tecnico:

- `email:...` quando c'e una email
- `name:...` quando abbiamo solo nome

Ma la chiave da usare per funzionalita future e':

```text
attendance_identities.id
```

## Identita forte e debole

Regola concettuale:

- identita forte: ha email
- identita debole: ha solo nome

Durante il rebuild delle identita:

- se un nome senza email corrisponde a una sola identita forte con lo stesso
  nome normalizzato, converge su quella identita forte;
- se lo stesso nome ha piu email forti, il record senza email resta separato;
- se esiste un alias, l'alias viene applicato prima di generare l'identita.

Questa scelta evita merge automatici pericolosi, ma risolve i casi non ambigui.

## Rebuild identita

L'endpoint:

```text
POST /api/attendance/identities/rebuild
```

esiste ancora, ma non e' piu esposto come bottone nella UI.

Motivo:

- non cancella righe;
- aggiunge o aggiorna identita osservate;
- non riallinea automaticamente tutti gli alias;
- e' quindi uno strumento di manutenzione, non un'azione ordinaria.

Il comando per cancellare tutto e ripartire non e' in UI. Se serve, e'
manuale:

```sql
TRUNCATE TABLE attendance_identities RESTART IDENTITY;
```

Da usare solo con consapevolezza.

## Flusso attuale sicuro

Per correggere identita:

1. creare alias dalla UI alias o dalla pagina identita;
2. applicare alias alle lezioni se serve consolidare i partecipanti;
3. ricostruire identita solo come manutenzione;
4. se necessario, aggiornare `attendance_identity_aliases.identity_id` per casi
   particolari.

## Perche non usare subito identity_id nelle lezioni

E' naturale pensare:

```text
fammi vedere tutto di questa identita
```

Questo arrivera.

Pero per ora la lezione resta autonoma:

- contiene partecipanti normalizzati;
- conserva le sorgenti originali;
- supporta rebuild e correzioni locali;
- non dipende ancora da `identity_id` per calcolare le presenze.

In futuro si potra aggiungere:

```text
attendance_lesson_participants.identity_id
```

ma solo come collegamento derivato, non come base del calcolo delle presenze.

## Uso futuro negli insiemi didattici

Gli insiemi didattici dovranno riferirsi agli studenti tramite:

```text
attendance_identities.id
```

Non tramite:

- nome
- email
- `identity_key`
- partecipante di una singola lezione

Questo garantisce che se domani aggiungiamo un alias, una email o una
correzione, le relazioni gia create sugli insiemi non perdano il riferimento.

## Checkpoint git

Prima dell'introduzione dell'id stabile e' stato creato il tag:

```text
before-identity-id-migration
```

Serve come punto di ritorno se la migrazione identita dovesse creare problemi.
