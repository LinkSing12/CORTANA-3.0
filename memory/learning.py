import json
import os
from datetime import datetime


class Learning:

    def __init__(self, data_file=None):

        if data_file is None:
            data_file = os.path.join(
                "data",
                "learned_commands.json"
            )

        self.data_file = data_file

        self._ensure_storage()

    # =========================================================
    # PREPARAR ALMACENAMIENTO
    # =========================================================

    def _ensure_storage(self):

        directory = os.path.dirname(
            self.data_file
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        if not os.path.exists(
            self.data_file
        ):
            self._write({})

    # =========================================================
    # LEER
    # =========================================================

    def _read(self):

        try:

            with open(
                self.data_file,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            if isinstance(data, dict):
                return data

            return {}

        except (
            FileNotFoundError,
            json.JSONDecodeError,
            OSError
        ):

            return {}

    # =========================================================
    # ESCRIBIR
    # =========================================================

    def _write(self, data):

        directory = os.path.dirname(
            self.data_file
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        temporary_file = (
            self.data_file + ".tmp"
        )

        with open(
            temporary_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4
            )

        os.replace(
            temporary_file,
            self.data_file
        )

    # =========================================================
    # NORMALIZAR
    # =========================================================

    def normalize(self, text):

        return " ".join(
            str(text)
            .lower()
            .strip()
            .split()
        )

    # =========================================================
    # APRENDER COMANDO
    # =========================================================

    def learn_command(
        self,
        phrase,
        intent,
        target="",
        confidence=1.0
    ):

        phrase = self.normalize(
            phrase
        )

        if not phrase:
            return False

        data = self._read()

        data[phrase] = {

            "type": "command",

            "intent": intent,

            "target": target,

            "confidence": float(
                confidence
            ),

            "learned_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "uses": 0
        }

        self._write(data)

        return True

    # =========================================================
    # BUSCAR COMANDO
    # =========================================================

    def find_command(self, phrase):

        phrase = self.normalize(
            phrase
        )

        data = self._read()

        command = data.get(
            phrase
        )

        if not isinstance(
            command,
            dict
        ):
            return None

        if command.get(
            "type"
        ) != "command":

            return None

        return command

    # =========================================================
    # REGISTRAR USO
    # =========================================================

    def register_use(self, phrase):

        phrase = self.normalize(
            phrase
        )

        data = self._read()

        command = data.get(
            phrase
        )

        if not isinstance(
            command,
            dict
        ):
            return False

        command["uses"] = (
            command.get(
                "uses",
                0
            ) + 1
        )

        command["last_used"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        self._write(data)

        return True

    # =========================================================
    # PREFERENCIAS
    # =========================================================

    def learn_preference(
        self,
        name,
        value
    ):

        name = self.normalize(
            name
        )

        if not name:
            return False

        data = self._read()

        if "__preferences__" not in data:

            data["__preferences__"] = {}

        data["__preferences__"][name] = {

            "value": value,

            "updated_at":
                datetime.now().isoformat(
                    timespec="seconds"
                )
        }

        self._write(data)

        return True

    # =========================================================
    # OBTENER PREFERENCIA
    # =========================================================

    def get_preference(
        self,
        name,
        default=None
    ):

        name = self.normalize(
            name
        )

        data = self._read()

        preferences = data.get(
            "__preferences__",
            {}
        )

        preference = preferences.get(
            name
        )

        if not isinstance(
            preference,
            dict
        ):
            return default

        return preference.get(
            "value",
            default
        )

    # =========================================================
    # OLVIDAR COMANDO
    # =========================================================

    def forget_command(
        self,
        phrase
    ):

        phrase = self.normalize(
            phrase
        )

        data = self._read()

        if phrase not in data:
            return False

        del data[phrase]

        self._write(data)

        return True

    # =========================================================
    # OBTENER TODO
    # =========================================================

    def get_all(self):

        return self._read()

    # =========================================================
    # CONTAR COMANDOS
    # =========================================================

    def count_commands(self):

        data = self._read()

        count = 0

        for key, value in data.items():

            if key == "__preferences__":
                continue

            if not isinstance(
                value,
                dict
            ):
                continue

            if value.get(
                "type"
            ) == "command":

                count += 1

        return count

    # =========================================================
    # BORRAR APRENDIZAJE
    # =========================================================

    def clear(self):

        self._write({})

        return True
