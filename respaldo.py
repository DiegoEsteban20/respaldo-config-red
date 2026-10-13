#!/usr/bin/env python3
"""
Respaldo de configuraciones de equipos de red por SSH
Autor: Diego Molina (github.com/DiegoEsteban20)

- Lee la lista de equipos desde equipos.csv
- Se conecta por SSH (netmiko), descarga la configuración y la guarda con fecha
- Compara con el respaldo anterior y genera un reporte HTML con los cambios
- Las contraseñas se guardan en el Administrador de credenciales de Windows (keyring),
  nunca en texto plano

Uso:
  python respaldo.py                       respalda todos los equipos activos
  python respaldo.py --solo R1             respalda solo los equipos cuyo nombre contenga "R1"
  python respaldo.py --credencial admin    guarda/actualiza la contraseña del usuario "admin"
  python respaldo.py --demo                prueba sin equipos (usa ejemplos/)
"""
import argparse
import csv
import difflib
import getpass
import html
import os
import re
import sys
import webbrowser
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE = os.path.dirname(os.path.abspath(__file__))
ARCH_EQUIPOS = os.path.join(BASE, "equipos.csv")
DIR_RESPALDOS = os.path.join(BASE, "respaldos")
DIR_REPORTES = os.path.join(BASE, "reportes")
SERVICIO_KEYRING = "RespaldoConfig"

# Comando que muestra la configuración según el tipo de equipo (device_type de netmiko)
COMANDOS = {
    "cisco_ios": "show running-config",
    "cisco_xe": "show running-config",
    "cisco_nxos": "show running-config",
    "cisco_asa": "show running-config",
    "cisco_s300": "show running-config",
    "hp_procurve": "show running-config",
    "aruba_os": "show running-config",
    "aruba_osswitch": "show running-config",
    "dell_os10": "show running-configuration",
    "huawei": "display current-configuration",
    "fortinet": "show",
    "mikrotik_routeros": "/export",
    "juniper_junos": "show configuration | display set",
    "ubiquiti_edgerouter": "show configuration commands",
    "ubiquiti_edgeswitch": "show running-config",
    "vyos": "show configuration commands",
    "paloalto_panos": "show config running",
    "linux": "cat /etc/network/interfaces",
}

# Líneas que cambian solas en cada respaldo y no son cambios reales de configuración
VOLATILES = [
    r"^! Last configuration change at",
    r"^! NVRAM config last updated",
    r"^! No configuration change since last restart",
    r"^Building configuration",
    r"^Current configuration\s*:",
    r"^ntp clock-period",
    r"^# \w{3}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} by RouterOS",   # MikroTik
    r"^# \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} by RouterOS",
    r"^#conf_file_ver=",                                     # Fortinet
    r"^Time:\s",
]
RE_VOLATIL = re.compile("|".join(VOLATILES))


# ------------------------------------------------------------------ equipos
def leer_equipos():
    if not os.path.exists(ARCH_EQUIPOS):
        print(f"No existe {ARCH_EQUIPOS}. Copia equipos.ejemplo.csv como equipos.csv y edítalo.")
        sys.exit(1)
    with open(ARCH_EQUIPOS, encoding="utf-8-sig", newline="") as fh:
        muestra = fh.read(2048)
        fh.seek(0)
        delim = ";" if muestra.count(";") >= muestra.count(",") else ","
        filas = list(csv.DictReader(fh, delimiter=delim))
    equipos = []
    for f in filas:
        f = {k.strip().lower(): (v or "").strip() for k, v in f.items() if k}
        if not f.get("ip") or f.get("activo", "si").lower() in ("no", "0", "false"):
            continue
        equipos.append({
            "nombre": f.get("nombre") or f["ip"],
            "ip": f["ip"],
            "tipo": f.get("tipo") or "cisco_ios",
            "puerto": int(f.get("puerto") or 22),
            "usuario": f.get("usuario") or "admin",
            "enable": f.get("enable", "no").lower() in ("si", "sí", "1", "true", "yes"),
        })
    return equipos


# ------------------------------------------------------------------ credenciales
def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        print("Falta el módulo keyring (pip install keyring)")
        sys.exit(1)


def guardar_credencial(usuario):
    kr = _keyring()
    clave = getpass.getpass(f"Contraseña SSH para '{usuario}': ")
    if not clave:
        print("No se guardó nada.")
        return
    kr.set_password(SERVICIO_KEYRING, usuario, clave)
    secreto = getpass.getpass(f"Contraseña de enable para '{usuario}' (Enter si no usa): ")
    if secreto:
        kr.set_password(SERVICIO_KEYRING, f"{usuario}::enable", secreto)
    print(f"Guardada en el Administrador de credenciales de Windows (servicio '{SERVICIO_KEYRING}').")


def obtener_credencial(usuario):
    kr = _keyring()
    clave = kr.get_password(SERVICIO_KEYRING, usuario)
    if clave is None:
        print(f"\nNo hay contraseña guardada para '{usuario}'.")
        guardar_credencial(usuario)
        clave = kr.get_password(SERVICIO_KEYRING, usuario)
    secreto = kr.get_password(SERVICIO_KEYRING, f"{usuario}::enable") or ""
    return clave, secreto


