# Handoff sviluppo - Consulente contabile e predizioni

Questo documento serve a orientare uno sviluppatore che deve continuare il lavoro
sulla funzionalita' di contabilità/predizione movimenti bancari.

La funzionalita' e' volutamente isolata dal resto dell'applicazione: se viene
rimossa la pagina `utilities/accounting-consultant.html`, gli endpoint
`/api/utilities/accounting/*`, il package `backend/accounting_app/` e lo schema
`accounting_*`, il resto di Rebekko continua a funzionare.

## Obiettivo funzionale

Dato un CSV bancario, il sistema deve proporre un conto contabile per ogni
movimento, lasciando esplicitamente in revisione i casi incerti.

Il flusso previsto e':

1. L'utente carica un CSV bancario nella pagina nascosta
   `/utilities/accounting-consultant`.
2. Il backend normalizza testo/importi e produce una predizione per riga.
3. L'utente corregge i casi sbagliati o incerti.
4. Le correzioni vengono salvate e devono migliorare i giri successivi.
5. Le regole deterministiche devono essere modificabili da UI, non tramite
   deploy di codice.

## File principali

- `utilities/accounting-consultant.html`: UI sperimentale del consulente
  contabile. Non e' esposta nelle card principali.
- `backend/main.py`: route HTML e API `/api/utilities/accounting/*`.
- `backend/accounting_app/models.py`: dataclass del dominio contabile.
- `backend/accounting_app/services.py`: parsing CSV, normalizzazione,
  ranking/predizione e validazioni applicative.
- `backend/db/accounting_repository.py`: persistenza PostgreSQL per conti,
  code hint, feedback, training examples e regole configurabili.
- `sql/schema/012_accounting_consultant.sql`: schema base contabilità.
- `sql/schema/013_accounting_prediction_rules.sql`: regole deterministiche
  configurabili.
- `scripts/import_accounting_legacy.py`: import iniziale dei dati legacy
  dalla vecchia implementazione.

## Tabelle attuali

### `accounting_accounts`

Dizionario dei conti contabili disponibili.

Campi rilevanti:

- `code`: codice conto, per esempio `3400`, `6552`, `6660`.
- `description`: descrizione leggibile.
- `active`: se `false`, il conto resta nello storico ma non viene proposto.

### `accounting_code_hints`

Regole manuali esplicite nel testo. Se nel movimento compare `c:qualcosa`, il
sistema cerca `qualcosa` e forza il conto associato.

Uso previsto: casi dove l'utente vuole guidare manualmente una transazione.

### `accounting_feedback`

Feedback salvati dalla UI.

Ci sono due varianti operative:

- `Salva con importo`: match su testo normalizzato e importo.
- `Salva solo testo`: match su testo normalizzato, senza importo.

Il feedback viene valutato prima delle regole configurabili e prima degli
esempi storici.

### `accounting_training_examples`

Esempi storici importati dalla vecchia implementazione. Sono usati per scoring
testuale semplice, non sono ancora vero ML.

Limite importante: la somiglianza testuale da sola non basta per molti casi
reali, perché i testi bancari cambiano spesso e importi simili/diversi possono
essere poco indicativi.

### `accounting_prediction_rules`

Regole deterministiche configurabili da UI.

Campi principali:

- `name`: nome umano della regola.
- `account_code`: conto da proporre.
- `priority`: ordine di valutazione, crescente.
- `active`: abilita/disabilita senza cancellare.
- `amount_sign`: `any`, `positive`, `negative`.
- `min_abs_amount`, `max_abs_amount`: limiti opzionali sull'importo assoluto.
- `required_tokens`: tutti questi token devono essere presenti.
- `any_tokens`: almeno uno di questi token deve essere presente.
- `message`: spiegazione mostrata nella predizione.

Regole iniziali create dallo schema `013`:

- Accrediti clienti scuola -> `3400`
- Ordine collettivo OPAE piccolo -> `6660`
- Wise verso Panoramen -> `4401`
- POSTA CH SA -> `6552`

## Ordine di predizione

Il motore segue questo ordine:

1. Code hint esplicito `c:...`
2. Feedback salvato in `accounting_feedback`
3. Regole configurabili in `accounting_prediction_rules`
4. Fallback legacy hardcoded, solo se la tabella regole non e' disponibile
5. Esempi storici `accounting_training_examples`
6. `review`, se non c'e' una proposta sufficientemente chiara

Nota importante: se la tabella `accounting_prediction_rules` esiste, le regole
DB comandano. Le vecchie regole hardcoded sono solo una rete di sicurezza per
non rompere la pagina prima di applicare lo schema.

## Stato attuale della UI

La pagina `/utilities/accounting-consultant` permette di:

- caricare un CSV bancario e vedere le predizioni;
- filtrare le righe da revisionare cliccando sul contatore;
- esportare le righe visibili in CSV;
- salvare feedback con importo o solo testo;
- gestire code hint;
- gestire conti contabili;
- vedere, modificare e cancellare feedback salvati;
- vedere, modificare e cancellare regole deterministiche configurabili.

La UI e' ancora un tool interno, non rifinito come prodotto finale.

## Decisioni gia' prese

