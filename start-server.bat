@echo off
REM ============================================================================
REM Rebekko Webapps - Local Development Server
REM ============================================================================
REM
REM Questo script avvia il backend FastAPI del workspace in locale
REM su http://localhost:8080
REM
REM ============================================================================

echo.
echo ========================================
echo   Rebekko Webapps - Local Server
echo ========================================
echo.

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

if exist .env (
    echo [OK] File .env trovato
) else (
    echo [INFO] File .env non presente: avvio con configurazione di default
)
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
python -m backend.main

REM If we get here, the server stopped
echo.
echo Server fermato.
pause
