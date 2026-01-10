@echo off
REM Complete Production Build for Windows
REM This creates:
REM 1. Standalone .exe
REM 2. Professional installer with Start Menu, Desktop shortcuts, Uninstaller

echo ============================================
echo Argo Log Viewer - Production Builder (Windows)
echo ============================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/6] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install PyInstaller if not already installed
echo.
echo [2/6] Installing PyInstaller...
pip install pyinstaller --quiet

REM Clean previous build
echo.
echo [3/6] Cleaning previous build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "installers" rmdir /s /q installers

REM Create necessary directories
mkdir installers\windows 2>nul

REM Build the standalone executable
echo.
echo [4/6] Building standalone executable...
echo This may take a few minutes...
echo.
pyinstaller --name="ArgoLogViewer" ^
    --onefile ^
    --windowed ^
    --icon=app/icon.ico ^
    --add-data="app;app" ^
    --hidden-import=PySide6 ^
    --hidden-import=paramiko ^
    --hidden-import=cryptography ^
    --clean ^
    app/main.py

REM Check if build was successful
if not exist "dist\ArgoLogViewer.exe" (
    echo.
    echo ========================================
    echo BUILD FAILED!
    echo ========================================
    echo.
    echo Executable creation failed. Check errors above.
    pause
    exit /b 1
)

echo.
echo [5/6] Standalone executable created successfully!
echo Location: dist\ArgoLogViewer.exe
echo Size: 
dir dist\ArgoLogViewer.exe | find "ArgoLogViewer.exe"
echo.

REM Build installer with Inno Setup
echo [6/6] Building professional installer...
echo.

REM Check if Inno Setup is installed
set INNO_PATH=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set INNO_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
)

if "%INNO_PATH%"=="" (
    echo.
    echo WARNING: Inno Setup not found!
    echo.
    echo The standalone .exe is ready in dist\ folder.
    echo.
    echo To create a professional installer:
    echo 1. Download Inno Setup from: https://jrsoftware.org/isdl.php
    echo 2. Install it
    echo 3. Run this script again
    echo.
    echo Or manually compile with:
    echo    Right-click installer_windows.iss and select "Compile"
    echo.
) else (
    echo Compiling installer with Inno Setup...
    "%INNO_PATH%" installer_windows.iss /Q
    
    if exist "installers\windows\ArgoLogViewer-*-Windows-Setup.exe" (
        echo.
        echo ========================================
        echo PRODUCTION BUILD COMPLETE!
        echo ========================================
        echo.
        echo Standalone Executable:
        echo   dist\ArgoLogViewer.exe
        echo.
        echo Professional Installer:
        for %%F in (installers\windows\ArgoLogViewer-*-Windows-Setup.exe) do (
            echo   %%F
            echo   Size: 
            dir "%%F" | find "ArgoLogViewer"
        )
        echo.
        echo The installer includes:
        echo   - Start Menu shortcuts
        echo   - Desktop icon (optional)
        echo   - Quick Launch icon (optional)
        echo   - Professional uninstaller
        echo   - System integration
        echo.
    ) else (
        echo WARNING: Installer creation failed
        echo Standalone .exe is available in dist\ folder
    )
)

echo.
echo ========================================
echo DISTRIBUTION READY!
echo ========================================
echo.
echo You can now distribute:
echo   1. dist\ArgoLogViewer.exe - Standalone (no install needed)
echo   2. installers\windows\*.exe - Professional installer
echo.
pause
