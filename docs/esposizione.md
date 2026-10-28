# Esposizione: lettura delle fatture ricorrenti

La pagina `/utilities/esposizione` e' protetta dall'autenticazione applicativa
ed e' collegata da Strumenti interni. Questa prima versione mostra i dati
ricevuti; non calcola ancora le previsioni mensili.

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

## Trasferimento e conservazione

I dati sono passati nel frammento `#esposizione=` dell'URL, non nella query.
Il login conserva questo frammento solo per la destinazione Esposizione.
La pagina rimuove il frammento dall'indirizzo, valida il contenuto e lo
conserva in sessionStorage per consentire il ricaricamento della scheda.
Il pulsante Rimuovi dati cancella questa copia. Non esiste persistenza DB.
Il trasferimento e' bloccato oltre 60.000 caratteri di URL o 2.000 righe;
in quel caso occorre ridurre le righe nella pagina sorgente.

## Verifiche

```bash
node --test tests/test_esposizione.cjs
python -m pytest tests -q
```

I file di esempio forniti dall'utente non sono asset dell'applicazione
e non devono essere inclusi nei commit o nel deploy.
