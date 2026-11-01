"""
Baja la música de las demás apps mientras Eco te escucha, sin tocar el
volumen general ni la voz de Eco, y luego la deja como estaba.

El volumen de cada app queda guardado por Windows. Por eso los valores
originales se anotan en data/ducked_volumes.json: si Eco se cierra de
golpe con la música bajada, al abrir de nuevo los devuelve.

Requiere: pip install pycaw (sin él, simplemente no baja la música).
"""

import json
import os

try:
    import comtypes
    from pycaw.pycaw import AudioUtilities
except Exception:
    comtypes = None
    AudioUtilities = None


class AudioDucker:

    LEVEL = 0.2  # la música queda al 20% de su volumen actual
    ACTIVE_STATE = 1

    def __init__(self, file_path=None):
        self.file_path = file_path or os.path.join("data", "ducked_volumes.json")
        self._saved = {}
        self._restore_leftovers()

    @property
    def ducked(self):
        return bool(self._saved)

    def _sessions(self):
        comtypes.CoInitialize()
        for session in AudioUtilities.GetAllSessions():
            process = session.Process
            if process and process.pid != os.getpid():
                yield process.name(), session

    def duck(self):
        if AudioUtilities is None or self._saved:
            return

        try:
            for name, session in self._sessions():
                if session.State != self.ACTIVE_STATE:
                    continue
                volume = session.SimpleAudioVolume
                current = volume.GetMasterVolume()
                self._saved.setdefault(name, current)
                volume.SetMasterVolume(current * self.LEVEL, None)
            self._write()
        except Exception as error:
            print("ERROR BAJANDO LA MÚSICA:", error)

    def restore(self):
        if AudioUtilities is None or not self._saved:
            return

        try:
            for name, session in self._sessions():
                if name in self._saved:
                    session.SimpleAudioVolume.SetMasterVolume(
                        self._saved[name], None
                    )
        except Exception as error:
            print("ERROR RESTAURANDO LA MÚSICA:", error)

        self._saved = {}
        self._write()

    def _write(self):
        try:
            if self._saved:
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                with open(self.file_path, "w", encoding="utf-8") as file:
                    json.dump(self._saved, file, ensure_ascii=False)
            elif os.path.exists(self.file_path):
                os.remove(self.file_path)
        except OSError as error:
            print("ERROR GUARDANDO VOLÚMENES:", error)

    def _restore_leftovers(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                self._saved = json.load(file)
        except (OSError, json.JSONDecodeError):
            return
        self.restore()
