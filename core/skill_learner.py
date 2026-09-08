import os
import re
import json
import difflib
import importlib.util
import ast
from datetime import datetime

from core.web_search import WebSearch


class SkillLearner:
    """
    Sistema de auto-aprendizaje de CORTANA.

    Flujo:

    1. Investiga cómo realizar una tarea.
    2. Genera código Python con el cerebro local.
    3. Valida el código.
    4. Muestra el código para revisión.
    5. Espera confirmación del usuario.
    6. Guarda la habilidad.
    7. La carga dinámicamente.
    8. La ejecuta.
    9. La registra para reutilizarla posteriormente.
    """

    def __init__(self, brain, skills_file=None, registry_file=None):

        self.brain = brain
        self.web_search = WebSearch()

        if skills_file is None:
            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            skills_file = os.path.join(
                base_dir,
                "core",
                "learned_skills.py"
            )

        if registry_file is None:
            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            registry_file = os.path.join(
                base_dir,
                "data",
                "learned_skills.json"
            )

        self.skills_file = skills_file
        self.registry_file = registry_file

        self._ensure_skills_file()
        self._ensure_registry_file()

    # =========================================================
    # PREPARAR ARCHIVOS
    # =========================================================

    def _ensure_skills_file(self):

        directory = os.path.dirname(
            self.skills_file
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        if not os.path.exists(
            self.skills_file
        ):

            with open(
                self.skills_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    '"""\n'
                    'Habilidades aprendidas automáticamente por CORTANA.\n'
                    'Este archivo es administrado por SkillLearner.\n'
                    '"""\n\n'
                    "import os\n"
                    "import re\n"
                    "import subprocess\n"
                    "import webbrowser\n"
                    "import requests\n"
                    "import time\n"
                    "import json\n\n"
                )

    def _ensure_registry_file(self):

        directory = os.path.dirname(
            self.registry_file
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        if not os.path.exists(
            self.registry_file
        ):

            with open(
                self.registry_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    {},
                    f,
                    ensure_ascii=False,
                    indent=4
                )

    # =========================================================
    # REGISTRO
    # =========================================================

    def _read_registry(self):

        try:

            with open(
                self.registry_file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            if isinstance(data, dict):
                return data

        except Exception as error:

            print(
                "ERROR LEYENDO REGISTRO:",
                error
            )

        return {}

    def _write_registry(self, data):

        directory = os.path.dirname(
            self.registry_file
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        temp_file = (
            self.registry_file
            + ".tmp"
        )

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

        os.replace(
            temp_file,
            self.registry_file
        )

    # =========================================================
    # NORMALIZAR TEXTO
    # =========================================================

    def normalize(self, text):

        text = str(text)

        text = text.lower().strip()

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text

    # =========================================================
    # BUSCAR HABILIDAD EXISTENTE
    # =========================================================

    def find_existing(self, description):

        normalized = self.normalize(
            description
        )

        registry = self._read_registry()

        if not registry:
            return None

        # Coincidencia exacta
        if normalized in registry:

            entry = registry[
                normalized
            ]

            if isinstance(entry, dict):
                return entry.get(
                    "function"
                )

        # Coincidencia aproximada
        close = difflib.get_close_matches(
            normalized,
            list(registry.keys()),
            n=1,
            cutoff=0.78
        )

        if close:

            entry = registry[
                close[0]
            ]

            if isinstance(entry, dict):
                return entry.get(
                    "function"
                )

        return None

    # =========================================================
    # INVESTIGAR
    # =========================================================

    def research(self, description):

        query = (
            "cómo hacer en Python en Windows: "
            + description
        )

        results = self.web_search.search(
            query
        )

        return self.web_search.format_results(
            results
        )

    # =========================================================
    # NOMBRE SEGURO DE FUNCIÓN
    # =========================================================

    def _make_function_name(self, description):

        normalized = self.normalize(
            description
        )

        safe_name = re.sub(
            r"[^a-z0-9_]",
            "_",
            normalized
        )

        safe_name = re.sub(
            r"_+",
            "_",
            safe_name
        )

        safe_name = safe_name.strip(
            "_"
        )

        safe_name = safe_name[:45]

        if not safe_name:

            safe_name = "generica"

        function_name = (
            "skill_"
            + safe_name
        )

        return function_name

    # =========================================================
    # GENERAR CÓDIGO
    # =========================================================

    def generate_code(
        self,
        description,
        research_text,
        function_name
    ):

        prompt = f"""
Eres el generador de habilidades de CORTANA.

CORTANA es un asistente local para Windows.

PETICIÓN DEL USUARIO:
"{description}"

INFORMACIÓN DE INVESTIGACIÓN:
{research_text}

Debes generar UNA función Python.

REQUISITOS:

1. La función debe llamarse exactamente:

{function_name}

2. Debe recibir:

target=""

3. Debe devolver SIEMPRE un texto en español.

4. El texto será leído por CORTANA mediante voz.

5. Puedes utilizar estas librerías:

os
re
subprocess
webbrowser
requests
time
json

6. No utilices input().

7. No utilices código interactivo.

8. No crees ventanas Tkinter.

9. No ejecutes código recibido directamente desde internet.

10. No utilices eval().

11. No utilices exec().

12. No descargues ni ejecutes archivos .exe.

13. No borres archivos personales.

14. No apagues ni reinicies Windows.

15. No modifiques el registro de Windows.

16. Utiliza try/except.

17. Si algo falla, devuelve un mensaje en español.

18. Devuelve SOLO código Python.

19. No uses markdown.

20. No escribas explicaciones.

La salida debe contener solamente:

def {function_name}(target=""):
    ...

"""

        raw = self.brain.generate(
            prompt
        )

        return self._clean_code(
            raw
        )

    # =========================================================
    # LIMPIAR CÓDIGO
    # =========================================================

    def _clean_code(self, raw):

        if raw is None:
            return ""

        code = str(raw).strip()

        code = re.sub(
            r"^```python\s*",
            "",
            code,
            flags=re.IGNORECASE
        )

        code = re.sub(
            r"^```\s*",
            "",
            code
        )

        code = re.sub(
            r"\s*```$",
            "",
            code
        )

        code = code.strip()

        # Si el modelo añadió texto antes de def,
        # intentamos quedarnos desde la primera función.
        match = re.search(
            r"\bdef\s+skill_[a-zA-Z0-9_]+\s*\(",
            code
        )

        if match:

            code = code[
                match.start():
            ]

        return code.strip()

    # =========================================================
    # VALIDAR SINTAXIS
    # =========================================================

    def validate_syntax(self, code):

        try:

            tree = ast.parse(
                code
            )

            functions = [
                node
                for node in tree.body
                if isinstance(
                    node,
                    ast.FunctionDef
                )
            ]

            if not functions:

                return (
                    False,
                    "No se encontró ninguna función."
                )

            if len(functions) != 1:

                return (
                    False,
                    "La habilidad debe contener una sola función."
                )

            return True, None

        except SyntaxError as error:

            return (
                False,
                str(error)
            )

        except Exception as error:

            return (
                False,
                str(error)
            )

    # =========================================================
    # VALIDAR SEGURIDAD
    # =========================================================

    def validate_safety(self, code):

        dangerous_patterns = {

            "eval(": "eval()",
            "exec(": "exec()",
            "os.remove(": "borrado de archivos",
            "os.unlink(": "borrado de archivos",
            "shutil.rmtree(": "borrado de carpetas",
            "winreg": "modificación del registro",
            "shutdown ": "apagado del sistema",
            "shutdown(": "apagado del sistema",
            "os.system(": "comandos directos del sistema",
        }

        code_lower = code.lower()

        for pattern, description in dangerous_patterns.items():

            if pattern.lower() in code_lower:

                return (
                    False,
                    description
                )

        return True, None

    # =========================================================
    # GUARDAR HABILIDAD
    # =========================================================

    def save_skill(
        self,
        function_name,
        code,
        description
    ):

        directory = os.path.dirname(
            self.skills_file
        )

        if directory:

            os.makedirs(
                directory,
                exist_ok=True
            )

        with open(
            self.skills_file,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                "\n\n"
            )

            f.write(
                "# =====================================================\n"
            )

            f.write(
                "# HABILIDAD APRENDIDA\n"
            )

            f.write(
                "# =====================================================\n"
            )

            f.write(
                f"# Descripción: {description}\n"
            )

            f.write(
                "# Fecha: "
                + datetime.now().isoformat(
                    timespec="seconds"
                )
                + "\n"
            )

            f.write(
                code.strip()
                + "\n"
            )

        registry = self._read_registry()

        registry[
            self.normalize(description)
        ] = {

            "function": function_name,

            "description": description,

            "learned_at":
                datetime.now().isoformat(
                    timespec="seconds"
                )
        }

        self._write_registry(
            registry
        )

    # =========================================================
    # CARGAR HABILIDADES
    # =========================================================

    def _load_skills_module(self):

        module_name = (
            "cortana_learned_skills"
        )

        spec = (
            importlib.util
            .spec_from_file_location(
                module_name,
                self.skills_file
            )
        )

        if spec is None:
            raise ImportError(
                "No pude crear el módulo."
            )

        if spec.loader is None:
            raise ImportError(
                "No pude cargar el módulo."
            )

        module = (
            importlib.util
            .module_from_spec(
                spec
            )
        )

        spec.loader.exec_module(
            module
        )

        return module

    # =========================================================
    # EJECUTAR HABILIDAD
    # =========================================================

    def run_skill(
        self,
        function_name,
        target=""
    ):

        try:

            module = (
                self._load_skills_module()
            )

        except Exception as error:

            return (
                "No pude cargar las habilidades "
                f"aprendidas: {error}"
            )

        func = getattr(
            module,
            function_name,
            None
        )

        if not func:

            return (
                "No encontré la función "
                f"{function_name}."
            )

        try:

            result = func(
                target
            )

            if result is None:

                return (
                    "La habilidad terminó "
                    "sin devolver una respuesta."
                )

            return str(
                result
            )

        except Exception as error:

            return (
                "La habilidad aprendida "
                f"falló al ejecutarse: {error}"
            )

    # =========================================================
    # RESUMEN
    # =========================================================

    def summarize_code(
        self,
        code,
        description
    ):

        risky_signals = {

            "subprocess":
                "puede ejecutar comandos de Windows",

            "webbrowser":
                "puede abrir páginas web",

            "requests.get":
                "puede consultar internet",

            "requests.post":
                "puede enviar información a internet",

            "requests.put":
                "puede enviar información a internet",

            "requests.delete":
                "puede eliminar información mediante internet",

        }

        found = []

        for signal, message in risky_signals.items():

            if signal in code:

                found.append(
                    message
                )

        summary = (
            "Generé una función para: "
            + description
            + "."
        )

        if found:

            summary += (
                " El código "
                + ", y ".join(found)
                + "."
            )

        return summary

    # =========================================================
    # PREPARAR HABILIDAD
    # =========================================================

    def prepare_skill(
        self,
        description,
        target=""
    ):

        function_name = (
            self._make_function_name(
                description
            )
        )

        print()
        print(
            "APRENDIZAJE: investigando ->",
            description
        )

        # -----------------------------------------------------
        # INVESTIGACIÓN
        # -----------------------------------------------------

        try:

            research_text = self.research(
                description
            )

        except Exception as error:

            print(
                "APRENDIZAJE: error investigando ->",
                error
            )

            research_text = ""

        # -----------------------------------------------------
        # GENERACIÓN
        # -----------------------------------------------------

        print(
            "APRENDIZAJE: generando código ->",
            function_name
        )

        try:

            code = self.generate_code(
                description,
                research_text,
                function_name
            )

        except Exception as error:

            print(
                "APRENDIZAJE: error generando código ->",
                error
            )

            return (
                None,
                "No pude generar una forma de hacer eso."
            )

        if not code:

            return (
                None,
                "No pude generar una habilidad."
            )

        if "def " not in code:

            return (
                None,
                "El cerebro no generó una función válida."
            )

        # -----------------------------------------------------
        # SINTAXIS
        # -----------------------------------------------------

        valid, syntax_error = (
            self.validate_syntax(
                code
            )
        )

        if not valid:

            print(
                "APRENDIZAJE: código inválido ->",
                syntax_error
            )

            return (
                None,
                "El código generado tiene errores de sintaxis."
            )

        # -----------------------------------------------------
        # SEGURIDAD
        # -----------------------------------------------------

        safe, safety_error = (
            self.validate_safety(
                code
            )
        )

        if not safe:

            print(
                "APRENDIZAJE: código bloqueado ->",
                safety_error
            )

            return (
                None,
                "Bloqueé el código porque contiene una "
                "acción potencialmente peligrosa."
            )

        # -----------------------------------------------------
        # MOSTRAR CÓDIGO
        # -----------------------------------------------------

        print()
        print(
            "=" * 60
        )

        print(
            "CÓDIGO GENERADO:"
        )

        print(
            "=" * 60
        )

        print(
            code
        )

        print(
            "=" * 60
        )

        # -----------------------------------------------------
        # PREPARAR
        # -----------------------------------------------------

        prepared = {

            "function_name":
                function_name,

            "code":
                code,

            "description":
                description,

            "target":
                target,

            "created_at":
                datetime.now().isoformat(
                    timespec="seconds"
                )
        }

        summary = (
            self.summarize_code(
                code,
                description
            )
        )

        return (
            prepared,
            summary
        )

    # =========================================================
    # CONFIRMAR + GUARDAR + EJECUTAR
    # =========================================================

    def confirm_and_save(
        self,
        prepared
    ):

        if not prepared:

            return (
                "No hay ninguna habilidad pendiente."
            )

        function_name = prepared.get(
            "function_name"
        )

        code = prepared.get(
            "code"
        )

        description = prepared.get(
            "description"
        )

        target = prepared.get(
            "target",
            ""
        )

        if not function_name or not code:

            return (
                "La habilidad pendiente no es válida."
            )

        # -----------------------------------------------------
        # VALIDACIÓN FINAL
        # -----------------------------------------------------

        valid, error = (
            self.validate_syntax(
                code
            )
        )

        if not valid:

            return (
                "No guardé la habilidad porque "
                f"el código tiene errores: {error}"
            )

        safe, safety_error = (
            self.validate_safety(
                code
            )
        )

        if not safe:

            return (
                "No guardé la habilidad porque "
                f"fue bloqueada: {safety_error}"
            )

        # -----------------------------------------------------
        # GUARDAR
        # -----------------------------------------------------

        try:

            self.save_skill(
                function_name,
                code,
                description
            )

        except Exception as error:

            return (
                "No pude guardar la habilidad: "
                f"{error}"
            )

        print()
        print(
            "APRENDIZAJE: habilidad guardada."
        )

        # -----------------------------------------------------
        # EJECUTAR
        # -----------------------------------------------------

        print(
            "APRENDIZAJE: ejecutando..."
        )

        return self.run_skill(
            function_name,
            target
        )

    # =========================================================
    # FLUJO DIRECTO
    # =========================================================

    def learn_and_run(
        self,
        description,
        target=""
    ):

        prepared, message = (
            self.prepare_skill(
                description,
                target
            )
        )

        if not prepared:

            return message

        return self.confirm_and_save(
            prepared
        )