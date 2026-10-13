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
if not exist "equipos.csv" (
  copy /Y "equipos.ejemplo.csv" "equipos.csv" >NUL
  echo Se creo equipos.csv: anota tus equipos, guarda y vuelve a ejecutar.
  start "" notepad "equipos.csv"
  pause
  exit /b
)
".venv\Scripts\python.exe" respaldo.py %*
pause
