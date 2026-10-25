"""
ECO - Cliente de WhatsApp (vía WhatsApp Web, sin API oficial).

WhatsApp no ofrece una API gratuita para automatizar una cuenta
PERSONAL (la "WhatsApp Business Platform" es de pago y pensada para
empresas). La única forma práctica de que Eco envíe, lea y borre
mensajes desde tu número es controlar WhatsApp Web con un navegador
real, tal como si tú mismo lo estuvieras usando.

IMPORTANTE — dos cosas que debes saber antes de usar esto:

1. TÉRMINOS DE SERVICIO: WhatsApp prohíbe los clientes no oficiales y
   la automatización. Usarlo tú mismo, sin mandar mensajes masivos,
   es lo que hace mucha gente con herramientas parecidas, pero el
   riesgo de que tu número reciba una advertencia o un bloqueo
   temporal existe y es tu responsabilidad, no algo que este código
   pueda garantizar que no pase.

2. FRAGILIDAD: WhatsApp Web cambia su interfaz interna sin avisar.
   Los selectores de abajo usan los atributos de accesibilidad
   (aria-label / title) más estables que se pudieron usar, asumiendo
   que TU WhatsApp Web está en ESPAÑOL (Configuración > Idioma de la
   app, o el idioma de tu cuenta). Si WhatsApp cambia su interfaz o
   usas otro idioma, hay que actualizar las cadenas de texto de este
   archivo — no es un bug de lógica.

Requiere: pip install selenium webdriver-manager
"""

import os
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException
    )
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None


