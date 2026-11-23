"""
Motor de IA local: llama.cpp (llama-server) en la tarjeta de video.

Reemplaza a Ollama, que en esta PC se caía con "instrucción ilegal"
(0xC000001D) en cada petición. llama.cpp elige una versión optimizada
según el procesador, y en este equipo la que elegía también fallaba; por
eso en engines/llama.cpp solo se deja ggml-cpu-haswell.dll (AVX2), que
funciona en cualquier CPU moderna. El trabajo pesado va en la GPU.

Archivos (no se suben a git, ver .gitignore):
    engines/llama.cpp/llama-server.exe   -> el motor
    engines/models/*.gguf                -> modelo propio (opcional)
Si no hay modelo propio, usa el qwen2.5:7b que ya descargó Ollama.
"""

import glob
import json
import os
import subprocess
import threading
import time

import requests


class LlamaEngine:

    PORT = 11436
    PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SERVER = os.path.join(PROJECT, "engines", "llama.cpp", "llama-server.exe")
    MODELS = os.path.join(PROJECT, "engines", "models")
    OLLAMA_MODEL = ("qwen2.5", "7b")

    def __init__(self):
        self.base_url = f"http://127.0.0.1:{self.PORT}"
        self._lock = threading.Lock()
        self._process = None

    # =========================================================
    # ARRANQUE
    # =========================================================

    def installed(self):
        return os.path.isfile(self.SERVER) and self.model_path() is not None

    def model_path(self):
        own = sorted(glob.glob(os.path.join(self.MODELS, "*.gguf")))
        if own:
            return own[0]

        name, tag = self.OLLAMA_MODEL
        ollama = os.path.join(os.path.expanduser("~"), ".ollama", "models")
        manifest = os.path.join(
            ollama, "manifests", "registry.ollama.ai", "library", name, tag
        )
        try:
            with open(manifest, "r", encoding="utf-8") as file:
                layers = json.load(file).get("layers", [])
        except (OSError, json.JSONDecodeError):
            return None

        for layer in layers:
            if str(layer.get("mediaType", "")).endswith(".model"):
                blob = os.path.join(
                    ollama, "blobs", layer["digest"].replace(":", "-")
                )
                return blob if os.path.isfile(blob) else None
        return None

    def is_ready(self, timeout=0.5):
        try:
            response = requests.get(self.base_url + "/health", timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False

    def start(self, wait_seconds=60):
        """Arranca el motor si no está corriendo. Devuelve True si quedó listo."""
        with self._lock:
            if self.is_ready():
                return True
            if not self.installed():
                return False

            if self._process is None or self._process.poll() is not None:
                print("🧠 INICIANDO MOTOR DE IA (llama.cpp en la GPU)...")
                self._process = subprocess.Popen(
                    [
                        self.SERVER,
                        "-m", self.model_path(),
                        "--host", "127.0.0.1",
                        "--port", str(self.PORT),
                        "-ngl", "99",        # todo el modelo en la GPU
                        "-c", "8192",
                        "--parallel", "1",
                    ],
                    cwd=os.path.dirname(self.SERVER),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )

            deadline = time.time() + wait_seconds
            while time.time() < deadline:
                if self.is_ready():
                    print("✅ MOTOR DE IA LISTO.")
                    return True
                if self._process.poll() is not None:
                    print(
                        "⚠️ El motor de IA se cerró al arrancar "
                        f"(código {self._process.returncode})."
                    )
                    return False
                time.sleep(0.3)
            return False

    def start_in_background(self):
        threading.Thread(target=self.start, daemon=True).start()

    # =========================================================
    # PREGUNTAR
    # =========================================================

    def complete(self, prompt, temperature=None, timeout=60):
        """
        Mismo uso que /api/generate de Ollama: el texto va como mensaje
        del usuario y el motor aplica la plantilla de chat del modelo.
        """
        if not self.is_ready() and not self.start():
            raise RuntimeError("el motor de IA no está disponible")

        payload = {"messages": [{"role": "user", "content": prompt}]}
        if temperature is not None:
            payload["temperature"] = temperature

        response = requests.post(
            self.base_url + "/v1/chat/completions",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
