"""
Pruebas automáticas de Eco. No usan micrófono, altavoces, internet
ni el motor de IA: solo la lógica que decide qué hacer.

Correrlas (en la carpeta del proyecto):
    .venv\\Scripts\\python.exe -m unittest discover tests -v
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.assistant import Eco
from core.reminders import ReminderManager, next_occurrence, parse_repeat
from core.skill_learner import SkillLearner
from core.web_search import WebSearch, is_spanish
from voice.listener import _ClampedRecognizer
from voice.speaker import Speaker
from windows.controller import WindowsController


def bare(cls):
    """Instancia sin __init__, para probar métodos sin abrir dispositivos."""
    return cls.__new__(cls)


class WakeWordTests(unittest.TestCase):

    def setUp(self):
        self.eco = bare(Eco)
        self.eco.WAKE_WORD_VARIANTS = (
            "eco", "ecko", "esco", "eko", "ecco", "hecko", "ehco", "equo",
            "heco", "echo", "keko", "gekko", "geko", "queco",
        )

    def test_eco_al_principio(self):
        self.assertEqual(self.eco._strip_wake_word("eco abre chrome"), "abre chrome")

    def test_saludo_y_variante(self):
        self.assertEqual(self.eco._strip_wake_word("oye ecko, qué hora es"), "qué hora es")

    def test_eco_al_final(self):
        self.assertEqual(self.eco._strip_wake_word("pausa la música eco"), "pausa la música")

    def test_solo_eco(self):
        self.assertEqual(self.eco._strip_wake_word("keko"), "")

    def test_sin_eco(self):
        self.assertIsNone(self.eco._strip_wake_word("qué bonito día"))

    def test_ordenes_rapidas_sin_eco(self):
        self.assertTrue(self.eco._is_instant_media_command("Pausa."))
        self.assertTrue(self.eco._is_instant_media_command("siguiente canción"))
        self.assertFalse(self.eco._is_instant_media_command("abre chrome"))


class ClockTests(unittest.TestCase):

    def test_hora_y_fecha(self):
        eco = bare(Eco)
        self.assertTrue(eco._clock_answer("qué hora es").startswith("Son las"))
        self.assertTrue(eco._clock_answer("¿qué día es hoy?").startswith("Hoy es"))
        self.assertIsNone(eco._clock_answer("qué hora es en japón"))


class ReminderTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.manager = ReminderManager(file_path=os.path.join(self.folder.name, "r.json"))

    def tearDown(self):
        self.folder.cleanup()

    def test_temporizador(self):
        intent, text = self.manager.handle("pon un temporizador de 10 minutos para la pasta")
        self.assertEqual(intent, "SET_TIMER")
        self.assertIn("10 minutos", text)
        self.assertIn("pasta", text)

    def test_alarma_diaria(self):
        intent, text = self.manager.handle("pon una alarma todos los días a las 7")
        self.assertEqual(intent, "SET_ALARM")
        self.assertIn("todos los días", text)
        item = self.manager.upcoming("alarm")[0]
        self.assertEqual(item["repeat"], [0, 1, 2, 3, 4, 5, 6])

    def test_alarma_se_reprograma(self):
        self.manager.handle("pon una alarma de lunes a viernes a las 6")
        item = self.manager.upcoming("alarm")[0]
        following = self.manager._reschedule(item)
        self.assertGreater(following["due"], item["due"])
        self.assertLess(datetime.fromtimestamp(following["due"]).weekday(), 5)

    def test_el_lunes_es_una_sola_vez(self):
        self.manager.handle("recuérdame el lunes a las 9 pagar la luz")
        item = self.manager.upcoming("reminder")[0]
        self.assertNotIn("repeat", item)
        self.assertEqual(item["message"], "pagar la luz")

    def test_pregunta_la_hora_si_falta(self):
        intent, _ = self.manager.handle("pon una alarma los fines de semana")
        self.assertEqual(intent, "ASK_REMINDER_TIME")
        intent, text = self.manager.handle("a las 10")
        self.assertEqual(intent, "SET_ALARM")
        self.assertIn("fines de semana", text)

    def test_repeticiones(self):
        self.assertEqual(parse_repeat("entre semana")[0], [0, 1, 2, 3, 4])
        self.assertEqual(parse_repeat("todos los lunes y jueves")[0], [0, 3])
        self.assertIsNone(parse_repeat("el lunes"))

    def test_proxima_fecha(self):
        friday_night = datetime(2026, 11, 27, 23, 0)
        moment = next_occurrence(7, 0, [0, 1, 2, 3, 4], friday_night)
        self.assertEqual(moment, datetime(2026, 11, 30, 7, 0))


class ProgramMatchTests(unittest.TestCase):

    def setUp(self):
        self.controller = bare(WindowsController)
        self.exe = r"E:\Dragon Ball Sparking ZERO\SparkingZERO.exe"

    def test_numero_dictado(self):
        self.assertGreaterEqual(self.controller._portable_game_score("sparking 0", self.exe), 60)

    def test_error_de_dictado(self):
        self.assertGreaterEqual(self.controller._portable_game_score("spain zero", self.exe), 60)

    def test_ignora_desinstalador(self):
        path = r"E:\Dragon Ball Sparking ZERO\unins000.exe"
        self.assertEqual(self.controller._portable_game_score("sparking zero", path), 0)

    def test_no_confunde_programas(self):
        self.assertLess(self.controller._portable_game_score("chrome", r"C:\x\Discord.exe"), 60)


class ListenerTests(unittest.TestCase):

    def test_umbral_limitado(self):
        recognizer = _ClampedRecognizer()
        recognizer.energy_threshold = 4876
        self.assertEqual(recognizer.energy_threshold, recognizer.max_threshold)
        recognizer.energy_threshold = 5
        self.assertEqual(recognizer.energy_threshold, recognizer.min_threshold)


class SpeechTextTests(unittest.TestCase):

    def test_no_lee_simbolos(self):
        speaker = bare(Speaker)
        text = speaker._sanitize_for_speech("© 2024 **Canción** — «éxito» #1")
        for symbol in "©*«»#—":
            self.assertNotIn(symbol, text)
        self.assertIn("éxito", text)


class SearchTests(unittest.TestCase):

    def test_detecta_espanol(self):
        self.assertTrue(is_spanish("La capital de Australia es Canberra, una ciudad planificada"))
        self.assertFalse(is_spanish("The capital of Australia is Canberra, a planned city"))

    def test_descarta_ingles_y_videos(self):
        search = bare(WebSearch)
        results = [
            {"title": "Capital of Australia", "body": "The capital of Australia is Canberra", "url": "https://a.com"},
            {"title": "Capital de Australia", "body": "La capital de Australia es Canberra", "url": "https://youtube.com/x"},
            {"title": "Canberra, capital de Australia", "body": "La capital de Australia es Canberra", "url": "https://b.com"},
        ]
        ranked = search.rank("cuál es la capital de australia", results)
        self.assertEqual([r["url"] for r in ranked], ["https://b.com"])


class SkillSafetyTests(unittest.TestCase):

    def setUp(self):
        self.learner = bare(SkillLearner)

    def test_bloquea_codigo_peligroso(self):
        for code in (
            "import os\nos.system('del x')",
            "x = getattr(__builtins__, 'ev' + 'al')",
            "import shutil\nshutil.rmtree('C:/')",
            "import subprocess\nsubprocess.run('cmd /c del x', shell=True)",
        ):
            safe, _ = self.learner.validate_safety(code)
            self.assertFalse(safe, code)

    def test_permite_codigo_normal(self):
        code = "import webbrowser\n\ndef run(command):\n    webbrowser.open('https://www.google.com')\n"
        safe, reason = self.learner.validate_safety(code)
        self.assertTrue(safe, reason)


if __name__ == "__main__":
    unittest.main()
