@echo off
title ClickAI Deploy
color 0A
cd /d "C:\Users\deonf\OneDrive\Desktop\click-main\click-main"

echo.
echo ============================================
echo    CLICKAI DEPLOY
echo    %date% %time%
echo ============================================
echo.

:: ──────────────────────────────────────────────
:: STAP 1: Check git status
:: ──────────────────────────────────────────────
echo [1/5] Checking git status...
git status --short
echo.

:: ──────────────────────────────────────────────
:: STAP 2: Stage all changes
:: ──────────────────────────────────────────────
echo [2/5] Staging all changes...
git add -A
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo *** FAILED: git add failed ***
    pause
    exit /b 1
)
echo     OK
echo.

:: ──────────────────────────────────────────────
:: STAP 3: Commit
:: ──────────────────────────────────────────────
echo [3/5] Committing...
git commit -m "deploy %date% %time%"
if %ERRORLEVEL% NEQ 0 (
    echo     Nothing new to commit - pushing existing commits...
)
echo.

:: ──────────────────────────────────────────────
:: STAP 4: Push to GitHub (MASTER branch)
:: ──────────────────────────────────────────────
echo [4/5] Pushing to GitHub (master)...
git push origin master 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ============================================
    echo    *** GIT PUSH FAILED ***
    echo ============================================
    echo.
    echo Possible fixes:
    echo   1. Check internet connection
    echo   2. Run: git pull origin master --rebase
    echo   3. Check GitHub credentials
    echo   4. Try: git push origin master --force
    echo.
    pause
    exit /b 1
)
echo.

:: ──────────────────────────────────────────────
:: STAP 5: Verify push actually worked
:: ──────────────────────────────────────────────
echo [5/5] Verifying push...

for /f %%i in ('git rev-parse HEAD') do set LOCAL_HEAD=%%i
for /f %%i in ('git rev-parse origin/master') do set REMOTE_HEAD=%%i

if "%LOCAL_HEAD%"=="%REMOTE_HEAD%" (
    color 0A
    echo.
    echo ============================================
    echo    DEPLOY SUCCESSFUL
    echo ============================================
    echo.
    echo    Local:  %LOCAL_HEAD:~0,8%
    echo    Remote: %REMOTE_HEAD:~0,8%
    echo.
    echo    Fly.io auto-deploy will start shortly.
    echo    Check: https://fly.io/apps/click-main
    echo ============================================
) else (
    color 0E
    echo.
    echo ============================================
    echo    *** WARNING: HEADS DON'T MATCH ***
    echo ============================================
    echo.
    echo    Local:  %LOCAL_HEAD:~0,8%
    echo    Remote: %REMOTE_HEAD:~0,8%
    echo.
    echo    Push may have failed silently.
    echo    Try: git push origin master --force
    echo ============================================
)

echo.
pause
