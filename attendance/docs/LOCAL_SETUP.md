# 🚀 Local Development Setup

Guida per eseguire l'applicazione Attendance System in locale per testing e sviluppo.

## 📋 Prerequisiti

- Python 3.9 o superiore
- pip (package manager Python)
- Git

---

## 🔧 Setup Iniziale

### 1. Clona il repository (se non l'hai già fatto)

```bash
git clone <repository-url>
cd webapps
```

### 2. Installa le dipendenze Python

```bash
pip install -r requirements.txt
```

Questo installerà:
- FastAPI (web framework)
- Uvicorn (server ASGI)
- httpx (HTTP client)
- python-dotenv (environment variables loader)

### 3. Configura le variabili d'ambiente

#### A. Copia il file template:

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

#### B. Recupera il Client Secret:

1. Vai su **Render Dashboard** → Tua app → **Environment**
2. Copia il valore di `GOOGLE_CLIENT_SECRET`

#### C. Modifica il file `.env`:

Apri `.env` con un editor di testo e incolla il secret:

```env
GOOGLE_CLIENT_SECRET=il_tuo_secret_copiato_da_render
PORT=8080
```

⚠️ **IMPORTANTE**: Il file `.env` non viene committato su git (è in `.gitignore`). Non condividerlo mai!

## ▶️ Avvio del Server Locale

### Metodo 1: Script principale (con auto-reload)

```bash
python -m backend.main
```

Il server partirà su: **http://localhost:8080**

### Metodo 2: Uvicorn diretto

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8080
```

---

## 🧪 Testing

1. Apri il browser e vai su: http://localhost:8080
2. Dovresti vedere l'applicazione Attendance System
### Test delle nuove feature:

#### Inactive Students Detection:
1. Carica un file CSV
2. Seleziona un corso dal filtro
3. Spunta "Evidenzia studenti inattivi"
4. Gli studenti senza presenze nelle ultime N lezioni saranno evidenziati in giallo

---

## 🔍 Troubleshooting

### Errore: "GOOGLE_CLIENT_SECRET not set"
- Verifica che il file `.env` esista
- Verifica che contenga il secret corretto
- Riavvia il server dopo aver modificato `.env`

### Il server non parte
```bash
# Verifica che la porta 8080 non sia già in uso
# Windows:
netstat -ano | findstr :8080

# Linux/Mac:
lsof -i :8080

# Se la porta è occupata, cambia PORT nel file .env
```

### Auto-reload non funziona
- Verifica di aver installato uvicorn[standard]: `pip install uvicorn[standard]`
- L'auto-reload funziona solo per modifiche ai file Python, non agli HTML/CSS/JS statici

---

## 📁 Struttura del Progetto

```
webapps/
├── backend/
│   ├── __init__.py             # Backend package
│   └── main.py                 # FastAPI server principale del workspace
├── requirements.txt            # Dipendenze Python condivise
├── .env                        # Variabili d'ambiente (NON committato)
├── .env.example                # Template per .env
├── setup-local.bat             # Setup locale Windows
├── start-server.bat            # Avvio server locale Windows
└── attendance/
    ├── docs/
    │   └── LOCAL_SETUP.md      # Questa guida
    ├── data/                   # File di lavoro e dataset storici
    ├── adapter/                # Prototipo Zoom adapter
    └── static/
        ├── index.html          # Frontend principale del modulo
        ├── courses-config.js   # Configurazione corsi
        ├── js/
        └── ...
```

---

## 🚢 Deploy in Produzione

Le modifiche in locale non sono automaticamente in produzione. Per deployare:

```bash
git add .
git commit -m "Descrizione modifiche"
git push
```

Render riceverà il push e farà automaticamente il deploy.

---

## 💡 Tips per lo Sviluppo

1. **Console del Browser**: Apri sempre la console (F12) per vedere log e errori
2. **Network Tab**: Utile per debuggare chiamate API
3. **LocalStorage**: Alcuni stati sono salvati in localStorage, svuotalo se hai problemi
4. **Hot Reload**: Modifica il codice e ricarica la pagina (non serve riavviare Python per file statici)

---

## 🆘 Supporto

Per problemi o domande:
- Controlla i log del server nella console
- Controlla la console del browser (F12)
- Verifica che tutte le dipendenze siano installate
- Verifica che Google OAuth sia configurato correttamente

---

**Happy Coding! 🎉**
