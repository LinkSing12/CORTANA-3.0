import json
import time
import requests


class Brain:

    def __init__(self):
        # 127.0.0.1 en vez de "localhost": en algunas configuraciones
        # de Windows, resolver "localhost" intenta primero IPv6 (::1)
        # y tarda un poco antes de caer a IPv4. Usar la IP directa
        # evita ese retraso extra en cada intento de conexión.
        self.base_url = "http://127.0.0.1:11434"
        self.url = self.base_url + "/api/generate"
        # qwen2.5:7b en vez de qwen3:14b: mucho más rápido en una
        # RTX 3060 y de sobra para clasificar órdenes — el conocimiento
        # factual ya no depende del modelo, sino de la búsqueda real
        # en internet (core/web_search.py).
        self.model = "qwen2.5:7b"

    def is_available(self):
        """
        Chequeo rápido (0.5s máx) de si Ollama está corriendo.
        Útil para avisar al usuario apenas arranca Cortana, en vez
        de que se entere comando por comando con un error de
        conexión repetido.
        """
        try:
            response = requests.get(self.base_url, timeout=0.5)
            return response.status_code == 200
        except Exception:
            return False

    def think(self, text, context=None):
        if context is None:
            context = {}

        prompt = self.build_prompt(text, context)

        try:
            t_req = time.time()
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    # Mantiene el modelo cargado en memoria 30 min
                    # entre comandos, para no pagar el costo de
                    # recarga (varios segundos con un modelo de 14B)
                    # cada vez que Cortana lleva un rato sin hablarle.
                    "keep_alive": "30m"
                },
                timeout=60
            )
            print(f"⏱ PETICIÓN HTTP A OLLAMA: {time.time() - t_req:.2f}s")
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "").strip()

            print()
            print("RESPUESTA CEREBRO:", raw)

            result = self.parse_response(raw)
            return self.repair_command(text, result)

        except Exception as error:
            print()
            print("ERROR CEREBRO:", error)
            return {"intent": "UNKNOWN", "target": "", "confidence": 0.0}

    def repair_command(self, text, result):
        text = str(text).lower().strip()

        if not isinstance(result, dict):
            result = {"intent": "UNKNOWN", "target": "", "confidence": 0.0}

        intent = str(result.get("intent", "UNKNOWN")).upper().strip()
        target = str(result.get("target", "")).strip()

        try:
            confidence = float(result.get("confidence", 0))
        except Exception:
            confidence = 0.0

        close_words = [
            "cierra", "cerrar", "termina", "terminar",
            "deten", "detener", "sierra"
        ]
        if any(word in text for word in close_words):
            program = self.extract_program(text)
            if program:
                return {"intent": "CLOSE_PROGRAM", "target": program, "confidence": 0.99}

        info_words = [
            "informacion", "información", "informacion de", "información de",
            "informacion sobre", "información sobre", "datos de", "datos sobre",
            "detalles de", "detalles sobre"
        ]
        if any(word in text for word in info_words):
            program = self.extract_program(text)
            if program:
                return {"intent": "PROGRAM_INFO", "target": program, "confidence": 0.99}

        check_words = [
            "esta abierto", "está abierto", "esta ejecutandose", "está ejecutándose",
            "esta ejecutando", "está ejecutando", "esta corriendo", "está corriendo"
        ]
        if any(word in text for word in check_words):
            program = self.extract_program(text)
            if program:
                return {"intent": "CHECK_PROGRAM", "target": program, "confidence": 0.99}

        list_words = [
            "que programas estan abiertos", "qué programas están abiertos",
            "que programas tengo abiertos", "qué programas tengo abiertos",
            "que programas estan ejecutandose", "qué programas están ejecutándose",
            "que esta ejecutandose", "qué está ejecutándose",
            "que esta abierto", "qué está abierto"
        ]
        if any(phrase in text for phrase in list_words):
            return {"intent": "LIST_PROGRAMS", "target": "", "confidence": 0.99}

        # =====================================================
        # ATAJOS DE CONTROL DEL SISTEMA
        # Router.detect_direct_command() ya resuelve apagar,
        # reiniciar, suspender, bloquear, cerrar sesión y
        # cancelar apagado directamente sobre el texto original,
        # así que aquí solo reforzamos lo que NO cubre ese atajo:
        # info de sistema/CPU/memoria/disco/batería.
        # =====================================================

        if any(p in text for p in (
            "informacion del sistema", "información del sistema",
            "estado del sistema", "info del sistema"
        )):
            return {"intent": "SYSTEM_INFO", "target": "", "confidence": 0.95}

        if "cpu" in text and any(w in text for w in ("uso", "informacion", "información", "estado")):
            return {"intent": "CPU_INFO", "target": "", "confidence": 0.9}

        if any(p in text for p in ("memoria ram", "uso de memoria", "cuanta memoria", "cuánta memoria")):
            return {"intent": "MEMORY_INFO", "target": "", "confidence": 0.9}

        if any(p in text for p in ("espacio en disco", "uso del disco", "cuanto disco", "cuánto disco")):
            return {"intent": "DISK_INFO", "target": "", "confidence": 0.9}

        if any(p in text for p in ("bateria", "batería")):
            return {"intent": "BATTERY_INFO", "target": "", "confidence": 0.9}

        # =====================================================
        # RESPALDO WEB: preguntas generales
        # Si Qwen devuelve UNKNOWN o confianza muy baja, una pregunta
        # factual se convierte automáticamente en búsqueda web.
        # Esto evita que preguntas como "Quién fue Juan Pablo?"
        # terminen bloqueadas por confianza 0.0.
        # =====================================================
        web_question_starts = (
            "quien ", "quién ",
            "que es ", "qué es ",
            "que fue ", "qué fue ",
            "que era ", "qué era ",
            "cual es ", "cuál es ",
            "cuales son ", "cuáles son ",
            "cuando ", "cuándo ",
            "donde ", "dónde ",
            "como ", "cómo ",
            "por que ", "por qué ",
            "para que ", "para qué ",
            "cuanto ", "cuánto ",
            "cuantos ", "cuántos ",
            "cuanta ", "cuánta ",
            "cuantas ", "cuántas ",
            "explicame ", "explícame ",
            "dime que ", "dime qué ",
            "dime quien ", "dime quién ",
            "busca ", "buscar ",
            "investiga ", "investigar ",
            "averigua ", "averiguar ",
            "consulta ", "consultar "
        )

        stripped = text.strip()
        is_question = (
            stripped.endswith("?")
            or stripped.startswith(web_question_starts)
        )

        if is_question and intent in {"UNKNOWN", "", "NONE"}:
            return {
                "intent": "WEB_SEARCH",
                "target": text.strip(" ¿?¡!"),
                "confidence": 0.99
            }

        # =====================================================
        # INTENTS VÁLIDOS
        # Debe reflejar TODO lo que router.py sabe ejecutar,
        # o Cortana "olvidará" esas órdenes aunque el modelo
        # las clasifique correctamente.
        # =====================================================
        valid_intents = {
            # Programas
            "OPEN_PROGRAM", "CLOSE_PROGRAM", "UNINSTALL_PROGRAM",
            "LIST_PROGRAMS", "LIST_RUNNING_PROGRAMS",
            "CHECK_PROGRAM", "PROGRAM_INFO", "REFRESH_PROGRAMS",

            # Archivos / carpetas / navegación
            "OPEN_FILE", "OPEN_FOLDER", "OPEN_URL",

            # Búsqueda e internet
            "SEARCH_WEB", "SEARCH_GOOGLE", "WEB_SEARCH",
            "SEARCH_YOUTUBE", "PLAY_YOUTUBE",

            # Multimedia
            "PLAY_MEDIA", "PAUSE_MEDIA", "RESUME_MEDIA", "STOP_MEDIA",
            "MEDIA_PLAY", "MEDIA_PAUSE", "MEDIA_STOP",
            "MEDIA_NEXT", "MEDIA_PREVIOUS",
            "VOLUME_UP", "VOLUME_DOWN",
            "MUTE", "VOLUME_MUTE", "UNMUTE", "VOLUME_UNMUTE",

            # Control del sistema
            "SHUTDOWN_PC", "RESTART_PC", "SLEEP_PC",
            "LOCK_PC", "LOGOUT_PC", "CANCEL_SHUTDOWN",
            "SYSTEM_INFO", "CPU_INFO", "MEMORY_INFO",
            "DISK_INFO", "BATTERY_INFO",

            # Conversación
            "IDENTITY", "GREETING", "THANKS", "HOW_ARE_YOU",

            "UNKNOWN"
        }

        if intent not in valid_intents:
            intent = "UNKNOWN"

        return {"intent": intent, "target": target, "confidence": confidence}

    def extract_program(self, text):
        text = str(text).lower().strip()

        if any(x in text for x in ("battle.net", "battle net", "battlenet")):
            return "battlenet.exe"
        if "google chrome" in text or "chrome" in text:
            return "chrome"
        if "microsoft edge" in text or "edge" in text:
            return "edge"
        if "firefox" in text:
            return "firefox"
        if "discord" in text:
            return "discord"
        if "steam" in text:
            return "steam"
        if "epic games" in text:
            return "epicgameslauncher.exe"
        if "bloc de notas" in text or "notepad" in text:
            return "notepad"
        if "calculadora" in text or "calculator" in text:
            return "calculadora"
        if "paint" in text:
            return "paint"
        if "cmd" in text or "simbolo del sistema" in text:
            return "cmd"
        if "powershell" in text:
            return "powershell"

        words = text.split()
        ignored = {
            "dame", "informacion", "información", "sobre", "de", "el", "la",
            "los", "las", "del", "programa", "program", "esta", "está",
            "abierto", "ejecutandose", "ejecutándose", "ejecutando", "corriendo",
            "que", "qué", "cierra", "sierra", "cerrar", "termina", "terminar",
            "deten", "detener"
        }
        possible = []
        for word in words:
            word = word.strip(".,:;!?¿¡")
            if word and word not in ignored:
                possible.append(word)
        return possible[-1] if possible else ""

    def generate(self, prompt):
        try:
            response = requests.post(
                self.url,
                json={"model": self.model, "prompt": prompt, "stream": False, "keep_alive": "30m"},
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception as error:
            print()
            print("ERROR GENERANDO RESPUESTA:", error)
            return ""

    def build_prompt(self, text, context):
        return f"""
Eres el cerebro de CORTANA, un asistente personal para Windows.

Tu trabajo es interpretar exactamente lo que el usuario quiere hacer.

DEVUELVE UNICAMENTE JSON valido.

INTENCIONES DISPONIBLES:

OPEN_PROGRAM
CLOSE_PROGRAM
UNINSTALL_PROGRAM
LIST_PROGRAMS
CHECK_PROGRAM
PROGRAM_INFO
REFRESH_PROGRAMS
OPEN_FILE
OPEN_FOLDER
OPEN_URL
SEARCH_GOOGLE
SEARCH_YOUTUBE
PLAY_MEDIA
PAUSE_MEDIA
RESUME_MEDIA
STOP_MEDIA
MEDIA_NEXT
MEDIA_PREVIOUS
VOLUME_UP
VOLUME_DOWN
MUTE
UNMUTE
SHUTDOWN_PC
RESTART_PC
SLEEP_PC
LOCK_PC
LOGOUT_PC
CANCEL_SHUTDOWN
SYSTEM_INFO
CPU_INFO
MEMORY_INFO
DISK_INFO
BATTERY_INFO
IDENTITY
GREETING
THANKS
HOW_ARE_YOU
WEB_SEARCH
UNKNOWN

REGLAS IMPORTANTES:

Si quiere abrir un programa: OPEN_PROGRAM
Si quiere cerrar un programa: CLOSE_PROGRAM
Si quiere desinstalar un programa: UNINSTALL_PROGRAM
Si quiere saber que programas estan abiertos: LIST_PROGRAMS
Si quiere saber si un programa esta abierto: CHECK_PROGRAM
Si quiere informacion sobre un programa: PROGRAM_INFO
Si quiere abrir un archivo especifico por ruta: OPEN_FILE
Si quiere abrir una carpeta: OPEN_FOLDER
Si quiere abrir una pagina web por URL o dominio: OPEN_URL
Si quiere apagar la PC: SHUTDOWN_PC
Si quiere reiniciar la PC: RESTART_PC
Si quiere suspender o hibernar la PC: SLEEP_PC
Si quiere bloquear la PC: LOCK_PC
Si quiere cerrar sesion: LOGOUT_PC
Si quiere cancelar un apagado o reinicio pendiente: CANCEL_SHUTDOWN
Si pregunta por el estado general del sistema: SYSTEM_INFO
Si pregunta especificamente por el uso de CPU: CPU_INFO
Si pregunta especificamente por la memoria RAM: MEMORY_INFO
Si pregunta especificamente por el disco: DISK_INFO
Si pregunta especificamente por la bateria: BATTERY_INFO

Si hace una pregunta factual, historica, geografica, cientifica o general que
requiera informacion externa, usa WEB_SEARCH y coloca la pregunta completa en target.

Ejemplos:
Usuario: Quien fue Juan Pablo?
{{"intent":"WEB_SEARCH","target":"Quien fue Juan Pablo","confidence":0.99}}

Usuario: Que es la fotosintesis?
{{"intent":"WEB_SEARCH","target":"Que es la fotosintesis","confidence":0.99}}

Usuario: Apaga la computadora
{{"intent":"SHUTDOWN_PC","target":"pc","confidence":0.99}}

Usuario: Cual es el uso de mi CPU
{{"intent":"CPU_INFO","target":"","confidence":0.95}}

Usuario: Desinstala Discord
{{"intent":"UNINSTALL_PROGRAM","target":"discord","confidence":0.95}}

Para preguntas ambiguas, no inventes la respuesta: usa WEB_SEARCH con la pregunta completa.

Si no puedes determinar que quiere y no parece una pregunta factual: UNKNOWN.

CONTEXTO ANTERIOR:
{json.dumps(context, ensure_ascii=False)}

USUARIO:
{text}

DEVUELVE SOLO EL JSON.
"""

    def parse_response(self, raw):
        if not raw:
            return {"intent": "UNKNOWN", "target": "", "confidence": 0.0}

        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            print()
            print("Qwen no devolvio JSON valido:")
            print(raw)
            return {"intent": "UNKNOWN", "target": "", "confidence": 0.0}

        try:
            result = json.loads(raw[start:end + 1])
        except Exception as error:
            print()
            print("ERROR JSON:", error)
            print("RESPUESTA:", raw)
            return {"intent": "UNKNOWN", "target": "", "confidence": 0.0}

        if not isinstance(result, dict):
            return {"intent": "UNKNOWN", "target": "", "confidence": 0.0}

        intent = str(result.get("intent", "UNKNOWN")).upper().strip()
        target = str(result.get("target", "")).strip()
        try:
            confidence = float(result.get("confidence", 0))
        except Exception:
            confidence = 0.0

        return {"intent": intent, "target": target, "confidence": confidence}
