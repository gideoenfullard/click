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

:: Show clickai.py file info
echo [CHECK] clickai.py:
for %%F in (clickai.py) do echo     Size: %%~zF bytes   Modified: %%~tF
echo.
findstr /c:"=== Customer Payment" clickai.py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     NEW CODE DETECTED - good to go!
) else (
    echo     WARNING: Old code detected!
)
echo.
pause

echo [1/5] Checking git status...
git status --short
echo.

echo [2/5] Staging all changes...
git add -A
if %ERRORLEVEL% NEQ 0 (
    echo *** git add failed ***
    pause
    exit /b 1
)
echo     OK
echo.

echo [3/5] Committing...
git commit -m "deploy %date% %time%"
echo.

echo [4/5] Pushing to GitHub (master)...
git push origin master 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo *** GIT PUSH FAILED ***
    echo Try: git push origin master --force
    pause
    exit /b 1
)
echo.

echo [5/5] Verifying...
for /f %%i in ('git rev-parse HEAD') do set LOCAL_HEAD=%%i
for /f %%i in ('git rev-parse origin/master') do set REMOTE_HEAD=%%i

if "%LOCAL_HEAD%"=="%REMOTE_HEAD%" (
    echo.
    echo ============================================
    echo    DEPLOY SUCCESSFUL
    echo    Fly.io auto-deploy will start shortly.
    echo ============================================
) else (
    echo.
    echo *** WARNING: Push may have failed ***
    echo Try: git push origin master --force
)

echo.
pause
