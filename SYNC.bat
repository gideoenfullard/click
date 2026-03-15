@echo off
title ClickAI SYNC - Pull Latest
color 0B

echo.
echo ============================================
echo    CLICKAI SYNC - PULL LATEST CODE
echo    %date% %time%
echo ============================================
echo.
echo    RUN THIS FIRST before you do ANY work!
echo.
echo ============================================
echo.

:: ──────────────────────────────────────────────
:: Find the repo folder
:: Try common locations
:: ──────────────────────────────────────────────
if exist "C:\Users\deonf\OneDrive\Desktop\click-main\click-main\.git" (
    cd /d "C:\Users\deonf\OneDrive\Desktop\click-main\click-main"
    goto :found
)
if exist "C:\click-main\.git" (
    cd /d "C:\click-main"
    goto :found
)
if exist "%USERPROFILE%\Desktop\click-main\click-main\.git" (
    cd /d "%USERPROFILE%\Desktop\click-main\click-main"
    goto :found
)
if exist "%USERPROFILE%\Desktop\click-main\.git" (
    cd /d "%USERPROFILE%\Desktop\click-main"
    goto :found
)

:: If not found, ask
color 0C
echo Could not find the ClickAI repo automatically.
echo.
set /p REPOPATH="Paste the full path to your click-main folder: "
cd /d "%REPOPATH%"
if not exist ".git" (
    echo.
    echo *** No .git folder found here. Not a git repo. ***
    echo.
    echo To set up this PC for the first time, run:
    echo   git clone https://github.com/gideoneofullard/click.git click-main
    echo.
    pause
    exit /b 1
)

:found
echo Repo found: %CD%
echo.

:: ──────────────────────────────────────────────
:: Check for uncommitted changes
:: ──────────────────────────────────────────────
echo [1/3] Checking for local changes...
git status --short > "%TEMP%\git_status.txt"
for %%A in ("%TEMP%\git_status.txt") do (
    if %%~zA GTR 0 (
        color 0E
        echo.
        echo *** WARNING: You have uncommitted local changes! ***
        echo.
        git status --short
        echo.
        echo Options:
        echo   1. Type Y to STASH them (save aside, pull, then restore)
        echo   2. Type N to ABORT (go commit/deploy first)
        echo.
        set /p STASH_CHOICE="Stash local changes? (Y/N): "
        if /i "%STASH_CHOICE%"=="Y" (
            echo Stashing local changes...
            git stash
            echo     Stashed OK - will restore after pull
            set RESTORE_STASH=1
        ) else (
            echo.
            echo Aborted. Commit or deploy your changes first.
            pause
            exit /b 1
        )
    ) else (
        echo     Clean - no local changes
    )
)
echo.

:: ──────────────────────────────────────────────
:: Pull latest from GitHub
:: ──────────────────────────────────────────────
echo [2/3] Pulling latest from GitHub (master)...
git pull origin master 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo *** PULL FAILED ***
    echo.
    echo Try these fixes:
    echo   1. Check internet connection
    echo   2. Run: git pull origin master --rebase
    echo   3. If desperate: delete folder and re-clone:
    echo      git clone https://github.com/gideoneofullard/click.git
    echo.
    pause
    exit /b 1
)
echo.

:: ──────────────────────────────────────────────
:: Restore stashed changes if any
:: ──────────────────────────────────────────────
if defined RESTORE_STASH (
    echo Restoring your stashed changes...
    git stash pop
    if %ERRORLEVEL% NEQ 0 (
        color 0E
        echo.
        echo *** MERGE CONFLICT restoring stash ***
        echo Your changes conflicted with the pulled code.
        echo Run: git stash drop   (to discard your local changes)
        echo  or: Fix conflicts manually
        echo.
        pause
        exit /b 1
    )
    echo     Restored OK
    echo.
)

:: ──────────────────────────────────────────────
:: Show current state
:: ──────────────────────────────────────────────
echo [3/3] Current state:
for /f %%i in ('git rev-parse --short HEAD') do set HEAD=%%i
for /f "delims=" %%i in ('git log -1 --format^="%%s"') do set MSG=%%i
echo.
color 0A
echo ============================================
echo    SYNC COMPLETE
echo ============================================
echo.
echo    Commit:  %HEAD%
echo    Message: %MSG%
echo.
echo    You are up to date with GitHub.
echo    Safe to work now!
echo ============================================
echo.
pause
