# Respaldo de configuraciones de red por SSH (Python)

Respalda la configuración de routers, switches y firewalls por SSH, la guarda con fecha y genera un reporte HTML con los cambios desde el respaldo anterior. Es la tarea típica de NOC para tener vuelta atrás y detectar cambios no documentados.

## Qué hace
- Lee los equipos desde `equipos.csv` (nombre, IP, tipo, puerto, usuario).
- Se conecta con **netmiko** y ejecuta el comando que corresponde a cada marca: Cisco IOS/XE/NX-OS/ASA, HP/Aruba, Huawei, Fortinet, MikroTik, Juniper, Ubiquiti EdgeRouter, VyOS, Palo Alto y Dell.
- Guarda `respaldos/<equipo>/<equipo>_AAAAMMDD_HHMMSS.cfg`. Si nada cambió, no duplica el archivo.
- Compara ignorando las líneas que cambian solas (marcas de hora, `Current configuration`, `ntp clock-period`, etc.), así solo se reportan cambios reales.
- Reporte HTML con el estado de cada equipo (primer respaldo, sin cambios, cambios, error) y el diff coloreado.
- Las contraseñas quedan en el **Administrador de credenciales de Windows** (`keyring`), nunca en el CSV ni en el código.

## Uso
1. `Demo.cmd`: muestra el flujo completo con configuraciones de ejemplo, sin equipos reales.
2. `GuardarCredencial.cmd`: guarda la contraseña SSH (y la de enable, si se usa).
3. `Respaldar.cmd`: la primera vez crea `equipos.csv` desde el ejemplo para que lo completes; después respalda todo.

```
python respaldo.py                 # todos los equipos activos
python respaldo.py --solo Core     # solo los que contengan "Core" en el nombre
python respaldo.py --credencial admin
```

`equipos.csv` (separado por `;`):

```
activo;nombre;ip;tipo;puerto;usuario;enable
SI;R1-Core;192.168.1.1;cisco_ios;22;admin;SI
SI;MikroTik-Borde;192.168.88.1;mikrotik_routeros;22;admin;NO
```

Para que corra solo todos los días, crea una tarea en el Programador de tareas que ejecute `.venv\Scripts\python.exe respaldo.py --no-abrir` en esta carpeta.

## Probarlo en un laboratorio
En GNS3 o EVE-NG, con un router Cisco que tenga SSH habilitado:

```
ip domain-name lab.local
crypto key generate rsa modulus 2048
username admin privilege 15 secret <clave>
ip ssh version 2
line vty 0 4
 login local
 transport input ssh
```

## Conceptos aplicados
Automatización de red con SSH (netmiko), manejo seguro de credenciales, control de cambios con `difflib`, normalización de configuraciones y reportes HTML.
