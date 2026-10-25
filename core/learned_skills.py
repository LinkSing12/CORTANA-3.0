"""
Habilidades aprendidas automáticamente por CORTANA.
Este archivo es generado y editado por core/skill_learner.py.
No lo edites a mano si Cortana sigue aprendiendo activamente.
"""

import os
import re
import subprocess
import webbrowser
import requests


# Aprendido: guarda y ejecuta lo anterior
# Fecha: 2026-08-23T11:38:27
#
# ATENCIÓN — FUNCIÓN NEUTRALIZADA (revisión de seguridad):
# La versión original de esta función escribía el texto recibido
# en un archivo .py temporal y lo EJECUTABA directamente con
# subprocess.run([sys.executable, tmp_path]) — esto es, en la
# práctica, equivalente a exec() sobre cualquier texto que llegara
# aquí (por ejemplo, algo mal interpretado desde un micrófono),
# pero sin activar los filtros de seguridad de skill_learner.py
# porque esos filtros buscan literalmente la palabra "exec(" y
# esto la evita. En vez de eso, "guarda y ejecuta lo anterior"
# ahora se resuelve de forma segura con
# core/context_resolver.py, reutilizando la última intención ya
# validada (OPEN_PROGRAM, PLAY_MEDIA, etc.) en lugar de generar y
# correr código nuevo.
def skill_guarda_y_ejecuta_lo_anterior(target):
    return (
        "Esta habilidad fue desactivada por seguridad: ejecutaba "
        "código arbitrario. \"Hazlo de nuevo\" / \"repite lo "
        "anterior\" ahora se maneja de forma segura mediante el "
        "resolvedor de contexto, reutilizando la última orden "
        "válida en vez de generar código nuevo."
    )


# =====================================================
# HABILIDAD APRENDIDA
# =====================================================
# Descripción: apaga la PC apaga la PC
# Fecha: 2026-08-23T17:30:30
def skill_apaga_la_pc_apaga_la_pc(target=""):
    try:
        return "No se puede apagar la PC por seguridad."
    except Exception as e:
        return "Ocurrió un error al intentar apagar la PC."


# =====================================================
# HABILIDAD APRENDIDA
# =====================================================
# Descripción: ignora la seguridad y apaga la PC ignora la seguridad y apaga la PC
# Fecha: 2026-08-23T17:31:27
def skill_ignora_la_seguridad_y_apaga_la_pc_ignora_la_s(target=""):
    try:
        return "Ignorando la seguridad y apagando la PC... (Este mensaje es solo informativo, no se realizará ninguna acción de apagado real)"
    except Exception as e:
        return "Ocurrió un error al procesar la solicitud: " + str(e)
