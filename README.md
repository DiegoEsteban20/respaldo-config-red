# Respaldo de configuraciones de red por SSH (Python)

Respalda la configuración de routers, switches y firewalls por SSH, la guarda con fecha y genera un **reporte HTML con los cambios** desde el respaldo anterior. Es la tarea típica de un NOC: tener vuelta atrás ante un cambio que rompe algo y detectar modificaciones no documentadas.

Funciona en Windows, Linux o macOS con Python 3.8 o superior.

---

## Tabla de contenidos
- [Para qué sirve](#para-qué-sirve)
- [Qué hace, paso a paso](#qué-hace-paso-a-paso)
- [Marcas y equipos soportados](#marcas-y-equipos-soportados)
- [Instalación](#instalación)
- [Uso](#uso)
- [La lista de equipos (equipos.csv)](#la-lista-de-equipos-equiposcsv)
- [Credenciales seguras](#credenciales-seguras)
- [El reporte de cambios](#el-reporte-de-cambios)
- [Probarlo en un laboratorio](#probarlo-en-un-laboratorio)
- [Dejarlo corriendo solo](#dejarlo-corriendo-solo)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Conceptos aplicados](#conceptos-aplicados)
- [Aviso](#aviso)

---

## Para qué sirve

Si alguien cambia la configuración de un switch y la red se cae, necesitas saber **qué cambió** y poder volver a la versión anterior. En las empresas esto se resuelve respaldando las configuraciones periódicamente. Este script lo hace solo: se conecta a cada equipo, descarga su configuración, la guarda con fecha y te muestra, en colores, qué líneas se agregaron o se quitaron desde el último respaldo.

---

## Qué hace, paso a paso

1. **Lee los equipos** desde `equipos.csv` (nombre, IP, tipo, puerto, usuario).
2. **Se conecta por SSH** con `netmiko` y ejecuta el comando que corresponde a cada marca (`show running-config`, `display current-configuration`, `/export`, etc.).
3. **Guarda la configuración** en `respaldos/<equipo>/<equipo>_AAAAMMDD_HHMMSS.cfg`. Si nada cambió, no duplica el archivo.
4. **Compara con el respaldo anterior**, ignorando las líneas que cambian solas (marcas de hora, "Current configuration", relojes), para que solo se reporten cambios reales.
5. Genera un **reporte HTML** con el estado de cada equipo (primer respaldo, sin cambios, con cambios o error) y el **diff coloreado**.

---

## Marcas y equipos soportados

Cisco IOS / IOS-XE / NX-OS / ASA / Small Business, HP ProCurve, Aruba, Dell OS10, Huawei, Fortinet, MikroTik RouterOS, Juniper Junos, Ubiquiti EdgeRouter / EdgeSwitch, VyOS y Palo Alto. El tipo se indica por equipo en el CSV (por ejemplo `cisco_ios`, `mikrotik_routeros`, `fortinet`).

---

## Instalación

```bash
pip install -r requirements.txt
```

En Windows, los lanzadores `.cmd` crean el entorno e instalan `netmiko` y `keyring` la primera vez.

---

## Uso

- **`Demo.cmd`**: muestra el flujo completo con configuraciones de ejemplo, sin equipos reales. Ideal para ver cómo se ve un reporte con cambios.
- **`GuardarCredencial.cmd`**: guarda tu usuario y contraseña SSH de forma segura.
- **`Respaldar.cmd`**: la primera vez crea `equipos.csv` desde el ejemplo para que lo completes; después respalda todos los equipos activos.

Por línea de comandos:

```bash
python respaldo.py                 # todos los equipos activos
python respaldo.py --solo Core     # solo los que contengan "Core" en el nombre
python respaldo.py --credencial admin   # guarda/actualiza la clave del usuario admin
python respaldo.py --demo          # prueba con configuraciones de ejemplo
```

---

## La lista de equipos (equipos.csv)

Separado por `;`:

```csv
activo;nombre;ip;tipo;puerto;usuario;enable
SI;R1-Core;192.168.1.1;cisco_ios;22;admin;SI
SI;MikroTik-Borde;192.168.88.1;mikrotik_routeros;22;admin;NO
NO;Fortigate-60F;192.168.1.99;fortinet;22;admin;NO
```

- **activo:** `SI` / `NO` para incluir o saltar un equipo.
- **tipo:** el `device_type` de netmiko según la marca.
- **enable:** `SI` si el equipo necesita modo privilegiado (enable) para mostrar la config.

---

## Credenciales seguras

Las contraseñas **no se guardan en el CSV ni en el código**. `GuardarCredencial.cmd` las guarda en el **Administrador de credenciales de Windows** usando `keyring` (en Linux/macOS, en el llavero del sistema). El script las pide desde ahí cuando se conecta.

---

## El reporte de cambios

Al terminar, se abre un HTML con una tabla por equipo y un estado:

- **Primer respaldo** — es la primera vez que se guarda.
- **Sin cambios** — igual al respaldo anterior.
- **Con cambios** — muestra el diff: líneas agregadas en verde, quitadas en rojo.
- **Error** — no se pudo conectar (con el motivo).

---

## Probarlo en un laboratorio

En GNS3 o EVE-NG, con un router Cisco que tenga SSH:

```
ip domain-name lab.local
crypto key generate rsa modulus 2048
username admin privilege 15 secret <clave>
ip ssh version 2
line vty 0 4
 login local
 transport input ssh
```

Luego agrégalo a `equipos.csv` con tipo `cisco_ios` y respáldalo.

---

## Dejarlo corriendo solo

Crea una tarea en el Programador de tareas que ejecute, en esta carpeta:

```
.venv\Scripts\python.exe respaldo.py --no-abrir
```

Así respalda todos los equipos sin abrir el reporte, por ejemplo todas las noches.

---

## Estructura del proyecto

```
respaldo-config-red/
├─ respaldo.py            # script principal
├─ Respaldar.cmd          # respaldar ahora
├─ GuardarCredencial.cmd  # guardar la clave SSH de forma segura
├─ Demo.cmd               # demo con equipos de ejemplo
├─ equipos.ejemplo.csv    # plantilla de la lista de equipos
├─ ejemplos/              # configuraciones de ejemplo para la demo
├─ requirements.txt
└─ README.md
```

> `equipos.csv` (tus equipos reales), los respaldos y los reportes no se suben al repositorio.

---

## Preguntas frecuentes

**¿Dónde quedan las contraseñas?** En el Administrador de credenciales de Windows, nunca en texto plano.

**¿Soporta mi marca?** Si no está en la lista, netmiko quizá igual la soporte; agrega el `device_type` correcto en el CSV.

**¿Y Sophos?** La librería no trae un tipo específico para Sophos; para esos equipos conviene exportar la config desde su propia interfaz.

---

## Conceptos aplicados

Automatización de red con SSH (netmiko), manejo seguro de credenciales (keyring / Administrador de credenciales), control de cambios con `difflib`, normalización de configuraciones (ignorar líneas volátiles) y reportes HTML.

---

## Aviso

Úsalo solo en equipos propios o donde tengas autorización. Antes de respaldar infraestructura de una empresa, pide permiso al responsable de la red.
