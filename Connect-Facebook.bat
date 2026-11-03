@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
python -m backend.scraper --login
pause
