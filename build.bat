@echo off
rem Builds dist\wxwx-toolkit\wxwx-toolkit.exe (Python 3.10+ must be installed)
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (
    echo [!] Python not found. Install it from python.org and tick "Add to PATH".
    pause & exit /b 1
)

if not exist .venv (
    echo === Creating virtual environment...
    python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat

echo === Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || goto :err

echo === Building exe...
pyinstaller --noconfirm wxwx-toolkit.spec || goto :err

echo.
echo Done: dist\wxwx-toolkit\wxwx-toolkit.exe
explorer dist\wxwx-toolkit
pause
exit /b 0

:err
echo.
echo [!] Build failed, see the messages above.
pause
exit /b 1
