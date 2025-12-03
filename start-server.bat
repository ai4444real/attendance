@echo off
REM ============================================================================
REM Attendance System - Local Development Server
REM ============================================================================
REM
REM Questo script avvia il server FastAPI in locale su http://localhost:8080
REM Usa questo per testare modifiche prima del deploy su Render
REM
REM ============================================================================

echo.
echo ========================================
echo   Attendance System - Local Server
echo ========================================
echo.

REM Check if .env file exists
if not exist .env (
    echo [ERRORE] File .env non trovato!
    echo.
    echo Devi creare il file .env prima di avviare il server.
    echo.
    echo Segui questi passi:
    echo   1. Copia .env.example a .env
    echo   2. Modifica .env e inserisci il GOOGLE_CLIENT_SECRET da Render
    echo.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato!
    echo.
    echo Installa Python da: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [OK] File .env trovato
echo [OK] Python installato
echo.

REM Check if dependencies are installed
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ATTENZIONE] Dipendenze non installate!
    echo.
    echo Installo le dipendenze da requirements.txt...
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
)

echo ========================================
echo   Avvio del server...
echo ========================================
echo.
echo Server disponibile su:
echo   http://localhost:8080
echo.
echo Premi CTRL+C per fermare il server
echo ========================================
echo.

REM Start the FastAPI server
python app.py

REM If we get here, the server stopped
echo.
echo Server fermato.
pause
