# Insiemi Didattici Per Scuola

## Problema

I dati Zoom normalizzati ci dicono:
- quale lezione e' avvenuta
- chi era presente
- con quale stato di presenza

Ma non ci dicono ancora **per quale percorso scolastico** quella lezione vale per uno studente.

Esempio:
- una lezione di `Practitioner` puo' valere anche per `Training Autogeno 2026`
- la stessa lezione puo' valere anche per `Medicina Accademica 2026`
- uno studente puo' appartenere a piu' percorsi contemporaneamente

Quindi non basta mappare banalmente `corso -> percorso`.

## Decisione

Introduciamo il concetto di **insieme didattico**.

Un insieme didattico e' un contenitore logico, per esempio:
- `Training Autogeno 2026`
- `Medicina Accademica 2026`

L'insieme non sostituisce il corso reale.
Serve per la rendicontazione e l'analisi scuola.

## Modello concettuale

Ci servono tre relazioni:

1. `lesson -> insieme`
- una lezione puo' appartenere a piu' insiemi

2. `studente -> insieme`
- uno studente puo' appartenere a piu' insiemi

3. `studente + insieme + lesson`
- si deriva automaticamente quando:
  - la lezione appartiene all'insieme
  - lo studente appartiene all'insieme

## Conseguenza importante

La stessa presenza puo' comparire in piu' report.

Esempio:
- la lesson `Practitioner 2026-03-10` appartiene a:
  - `Training Autogeno 2026`
  - `Medicina Accademica 2026`
- Gino appartiene a entrambi gli insiemi

Allora la stessa presenza di Gino:
- compare nel report di `Training Autogeno 2026`
- compare nel report di `Medicina Accademica 2026`

Questo non e' un errore.
E' il comportamento voluto.

## Perche' questa soluzione

Questa scelta evita di:
- modellare subito tutta la scuola e tutta la programmazione
- decidere a livello globale che un intero corso appartiene sempre a un percorso
- costruire subito un'anagrafica completa di studenti/iscrizioni

E permette invece di:
- associare manualmente le lezioni agli insiemi giusti
- associare gli studenti agli insiemi giusti
- ottenere report utili senza riscrivere i dati attendance

## Cosa non stiamo facendo adesso

Per ora **non** stiamo ancora modellando:
- la programmazione completa dei corsi
- le iscrizioni amministrative ufficiali
- un mapping globale e definitivo `corso -> percorso`

Questo potra' arrivare piu' avanti.

## MVP futuro

Il primo MVP coerente con questa decisione e':

- tabella `lesson_sets`
- tabella `lesson_set_lessons`
- tabella `lesson_set_students`

Con questo possiamo gia' costruire:
- vista di un insieme
- vista di uno studente dentro un insieme
- assenze implicite derivate dalle lezioni dell'insieme senza doverle materializzare subito nel DB
