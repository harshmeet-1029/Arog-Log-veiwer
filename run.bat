@echo off
REM Argo Log Viewer - Windows Startup Script

echo =======================================
echo  Argo Log Viewer - Production Grade
echo =======================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please run setup first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment and run application
echo Starting application...
echo.

call venv\Scripts\activate.bat
python -m app.main

REM Deactivate on exit
call venv\Scripts\deactivate.bat

echo.
echo Application closed.
pause
