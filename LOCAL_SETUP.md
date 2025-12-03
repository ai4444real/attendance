# 🚀 Local Development Setup

Guida per eseguire l'applicazione Attendance System in locale per testing e sviluppo.

## 📋 Prerequisiti

- Python 3.9 o superiore
- pip (package manager Python)
- Git
- Account Google Cloud con OAuth configurato

---

## 🔧 Setup Iniziale

### 1. Clona il repository (se non l'hai già fatto)

```bash
git clone <repository-url>
cd attendance
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

### 4. Configura Google OAuth Console

Per permettere l'autenticazione da localhost:

1. Vai su: https://console.cloud.google.com/apis/credentials
2. Trova il tuo **OAuth 2.0 Client ID**
3. Clicca per modificarlo
4. Aggiungi questi URL:

**Authorized JavaScript origins:**
```
http://localhost:8080
```

**Authorized redirect URIs:**
```
http://localhost:8080/oauth-callback
```

5. **Salva** le modifiche

---

## ▶️ Avvio del Server Locale

### Metodo 1: Script principale (con auto-reload)

```bash
python app.py
```

Il server partirà su: **http://localhost:8080**

### Metodo 2: Uvicorn diretto

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

---

## 🧪 Testing

1. Apri il browser e vai su: http://localhost:8080
2. Dovresti vedere l'applicazione Attendance System
3. Prova a connetterti a Google Calendar:
   - Clicca "Connetti Google Calendar"
   - Autorizza l'applicazione
   - Se tutto funziona, vedrai "✅ Connesso!"

### Test delle nuove feature:

#### Calendar Selection:
1. Connetti Google Calendar
2. Clicca "Mostra Calendari"
3. Apri la console del browser (F12)
4. Dovresti vedere tutti i calendari disponibili
5. Copia un ID calendario e usa: `CalendarIntegration.selectCalendar("id")`

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

### Errore OAuth: "redirect_uri_mismatch"
- Controlla che `http://localhost:8080/oauth-callback` sia nelle Authorized redirect URIs
- Verifica di non avere una porta diversa (es. 8000 invece di 8080)
- Attendi qualche minuto dopo aver salvato le modifiche su Google Cloud Console

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
attendance/
├── app.py                      # FastAPI server principale
├── requirements.txt            # Dipendenze Python
├── .env                        # Variabili d'ambiente (NON committato)
├── .env.example               # Template per .env
├── static/
│   ├── index.html             # Frontend principale
│   ├── courses-config.js      # Configurazione corsi
│   ├── js/
│   │   ├── google-auth.js     # OAuth handler
│   │   ├── google-calendar-api.js  # Calendar API wrapper
│   │   └── oauth-config.js    # OAuth config loader
│   └── oauth-callback.html    # OAuth callback page
└── LOCAL_SETUP.md             # Questa guida
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
