import hashlib
import hmac
import time
import xml.etree.ElementTree as ET

import requests


# =============================================================
# CLIENTE HNAP (Home Network Administration Protocol)
#
# Protocolo usado por routers Linksys/Cisco de la era "Classic"
# (no Smart Wi-Fi / cloud) para administración remota, incluido
# el Linksys E2500. No es una API oficialmente publicada por
# Linksys para terceros, pero es estable y bien documentada por
# la comunidad desde hace más de una década.
#
# Flujo de autenticación (resumen):
# 1. Pedimos un "reto" (Challenge + PublicKey + Cookie) al router.
# 2. Calculamos una "llave privada" combinando el reto con la
#    contraseña de administrador (HMAC-MD5).
# 3. Confirmamos el login enviando esa llave privada.
# 4. Cada acción posterior se firma con esa llave privada + un
#    timestamp, en el header HNAP_AUTH.
# =============================================================

HNAP_NS = "http://purenetworks.com/HNAP1/"


class HNAPError(Exception):
    pass


class HNAPClient:

    def __init__(self, host="192.168.1.1", username="admin", password="", timeout=8):

        self.base_url = f"http://{host}/HNAP1/"
        self.username = username
        self.password = password
        self.timeout = timeout

        self.session = requests.Session()
        self.private_key = None

    # ------------------------------------------------------------------
    # UTILIDADES INTERNAS
    # ------------------------------------------------------------------
    def _hmac_md5(self, key, message):
        return hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.md5
        ).hexdigest().upper()

    def _soap_envelope(self, action_name, inner_xml):
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soap:Body>'
            f'<{action_name} xmlns="{HNAP_NS}">'
            f'{inner_xml}'
            f'</{action_name}>'
            '</soap:Body>'
            '</soap:Envelope>'
        )

    def _build_auth_header(self, action_name):
        timestamp = str(int(time.time() * 1000) % 2000000000000)
        soap_action_full = f'"{HNAP_NS}{action_name}"'
        auth = self._hmac_md5(self.private_key, timestamp + soap_action_full)
        return f"{auth} {timestamp}"

    def _post(self, action_name, body_xml, signed=False):

        soap_action = f'"{HNAP_NS}{action_name}"'

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": soap_action,
        }

        if signed:
            if not self.private_key:
                raise HNAPError("No hay sesión activa. Llama a login() primero.")
            headers["HNAP_AUTH"] = self._build_auth_header(action_name)

        envelope = self._soap_envelope(action_name, body_xml)

        response = self.session.post(
            self.base_url,
            data=envelope.encode("utf-8"),
            headers=headers,
            timeout=self.timeout
        )

        response.raise_for_status()

        return response.text

    def _extract_tag(self, xml_text, tag_name):
        try:
            root = ET.fromstring(xml_text)
            for elem in root.iter():
                if elem.tag.endswith(tag_name):
                    return elem.text
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------------------
    def login(self):

        body = (
            "<Action>request</Action>"
            f"<Username>{self.username}</Username>"
            "<LoginPassword></LoginPassword>"
            "<Captcha></Captcha>"
        )

        raw = self._post("Login", body)

        challenge = self._extract_tag(raw, "Challenge")
        public_key = self._extract_tag(raw, "PublicKey")
        cookie = self._extract_tag(raw, "Cookie")

        if not challenge or not public_key or not cookie:
            raise HNAPError(
                "El router no respondió el reto de HNAP esperado. "
                "Puede que HNAP esté deshabilitado, la IP sea incorrecta, "
                "o este firmware use un protocolo distinto."
            )

        self.session.cookies.set("uid", cookie)

        self.private_key = self._hmac_md5(public_key + self.password, challenge)

        login_password = self._hmac_md5(self.private_key, challenge)

        body2 = (
            "<Action>login</Action>"
            f"<Username>{self.username}</Username>"
            f"<LoginPassword>{login_password}</LoginPassword>"
            "<Captcha></Captcha>"
        )

        auth_header = self._build_auth_header("Login")

        response = self.session.post(
            self.base_url,
            data=self._soap_envelope("Login", body2).encode("utf-8"),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPAction": f'"{HNAP_NS}Login"',
                "HNAP_AUTH": auth_header,
            },
            timeout=self.timeout
        )

        response.raise_for_status()

        result = self._extract_tag(response.text, "LoginResult")

        if result != "OK":
            self.private_key = None
            raise HNAPError(
                f"Login HNAP rechazado por el router (resultado: {result}). "
                "Revisa el usuario y la contraseña de administrador."
            )

        return True

    # ------------------------------------------------------------------
    # LLAMAR CUALQUIER ACCIÓN (una vez logueado)
    # ------------------------------------------------------------------
    def call_action(self, action_name, body_xml=""):

        if not self.private_key:
            self.login()

        return self._post(action_name, body_xml, signed=True)
