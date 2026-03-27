@echo off
cd /d "%~dp0"

echo ========================================
echo  Build capture_tool (onefile mode)
echo ========================================

echo.
echo [1/3] Cleaning old build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [2/3] Installing dependencies...
pip install -q pyinstaller

echo [3/3] Packaging...
pyinstaller capture_tool.spec --clean

echo.
echo ========================================
echo  Done!
echo  Output: dist\capture_tool.exe
echo ========================================
pause
