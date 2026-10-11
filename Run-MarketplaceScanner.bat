@echo off
title Facebook Marketplace Scanner Web Server
echo ========================================================
echo   Facebook Marketplace Scanner & Web UI
echo   http://127.0.0.1:5080/
echo ========================================================
echo.
echo Starting web dashboard on http://127.0.0.1:5080...
start "" http://127.0.0.1:5080/
python app.py
pause
