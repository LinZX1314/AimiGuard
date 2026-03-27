@echo off
chcp 65001 >nul
echo ========================================
echo  构建 capture_tool (单文件模式)
echo ========================================

cd /d "%~dp0"

echo.
echo [1/3] 清理旧构建...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [2/3] 安装依赖...
pip install -q pyinstaller

echo [3/3] 开始打包 (onefile 模式)...
pyinstaller capture_tool.spec --clean

echo.
echo ========================================
echo  构建完成!
echo  输出目录: dist\capture_tool.exe
echo ========================================
pause
