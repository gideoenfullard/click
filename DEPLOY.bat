@echo off
title ClickAI Deploy
color 0A

:: ============================================
set "DEPLOY_DIR=C:\Users\deonf\OneDrive\Desktop\click-main\click-main"
:: ============================================

cd /d "%DEPLOY_DIR%"
if errorlevel 1 (
    color 0C
    echo ERROR: Kan nie folder vind: %DEPLOY_DIR%
    pause
    exit /b 1
)

echo.
echo ========================================
echo   CLICKAI DEPLOY
echo   %CD%
echo ========================================
echo.

:: --- Check belangrike files ---
if not exist clickai.py (
    color 0C
    echo [FATAL] clickai.py MISSING!
    pause
    exit /b 1
)
for %%F in (clickai.py) do echo   [OK] clickai.py              %%~zF bytes  %%~tF
for %%F in (clickai_cashup.py) do echo   [OK] clickai_cashup.py       %%~zF bytes  %%~tF
for %%F in (clickai_fraud_guard.py) do echo   [OK] clickai_fraud_guard.py  %%~zF bytes  %%~tF
for %%F in (clickai_allocation_log.py) do echo   [OK] clickai_allocation_log.py %%~zF bytes  %%~tF
echo.

:: --- Git: stage + commit + push ---
echo [1/3] Git add + commit...
git add -A
git commit -m "deploy %date% %time:~0,5%"
echo.

echo [2/3] Git push...
git push origin master 2>nul || git push origin main 2>nul
echo.

:: --- FLY DEPLOY (die belangrike stuk!) ---
echo [3/3] Fly deploy...
echo.
fly deploy
if errorlevel 1 (
    color 0C
    echo.
    echo   FLY DEPLOY FAILED!
    echo   Run "fly deploy" handmatig om te debug
    pause
    exit /b 1
)

echo.
color 0A
echo ========================================
echo   DEPLOY COMPLETE!
echo   https://clickai.fly.dev
echo ========================================
echo.
pause
