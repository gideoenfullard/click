@echo off
title ClickAI Deploy
color 0A

:: ============================================
:: DEPLOY FOLDER - alle edits HIER doen
:: ============================================
set "DEPLOY_DIR=C:\Users\deonf\OneDrive\Desktop\click-main\click-main"

cd /d "%DEPLOY_DIR%"
if errorlevel 1 (
    color 0C
    echo ERROR: Cannot find deploy folder: %DEPLOY_DIR%
    pause
    exit /b 1
)

echo.
echo ========================================
echo   CLICKAI DEPLOY
echo ========================================
echo.
echo Deploy folder: %CD%
echo.

:: --- Show file info ---
for %%F in (clickai.py) do echo   clickai.py:         %%~zF bytes   Modified: %%~tF
for %%F in (clickai_cashup.py) do echo   clickai_cashup.py:  %%~zF bytes   Modified: %%~tF
for %%F in (clickai_fraud_guard.py) do echo   clickai_fraud_guard.py: %%~zF bytes   Modified: %%~tF
echo.

:: --- Check for uncommitted changes ---
echo [1/4] Checking for changes...
git status --short
echo.

:: --- Show what changed ---
git diff --stat
echo.

:: --- Stage all changes ---
echo [2/4] Staging files...
git add -A
echo.

:: --- Show what will be committed ---
echo Files to commit:
git diff --cached --name-only
echo.

:: --- Count staged files ---
set "CHANGED=0"
for /f %%i in ('git diff --cached --name-only ^| find /c /v ""') do set CHANGED=%%i

if "%CHANGED%"=="0" (
    color 0E
    echo ========================================
    echo   WARNING: Nothing to commit!
    echo   No files were changed since last deploy.
    echo ========================================
    echo.
    echo If you expected changes, check that you
    echo saved the file in THIS folder:
    echo   %DEPLOY_DIR%
    echo.
    echo NOT in C:\click-main\click-main or
    echo any other copy of the folder.
    echo.
    pause
    exit /b 0
)

echo %CHANGED% file(s) will be deployed.
echo.

:: --- Commit ---
echo [3/4] Committing...
git commit -m "deploy %date% %time:~0,5%"
echo.

:: --- Push ---
echo [4/4] Pushing to GitHub + deploying to Fly.io...
git push origin master
if errorlevel 1 (
    color 0C
    echo.
    echo ========================================
    echo   ERROR: Push failed!
    echo   Check your internet connection or
    echo   run: git push origin master
    echo ========================================
    pause
    exit /b 1
)

echo.
color 0A
echo ========================================
echo   DEPLOY COMPLETE
echo   %CHANGED% file(s) pushed to production
echo ========================================
echo.
pause
