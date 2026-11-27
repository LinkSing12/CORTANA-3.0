"""
Detecta la palabra "eco" en la PC, sin internet.

Mientras Eco está en modo pasivo, cada frase que capta el micrófono
(música, conversaciones, la tele) se mandaba a Google solo para saber
si empezaba con "eco". Ahora la revisa primero un reconocedor local
(Vosk) que solo distingue unas pocas palabras: "eco" y los controles
rápidos ("pausa", "siguiente"...). Si no oye ninguna, la frase se
descarta al momento y no se envía nada.

Es opcional: si falta el paquete "vosk" o el modelo en
data/vosk_model, Eco funciona como antes (todo pasa por Google).
"""

import json
import os
import re
import unicodedata

try:
    import vosk
except Exception:
    vosk = None


MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "vosk_model",
)

SAMPLE_RATE = 16000

WAKE_WORDS = ("eco", "echo", "eko", "ecos")

# Órdenes que funcionan sin decir "eco" (ver INSTANT_MEDIA_COMMANDS en
# core/assistant.py). Si Vosk oye una de estas, la frase sí va a Google.
INSTANT_WORDS = (
    "pausa", "pausar", "ponlo", "siguiente", "anterior", "vuelve",
    "pasa", "reanuda", "reanudar", "continúa", "continua", "sigue",
    "reproduce", "reproducir",
)


def _plain(word):
    word = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in word if unicodedata.category(c) != "Mn")


class WakeWordDetector:

    def __init__(self, model_dir=MODEL_DIR):
        self.available = False
        self._model = None

        if vosk is None:
            print("Info: falta 'vosk'; la palabra 'eco' se detecta con Google.")
            return
        if not os.path.isdir(model_dir):
            print("Info: falta data/vosk_model; la palabra 'eco' se detecta con Google.")
            return

        try:
            vosk.SetLogLevel(-1)
            self._model = vosk.Model(model_dir)
        except Exception as error:
            print("⚠️ No pude cargar el detector local de 'eco':", error)
            return

        words = list(WAKE_WORDS + INSTANT_WORDS)
        self._grammar = json.dumps(words + ["[unk]"], ensure_ascii=False)
        self._wake = {_plain(w) for w in WAKE_WORDS}
        self._instant = {_plain(w) for w in INSTANT_WORDS}
        self.available = True
        print("✅ DETECTOR LOCAL DE 'ECO' LISTO (sin internet)")

    def words_in(self, pcm16):
        """Palabras de la gramática que Vosk oyó en un audio de 16 kHz."""
        recognizer = vosk.KaldiRecognizer(self._model, SAMPLE_RATE, self._grammar)
        recognizer.AcceptWaveform(pcm16)
        text = json.loads(recognizer.FinalResult()).get("text", "")
        return [_plain(w) for w in re.findall(r"[^\s\[\]]+", text) if w != "unk"]

    def check(self, audio):
        """
        Devuelve (oyó_eco, oyó_orden_rápida) para un sr.AudioData.
        Si algo falla, responde (True, True) para no perder la orden.
        """
        if not self.available:
            return True, True
        try:
            pcm = audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)
            words = set(self.words_in(pcm))
        except Exception as error:
            print("⚠️ Detector local de 'eco':", error)
            return True, True
        return bool(words & self._wake), bool(words & self._instant)
