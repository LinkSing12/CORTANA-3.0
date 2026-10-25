"""
ECO - Wi-Fi (listar redes disponibles y conectar), vía netsh.

netsh es una herramienta nativa de Windows — no hace falta instalar
nada nuevo. Es la forma estándar de listar y administrar redes Wi-Fi
desde línea de comandos.

No requiere permisos de administrador para listar redes ni para
conectar a una que ya use el mismo tipo de seguridad que otra
conocida; Windows puede llegar a pedir permiso la primera vez según
la configuración de tu equipo.
"""

import os
import re
import subprocess
import tempfile
from xml.sax.saxutils import escape as xml_escape


class WifiController:

    def _run(self, args, timeout=15):
        return subprocess.run(
            args,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def _interface_name(self):
        """
        netsh necesita el nombre EXACTO del adaptador. La mayoría de
        equipos en español lo llaman "Wi-Fi", pero por si acaso se
        intenta detectar automáticamente la interfaz inalámbrica real
        leyendo la salida de netsh (que también viene en español).
        """
        try:
            result = self._run(["netsh", "wlan", "show", "interfaces"])
            match = re.search(r"Nombre\s*:\s*(.+)", result.stdout)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return "Wi-Fi"

    def list_networks(self):
        """
        Devuelve una lista de dicts: {"ssid", "secured", "signal"}.
        netsh agrupa varios puntos de acceso bajo el mismo SSID; aquí
        se listan SSIDs únicos.
        """
        try:
            result = self._run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"]
            )
        except Exception as error:
            print("ERROR LISTANDO REDES WIFI:", error)
            return []

        if result.returncode != 0:
            return []

        networks = []
        current = None

        for line in result.stdout.splitlines():
            line = line.strip()

            ssid_match = re.match(r"SSID\s+\d+\s*:\s*(.*)", line)
            if ssid_match:
                if current and current["ssid"]:
                    networks.append(current)
                current = {
                    "ssid": ssid_match.group(1).strip(),
                    "secured": True,
                    "signal": "",
                }
                continue

            if current is None:
                continue

            auth_match = re.match(
                r"Autenticaci[oó]n\s*:\s*(.+)", line, re.IGNORECASE
            )
            if auth_match:
                auth = auth_match.group(1).strip().lower()
                current["secured"] = (
                    "abierta" not in auth and "open" not in auth
                )
                continue

            signal_match = re.match(
                r"Se[ñn]al\s*:\s*(.+)", line, re.IGNORECASE
            )
            if signal_match:
                current["signal"] = signal_match.group(1).strip()

        if current and current["ssid"]:
            networks.append(current)

        return networks

    def list_networks_text(self):
        networks = self.list_networks()

        if not networks:
            return "No encontré redes Wi-Fi disponibles cerca."

        partes = []
        for network in networks:
            candado = "con seguridad" if network["secured"] else "abierta"
            señal = f", señal {network['signal']}" if network["signal"] else ""
            partes.append(f"{network['ssid']} ({candado}{señal})")

        return "Redes Wi-Fi disponibles: " + "; ".join(partes) + "."

    def is_network_secured(self, ssid):
        ssid_lower = ssid.strip().lower()
        for network in self.list_networks():
            if network["ssid"].strip().lower() == ssid_lower:
                return network["secured"]
        # Si no aparece en el escaneo actual (señal débil, etc.), se
        # asume que SÍ tiene seguridad — es más seguro pedir la
        # contraseña de más que intentar conectar sin ella.
        return True

    def connect(self, ssid, password=None):
        ssid = str(ssid).strip()

        if not ssid:
            return "¿A qué red Wi-Fi quieres que me conecte?"

        interface = self._interface_name()
        ssid_xml = xml_escape(ssid)

        if password:
            auth, cipher = "WPA2PSK", "AES"
            key_block = (
                "<sharedKey>"
                "<keyType>passPhrase</keyType>"
                "<protected>false</protected>"
                f"<keyMaterial>{xml_escape(password)}</keyMaterial>"
                "</sharedKey>"
            )
        else:
            auth, cipher = "open", "none"
            key_block = ""

        profile_xml = (
            '<?xml version="1.0"?>\n'
            '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">\n'
            f"    <name>{ssid_xml}</name>\n"
            "    <SSIDConfig>\n"
            "        <SSID>\n"
            f"            <name>{ssid_xml}</name>\n"
            "        </SSID>\n"
            "    </SSIDConfig>\n"
            "    <connectionType>ESS</connectionType>\n"
            "    <connectionMode>manual</connectionMode>\n"
            "    <MSM>\n"
            "        <security>\n"
            "            <authEncryption>\n"
            f"                <authentication>{auth}</authentication>\n"
            f"                <encryption>{cipher}</encryption>\n"
            "                <useOneX>false</useOneX>\n"
            "            </authEncryption>\n"
            f"            {key_block}\n"
            "        </security>\n"
            "    </MSM>\n"
            "</WLANProfile>\n"
        )

        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".xml", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(profile_xml)
                tmp_path = tmp.name

            add_result = self._run([
                "netsh", "wlan", "add", "profile",
                f"filename={tmp_path}", f"interface={interface}",
                "user=current",
            ])

            if add_result.returncode != 0:
                output = (add_result.stdout or "") + (add_result.stderr or "")
                print("SALIDA NETSH (ADD PROFILE):", output)
                return f"No pude preparar la conexión a {ssid}."

            connect_result = self._run([
                "netsh", "wlan", "connect",
                f"name={ssid}", f"ssid={ssid}", f"interface={interface}",
            ])

            output = (
                (connect_result.stdout or "") + (connect_result.stderr or "")
            )
            print("SALIDA NETSH (CONNECT):", output)

            if connect_result.returncode == 0:
                return f"Conectando a {ssid}."

            return (
                f"No pude conectarme a {ssid}. Si tiene contraseña, "
                "revisa que esté bien escrita."
            )

        except subprocess.TimeoutExpired:
            return f"Conectar a {ssid} está tardando demasiado."
        except Exception as error:
            print("ERROR CONECTANDO WIFI:", error)
            return f"Ocurrió un error conectando a {ssid}."
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
