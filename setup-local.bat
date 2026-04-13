@echo off
REM ============================================================================
REM First Time Setup - Local Development Environment
REM ============================================================================
REM
REM Usa questo script la PRIMA VOLTA per configurare l'ambiente locale
REM
REM ============================================================================

echo.
echo ========================================
echo   Setup Ambiente Locale - Prima Volta
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato!
    echo.
    echo 1. Scarica Python da: https://www.python.org/downloads/
    echo 2. Installa Python (assicurati di selezionare "Add Python to PATH")
    echo 3. Riavvia questo script
    echo.
    pause
    exit /b 1
)

echo [OK] Python installato
echo.

REM Step 1: Optional .env creation
if not exist .env (
    echo [STEP 1] File .env opzionale
    echo.
    echo Il progetto puo' partire anche senza .env.
    echo Crea .env solo se devi usare segreti o configurazioni locali.
    echo.
    if exist .env.example (
        echo Vuoi creare .env da .env.example? (S/N)
        choice /c SN /n /m "Premi S per creare, N per saltare: "
        if errorlevel 2 goto skip_env
        if errorlevel 1 (
            copy .env.example .env >nul
            echo [OK] File .env creato da .env.example
            echo.
            echo Se devi usare OAuth o altre integrazioni:
            echo 1. Apri il file .env con un editor di testo
            echo 2. Vai su Render Dashboard ^> Environment Variables
            echo 3. Copia il valore di GOOGLE_CLIENT_SECRET
            echo 4. Incollalo nel file .env al posto di "your_secret_here_from_render"
            echo 5. Salva il file
            echo.
            echo Vuoi aprire .env ora? (S/N)
            choice /c SN /n /m "Premi S per aprire, N per saltare: "
            if errorlevel 2 goto skip_env
            if errorlevel 1 notepad .env
        )
        :skip_env
        echo.
    ) else (
        echo [INFO] File .env.example non trovato: continuo senza .env
        echo.
    )
) else (
    echo [OK] File .env già esistente
    echo.
)

REM Step 2: Install dependencies
echo [STEP 2] Installazione dipendenze Python...
echo.
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione fallita!
    pause
    exit /b 1
)

echo.
echo [OK] Dipendenze installate
echo.

REM Step 3: Check OAuth configuration
echo ========================================
echo [STEP 3] Configurazione Google OAuth
echo ========================================
echo.
echo Hai configurato Google OAuth Console? (S/N)
echo.
echo Devi aggiungere questi URL:
echo.
echo   Authorized JavaScript origins:
echo     http://localhost:8080
echo.
echo   Authorized redirect URIs:
echo     http://localhost:8080/oauth-callback
echo.
echo Link: https://console.cloud.google.com/apis/credentials
echo.
choice /c SN /n /m "Premi S se hai già configurato, N se devi ancora farlo: "
if errorlevel 2 (
    echo.
    echo [ATTENZIONE] Configura OAuth prima di avviare il server!
    echo.
    echo Dopo averlo configurato, avvia il server con: start-server.bat
    echo.
    pause
    exit /b 0
)

echo.
echo ========================================
echo [OK] Setup completato!
echo ========================================
echo.
echo Prossimi passi:
echo   1. Se usi OAuth, verifica che .env contenga il GOOGLE_CLIENT_SECRET corretto
echo   2. Se usi OAuth, verifica la configurazione su Google Cloud Console
echo   3. Avvia il server con: start-server.bat
echo   4. Apri http://localhost:8080 nel browser
echo.
echo Vuoi avviare il server ora? (S/N)
choice /c SN /n /m "Premi S per avviare, N per uscire: "
if errorlevel 2 goto end
if errorlevel 1 (
    echo.
    call start-server.bat
)

:end
echo.
pause
