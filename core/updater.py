import os
import re
import shutil
import tempfile
import zipfile

import requests


class Updater:
    """
    Revisa, descarga e instala actualizaciones de Cortana publicadas
    como "Releases" en un repositorio de GitHub.

    Cómo funciona:
    1. Lee la versión actual desde el archivo VERSION en la raíz
       del proyecto.
    2. Pregunta a la API de GitHub cuál es el último release
       publicado en el repositorio configurado.
    3. Si la versión del release es más nueva, descarga el código
       fuente de ese release (GitHub lo genera automáticamente,
       no hay que subir nada manualmente) y lo copia encima del
       proyecto actual.
    4. Actualiza el archivo VERSION local.

    IMPORTANTE: en tu repositorio de GitHub, agrega un .gitignore
    que excluya la carpeta data/ (o al menos los .json con datos
    reales), para que una actualización nunca sobreescriba tu
    memoria, tus comandos aprendidos, ni tu caché de programas.
    """

    # =====================================================
    # AJUSTA ESTO CON TU REPOSITORIO REAL
    # Formato: "usuario/nombre-del-repo"
    # =====================================================
    GITHUB_REPO = "LinkSing12/cortana-ia"

    def __init__(self, project_root=None, version_file=None):

        self.project_root = project_root or os.getcwd()

        self.version_file = version_file or os.path.join(
            self.project_root, "VERSION"
        )

        self.api_url = (
            f"https://api.github.com/repos/{self.GITHUB_REPO}/releases/latest"
        )

    # =========================================================
    # VERSIÓN LOCAL
    # =========================================================
    def get_local_version(self):
        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return "0.0.0"

    def set_local_version(self, version):
        try:
            with open(self.version_file, "w", encoding="utf-8") as f:
                f.write(str(version).strip())
            return True
        except Exception as error:
            print("ERROR GUARDANDO VERSION LOCAL:", error)
            return False

    def _parse_version(self, value):
        value = str(value).strip().lstrip("vV")
        parts = re.split(r"[.\-]", value)
        numbers = []
        for part in parts:
            if part.isdigit():
                numbers.append(int(part))
            else:
                break
        return tuple(numbers) if numbers else (0,)

    # =========================================================
    # CHEQUEAR ACTUALIZACIONES
    # =========================================================
    def check_for_update(self, timeout=5):
        """
        Devuelve un dict:
        {
            "available": bool,
            "current_version": str,
            "latest_version": str,
            "download_url": str,   # zip fuente del release
            "changelog": str,
        }
        o None si no se pudo consultar (sin internet, repo mal
        configurado, GitHub caído, etc.)
        """

        if self.GITHUB_REPO == "TU_USUARIO/TU_REPO":
            print(
                "⚠️ ACTUALIZADOR: todavía no configuraste GITHUB_REPO "
                "en core/updater.py."
            )
            return None

        try:
            response = requests.get(self.api_url, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as error:
            print("ERROR CONSULTANDO ACTUALIZACIONES:", error)
            return None

        current_version = self.get_local_version()
        latest_tag = data.get("tag_name", "0.0.0")

        available = self._parse_version(latest_tag) > self._parse_version(
            current_version
        )

        return {
            "available": available,
            "current_version": current_version,
            "latest_version": latest_tag,
            "download_url": data.get("zipball_url", ""),
            "changelog": data.get("body", "") or "",
        }

    # =========================================================
    # DESCARGAR
    # =========================================================
    def download_update(self, download_url, timeout=30):
        if not download_url:
            raise ValueError("No hay URL de descarga.")

        response = requests.get(download_url, timeout=timeout, stream=True)
        response.raise_for_status()

        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")

        with os.fdopen(temp_fd, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return temp_path

    # =========================================================
    # APLICAR
    # =========================================================
    def apply_update(self, zip_path):

        extract_dir = tempfile.mkdtemp(prefix="cortana_update_")

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # El zip que genera GitHub trae todo dentro de una sola
            # carpeta raíz (ej. "usuario-repo-a1b2c3d"). Hay que
            # entrar ahí antes de copiar.
            entries = os.listdir(extract_dir)

            if (
                len(entries) == 1
                and os.path.isdir(os.path.join(extract_dir, entries[0]))
            ):
                source_root = os.path.join(extract_dir, entries[0])
            else:
                source_root = extract_dir

            self._merge_copy_dir(source_root, self.project_root)

            return True

        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)
            try:
                os.remove(zip_path)
            except Exception:
                pass

    def _merge_copy_dir(self, src_dir, dst_dir):
        os.makedirs(dst_dir, exist_ok=True)

        for item in os.listdir(src_dir):

            src = os.path.join(src_dir, item)
            dst = os.path.join(dst_dir, item)

            if os.path.isdir(src):
                self._merge_copy_dir(src, dst)
            else:
                try:
                    shutil.copy2(src, dst)
                except Exception as error:
                    print(f"ERROR COPIANDO {item}:", error)

    # =========================================================
    # TODO EN UNO
    # =========================================================
    def check_download_and_apply(self):
        """
        Hace todo el proceso de una vez. Devuelve un mensaje de
        texto listo para que Cortana lo diga en voz alta.
        """

        info = self.check_for_update()

        if info is None:
            return "No pude comprobar si hay actualizaciones ahora mismo."

        if not info["available"]:
            return f"Ya tienes la versión más reciente, la {info['current_version']}."

        print(
            f"Actualización disponible: {info['current_version']} -> "
            f"{info['latest_version']}"
        )

        try:
            zip_path = self.download_update(info["download_url"])
            self.apply_update(zip_path)
            self.set_local_version(info["latest_version"])

            return (
                f"Actualicé Cortana de la versión {info['current_version']} "
                f"a la {info['latest_version']}. Reinicia el programa para "
                "que tome efecto."
            )

        except Exception as error:
            print("ERROR APLICANDO ACTUALIZACIÓN:", error)
            return "Encontré una actualización, pero no pude instalarla."