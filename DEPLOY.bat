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
    echo Check if git is installed and repo is initialized.
    echo.
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
    :: errorlevel 1 from commit usually means "nothing to commit"
    echo     Nothing new to commit - pushing existing commits...
)
echo.

:: ──────────────────────────────────────────────
:: STAP 4: Push to GitHub
:: ──────────────────────────────────────────────
echo [4/5] Pushing to GitHub...
git push origin main 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ============================================
    echo    *** GIT PUSH FAILED ***
    echo ============================================
    echo.
    echo Possible fixes:
    echo   1. Check internet connection
    echo   2. Run: git pull origin main --rebase
    echo   3. Check GitHub credentials
    echo   4. Try: git push origin main --force
    echo.
    pause
    exit /b 1
)
e