def _xpath_literal(value):
    """
    Convierte un texto en un literal seguro para XPath, incluso si
    contiene comillas simples (ej. nombres de contacto tipo "O'Brien").
    """
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat('" + "', \"'\", '".join(parts) + "')"


class WhatsAppClient:

    WHATSAPP_URL = "https://web.whatsapp.com/"

    def __init__(self, profile_dir=None):
        self.profile_dir = profile_dir or os.path.join(
            os.path.abspath("data"), "whatsapp_profile"
        )
        self.driver = None

    # =====================================================
    # NAVEGADOR
    # =====================================================

    LOCK_FILE_NAMES = ("SingletonLock", "SingletonCookie", "SingletonSocket")

    def _ensure_driver(self):
        if webdriver is None:
            raise RuntimeError(
                "Faltan 'selenium' y 'webdriver-manager'. Instálalos "
                "con: pip install selenium webdriver-manager"
            )

        if self.driver is not None:
            try:
                _ = self.driver.title
                return self.driver
            except Exception:
                # La sesión ya está muerta (Chrome se cerró solo, se
                # bloqueó una actualización, etc.) — se intenta cerrar
                # limpio para no dejar más basura detrás.
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

        os.makedirs(self.profile_dir, exist_ok=True)
        self._clear_stale_lock_files()

        options = Options()
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        # NO headless: la primera vez hay que escanear el código QR,
        # y WhatsApp Web detecta y bloquea navegadores headless con
        # más facilidad que uno visible normal.

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        self.driver.get(self.WHATSAPP_URL)
        return self.driver

    def _clear_stale_lock_files(self):
        """
        Si un intento anterior terminó mal (Chrome se cerró solo, se
        mató el proceso, etc. sin pasar por quit()), deja archivos de
        bloqueo en la carpeta del perfil. El SIGUIENTE intento con ese
        mismo perfil entonces falla de inmediato — el síntoma es
        exactamente "invalid session id: session deleted as the
        browser has closed the connection" apenas se abre. Se limpian
        antes de cada intento nuevo, nunca mientras uno real sigue
        abierto (self.driver ya es None en este punto).
        """
        for name in self.LOCK_FILE_NAMES:
            path = os.path.join(self.profile_dir, name)
            try:
                if os.path.exists(path) or os.path.islink(path):
                    os.remove(path)
            except Exception:
                pass

    def _wait_for_chat_list(self, timeout):
        driver = self._ensure_driver()
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@aria-label='Lista de chats']")
                )
            )
            return True
        except TimeoutException:
            return False

    def ensure_logged_in(self, timeout=120):
        """
        Abre WhatsApp Web. La primera vez, deja el navegador visible
        para que escanees el código QR con tu teléfono — la sesión
        queda guardada en data/whatsapp_profile/ y no hace falta
        volver a escanearlo en usos futuros (mientras no cierres esa
        sesión desde el teléfono).
        """
        if self._wait_for_chat_list(timeout=5):
            return True

        print(
            "📱 WHATSAPP: escanea el código QR con tu teléfono "
            "(WhatsApp > Ajustes > Dispositivos vinculados)..."
        )

        logged_in = self._wait_for_chat_list(timeout=timeout)

        if logged_in:
            # Aviso explícito: después de escanear, sigue trabajando
            # (busca el chat, escribe, envía). Si se cierra la ventana
            # ahora pensando que ya terminó, se pierde la sesión antes
            # de que Eco llegue a hacer nada.
            print(
                "✅ WHATSAPP: sesión iniciada. NO cierres esta ventana "
                "todavía — Eco va a escribir el mensaje ahora mismo."
            )

        return logged_in

    def _open_chat(self, contact_name, timeout=20):
        contact_name = str(contact_name).strip()
        driver = self._ensure_driver()

        if not self.ensure_logged_in():
            raise RuntimeError(
                "No se pudo iniciar sesión en WhatsApp Web (¿se escaneó "
                "el código QR a tiempo?)."
            )

        search_box = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[@aria-label='Cuadro de texto de búsqueda']"
            ))
        )
        search_box.click()
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(Keys.DELETE)
        search_box.send_keys(contact_name)
        time.sleep(1.5)

        try:
            first_result = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//span[@title={_xpath_literal(contact_name)}]"
                ))
            )
        except TimeoutException:
            raise RuntimeError(
                f"No encontré ningún chat de WhatsApp llamado "
                f"'{contact_name}'."
            )

        first_result.click()
        time.sleep(1)
        return driver

    # =====================================================
    # ENVIAR
    # =====================================================

    def send_message(self, contact_name, message):
        contact_name = str(contact_name).strip()
        message = str(message).strip()

        if not contact_name or not message:
            return "Necesito a quién y qué mensaje enviar por WhatsApp."

        try:
            driver = self._open_chat(contact_name)

            message_box = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((
                    By.XPATH, "//div[@aria-label='Escribe un mensaje']"
                ))
            )
            message_box.click()

            lines = message.split("\n")
            for index, line in enumerate(lines):
                message_box.send_keys(line)
                if index < len(lines) - 1:
                    message_box.send_keys(Keys.SHIFT, Keys.ENTER)

            message_box.send_keys(Keys.ENTER)

            return f"Mensaje enviado a {contact_name} por WhatsApp."

        except RuntimeError as error:
            return str(error)
        except Exception as error:
            print("ERROR ENVIANDO WHATSAPP:", error)
            return (
                f"No pude enviar el mensaje a {contact_name} por "
                "WhatsApp (puede que la interfaz haya cambiado)."
            )

    # =====================================================
    # LEER
    # =====================================================

    def read_last_messages(self, contact_name, count=5):
        contact_name = str(contact_name).strip()

        if not contact_name:
            return ["¿De quién quieres que lea los mensajes?"]

        try:
            driver = self._open_chat(contact_name)
            time.sleep(1)

            bubbles = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'message-in') or "
                "contains(@class,'message-out')]"
            )

            messages = []
            for bubble in bubbles[-count:]:
                try:
                    text_span = bubble.find_element(
                        By.XPATH,
                        ".//span[contains(@class,'selectable-text')]"
                    )
                except NoSuchElementException:
                    continue

                is_outgoing = "message-out" in (
                    bubble.get_attribute("class") or ""
                )
                who = "Tú" if is_outgoing else contact_name
                messages.append(f"{who}: {text_span.text}")

            if not messages:
                return [
                    f"No encontré mensajes de texto recientes con "
                    f"{contact_name} (puede que el último sea una "
                    "imagen, audio o algo que no es texto)."
                ]

            return messages

        except RuntimeError as error:
            return [str(error)]
        except Exception as error:
            print("ERROR LEYENDO WHATSAPP:", error)
            return [
                f"No pude leer los mensajes de {contact_name} "
                "(puede que la interfaz haya cambiado)."
            ]

    # =====================================================
    # BORRAR
    # =====================================================

    def delete_last_sent_message(self, contact_name, for_everyone=False):
        contact_name = str(contact_name).strip()

        if not contact_name:
            return "¿De qué chat de WhatsApp quieres borrar el mensaje?"

        try:
            driver = self._open_chat(contact_name)
            time.sleep(1)

            outgoing = driver.find_elements(
                By.XPATH, "//div[contains(@class,'message-out')]"
            )
            if not outgoing:
                return (
                    f"No encontré ningún mensaje tuyo en el chat con "
                    f"{contact_name}."
                )

            last_message = outgoing[-1]

            # Pasar el mouse por encima para que aparezca el botón de
            # opciones del mensaje (no siempre es visible de entrada).
            ActionChains(driver).move_to_element(last_message).perform()

            options_button = last_message.find_element(
                By.XPATH,
                ".//div[@aria-label='Menú' or "
                "@aria-label='Opciones de mensaje']"
            )
            options_button.click()

            delete_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//li[.//div[text()='Eliminar mensaje']] | "
                    "//div[text()='Eliminar mensaje']"
                ))
            )
            delete_option.click()

            target_text = (
                "Eliminar para todos" if for_everyone else "Eliminar para mí"
            )
            confirm_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH, f"//div[text()='{target_text}']"
                ))
            )
            confirm_button.click()

            modo = "para todos" if for_everyone else "solo para ti"
            return (
                f"Borré el último mensaje que le enviaste a "
                f"{contact_name} ({modo})."
            )

        except RuntimeError as error:
            return str(error)
        except (NoSuchElementException, TimeoutException):
            return (
                f"Encontré el chat con {contact_name}, pero no pude dar "
                "con el botón para borrar el mensaje (puede que WhatsApp "
                "Web haya cambiado su interfaz, o que ya pasó el tiempo "
                "límite para 'eliminar para todos')."
            )
        except Exception as error:
            print("ERROR BORRANDO MENSAJE DE WHATSAPP:", error)
            return f"No pude borrar el mensaje de {contact_name}."

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
