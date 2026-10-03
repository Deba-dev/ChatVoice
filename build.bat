@echo off
REM Builds dist\ChatVoice\ChatVoice.exe and, if Inno Setup is installed, installer\ChatVoice-Setup.exe
cd /d "%~dp0"
py -3.12 -m pip install -r requirements.txt pyinstaller
py -3.12 -m PyInstaller --noconfirm --windowed --noupx --name ChatVoice --icon assets\icon.ico --version-file version_info.txt --add-data "assets;assets" --exclude-module numpy --exclude-module PIL --exclude-module tkinter --exclude-module matplotlib --collect-submodules pytchat --collect-submodules edge_tts main.py
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" (
  "%ISCC%" installer.iss
  echo.
  echo Installer ready: installer\ChatVoice-Setup.exe
) else (
  echo.
  echo App ready: dist\ChatVoice\ChatVoice.exe
  echo For a proper Setup.exe, install the free Inno Setup 6 from jrsoftware.org and run build.bat again.
)
pause
