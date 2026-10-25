"""
Notificaciones emergentes de Windows (las de la esquina de la pantalla).

No necesita paquetes extra: usa PowerShell y la API de notificaciones que
ya trae Windows 10/11. El aviso sale con el nombre "Windows PowerShell",
porque Windows exige una app registrada para mostrar notificaciones.
Si algo falla (Windows viejo, notificaciones desactivadas), no pasa nada:
Eco igual avisa con la voz.
"""

import base64
import subprocess
from xml.sax.saxutils import escape


# Identificador de PowerShell en Windows: con este, Windows acepta
# mostrar la notificación sin registrar una app propia.
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('__XML__')
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('__APP__').Show($toast)
"""


def notify(title, message):
    """Muestra la notificación sin esperar a que PowerShell termine."""

    xml = (
        '<toast scenario="reminder"><visual><binding template="ToastGeneric">'
        f"<text>{escape(str(title))}</text>"
        f"<text>{escape(str(message))}</text>"
        "</binding></visual>"
        '<actions><action content="Cerrar" arguments="dismiss" '
        'activationType="system"/></actions></toast>'
    )

    # Las comillas simples se duplican porque el XML va dentro de un
    # texto '...' de PowerShell; -EncodedCommand evita cualquier otro
    # problema de comillas o acentos al pasar el script.
    script = (
        _SCRIPT
        .replace("__XML__", xml.replace("'", "''"))
        .replace("__APP__", _APP_ID)
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")

    try:
        subprocess.Popen(
            [
                "powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception as error:
        print("ERROR MOSTRANDO NOTIFICACIÓN:", error)
        return False
