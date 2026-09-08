import subprocess
import re
from typing import List, Dict, Optional


# ============================================================
# CORTANA 3.0
# GESTOR DE PROGRAMAS Y PROCESOS DE WINDOWS
# ============================================================


# Procesos que Cortana NO debe cerrar automáticamente.
PROCESOS_PROTEGIDOS = {
    "system",
    "system idle process",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "dwm.exe",
    "explorer.exe",
    "fontdrvhost.exe",
    "spoolsv.exe",
}


# ============================================================
# LISTAR PROCESOS
# ============================================================

def listar_procesos() -> List[Dict[str, str]]:
    """
    Devuelve una lista de procesos actualmente ejecutándose.
    """

    procesos = []

    try:
        resultado = subprocess.run(
            [
                "tasklist",
                "/FO",
                "CSV",
                "/NH"
            ],
            capture_output=True,
            text=True,
            encoding="cp850",
            errors="ignore"
        )

        if resultado.returncode != 0:
            return procesos

        for linea in resultado.stdout.splitlines():

            partes = re.findall(r'"([^"]*)"', linea)

            if len(partes) >= 2:

                nombre = partes[0]
                pid = partes[1]

                procesos.append({
                    "name": nombre,
                    "pid": pid
                })

    except Exception as e:
        print(f"ERROR AL LISTAR PROCESOS: {e}")

    return procesos


# ============================================================
# OBTENER NOMBRES ÚNICOS
# ============================================================

def obtener_programas_en_ejecucion() -> List[str]:
    """
    Devuelve únicamente los nombres de los programas ejecutándose.
    """

    procesos = listar_procesos()

    nombres = set()

    for proceso in procesos:
        nombre = proceso.get("name")

        if nombre:
            nombres.add(nombre)

    return sorted(nombres, key=str.lower)


# ============================================================
# BUSCAR PROGRAMA
# ============================================================

def buscar_proceso(nombre: str) -> List[Dict[str, str]]:
    """
    Busca procesos cuyo nombre coincida de forma
    flexible con el nombre proporcionado por el usuario.
    """

    nombre = str(nombre).lower().strip()

    if not nombre:
        return []

    # Normalizar espacios, puntos y guiones
    nombre_normalizado = re.sub(
        r"[\s._-]+",
        "",
        nombre
    )

    resultados = []

    for proceso in listar_procesos():

        nombre_proceso = proceso["name"].lower().strip()

        nombre_proceso_normalizado = re.sub(
            r"[\s._-]+",
            "",
            nombre_proceso
        )

        # Coincidencia normal
        if nombre in nombre_proceso:
            resultados.append(proceso)
            continue

        # Coincidencia normalizada
        if nombre_normalizado in nombre_proceso_normalizado:
            resultados.append(proceso)
            continue

    return resultados

# ============================================================
# COMPROBAR SI ESTÁ EJECUTÁNDOSE
# ============================================================

def esta_ejecutandose(nombre: str) -> bool:
    """
    Comprueba si un programa está actualmente ejecutándose.
    """

    return len(buscar_proceso(nombre)) > 0


# ============================================================
# OBTENER PID
# ============================================================

def obtener_pids(nombre: str) -> List[str]:
    """
    Devuelve los PID de un programa.
    """

    procesos = buscar_proceso(nombre)

    return [
        proceso["pid"]
        for proceso in procesos
    ]


# ============================================================
# COMPROBAR PROTECCIÓN
# ============================================================

def proceso_protegido(nombre: str) -> bool:
    """
    Determina si un proceso está protegido.
    """

    nombre = nombre.lower().strip()

    if nombre not in PROCESOS_PROTEGIDOS:
        return False

    return True


# ============================================================
# CERRAR PROCESO
# ============================================================

def cerrar_proceso(nombre: str) -> Dict:
    """
    Cierra un programa de forma controlada.
    """

    nombre = nombre.strip()

    if not nombre:
        return {
            "success": False,
            "message": "No se especificó ningún programa."
        }

    procesos = buscar_proceso(nombre)

    if not procesos:
        return {
            "success": False,
            "message": f"No encontré el programa {nombre} ejecutándose."
        }

    resultados = []

    for proceso in procesos:

        nombre_real = proceso["name"]
        pid = proceso["pid"]

        if proceso_protegido(nombre_real):

            resultados.append({
                "name": nombre_real,
                "pid": pid,
                "success": False,
                "message": "Proceso protegido."
            })

            continue

        try:

            resultado = subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    pid,
                    "/T"
                ],
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="ignore"
            )

            if resultado.returncode == 0:

                resultados.append({
                    "name": nombre_real,
                    "pid": pid,
                    "success": True,
                    "message": "Proceso cerrado."
                })

            else:

                resultados.append({
                    "name": nombre_real,
                    "pid": pid,
                    "success": False,
                    "message": resultado.stderr.strip()
                })

        except Exception as e:

            resultados.append({
                "name": nombre_real,
                "pid": pid,
                "success": False,
                "message": str(e)
            })

    exitosos = [
        r for r in resultados
        if r["success"]
    ]

    return {
        "success": len(exitosos) > 0,
        "results": resultados
    }


# ============================================================
# INFORMACIÓN DEL PROCESO
# ============================================================

def informacion_proceso(nombre: str) -> Optional[Dict]:
    """
    Obtiene información básica de un proceso.
    """

    procesos = buscar_proceso(nombre)

    if not procesos:
        return None

    return {
        "name": procesos[0]["name"],
        "pid": procesos[0]["pid"],
        "instances": len(procesos)
    }


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("CORTANA 3.0 - GESTOR DE PROCESOS")
    print("=" * 60)

    procesos = obtener_programas_en_ejecucion()

    print(f"\nProcesos encontrados: {len(procesos)}\n")

    for programa in procesos:
        print(programa)

    print("\n" + "=" * 60)