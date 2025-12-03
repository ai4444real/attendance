@echo off
REM ============================================================================
REM Install Python Dependencies
REM ============================================================================
REM
REM Usa questo script per installare o aggiornare le dipendenze Python
REM
REM ============================================================================

echo.
echo ========================================
echo   Installazione Dipendenze
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

echo Installazione delle dipendenze da requirements.txt...
echo.

pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione fallita!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo [OK] Dipendenze installate con successo!
echo ========================================
echo.
echo Puoi ora avviare il server con: start-server.bat
echo.
pause
