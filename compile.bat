@echo off
cd /d "%~dp0"

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install ttkbootstrap pyinstaller

echo Cleaning old builds...
rmdir /s /q build dist 2>nul
del *.spec 2>nul

echo Compiling EXE...
python -m PyInstaller --onefile --name "Dolby Atmos scanner" --distpath . --windowed ^
 --icon=icon/icon.ico ^
 --add-data "icon/icon.ico;." ^
 --add-data "translations;translations" ^
 --add-binary "ffmpeg/ffprobe.exe;ffmpeg" ^
 --add-binary "ffmpeg/ffmpeg.exe;ffmpeg" ^
 Dolby_Atmos_scanner.py
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo.
echo DONE!
pause
