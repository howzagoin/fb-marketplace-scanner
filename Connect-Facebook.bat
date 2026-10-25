@echo off
cd /d "%~dp0"
title Facebook 2FA Session Connector
echo ========================================================
echo   Facebook Marketplace Scanner - Interactive Login
echo ========================================================
echo.
echo Launching browser for Facebook sign-in...
echo Complete your 2FA authentication and approve the device.
echo Your session will be automatically saved and synced to VPS.
echo.
python -m backend.scraper --login
echo.
pause