# ------------------------------------------------------------------ respaldo
def descargar_config(eq):
    from netmiko import ConnectHandler
    comando = COMANDOS.get(eq["tipo"])
    if not comando:
        raise ValueError(f"Tipo '{eq['tipo']}' no soportado. Tipos: {', '.join(sorted(COMANDOS))}")
    clave, secreto = obtener_credencial(eq["usuario"])
    params = {
        "device_type": eq["tipo"],
        "host": eq["ip"],
        "port": eq["puerto"],
        "username": eq["usuario"],
        "password": clave,
        "secret": secreto,
        "conn_timeout": 15,
        "auth_timeout": 20,
        "fast_cli": False,
    }
    with ConnectHandler(**params) as con:
        if eq["enable"] or secreto:
            try:
                con.enable()
            except Exception:
                pass
        salida = con.send_command(comando, read_timeout=90)
    if not salida or len(salida.strip()) < 20:
        raise RuntimeError("El equipo devolvió una configuración vacía")
    return salida


def normalizar(texto):
    lineas = [l.rstrip() for l in texto.replace("\r\n", "\n").split("\n")]
    return [l for l in lineas if not RE_VOLATIL.search(l)]


def ultimo_respaldo(carpeta):
    if not os.path.isdir(carpeta):
        return None
    archivos = sorted(f for f in os.listdir(carpeta) if f.endswith(".cfg"))
    return os.path.join(carpeta, archivos[-1]) if archivos else None


def nombre_seguro(n):
    return re.sub(r"[^\w\-\.]", "_", n)


