@echo off
REM Simple Build Script for Windows

echo ==========================================
echo  Argo Log Viewer - Windows Builder
echo ==========================================
echo.

REM Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

REM Build
echo Building application...
echo.
pyinstaller ArgoLogViewer.spec --clean

REM Check result
if exist "dist\ArgoLogViewer.exe" (
    echo.
    echo ==========================================
    echo  BUILD SUCCESSFUL!
    echo ==========================================
    echo.
    echo Output: dist\ArgoLogViewer.exe
    echo.
    for %%F in (dist\ArgoLogViewer.exe) do echo Size: %%~zF bytes
    echo.
    echo To test: dist\ArgoLogViewer.exe
    echo.
) else (
    echo.
    echo ==========================================
    echo  BUILD FAILED!
    echo ==========================================
    echo.
    pause
    exit /b 1
)

echo Build complete!
pause
