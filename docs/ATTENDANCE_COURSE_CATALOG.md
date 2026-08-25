# Catalogo corsi e arricchimento delle lezioni Attendance

## Perche' questo documento

Attendance nasce dai dati realmente osservati: corsi, lezioni e partecipanti
entrano in Rebekko perche' sono presenti nei file delle presenze, non perche'
siano stati definiti prima in un catalogo.

Questo comportamento deve rimanere invariato. Il catalogo descritto qui serve
ad arricchire e interpretare i dati importati, non a stabilire quali dati siano
ammessi.

Il documento registra le decisioni prese prima dell'implementazione, in modo
che il lavoro possa essere ripreso e verificato anche in un altro contesto.

## Correzione semantica delle viste

L'attuale pagina `/attendance/courses` mostra in realta' le lezioni ufficiali
importate, raggruppate secondo il nome del corso ricevuto dalle presenze.
Quella pagina non e' un catalogo corsi.

La destinazione prevista e':

- `/attendance/courses`: catalogo dei corsi e delle edizioni;
- `/attendance/lessons`: lezioni importate, con il relativo corso osservato.

La navigazione Attendance deve esporre entrambe le funzioni con nomi non
ambigui: "Catalogo corsi" e "Lezioni importate".

## Principio lenient

Il catalogo non deve mai bloccare l'importazione delle presenze.

Una lezione continua a essere importata conservando il `course_name` originale
anche quando:

- il corso non esiste nel catalogo;
- non si trova un'edizione compatibile;
- una chiave e' sconosciuta;
- il matching produce piu' candidati;
- Google non e' disponibile.

In questi casi l'informazione di catalogo rimane assente e l'interfaccia deve
renderlo visibile. La risoluzione puo' avvenire successivamente, anche a mano.

## Concetti distinti

### Corso logico

E' il programma stabile, per esempio `FSEA` o `PRACTITIONER`.

### Edizione

E' una specifica erogazione del corso logico, per esempio:

- `FSEA_04.10.2025`;
- `FSEA_21.03.2026`;
- `FSEA_10.10.2026`.

Alcuni corsi possono avere una sola edizione operativa iniziale. Il modello
deve comunque mantenere separati corso logico ed edizione.

### Identificatore esterno

Un'edizione puo' essere conosciuta da piu' sistemi con valori differenti:

- chiave destinatario dello spreadsheet;
- nome corso osservato nei file Attendance;
- ID Classroom;
- ID Calendar;
- eventuale ID Zoom ricorrente;
- altri identificatori futuri.

Gli identificatori sono una collezione tipizzata, non colonne obbligatorie del
corso. Questo consente piu' alias dello stesso tipo e l'aggiunta di nuove
sorgenti senza cambiare ogni volta lo schema principale.

Gli identificatori stabili, come i nomi osservati da Attendance, appartengono
al corso logico e non vengono ripetuti su tutte le edizioni. Gli identificatori
operativi specifici, come `target_key`, Classroom e Calendar, appartengono
invece all'edizione. Uno Zoom meeting ID viene collocato sul corso logico solo
quando e' realmente comune alle sue edizioni; in caso contrario resta un dato
dell'edizione o della singola lezione.

### Lezione pianificata e lezione osservata

Una riga del foglio `Lezioni` e' una sessione pianificata e possiede un
`lesson_id` esterno stabile. Una riga di `attendance_lessons` e' invece una
lezione osservata attraverso le presenze.

Il matching futuro dovra' collegare esplicitamente queste due identita'. Dopo
la prima associazione non si dovra' ripetere il riconoscimento euristico.

## Significato dei destinatari

Nel foglio `Lezioni`, la colonna `destinatari` contiene una lista ordinata.

- il primo valore e' il corso/edizione di casa, cioe' quello con cui la lezione
  viene erogata online e dal quale normalmente arrivano le presenze;
- i valori successivi indicano altri corsi per i quali la lezione e' valida.

Esempio per la lezione esterna `1209`:

