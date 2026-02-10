@echo off
color 0A
echo.
echo  =============================================
echo     CLICKAI - BACKUP + DEPLOY
echo     GitHub backup + Fly.io deploy
echo  =============================================
echo.

cd /d "D:\Click AI\click-main\click-main"

if not exist "clickai.py" (
    color 0C
    echo  [FOUT] clickai.py nie gevind nie!
    pause
    exit /b 1
)

echo  [INFO] Folder: %CD%
echo.
echo  Laaste keer clickai.py verander:
for %%f in (clickai.py) do echo  %%~tf
echo.
echo  =============================================
echo  Hierdie script gaan:
echo    1. BACKUP na GitHub (safe copy)
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
echo  -- STAP 1/3: Backup na GitHub --
git add -A
git commit -m "Update %date% %time:~0,5%"
if %ERRORLEVEL% NEQ 0 (
    echo  [NOTA] Niks nuut om te save nie, gaan voort...
)

echo.
echo  -- STAP 2/3: Push na GitHub --
git push
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo  [FOUT] Kon nie na GitHub push nie!
    pause
    exit /b 1
)
echo  [OK] GitHub backup klaar

echo.
echo  -- STAP 3/3: Deploy na Fly.io --
echo  (2-5 minute, wag net)
echo.
fly deploy
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo  [FOUT] Deploy het gefaal!
    echo  Maar jou code is SAFE op GitHub.
    pause
    exit /b 1
)

echo.
color 0A
echo  =============================================
echo.
echo     KLAAR!
echo.
echo     GitHub:  Backed up
echo     Fly.io:  Deployed
echo     Users:   Het die nuwe code
echo.
echo  =============================================
echo.
pause
