================================================================================
  ATTENDANCE SYSTEM - Script di Sviluppo Locale
================================================================================

📁 Script disponibili:

  🚀 start-server.bat
     → Avvia il server locale su http://localhost:8080
     → Usa questo per testare modifiche in locale
     → Doppio click per avviare
     → CTRL+C per fermare

  🔧 setup-local.bat
     → Setup iniziale (prima volta)
     → Crea .env, installa dipendenze, guida configurazione
     → Esegui questo se è la prima volta che configuri l'ambiente locale

  📦 install-dependencies.bat
     → Installa o aggiorna le dipendenze Python
     → Usa dopo aver aggiornato requirements.txt

================================================================================

🎯 Quick Start (prima volta):

  1. Doppio click su: setup-local.bat
  2. Segui le istruzioni per configurare .env e OAuth
  3. Doppio click su: start-server.bat
  4. Apri http://localhost:8080 nel browser

================================================================================

🔄 Uso quotidiano (dopo il setup):

  1. Doppio click su: start-server.bat
  2. Lavora sul codice (modifica HTML/JS/CSS)
  3. Ricarica la pagina nel browser per vedere le modifiche
  4. CTRL+C nella finestra del server per fermare

================================================================================

📝 File importanti:

  .env              → Variabili d'ambiente (SECRET, non committare!)
  .env.example      → Template per .env
  LOCAL_SETUP.md    → Guida dettagliata setup locale
  requirements.txt  → Dipendenze Python

================================================================================

🆘 Problemi comuni:

  ❌ "File .env non trovato"
     → Esegui setup-local.bat oppure copia .env.example a .env

  ❌ "GOOGLE_CLIENT_SECRET not set"
     → Apri .env e incolla il secret da Render

  ❌ "redirect_uri_mismatch"
     → Verifica OAuth Console: http://localhost:8080/oauth-callback

  ❌ "Port 8080 already in use"
     → Chiudi altre applicazioni sulla porta 8080
     → Oppure cambia PORT nel file .env

================================================================================

💡 Tips:

  • Console browser (F12) per vedere log e errori JavaScript
  • Log server visibile nella finestra del terminale
  • Per modifiche Python serve riavviare il server
  • Per modifiche HTML/CSS/JS basta ricaricare la pagina

================================================================================

📚 Documentazione completa: LOCAL_SETUP.md

================================================================================
