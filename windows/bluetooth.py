"""
ECO - Bluetooth (listar y reconectar dispositivos YA EMPAREJADOS).

IMPORTANTE — alcance real de este módulo, para que no esperes más de
lo que puede hacer:

Windows no tiene un equivalente de "netsh" para Bluetooth. Lo único
que se puede hacer de forma confiable con herramientas nativas
(PowerShell) es:

1. LISTAR los dispositivos Bluetooth que Windows YA CONOCE (los que
   aparecen en Configuración > Bluetooth y otros dispositivos),
   estén conectados en este momento o no.
2. Intentar RECONECTAR (habilitar) uno de esos dispositivos ya
   emparejados, si Windows lo tiene deshabilitado o desconectado.

Lo que este módulo NO hace, porque requeriría las APIs de
Bluetooth de Windows Runtime (mucho más pesadas y frágiles, y que no
pude probar contra hardware real):

- Descubrir un dispositivo Bluetooth NUEVO que nunca se ha
  emparejado con este equipo.
- Emparejar un dispositivo nuevo pidiendo un PIN/código de
  seguridad.

Es decir: "conecta los audífonos que ya empareja antes" funciona;
"empareja unos audífonos nuevos" no, todavía — para eso hay que
usar Configuración > Bluetooth en Windows la primera vez, y luego sí
podrá reconectarlos por voz.
"""

import re
import subprocess


class BluetoothController:

    def _run_powershell(self, script, timeout=20):
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def list_devices(self):
        """
        Devuelve una lista de dicts: {"name", "connected"} con los
        dispositivos Bluetooth que Windows ya conoce (emparejados).
        """
        script = (
            "Get-PnpDevice -Class Bluetooth | "
            "Where-Object { $_.FriendlyName -and "
            "$_.FriendlyName -notmatch '^(Bluetooth|Adaptador)' } | "
            "Select-Object FriendlyName, Status | "
            "ConvertTo-Csv -NoTypeInformation"
        )

        try:
            result = self._run_powershell(script)
        except Exception as error:
            print("ERROR LISTANDO BLUETOOTH:", error)
            return []

        if result.returncode != 0:
            print("SALIDA POWERSHELL (LISTAR BLUETOOTH):", result.stderr)
            return []

        devices = []
        lines = [l for l in result.stdout.splitlines() if l.strip()]

        for line in lines[1:]:  # la primera línea es el encabezado CSV
            match = re.match(r'^"(.*)","(.*)"$', line.strip())
            if not match:
                continue
            name, status = match.group(1), match.group(2)
            devices.append({
                "name": name,
                "connected": status.strip().upper() == "OK",
            })

        return devices

    def list_devices_text(self):
        devices = self.list_devices()

        if not devices:
            return (
                "No encontré dispositivos Bluetooth ya emparejados en "
                "este equipo."
            )

        partes = [
            f"{d['name']} ({'conectado' if d['connected'] else 'desconectado'})"
            for d in devices
        ]

        return "Dispositivos Bluetooth emparejados: " + "; ".join(partes) + "."

    def connect(self, name):
        """
        Intenta RECONECTAR (habilitar) un dispositivo ya emparejado
        cuyo nombre se parezca al que se pide. No empareja
        dispositivos nuevos — ver el aviso al inicio del archivo.
        """
        name = str(name).strip()
        if not name:
            return "¿A qué dispositivo Bluetooth quieres que me conecte?"

        devices = self.list_devices()
        name_lower = name.lower()

        match = next(
            (d for d in devices if name_lower in d["name"].lower()), None
        )

        if not match:
            return (
                f"No encontré ningún dispositivo Bluetooth emparejado "
                f"llamado algo parecido a '{name}'. Si es la primera vez "
                "que lo usas, tienes que emparejarlo desde Configuración "
                "> Bluetooth — después de eso ya puedo reconectarlo por ti."
            )

        if match["connected"]:
            return f"{match['name']} ya está conectado."

        script = (
            "Get-PnpDevice -Class Bluetooth | "
            f"Where-Object {{ $_.FriendlyName -eq '{match['name']}' }} | "
            "Enable-PnpDevice -Confirm:$false"
        )

        try:
            result = self._run_powershell(script)
        except Exception as error:
            print("ERROR CONECTANDO BLUETOOTH:", error)
            return f"No pude reconectar {match['name']}."

        if result.returncode != 0:
            print("SALIDA POWERSHELL (CONECTAR BLUETOOTH):", result.stderr)
            # El motivo más común: hace falta ejecutar Eco como
            # administrador para habilitar dispositivos.
            return (
                f"No pude reconectar {match['name']} — es posible que "
                "haga falta ejecutar Eco como administrador para "
                "esto."
            )

        return f"Reconectando {match['name']}."
