@echo off
color 0A
echo.
echo  =============================================
echo     CLICKAI - DEPLOY SCRIPT
echo     Een klik = GitHub + Fly.io
echo  =============================================
echo.

cd /d "D:\Click AI\click-main\click-main"

:: Check of ons in die regte folder is
if not exist "clickai.py" (
    color 0C
    echo  [FOUT] clickai.py nie gevind nie!
    echo  Maak seker jy het die nuwe clickai.py
    echo  in hierdie folder gesit.
    echo.
    pause
    exit /b 1
)

echo  [INFO] Folder: %CD%
echo  [INFO] File: clickai.py gevind
echo.

:: Wys laaste modify date so jy kan check dis die nuwe een
echo  Laaste keer clickai.py verander:
for %%f in (clickai.py) do echo  %%~tf
echo.

:: STAP 1: Bevestig
echo  =============================================
echo  Hierdie script gaan:
echo    1. Jou code SAVE na GitHub (backup)
echo    2. DEPLOY na Fly.io (users kry nuwe code)
echo  =============================================
echo.
set /p confirm="Is jy seker? (J/N): "
if /i not "%confirm%"=="J" (
    echo  Gekanselleer.
    pause
    exit /b 0
)

echo.
echo  -- STAP 1/3: Save na GitHub --
git add -A
for /f "tokens=1-3 delims=/" %%a in ('date /t') do set mydate=%%a-%%b-%%c
git commit -m "Update %mydate% %time:~0,5%"
if %ERRORLEVEL% NEQ 0 (
    echo  [NOTA] Niks nuut om te save nie, gaan voort...
)

echo.
echo  -- STAP 2/3: Push na GitHub --
git push
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo  [FOUT] Kon nie na GitHub push nie!
    echo  Check jou internet of git setup.
    pause
    exit /b 1
)
echo  [OK] GitHub is up to date

echo.
echo  -- STAP 3/3: Deploy na Fly.io --
echo  (Dit vat 2-5 minute, moenie panic nie)
echo.
fly deploy
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo  =============================================
    echo  [FOUT] Fly deploy het gefaal!
    echo  Maar jou code is SAFE op GitHub.
    echo  Probeer weer of check: fly logs
    echo  =============================================
    pause
    exit /b 1
)

echo.
color 0A
echo  =============================================
echo.
echo     KLAAR! 
echo.
echo     GitHub:  Saved
echo     Fly.io:  Deployed
echo     Users:   Het nuwe code
echo.
echo     Check: https://clickai.fly.dev/pulse
echo.
echo  =============================================
echo.
pause
