"""Aliases y rutinas locales configurables por el usuario."""

import json
import os
from datetime import datetime


class CommandCatalog:
    def __init__(self, file_path=None):
        self.file_path = file_path or os.path.join("data", "command_catalog.json")
        self._ensure_storage()

    def _ensure_storage(self):
        directory = os.path.dirname(self.file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write({"aliases": {}, "routines": {}})

    def _read(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                data.setdefault("aliases", {})
                data.setdefault("routines", {})
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"aliases": {}, "routines": {}}

    def _write(self, data):
        temporary = self.file_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary, self.file_path)

    @staticmethod
    def normalize(value):
        return " ".join(str(value).lower().strip().split())

    def add_alias(self, alias, command):
        alias = self.normalize(alias)
        command = str(command).strip()
        if not alias or not command:
            return False
        data = self._read()
        data["aliases"][alias] = {
            "command": command,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write(data)
        return True

    def resolve_alias(self, text):
        entry = self._read()["aliases"].get(self.normalize(text))
        return entry.get("command") if isinstance(entry, dict) else None

    def add_routine(self, name, actions):
        name = self.normalize(name)
        actions = [str(action).strip() for action in actions if str(action).strip()]
        if not name or not actions:
            return False
        data = self._read()
        data["routines"][name] = {
            "actions": actions,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write(data)
        return True

    def get_routine(self, name):
        entry = self._read()["routines"].get(self.normalize(name))
        return entry.get("actions") if isinstance(entry, dict) else None

    def list_items(self):
        data = self._read()
        return {
            "aliases": sorted(data["aliases"].keys()),
            "routines": sorted(data["routines"].keys()),
        }
