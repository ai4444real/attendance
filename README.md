# Sistema Gestione Presenze

Sistema web per la gestione e l'analisi delle presenze scolastiche. Permette di importare, pulire, filtrare e visualizzare i dati di attendance provenienti da sistemi legacy.

## Caratteristiche

### Importazione e Pulizia Dati
- **Caricamento CSV**: Import diretto di file CSV con parsing robusto
- **Pulizia automatica**: Rimozione record con dati incompleti (check-in status vuoto)
- **Validazione**: Gestione errori e feedback chiaro all'utente

### Visualizzazione
- **Tabella ordinata**: Dati organizzati per Corso → Data → Studente
- **Formattazione date**: Formato italiano (gg/mm/aaaa)
- **Badge ruoli**: Identificazione visuale di Docenti e Tutor
- **Stati presenza colorati**:
  - Verde: Presente in aula
  - Blu: Presente su Zoom
  - Rosso: Assente
  - Giallo: Uscito prima

### Filtri Avanzati
- **Filtro per Corso**: Visualizza solo un corso specifico
- **Filtro per Studente**: Visualizza le presenze di un singolo studente
- **Filtri cascading**: Il dropdown studenti si adatta al corso selezionato
- **Toggle Assenti**: Nascondi/mostra gli studenti assenti (default: nascosti)
- **Reset rapido**: Ripristino immediato di tutti i filtri

### Statistiche
Dashboard con metriche in tempo reale:
- Record totali processati
- Record validi (con check-in status)
- Record vuoti rimossi
- Numero di corsi unici
- Numero di studenti unici

## Tecnologie

- **HTML5** - Struttura
- **CSS3** - Styling responsive
- **JavaScript ES6+** - Logica applicativa
- **Architettura a layer** - Separazione delle responsabilità

## Architettura

Il codice segue le best practice dello sviluppo software professionale con una chiara separazione in layer:

```
┌─────────────────────────────────────────┐
│         APPLICATION LAYER               │
│  (App - Orchestrazione e controllo)     │
└────────────┬────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
┌───▼──────────┐  ┌──▼────────────────┐
│  UI LAYER    │  │  BUSINESS LOGIC   │
│ (UIService)  │  │ (AttendanceService)│
└──────────────┘  └───────────┬────────┘
                              │
                        ┌─────▼──────┐
                        │ DATA LAYER │
                        │(DataService)│
                        └────────────┘
```

### Layer

**DataService (Data Layer)**
- Parsing CSV con gestione quote
- Validazione input
- Accesso dati grezzo

**AttendanceService (Business Logic Layer)**
- Pulizia e trasformazione dati
- Ordinamento e filtraggio
- Calcolo statistiche
- Raggruppamenti per corso/studente
- Funzioni pure e riutilizzabili

**UIService (Presentation Layer)**
- Rendering HTML
- Formattazione date e testi
- Gestione DOM
- Protezione XSS
- Popolamento filtri

**App (Application Controller)**
- Orchestrazione flussi
- Event handling
- State management
- Error handling

## Come Usare

1. **Apri** il file `index.html` nel browser
2. **Carica** il file CSV tramite il pulsante "Carica File CSV"
3. **Visualizza** i dati puliti e ordinati automaticamente
4. **Filtra** per corso, studente, o nascondi gli assenti
5. **Analizza** le statistiche in tempo reale

## Formato CSV Richiesto

```csv
Class name,Date,First name,Last name,Check-in time,Check-in status,Check-out time,Check-out status
Corso Nome,MM/DD/YYYY,Nome,Cognome,HH:MM:SS AM/PM,Status,,
```

**Campi utilizzati:**
- `Class name`: Nome del corso
- `Date`: Data della lezione
- `First name`: Nome studente (può includere `(DOCENTE)` o `(TUTOR)`)
- `Last name`: Cognome studente
- `Check-in status`: Stato presenza (es. "Presente in aula", "Presente su Zoom", "Assente")

**Nota**: I campi `Check-in time`, `Check-out time` e `Check-out status` sono ignorati (timestamp non affidabili).

## Privacy e Sicurezza

- **Elaborazione locale**: Tutti i dati rimangono nel browser, nessun upload a server
- **XSS Protection**: Escape HTML automatico per prevenire injection
- **No tracking**: Zero analytics o telemetria
- **File CSV escluso dal repo**: I dati sensibili non sono versionati

## Roadmap

### Prossime funzionalità
- [ ] Vista dettaglio corso (report completo per corso)
- [ ] Vista dettaglio studente (storico presenze)
- [ ] Export dati filtrati (PDF/Excel)
- [ ] Grafici e statistiche avanzate
- [ ] Gestione qualità (alert per studenti con troppe assenze)
- [ ] Tool per docenti (registri, certificati presenza)

### Visione futura
Questo progetto è concepito come un modulo del futuro "Sistema Operativo della Scuola" - una piattaforma integrata per la gestione completa delle attività scolastiche.

## Struttura File

```
attendance/
├── index.html          # Applicazione completa (HTML + CSS + JS)
├── README.md           # Questa documentazione
├── .gitignore          # File da escludere dal versioning
└── *.csv              # File dati (locale, non versionato)
```

## Licenza

Progetto interno - Uso scolastico

## Contributi

Sviluppato con l'obiettivo di semplificare la gestione delle presenze e fornire insight utili per docenti e amministrazione.

---

**Versione**: 1.0
**Ultimo aggiornamento**: Dicembre 2024
