# Esposizione: lettura delle fatture ricorrenti

La pagina `/utilities/esposizione` e' protetta dall'autenticazione applicativa
ed e' collegata da Strumenti interni. Mostra i dati ricevuti e la previsione
mensile delle fatture ricorrenti in CHF, con grafico e dettaglio apribile.

## Utilizzo

1. Aprire Esposizione e trascinare il pulsante nei preferiti, oppure copiare
   il codice mostrato e sostituire l'URL del preferito di prova.
2. In Smallinvoice aprire le fatture ricorrenti e ordinare la pagina corrente.
3. Cliccare il preferito e confermare i conteggi. La stessa scheda apre Rebekko.
4. Controllare la tabella e il contenuto delle eventuali righe da verificare.

Il bookmarklet identifica la tabella visibile dalle intestazioni inglesi,
gestisce l'intestazione Frequency con colspan=2 e include solo le righe
con Next valorizzato (esclude anche i trattini usati come segnaposto).
Non visita altre pagine e non modifica Smallinvoice. Le righe con struttura
diversa vengono mostrate separatamente, senza considerarle fatture.

## Bookmarklet pronto da copiare

Per ricreare il preferito, chiamalo **Esposizione Rebekko** e incolla nel
campo **URL** tutta la riga qui sotto, compreso `javascript:`. Usalo dalla
pagina delle fatture ricorrenti Smallinvoice, dopo aver impostato l'ordinamento.

Questo e' lo stesso bookmarklet generato dalla pagina Esposizione per il sito
di produzione; non occorre modificarlo o eseguire altri comandi.

```text
javascript:(function%20(read%2C%20target)%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20try%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20if%20(location.origin%20!%3D%3D%20%22https%3A%2F%2Fapp.smallinvoice.com%22)%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20throw%20new%20Error(%22Usa%20questo%20preferito%20sulla%20pagina%20delle%20fatture%20ricorrenti%20Smallinvoice.%22)%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20const%20payload%20%3D%20read(document)%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20const%20url%20%3D%20target%20%2B%20%22%23esposizione%3D%22%20%2B%20encodeURIComponent(JSON.stringify(payload))%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20if%20(url.length%20%3E%2060000%20%7C%7C%20payload.scanned%20%3E%202000)%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20throw%20new%20Error(%22Troppi%20dati%20per%20il%20trasferimento.%20Riduci%20le%20righe%20nella%20pagina%20e%20riprova.%22)%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20if%20(confirm(%22Aprire%20Esposizione%20su%20Rebekko%3F%5Cn%5Cn%22%20%2B%20payload.rows.length%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%2B%20%22%20righe%20con%20Next%5Cn%22%20%2B%20payload.excluded%20%2B%20%22%20escluse%20senza%20Next%5Cn%22%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%2B%20payload.unrecognized.length%20%2B%20%22%20righe%20da%20verificare%5Cn%5CnViene%20letta%20soltanto%20la%20pagina%20corrente.%22))%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20location.assign(url)%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%20%20%20%20%7D%20catch%20(error)%20%7B%20alert(error.message)%3B%20%7D%0A%20%20%20%20%20%20%20%20%7D)(function%20readRecurringPage(doc)%20%7B%0A%20%20%20%20%20%20%20%20const%20normalize%20%3D%20value%20%3D%3E%20value.replace(%2F%5Cs%2B%2Fg%2C%20%22%20%22).trim().toLowerCase()%3B%0A%20%20%20%20%20%20%20%20const%20required%20%3D%20%5B%22frequency%22%2C%20%22customer%22%2C%20%22first%20invoice%22%2C%20%22next%22%2C%20%22end%20date%22%2C%20%22amount%22%2C%20%22status%22%5D%3B%0A%20%20%20%20%20%20%20%20const%20matches%20%3D%20%5B%5D%3B%0A%20%20%20%20%20%20%20%20for%20(const%20table%20of%20doc.querySelectorAll(%22table%22))%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20if%20(!table.getClientRects().length)%20continue%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20for%20(const%20header%20of%20%5B...table.rows%5D.slice(0%2C%205))%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20const%20cells%20%3D%20%5B...header.cells%5D%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20if%20(!required.every(label%20%3D%3E%20cells.some(cell%20%3D%3E%20normalize(cell.innerText)%20%3D%3D%3D%20label)))%20continue%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20let%20width%20%3D%200%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20const%20columns%20%3D%20%7B%7D%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20for%20(const%20cell%20of%20cells)%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20const%20span%20%3D%20cell.colSpan%20%7C%7C%201%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%2F%2F%20Smallinvoice%20merges%20Preview%20%2B%20Frequency%20in%20its%20header.%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20columns%5Bnormalize(cell.innerText)%5D%20%3D%20width%20%2B%20span%20-%201%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20width%20%2B%3D%20span%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20matches.push(%7B%20table%2C%20header%2C%20columns%2C%20width%20%7D)%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20break%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20if%20(matches.length%20!%3D%3D%201)%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20throw%20new%20Error(%22Apri%20le%20fatture%20ricorrenti%3A%20trovate%20%22%20%2B%20matches.length%20%2B%20%22%20tabelle%20compatibili%2C%20attesa%20una%20sola.%22)%3B%0A%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20const%20%7B%20table%2C%20header%2C%20columns%2C%20width%20%7D%20%3D%20matches%5B0%5D%3B%0A%20%20%20%20%20%20%20%20const%20rows%20%3D%20%5B%5D%3B%0A%20%20%20%20%20%20%20%20const%20unrecognized%20%3D%20%5B%5D%3B%0A%20%20%20%20%20%20%20%20let%20excluded%20%3D%200%3B%0A%20%20%20%20%20%20%20%20const%20dataRows%20%3D%20%5B...table.rows%5D.slice(%5B...table.rows%5D.indexOf(header)%20%2B%201)%3B%0A%20%20%20%20%20%20%20%20for%20(const%20row%20of%20dataRows)%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20const%20cells%20%3D%20%5B...row.cells%5D%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20if%20(cells.length%20!%3D%3D%20width%20%7C%7C%20cells.some(cell%20%3D%3E%20cell.colSpan%20%3E%201%20%7C%7C%20cell.rowSpan%20%3E%201))%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20unrecognized.push(cells.map(cell%20%3D%3E%20cell.innerText.trim()))%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20continue%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%20%20%20%20const%20get%20%3D%20label%20%3D%3E%20cells%5Bcolumns%5Blabel%5D%5D.innerText.trim()%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20const%20next%20%3D%20get(%22next%22)%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20if%20(!next%20%7C%7C%20%2F%5E%5B-%E2%80%93%E2%80%94%5D%2B%24%2F.test(next))%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20excluded%2B%2B%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20continue%3B%0A%20%20%20%20%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20%20%20%20%20rows.push(%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20frequency%3A%20get(%22frequency%22)%2C%20customer%3A%20get(%22customer%22)%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20first%3A%20get(%22first%20invoice%22)%2C%20next%2C%20end%3A%20get(%22end%20date%22)%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20amount%3A%20get(%22amount%22)%2C%20status%3A%20get(%22status%22)%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%7D)%3B%0A%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%20%20%20%20return%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20version%3A%201%2C%20capturedAt%3A%20new%20Date().toISOString()%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20source%3A%20%22https%3A%2F%2Fapp.smallinvoice.com%22%2C%20scanned%3A%20dataRows.length%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20excluded%2C%20rows%2C%20unrecognized%2C%0A%20%20%20%20%20%20%20%20%7D%3B%0A%20%20%20%20%7D%2C%22https%3A%2F%2Frebekko.pnlevolution.com%2Futilities%2Fesposizione%22)%3B
```

