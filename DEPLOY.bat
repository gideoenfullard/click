@echo off
cd /d C:\clickai
git add -A
git commit -m "deploy %date% %time%"
git push
echo.
echo Gestoot - kyk vordering by https://github.com/gideoenfullard/click-main/actions
pause