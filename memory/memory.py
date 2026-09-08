import json
import os
from datetime import datetime


class Memory:

    def __init__(self, data_file=None):

        if data_file is None:
            data_file = os.path.join(
                "data",
                "memory.json"
            )

        self.data_file = data_file

        self._ensure_storage()

    # =========================================================
    # PREPARAR ARCHIVO
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

            self._write({
                "conversations": [],
                "context": {}
            })

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

            if not isinstance(data, dict):
                return {
                    "conversations": [],
                    "context": {}
                }

            if "conversations" not in data:
                data["conversations"] = []

            if "context" not in data:
                data["context"] = {}

            return data

        except (
            FileNotFoundError,
            json.JSONDecodeError,
            OSError
        ):

            return {
                "conversations": [],
                "context": {}
            }

    # =========================================================
    # ESCRIBIR
    # =========================================================

    def _write(self, data):

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
    # GUARDAR CONVERSACIÓN
    # =========================================================

    def save(
        self,
        user_text,
        assistant_response
    ):

        data = self._read()

        conversation = {

            "time":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "user":
                user_text,

            "assistant":
                assistant_response
        }

        data["conversations"].append(
            conversation
        )

        # Mantener las últimas 100
        data["conversations"] = (
            data["conversations"][-100:]
        )

        self._write(data)

    # =========================================================
    # GUARDAR CONTEXTO
    # =========================================================

    def set_context(
        self,
        key,
        value
    ):

        data = self._read()

        data["context"][key] = value

        self._write(data)

    # =========================================================
    # OBTENER CONTEXTO
    # =========================================================

    def get_context(
        self,
        key,
        default=None
    ):

        data = self._read()

        return data["context"].get(
            key,
            default
        )

    # =========================================================
    # BORRAR CONTEXTO
    # =========================================================

    def clear_context(self):

        data = self._read()

        data["context"] = {}

        self._write(data)

    # =========================================================
    # ÚLTIMA CONVERSACIÓN
    # =========================================================

    def last_conversation(self):

        data = self._read()

        conversations = (
            data.get(
                "conversations",
                []
            )
        )

        if not conversations:
            return None

        return conversations[-1]

    # =========================================================
    # HISTORIAL
    # =========================================================

    def get_history(
        self,
        amount=10
    ):

        data = self._read()

        return data.get(
            "conversations",
            []
        )[-amount:]