Nota manutenzione: se cambia `makeBookmarklet` o `readRecurringPage` in
`utilities/esposizione-core.js`, aggiornare anche questa copia usando il
bookmarklet mostrato dalla pagina Esposizione.

## Trasferimento e conservazione

I dati sono passati nel frammento `#esposizione=` dell'URL, non nella query.
Il login conserva questo frammento solo per la destinazione Esposizione.
La pagina rimuove il frammento dall'indirizzo, valida il contenuto e lo
conserva in sessionStorage per consentire il ricaricamento della scheda.
Il pulsante Rimuovi dati cancella questa copia. Non esiste persistenza DB.
Il trasferimento e' bloccato oltre 60.000 caratteri di URL o 2.000 righe;
in quel caso occorre ridurre le righe nella pagina sorgente.

## Previsione mensile

Ogni serie genera fatture da Next fino a End date inclusa. Le frequenze
supportate sono Monthly ed Every 6 months, come nello script originale.
Per i giorni 29-31 il giorno viene limitato all'ultimo giorno del mese breve,
senza perdere il giorno originario nei mesi successivi. Gli importi vengono
sommati in centesimi interi. Date, importi o frequenze non riconosciuti e
date finali mancanti sono segnalati come esclusioni dal calcolo.

Grafico e tabella includono tutti i mesi dalla prima all'ultima emissione,
anche quelli a zero, senza filtrare automaticamente le date precedenti a oggi.
Il grafico si scorre orizzontalmente e ogni barra apre il dettaglio del mese.
La tabella originale delle serie importate resta disponibile sotto il riepilogo.
Il mese e' quello di emissione, non una previsione dei tempi effettivi di pagamento.

I pulsanti Copia tabella mensile e Copia dettaglio fatture copiano testo con
colonne separate da tabulazioni, incollabile nei fogli di calcolo. Il riepilogo
include tutti i mesi e la riga totale; il dettaglio include ogni fattura prevista.
Se il browser blocca gli appunti, viene mostrato il testo selezionabile.
Non serve aggiornare il bookmarklet per utilizzare queste visualizzazioni.

## Verifiche

```bash
node --test tests/test_esposizione.cjs tests/test_esposizione_forecast.cjs
python -m pytest tests -q
```

I file di esempio forniti dall'utente non sono asset dell'applicazione
e non devono essere inclusi nei commit o nel deploy.