- L'importo non deve dominare la classificazione dei pagamenti clienti:
  movimenti tipo `ACCREDITO MITTENTE... COMUNICAZIONI...` sono spesso ricavi
  scuola `3400` indipendentemente dall'importo.
- Le regole deterministiche devono stare in DB, non nel codice, perché devono
  essere correggibili senza deploy.
- Il frontend non deve contenere logica contabile sostanziale: deve mostrare,
  inviare correzioni e gestire CRUD. La decisione resta nel backend.
- Questo modulo deve restare isolato e cancellabile senza impattare Attendance.
- La soluzione attuale non e' ancora ML. E' un ibrido: regole configurabili,
  feedback persistito ed esempi storici.

## Cosa manca

### 1. Migliorare il motore di apprendimento

Il punto aperto principale e' decidere quanto spingersi verso ML/vector search.

L'idea originale della vecchia app era: il sistema impara dai feedback. Quello
attuale salva feedback e regole, ma non ha ancora un vero modello che generalizza.

Possibile evoluzione pragmatica:

- tenere regole DB per casi business ovvi;
- tenere feedback esatto per correzioni puntuali;
- aggiungere un classificatore leggero su testo normalizzato + token + direzione
  importo;
- introdurre embeddings/vector search solo se il classificatore leggero non
  basta.

### 2. Rendere le regole piu' espressive

La tabella `accounting_prediction_rules` supporta solo:

- segno importo;
- range importo assoluto;
- token obbligatori;
- almeno uno tra alcuni token.

Potrebbero servire:

- token vietati;
- regex;
- gruppi di condizioni `AND/OR`;
- priorita' per banca;
- regole legate al tipo movimento;
- soglia di confidenza configurabile.

Non aggiungere tutto subito: prima raccogliere casi reali.

### 3. Separare meglio “regole” e “training”

Oggi:

- `accounting_prediction_rules` = regole deterministiche generali;
- `accounting_feedback` = correzioni utente puntuali;
- `accounting_training_examples` = esempi storici legacy.

Questa separazione e' utile, ma il prossimo sviluppatore deve decidere se:

- mantenere tre livelli distinti;
- trasformare feedback e training examples in un unico dataset supervisionato;
- generare automaticamente suggerimenti di nuove regole dai feedback ricorrenti.

### 4. Report di qualità

Serve una vista o sezione che dica:

- quante righe sono auto-classificate;
- quante restano in review;
- quali regole producono piu' match;
- quali regole generano piu' correzioni successive;
- quali conti sono spesso confusi.

Senza questi numeri si rischia di “sentire” che il sistema migliora senza
misurarlo.

### 5. Test automatici

Al momento non ci sono test dedicati al consulente contabile. Sono stati fatti
solo smoke test manuali/inline.

Test minimi da aggiungere:

- parsing PostFinance;
- parsing Raiffeisen, se ancora supportato;
- code hint vince su tutto;
- feedback vince sulle regole;
- regola configurabile vince sugli esempi storici;
- se `accounting_prediction_rules` non esiste, il fallback legacy non rompe;
- export CSV UI non rompe la pagina.

### 6. Migrazione dati legacy

Lo script `scripts/import_accounting_legacy.py` esiste, ma va eseguito con la
venv applicativa e con `DATABASE_URL` configurato.

Sul server tipicamente:

```bash
cd /opt/rebekko/webapps
export DATABASE_URL="$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)"
.venv/bin/python scripts/import_accounting_legacy.py
```

Non usare `python` generico sul server: spesso non punta alla venv corretta.

## Comandi operativi utili

Applicare schema:

```bash
cd /opt/rebekko/webapps
export DATABASE_URL="$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)"
psql "$DATABASE_URL" -f sql/schema/012_accounting_consultant.sql
psql "$DATABASE_URL" -f sql/schema/013_accounting_prediction_rules.sql
```

Smoke check pagina/API:

```bash
curl -s https://rebekko.pnlevolution.com/api/utilities/accounting/accounts
curl -s https://rebekko.pnlevolution.com/api/utilities/accounting/prediction-rules
```

Log errori produzione:

```bash
journalctl -u rebekko-webapps -p err -n 100 --no-pager
```

## Rischi noti

- Se una regola configurabile e' troppo larga, classifica troppe righe in modo
  sbagliato. Usare priorita' e token con disciplina.
- Se si salva “solo testo” su un testo troppo generico, il feedback puo'
  catturare casi futuri non desiderati.
- Se si disattiva una regola DB pensando che resti il fallback hardcoded, non e'
  cosi': quando la tabella regole esiste, il DB comanda.
- I dati CSV possono contenere informazioni reali/sensibili: non committare
  export bancari o zip legacy.

## Prossimo passo consigliato

Prima di introdurre ML vero, fare un giro operativo con le regole configurabili:

1. Importare un CSV reale.
2. Correggere i casi evidenti creando regole DB, non codice.
3. Salvare feedback solo dove serve davvero un match puntuale.
4. Misurare quante righe restano in review.
5. Solo dopo decidere se aggiungere un modello ML/vector search.

Il criterio pratico e': se con regole DB + feedback scendiamo abbastanza sotto
la soglia di fatica umana, non serve complicare. Se restano troppi casi variabili
e ricorrenti, allora il passo successivo e' un dataset supervisionato e un
classificatore.
