"""
ECO - resolvedor de comandos contextuales.
No genera ni ejecuta codigo Python.
"""
import re


class ContextCommandResolver:
    def __init__(self):
        self.patterns = [
            r"\b(repite|reproduce|reproducir|haz|hacer|ejecuta|ejecutar|abre|abrir|continua|continuar)\b.*\b(lo|el|eso|esto)\s+(anterior|mismo)\b",
            r"\b(haz|hacer|ejecuta|ejecutar|abre|abrir|repite|repetir)\s+(lo\s+)?mismo\b",
            r"\bvuelve\s+a\s+(hacerlo|ejecutarlo|reproducirlo|abrirlo)\b",
            r"\botra\s+vez\b",
            r"\bde\s+nuevo\b",
            r"\bguarda\s+y\s+ejecuta\s+lo\s+anterior\b",
        ]

    def _normalize(self, text):
        text = str(text or "").lower().strip()
        for old, new in {
            "á": "a", "é": "e", "í": "i",
            "ó": "o", "ú": "u", "ü": "u"
        }.items():
            text = text.replace(old, new)
        text = re.sub(r"[¿?¡!.,;:]+", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def is_context_command(self, text):
        text = self._normalize(text)
        return any(re.search(p, text) for p in self.patterns)

    def resolve(self, text, context):
        if not self.is_context_command(text):
            return None

        context = context or {}
        intent = str(context.get("last_intent", "UNKNOWN")).upper().strip()
        target = str(context.get("last_target", "")).strip()
        command = str(context.get("last_command", "")).strip()

        valid = {
            "OPEN_PROGRAM", "CLOSE_PROGRAM", "LIST_PROGRAMS",
            "CHECK_PROGRAM", "PROGRAM_INFO", "PLAY_MEDIA",
            "PAUSE_MEDIA", "RESUME_MEDIA", "STOP_MEDIA",
            "VOLUME_UP", "VOLUME_DOWN", "MUTE",
            "MEDIA_PLAY", "MEDIA_PAUSE", "MEDIA_NEXT",
            "MEDIA_PREVIOUS", "OPEN_URL", "SEARCH_GOOGLE",
            "GOOGLE_SEARCH", "SEARCH_WEB", "WEB_SEARCH",
            "SEARCH_YOUTUBE", "YOUTUBE_SEARCH", "PLAY_YOUTUBE",
            "OPEN_FILE",
        }

        if intent not in valid:
            return None

        return {
            "intent": intent,
            "target": target,
            "confidence": 1.0,
            "command": command,
            "context_reused": True,
        }
