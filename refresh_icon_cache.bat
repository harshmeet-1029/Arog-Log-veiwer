@echo off
REM This script refreshes Windows icon cache so the new icon appears

echo Refreshing Windows Icon Cache...
echo.

REM Method 1: Delete icon cache files
echo [1/3] Clearing icon cache database...
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 2 /nobreak >nul
del /a /q "%localappdata%\IconCache.db" >nul 2>&1
del /a /f /q "%localappdata%\Microsoft\Windows\Explorer\iconcache*" >nul 2>&1

REM Method 2: Restart Explorer
echo [2/3] Restarting Windows Explorer...
start explorer.exe
timeout /t 2 /nobreak >nul

REM Method 3: Refresh the dist folder
echo [3/3] Refreshing dist folder view...
echo.

echo ========================================
echo DONE!
echo ========================================
echo.
echo The icon cache has been cleared.
echo.
echo Now:
echo 1. Navigate to the dist\ folder in Windows Explorer
echo 2. Press F5 to refresh the view
echo 3. The ArgoLogViewer.exe should now show its icon
echo.
echo If still not visible:
echo - Right-click ArgoLogViewer.exe and select Properties
echo - The icon should be visible in the Properties dialog
echo - Try copying the .exe to a different folder
echo.
pause