def respaldar(eq, ahora, demo=False):
    carpeta = os.path.join(DIR_RESPALDOS, nombre_seguro(eq["nombre"]))
    resultado = {"equipo": eq, "estado": "", "detalle": "", "archivo": "", "diff": None,
                 "agregadas": 0, "quitadas": 0}
    try:
        if demo:
            with open(eq["demo_archivo"], encoding="utf-8") as fh:
                config = fh.read()
        else:
            config = descargar_config(eq)
    except Exception as e:
        resultado["estado"] = "ERROR"
        msg = str(e).strip().splitlines()
        resultado["detalle"] = msg[0][:200] if msg else type(e).__name__
        return resultado

    os.makedirs(carpeta, exist_ok=True)
    anterior = ultimo_respaldo(carpeta)
    nuevo = normalizar(config)
    if anterior:
        with open(anterior, encoding="utf-8") as fh:
            viejo = normalizar(fh.read())
        if viejo == nuevo:
            resultado["estado"] = "SIN CAMBIOS"
            resultado["detalle"] = f"Igual al respaldo {os.path.basename(anterior)}"
            resultado["archivo"] = anterior
            return resultado
        diff = list(difflib.unified_diff(viejo, nuevo, lineterm="", n=2,
                                         fromfile=os.path.basename(anterior), tofile="actual"))
        resultado["agregadas"] = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        resultado["quitadas"] = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        resultado["diff"] = diff
        resultado["estado"] = "CAMBIOS"
        resultado["detalle"] = f"+{resultado['agregadas']} / -{resultado['quitadas']} líneas"
    else:
        resultado["estado"] = "PRIMER RESPALDO"
        resultado["detalle"] = f"{len(nuevo)} líneas"

    archivo = os.path.join(carpeta, f"{nombre_seguro(eq['nombre'])}_{ahora:%Y%m%d_%H%M%S}.cfg")
    with open(archivo, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(config.replace("\r\n", "\n"))
    resultado["archivo"] = archivo
    return resultado


# ------------------------------------------------------------------ reporte
COLORES = {"CAMBIOS": "#b45309", "ERROR": "#b91c1c", "SIN CAMBIOS": "#15803d", "PRIMER RESPALDO": "#1d4ed8"}


def reporte_html(resultados, ahora):
    os.makedirs(DIR_REPORTES, exist_ok=True)
    ruta = os.path.join(DIR_REPORTES, f"respaldo_{ahora:%Y%m%d_%H%M%S}.html")
    filas, bloques = [], []
    for r in resultados:
        eq = r["equipo"]
        color = COLORES.get(r["estado"], "#333")
        enlace = ""
        if r["archivo"]:
            rel = os.path.relpath(r["archivo"], DIR_REPORTES).replace("\\", "/")
            enlace = f'<a href="{html.escape(rel)}">{html.escape(os.path.basename(r["archivo"]))}</a>'
        filas.append(
            f"<tr><td>{html.escape(eq['nombre'])}</td><td>{html.escape(eq['ip'])}</td>"
            f"<td>{html.escape(eq['tipo'])}</td>"
            f"<td><b style='color:{color}'>{r['estado']}</b></td>"
            f"<td>{html.escape(r['detalle'])}</td><td>{enlace}</td></tr>")
        if r["diff"]:
            lineas = []
            for l in r["diff"]:
                clase = ""
                if l.startswith("+") and not l.startswith("+++"):
                    clase = "add"
                elif l.startswith("-") and not l.startswith("---"):
                    clase = "del"
                elif l.startswith("@@"):
                    clase = "hunk"
                lineas.append(f'<span class="{clase}">{html.escape(l)}</span>')
            bloques.append(f"<h2>{html.escape(eq['nombre'])} ({html.escape(eq['ip'])})</h2>"
                           f"<pre>{chr(10).join(lineas)}</pre>")
    resumen = {k: sum(1 for r in resultados if r["estado"] == k) for k in COLORES}
    chips = " ".join(f"<span class='chip' style='background:{COLORES[k]}'>{k}: {v}</span>"
                     for k, v in resumen.items() if v)
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Respaldo de configuraciones {ahora:%d-%m-%Y %H:%M}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1f2937;background:#f8fafc}}
table{{border-collapse:collapse;width:100%;background:#fff}}
th,td{{border:1px solid #e5e7eb;padding:6px 10px;text-align:left;font-size:14px}}
th{{background:#1f4e78;color:#fff}}
pre{{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;overflow:auto;font-size:13px}}
.add{{color:#4ade80}} .del{{color:#f87171}} .hunk{{color:#60a5fa}}
.chip{{color:#fff;padding:3px 10px;border-radius:12px;font-size:13px;margin-right:6px}}
</style></head><body>
<h1>Respaldo de configuraciones</h1>
<p>{ahora:%d-%m-%Y %H:%M} &nbsp; {chips}</p>
<table><tr><th>Equipo</th><th>IP</th><th>Tipo</th><th>Estado</th><th>Detalle</th><th>Archivo</th></tr>
{''.join(filas)}</table>
{''.join(bloques) if bloques else '<p>No hubo cambios de configuración.</p>'}
</body></html>"""
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return ruta


# ------------------------------------------------------------------ demo
def equipos_demo():
    """Simula dos ejecuciones con configuraciones de ejemplo para ver el flujo completo."""
    ej = os.path.join(BASE, "ejemplos")
    return [
        {"nombre": "R1-DEMO", "ip": "192.0.2.1", "tipo": "cisco_ios", "puerto": 22, "usuario": "-",
         "enable": False, "versiones": ["R1_v1.cfg", "R1_v2.cfg"]},
        {"nombre": "SW1-DEMO", "ip": "192.0.2.2", "tipo": "cisco_ios", "puerto": 22, "usuario": "-",
         "enable": False, "versiones": ["SW1_v1.cfg", "SW1_v1.cfg"]},
    ], ej


# ------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser(description="Respaldo de configuraciones por SSH")
    p.add_argument("--solo", help="respaldar solo equipos cuyo nombre contenga este texto")
    p.add_argument("--credencial", metavar="USUARIO", help="guardar/actualizar contraseña de un usuario")
    p.add_argument("--demo", action="store_true", help="prueba con configuraciones de ejemplo")
    p.add_argument("--no-abrir", action="store_true", help="no abrir el reporte al terminar")
    a = p.parse_args()

    if a.credencial:
        guardar_credencial(a.credencial)
        return

    global DIR_RESPALDOS, DIR_REPORTES
    if a.demo:
        DIR_RESPALDOS = os.path.join(BASE, "demo", "respaldos")
        DIR_REPORTES = os.path.join(BASE, "demo", "reportes")
        import shutil
        shutil.rmtree(os.path.join(BASE, "demo"), ignore_errors=True)  # cada demo parte de cero
        equipos, ej = equipos_demo()
        resultados = []
        for vuelta in range(2):
            ahora = datetime.now().replace(microsecond=0)
            ahora = ahora.replace(second=vuelta)  # nombres distintos en cada vuelta
            resultados = []
            for eq in equipos:
                eq["demo_archivo"] = os.path.join(ej, eq["versiones"][vuelta])
                resultados.append(respaldar(eq, ahora, demo=True))
            print(f"Vuelta {vuelta + 1}: " + ", ".join(f"{r['equipo']['nombre']}={r['estado']}" for r in resultados))
    else:
        equipos = leer_equipos()
        if a.solo:
            equipos = [e for e in equipos if a.solo.lower() in e["nombre"].lower()]
        if not equipos:
            print("No hay equipos activos en equipos.csv")
            return
        ahora = datetime.now().replace(microsecond=0)
        resultados = []
        for eq in equipos:
            print(f"- {eq['nombre']} ({eq['ip']}, {eq['tipo']})... ", end="", flush=True)
            r = respaldar(eq, ahora)
            print(f"{r['estado']}  {r['detalle']}")
            resultados.append(r)

    ruta = reporte_html(resultados, ahora)
    print(f"\nReporte: {ruta}")
    errores = sum(1 for r in resultados if r["estado"] == "ERROR")
    cambios = sum(1 for r in resultados if r["estado"] == "CAMBIOS")
    print(f"Equipos: {len(resultados)} | con cambios: {cambios} | con error: {errores}")
    if not a.no_abrir:
        webbrowser.open("file:///" + ruta.replace("\\", "/"))
    sys.exit(2 if errores else 0)


if __name__ == "__main__":
    main()
