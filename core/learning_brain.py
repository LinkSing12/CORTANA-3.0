import re

from memory.learning import Learning


class LearningBrain:

    def __init__(self, learning=None):

        if learning is None:
            learning = Learning()

        self.learning = learning

    # =========================================================
    # DETECTAR PETICIÓN DE APRENDIZAJE
    # =========================================================

    def is_learning_request(self, text):

        text = text.lower().strip()

        patterns = [
            "aprende que",
            "aprende esto",
            "recuerda que",
            "quiero enseñarte",
            "te voy a enseñar",
            "cuando diga"
        ]

        return any(
            pattern in text
            for pattern in patterns
        )

    # =========================================================
    # EXTRAER FRASE + ACCIÓN
    # =========================================================

    def parse_learning_request(self, text):

        original = text.strip()

        text = original.lower()

        # -----------------------------------------------------
        # FORMATO:
        #
        # cuando diga "trabajo" quiero que abras chrome
        # -----------------------------------------------------

        pattern = re.search(
            r'cuando\s+(?:diga|digo)\s+["“]?(.+?)["”]?\s+'
            r'(?:quiero\s+que|quiero|debes|haz)\s+(.+)',
            text,
            re.IGNORECASE
        )

        if pattern:

            phrase = pattern.group(1).strip()

            action = pattern.group(2).strip()

            phrase = self._clean_phrase(
                phrase
            )

            action = self._clean_action(
                action
            )

            if phrase and action:

                return {
                    "phrase": phrase,
                    "action": action
                }

        # -----------------------------------------------------
        # FORMATO:
        #
        # aprende que cuando diga trabajo abre chrome
        # -----------------------------------------------------

        pattern = re.search(
            r'aprende\s+que\s+cuando\s+'
            r'(?:diga|digo)\s+["“]?(.+?)["”]?\s+'
            r'(?:quiero\s+que|quiero|debes|haz)\s+(.+)',
            text,
            re.IGNORECASE
        )

        if pattern:

            phrase = pattern.group(1).strip()

            action = pattern.group(2).strip()

            phrase = self._clean_phrase(
                phrase
            )

            action = self._clean_action(
                action
            )

            if phrase and action:

                return {
                    "phrase": phrase,
                    "action": action
                }

        return None

    # =========================================================
    # LIMPIAR FRASE
    # =========================================================

    def _clean_phrase(self, phrase):

        phrase = phrase.strip()

        phrase = phrase.strip(
            "\"'“”"
        )

        phrase = phrase.strip()

        return phrase

    # =========================================================
    # LIMPIAR ACCIÓN
    # =========================================================

    def _clean_action(self, action):

        action = action.strip()

        action = action.rstrip(
            ".!?¿¡"
        )

        return action

    # =========================================================
    # GUARDAR APRENDIZAJE
    # =========================================================

    def teach(
        self,
        phrase,
        intent,
        target="",
        confidence=1.0
    ):

        phrase = self._clean_phrase(
            phrase
        )

        if not phrase:

            return False

        return self.learning.learn_command(
            phrase=phrase,
            intent=intent,
            target=target,
            confidence=confidence
        )

    # =========================================================
    # RECORDAR
    # =========================================================

    def remember(self, phrase):

        return self.learning.find_command(
            phrase
        )

    # =========================================================
    # OLVIDAR
    # =========================================================

    def forget(self, phrase):

        return self.learning.forget_command(
            phrase
        )

    # =========================================================
    # CONTAR APRENDIZAJES
    # =========================================================

    def count(self):

        return self.learning.count_commands()