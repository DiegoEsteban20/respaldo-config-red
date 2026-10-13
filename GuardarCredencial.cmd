@echo off
chcp 65001 >NUL
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno de Python, solo la primera vez...
  py -3 -m venv .venv || python -m venv .venv
)
".venv\Scripts\python.exe" -c "import netmiko, keyring" 2>NUL || (
  echo Instalando netmiko y keyring, solo la primera vez...
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
)
set /p USUARIO=Usuario SSH de los equipos (ej. admin): 
".venv\Scripts\python.exe" respaldo.py --credencial "%USUARIO%"
pause
