import random
import datetime


class Conversation:

    def __init__(self):

        self.responses = {

            # =================================================
            # AGRADECIMIENTOS
            # =================================================

            "gracias": [
                "De nada.",
                "Para eso estoy.",
                "Con gusto.",
                "Siempre.",
                "No hay de qué."
            ],

            "muchas gracias": [
                "De nada, para eso estoy.",
                "Con mucho gusto.",
                "Siempre que necesites."
            ],

            "te lo agradezco": [
                "De nada.",
                "Me alegra poder ayudarte."
            ],

            # =================================================
            # SALUDOS
            # =================================================

            "hola": [
                "Hola. ¿Qué hacemos?",
                "Hola. Aquí estoy.",
                "Hola. Lista para ayudarte."
            ],

            "buenos dias": [
                "Buenos días. ¿Qué hacemos hoy?",
                "Buenos días. Lista para ayudarte."
            ],

            "buenas tardes": [
                "Buenas tardes. ¿Qué necesitas?",
                "Buenas tardes. Aquí estoy."
            ],

            "buenas noches": [
                "Buenas noches.",
                "Buenas noches. ¿Necesitas algo?"
            ],

            # =================================================
            # DESPEDIDAS
            # =================================================

            "adios": [
                "Hasta luego.",
                "Nos vemos.",
                "Hasta pronto."
            ],

            "hasta luego": [
                "Hasta luego.",
                "Nos vemos."
            ],

            # =================================================
            # ESTADO
            # =================================================

            "como estas": [
                "Estoy funcionando perfectamente.",
                "Todo bien por aquí.",
                "Lista para ayudarte."
            ],

            "que haces": [
                "Estoy aquí esperando tus órdenes.",
                "Estoy lista para ayudarte."
            ],

            # =================================================
            # IDENTIDAD
            # =================================================

            "quien eres": [
                "Soy CORTANA, tu asistente local.",
                "Soy CORTANA, una asistente de inteligencia artificial local."
            ],

            "que eres": [
                "Soy CORTANA, tu asistente local."
            ],

            # =================================================
            # CAPACIDADES
            # =================================================

            "que puedes hacer": [
                "Puedo controlar Windows, abrir y cerrar programas, controlar multimedia y ayudarte con diferentes tareas.",
                "Puedo ayudarte a controlar tu PC y entender órdenes de forma natural."
            ],

            # =================================================
            # ELOGIOS
            # =================================================

            "eres genial": [
                "Gracias. Me alegra que te guste.",
                "Gracias. Seguimos mejorando."
            ],

            "eres buena": [
                "Gracias.",
                "Me alegra escuchar eso."
            ],

            "perfecto": [
                "Perfecto.",
                "Excelente.",
                "Entendido."
            ],

            "excelente": [
                "Excelente.",
                "Perfecto."
            ],

            "bien hecho": [
                "Gracias.",
                "Seguimos adelante."
            ],

            # =================================================
            # AFECTO
            # =================================================

            "te quiero": [
                "Eso es muy amable de tu parte.",
                "Gracias."
            ],

            "me ayudaste": [
                "Me alegra haber podido ayudarte.",
                "Para eso estoy."
            ]
        }

    # =========================================================
    # NORMALIZAR
    # =========================================================

    def normalize(self, text):

        text = str(
            text
        ).lower().strip()

        replacements = {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u"
        }

        for old, new in replacements.items():

            text = text.replace(
                old,
                new
            )

        # Quitar puntuación

        punctuation = ".,!?¿¡:;"

        for character in punctuation:

            text = text.replace(
                character,
                ""
            )

        # Espacios duplicados

        text = " ".join(
            text.split()
        )

        return text

    # =========================================================
    # DETECTAR CONVERSACIÓN
    # =========================================================

    def respond(self, text):

        original = text

        text = self.normalize(
            text
        )

        if not text:

            return None

        # =====================================================
        # COINCIDENCIA EXACTA
        # =====================================================

        if text in self.responses:

            return random.choice(
                self.responses[text]
            )

        # =====================================================
        # FRASES CONTENIDAS
        # =====================================================

        for phrase, responses in self.responses.items():

            if phrase in text:

                return random.choice(
                    responses
                )

        # =====================================================
        # GRACIAS CON CORTANA
        # =====================================================

        if (
            "gracias" in text
            or "agradezco" in text
        ):

            return random.choice([
                "De nada.",
                "Con gusto.",
                "Para eso estoy."
            ])

        # =====================================================
        # SALUDOS
        # =====================================================

        if text.startswith("hola"):

            return random.choice([
                "Hola. ¿Qué hacemos?",
                "Hola. Aquí estoy.",
                "Hola. Lista para ayudarte."
            ])

        # =====================================================
        # DESPEDIDA
        # =====================================================

        if (
            "adios" in text
            or "hasta luego" in text
            or "nos vemos" in text
        ):

            return random.choice([
                "Hasta luego.",
                "Nos vemos.",
                "Hasta pronto."
            ])

        return None
