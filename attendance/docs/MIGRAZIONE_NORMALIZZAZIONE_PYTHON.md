# Migrazione normalizzazione Zoom in Python

## Scopo

Portare la logica oggi presente in `attendance/adapter/js/` dentro Python, senza toccare il JavaScript esistente e senza rompere il flusso operativo attuale.

Regola di lavoro:

- il JavaScript resta `readonly` finche' la migrazione non e' consolidata;
- ogni blocco viene migrato in quest'ordine:
  1. caso d'uso dedotto dal JS;
  2. test espliciti;
  3. implementazione Python;
  4. confronto con il comportamento attuale.

## Stato

### Fase 1: regole di presenza pure

Obiettivo:

- portare in Python la funzione che decide `presente / prima_meta / seconda_meta / assente`.

Stato:

- completata

Comando test attuale:

```bash
python -m unittest attendance.tests.attendance_normalization.test_presence_rules -v
```

Perche' questa fase viene per prima:

- e' la parte piu' piccola e piu' facile da testare in modo esplicito;
- non dipende ancora da parser o detector;
- mette subito sotto test la regola amministrativa finale.

## Fasi successive

### Fase 2: selezione meeting/corsi da elaborare

Obiettivo:

- portare in Python la regola del frontend che preseleziona i meeting rilevanti;
- replicare il comportamento attuale basato sui nomi corso in maiuscolo.

Stato:

- in corso

Comando test attuale:

```bash
python -m unittest attendance.tests.attendance_normalization.test_meeting_selection -v
```

Nota:

- questa fase non decide ancora "cosa e' una lezione" in senso business;
- replica solo la regola attuale del JS, che usa il maiuscolo come filtro pratico iniziale.

### Fase 3: aggregazione minuti per prima/seconda parte

Obiettivo:

- portare in Python l'aggregazione dei segmenti Zoom di uno stesso partecipante;
- calcolare minuti presenti e durate per le due meta' della lezione.

Attenzione:

- questa fase dipende da due marker critici:
  - marker blu: `effectiveStart`
  - marker giallo: `breakPoint`

Rischio:

- alto

Stato:

- in corso

Comando test attuale:

```bash
python -m unittest attendance.tests.attendance_normalization.test_temporal_markers -v
```

Nota importante:

- il marker blu viene portato in Python come euristica `:00 / :30`, uguale al JS;
- il marker giallo viene portato con la stessa logica `valley / boundary` del JS;
- questo non significa che siano "giusti sempre", ma che sono ora testabili e verificabili fuori dal browser.

Comando test attuale:

```bash
python -m unittest attendance.tests.attendance_normalization.test_aggregator -v
```

Nota:

- questi due punti non vanno automatizzati "a sensazione";
- servono test espliciti che mostrino cosa succede quando il docente apre Zoom prima del vero inizio, o quando la pausa reale non coincide con la meta' matematica.

### Fase 4: detection automatica dei marker temporali

Obiettivo:

- portare in Python la logica del `BreakDetector`;
- decidere in modo riproducibile:
  - inizio effettivo;
  - pausa/split tra prima e seconda parte.

Rischio:

- molto alto

Strategia:

- prima si congelano casi reali;
- poi si scrivono test di regressione;
- solo dopo si implementa Python.

### Fase 5: parser CSV Zoom

Obiettivo:

- portare in Python il parsing dei CSV Zoom e la costruzione dei meeting con segmenti.

Punti da coprire:

- BOM;
- righe vuote;
- campi mancanti;
- piu' segmenti per lo stesso partecipante;
- meeting multipli nello stesso file.

### Fase 6: report di normalizzazione e casi dubbi

Obiettivo:

- produrre da backend un output strutturato con:
  - record normalizzati;
  - warning;
  - casi dubbi;
  - possibili suggerimenti di merge o override.

## Criteri di accettazione

La migrazione Python e' accettabile solo se:

- i test spiegano chiaramente i casi d'uso;
- il comportamento e' uguale o piu' esplicito rispetto al JS;
- i casi borderline restano correggibili a mano;
- i marker blu e giallo non vengono trattati come "banali".

## Backlog di sviluppo immediato

- Completare la Fase 1 con test eseguibili e documentati.
- Mantenere come comando standard dei test di normalizzazione:
  - `python -m unittest attendance.tests.attendance_normalization.test_presence_rules -v`
- Definire un set minimo di fixture Zoom anonime per i casi reali.
- Scrivere i primi casi di test sui marker:
  - Zoom aperto prima dell'inizio reale;
  - pausa reale evidente;
  - assenza di pausa reale;
  - lezione con split manuale necessario.
