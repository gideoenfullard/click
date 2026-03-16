@echo off
title ClickAI Deploy
color 0A

cd /d "C:\Users\deonf\OneDrive\Desktop\click-main\click-main"

echo.
echo CLICKAI DEPLOY
echo.

for %%F in (clickai.py) do echo clickai.py: %%~zF bytes  Modified: %%~tF
echo.

git add -A
git commit -m "deploy"
git push origin master

echo.
echo DONE
echo.
pause