```text
PRACTITIONER, ASSISTENTI_PRACTITIONER,
MENTORE_AZIENDALE, PNL_ESSENTIALS
```

`PRACTITIONER` e' il corso di erogazione. Gli altri sono destinatari secondari.
In una fase successiva questi destinatari diventeranno una relazione tra
lezione pianificata ed edizioni del catalogo.

## Ruolo degli identificatori Zoom

Un identificatore Zoom e' un'evidenza utile, ma non e' automaticamente una
chiave del corso.

- se e' stabile e ricorrente per un'edizione, puo' essere registrato tra gli
  identificatori dell'edizione;
- se identifica una singola sessione, appartiene alla lezione;
- se un link viene riutilizzato da piu' corsi o edizioni, non e' univoco e non
  deve produrre da solo un'associazione automatica.

Il sistema deve conservare questa distinzione e non forzare una cardinalita'
che i dati reali non garantiscono.

## Spreadsheet come sorgente iniziale

Il foglio `Corsi` e' il seme del catalogo. Attualmente espone almeno:

- `target_key`;
- `classroom_course_id`;
- `calendar_id`;
- descrizione/cartella;
- link predefinito.

L'importazione avviene esclusivamente on demand tramite il pulsante
"Importa da Google". Non sono previsti polling o sincronizzazioni temporizzate.

L'importazione deve essere idempotente e best effort:

- crea o aggiorna i record riconosciuti;
- non cancella automaticamente record locali assenti dal foglio;
- non blocca l'intero import per una riga incompleta;
- restituisce un riepilogo di creati, aggiornati, invariati e scartati;
- conserva la provenienza e la data dell'ultima importazione.

L'importazione aggiorna esclusivamente i campi e gli identificatori provenienti
da Google. Non modifica `course_id`, corsi logici o identificatori manuali. Una
nuova edizione nasce con `course_id` nullo e viene mostrata nel gruppo grafico
`N/A`; dopo l'assegnazione si sposta sotto il relativo corso logico. `N/A` non
e' un record del catalogo.

Il foglio non esprime in modo affidabile il raggruppamento tra corso logico ed
edizioni. Per esempio, le tre chiavi FSEA devono essere associate esplicitamente
al corso logico `FSEA`; il prefisso puo' aiutare l'operatore ma non deve essere
considerato una regola definitiva.

## Prima fase di implementazione

La prima fase comprende soltanto:

1. persistenza di corsi logici, edizioni e identificatori;
2. pagina `/attendance/courses` con la tabella del catalogo;
3. pulsante "Importa da Google";
4. importazione on demand del foglio `Corsi`;
5. riepilogo trasparente dell'esito;
6. nuova pagina `/attendance/lessons` per la vista oggi chiamata "Corsi
   importati".

Non comprende ancora:

- matching con `attendance_lessons`;
- import del foglio `Lezioni`;
- sincronizzazione con Calendar, Classroom o Drive;
- sostituzione degli Apps Script;
- sincronizzazione bidirezionale;
- vincoli che impediscano l'arrivo di corsi sconosciuti.

## Direzione del matching futuro

Quando il catalogo sara' stabile, l'arricchimento delle lezioni usera' regole
deterministiche e prudenti:

1. `lesson_id` esterno gia' collegato, quando disponibile;
2. data e corso di casa, risolto dal primo destinatario;
3. alias espliciti del nome corso osservato da Attendance;
4. ora e identificatori Zoom come evidenze aggiuntive;
5. applicazione automatica solo con un candidato univoco;
6. conferma manuale negli altri casi.

L'AI non e' necessaria. Una somiglianza testuale puo' generare un suggerimento,
ma non deve modificare autonomamente il collegamento.

## Confine del progetto

Il catalogo non rappresenta la decisione di trasferire in Rebekko tutte le
funzioni dello spreadsheet.

Lo spreadsheet e gli Apps Script continuano a gestire calendari, Classroom e
materiali. Un eventuale trasferimento di queste responsabilita' verra'
valutato separatamente solo in presenza di un vantaggio operativo molto grande
e verificabile.
