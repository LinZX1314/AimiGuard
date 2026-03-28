@echo off
cd /d "%~dp0"
set PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe

echo ========================================
echo  Build capture_tool (onefile mode)
echo ========================================

echo.
echo [1/4] Cleaning old build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [2/4] Embedding URL from server_url.txt...
%PYTHON_EXE% embed_server_url.py
if errorlevel 1 (
	echo [ERROR] Failed to embed server URL.
	pause
	exit /b 1
)

echo [3/4] Installing dependencies...
%PYTHON_EXE% -m pip install -q pyinstaller

echo [4/4] Packaging...
%PYTHON_EXE% -m PyInstaller capture_tool.spec --clean

echo.
echo ========================================
echo  Done!
echo  Output: dist\capture_tool.exe
echo ========================================
pause
