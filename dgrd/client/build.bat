@echo off
cd /d "%~dp0"

echo ========================================
echo  Build capture_tool (onefile mode)
echo ========================================

echo.
echo [1/4] Cleaning old build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [2/4] Embedding URL from server_url.txt...
python embed_server_url.py
if errorlevel 1 (
	echo [ERROR] Failed to embed server URL.
	pause
	exit /b 1
)

echo [3/4] Installing dependencies...
python -m pip install -q pyinstaller

echo [4/4] Packaging...
python -m PyInstaller capture_tool.spec --clean

echo.
echo ========================================
echo  Done!
echo  Output: dist\capture_tool.exe
echo ========================================
pause
