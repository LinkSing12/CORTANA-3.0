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
    Sistema de auto-aprendizaje de ECO.

    NOTA DE SEGURIDAD IMPORTANTE:
    Este sistema genera y ejecuta código Python a partir de lenguaje
    natural interpretado por un modelo local. Cualquier integración
    que lo conecte a un flujo de voz/texto en vivo DEBE usar
    prepare_skill() + confirm_and_save() como dos pasos separados,
    con una confirmación real del usuario en medio. El método
    learn_and_run() existe solo por compatibilidad/pruebas manuales
    y NO debe usarse en un flujo automático sin supervisión, porque
    encadena preparación y ejecución sin pausa real para confirmar.

    La validación de seguridad (validate_safety) es una lista de
    patrones conocidos, NO un sandbox real. Es defensa en
    profundidad, no una garantía — un modelo de lenguaje puede
    encontrar formas nuevas de lograr lo mismo que un patrón
    bloqueado (ya pasó una vez: escribir código en un archivo
    temporal y ejecutarlo con subprocess logra lo mismo que exec(),
    sin contener la palabra "exec("). Por eso esta versión bloquea
    también esa combinación específica y otras equivalentes.
    """

    def __init__(self, brain, skills_file=None, registry_file=None):

        self.brain = brain
        self.web_search = WebSearch()

        if skills_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_file = os.path.join(base_dir, "core", "learned_skills.py")

        if registry_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            registry_file = os.path.join(base_dir, "data", "learned_skills.json")

        self.skills_file = skills_file
        self.registry_file = registry_file

        self._ensure_skills_file()
        self._ensure_registry_file()

    # =========================================================
    # PREPARAR ARCHIVOS
    # =========================================================

    def _ensure_skills_file(self):
        directory = os.path.dirname(self.skills_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.skills_file):
            with open(self.skills_file, "w", encoding="utf-8") as f:
                f.write(
                    '"""\n'
                    'Habilidades aprendidas automáticamente por ECO.\n'
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
        directory = os.path.dirname(self.registry_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.registry_file):
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)

    # =========================================================
    # REGISTRO
    # =========================================================

    def _read_registry(self):
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as error:
            print("ERROR LEYENDO REGISTRO:", error)
        return {}

    def _write_registry(self, data):
        directory = os.path.dirname(self.registry_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        temp_file = self.registry_file + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, self.registry_file)

    # =========================================================
    # NORMALIZAR TEXTO
    # =========================================================

    def normalize(self, text):
        text = str(text)
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    # =========================================================
    # BUSCAR HABILIDAD EXISTENTE
    # =========================================================

    def find_existing(self, description):
        normalized = self.normalize(description)
        registry = self._read_registry()

        if not registry:
            return None

        if normalized in registry:
            entry = registry[normalized]
            if isinstance(entry, dict):
                return entry.get("function")

        close = difflib.get_close_matches(
            normalized, list(registry.keys()), n=1, cutoff=0.78
        )

        if close:
            entry = registry[close[0]]
            if isinstance(entry, dict):
                return entry.get("function")

        return None

    # =========================================================
    # INVESTIGAR
    # =========================================================

    def research(self, description):
        query = "cómo hacer en Python en Windows: " + description
        results = self.web_search.search(query)
        return self.web_search.format_results(results)

    # =========================================================
    # NOMBRE SEGURO DE FUNCIÓN
    # =========================================================

    def _make_function_name(self, description):
        normalized = self.normalize(description)
        safe_name = re.sub(r"[^a-z0-9_]", "_", normalized)
        safe_name = re.sub(r"_+", "_", safe_name)
        safe_name = safe_name.strip("_")
        safe_name = safe_name[:45]

        if not safe_name:
            safe_name = "generica"

        return "skill_" + safe_name

    # =========================================================
    # GENERAR CÓDIGO
    # =========================================================

    def generate_code(self, description, research_text, function_name):

        prompt = f"""
Eres el generador de habilidades de ECO.

ECO es un asistente local para Windows.

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

4. El texto será leído por ECO mediante voz.

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

21. NUNCA escribas código a un archivo temporal (tempfile, NamedTemporaryFile,
    open(..., "w") de un .py/.bat/.ps1/.exe) para luego ejecutarlo con
    subprocess, os.system, sys.executable, o cualquier otro medio. Eso
    equivale a ejecutar código arbitrario y está PROHIBIDO igual que
    eval()/exec(), sin excepción.

22. No uses compile(), __import__(), ni importlib para cargar y correr
    código generado dinámicamente.

La salida debe contener solamente:

def {function_name}(target=""):
    ...

"""
        raw = self.brain.generate(prompt)
        return self._clean_code(raw)

    # =========================================================
    # LIMPIAR CÓDIGO
    # =========================================================

    def _clean_code(self, raw):
        if raw is None:
            return ""

        code = str(raw).strip()
        code = re.sub(r"^```python\s*", "", code, flags=re.IGNORECASE)
        code = re.sub(r"^```\s*", "", code)
        code = re.sub(r"\s*```$", "", code)
        code = code.strip()

        match = re.search(r"\bdef\s+skill_[a-zA-Z0-9_]+\s*\(", code)
        if match:
            code = code[match.start():]

        return code.strip()

    # =========================================================
    # VALIDAR SINTAXIS
    # =========================================================

    def validate_syntax(self, code):
        try:
            tree = ast.parse(code)
            functions = [
                node for node in tree.body
                if isinstance(node, ast.FunctionDef)
            ]

            if not functions:
                return False, "No se encontró ninguna función."

            if len(functions) != 1:
                return False, "La habilidad debe contener una sola función."

            return True, None

        except SyntaxError as error:
            return False, str(error)
        except Exception as error:
            return False, str(error)

    # =========================================================
    # VALIDAR SEGURIDAD
    #
    # Lista de patrones conocidos peligrosos. NO es un sandbox real
    # — es defensa en profundidad. Incluye, además de los patrones
    # originales, los que cierran el hueco encontrado en producción
    # (escribir código a un archivo temporal y ejecutarlo con
    # subprocess logra lo mismo que exec() sin contener esa palabra).
    # =========================================================

    def validate_safety(self, code):
        dangerous_patterns = {
            "eval(": "eval()",
            "exec(": "exec()",
            "compile(": "compile() de código dinámico",
            "__import__": "importación dinámica de módulos",
            "importlib": "carga dinámica de módulos",
            "os.remove(": "borrado de archivos",
            "os.unlink(": "borrado de archivos",
            "shutil.rmtree(": "borrado de carpetas",
            "winreg": "modificación del registro",
            "shutdown ": "apagado del sistema",
            "shutdown(": "apagado del sistema",
            "os.system(": "comandos directos del sistema",
            "os.popen(": "comandos directos del sistema",
            "sys.executable": (
                "invocar el propio intérprete de Python "
                "(equivalente a ejecutar código arbitrario)"
            ),
            "namedtemporaryfile": (
                "escribir y luego ejecutar un archivo temporal "
                "(equivalente a exec())"
            ),
            "tempfile": (
                "uso de archivos temporales combinado con ejecución "
                "(equivalente a exec() si el archivo luego se corre)"
            ),
            "ctypes.windll": "acceso directo a la API de Windows",
        }

        code_lower = code.lower()

        for pattern, description in dangerous_patterns.items():
            if pattern.lower() in code_lower:
                return False, description

        return self._validate_ast(code)

    # =========================================================
    # VALIDAR SEGURIDAD SOBRE EL ÁRBOL (AST)
    #
    # La lista de arriba busca texto, y se esquiva fácil: por ejemplo
    # getattr(os, "sys" + "tem") no contiene "os.system(". Esta parte
    # mira la ESTRUCTURA del código: solo deja importar las librerías
    # permitidas, bloquea el acceso dinámico a atributos/funciones
    # internas, la escritura de archivos y los subprocess que abren
    # un intérprete o shell (cmd, powershell, python...).
    # =========================================================

    ALLOWED_IMPORTS = {
        "os", "re", "subprocess", "webbrowser", "requests", "time", "json",
    }

    FORBIDDEN_CALLS = {
        "eval", "exec", "compile", "__import__", "getattr", "setattr",
        "delattr", "globals", "locals", "vars", "breakpoint", "input",
    }

    FORBIDDEN_NAMES = {"__builtins__", "builtins", "sys", "ctypes", "winreg"}

    SHELL_PROGRAMS = (
        "cmd", "powershell", "pwsh", "python", "pythonw", "py", "wscript",
        "cscript", "mshta", "rundll32", "regsvr32", "reg", "bitsadmin",
        "certutil", "schtasks", "shutdown", "format", "del", "rmdir",
    )

    def _validate_ast(self, code):
        try:
            tree = ast.parse(code)
        except SyntaxError as error:
            return False, str(error)

        for node in ast.walk(tree):

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [node.module or ""] if isinstance(node, ast.ImportFrom)
                    else [alias.name for alias in node.names]
                )
                for name in names:
                    if name.split(".")[0] not in self.ALLOWED_IMPORTS:
                        return False, f"importar la librería no permitida {name}"

            elif isinstance(node, ast.Name) and node.id in self.FORBIDDEN_NAMES:
                return False, f"acceso a {node.id}"

            elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return False, "acceso a atributos internos de Python"

            elif isinstance(node, ast.Call):
                problem = self._check_call(node)
                if problem:
                    return False, problem

        return True, None

    def _check_call(self, node):
        func = node.func
        name = (
            func.id if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute)
            else ""
        )

        if name in self.FORBIDDEN_CALLS:
            return f"{name}()"

        if name == "open":
            for arg in list(node.args[1:2]) + [
                kw.value for kw in node.keywords if kw.arg == "mode"
            ]:
                if not (
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and set(arg.value) <= set("rbt")
                ):
                    return "escribir archivos"

        if name in ("system", "popen", "startfile", "spawnl", "spawnv",
                    "execv", "execl", "remove", "unlink", "rmdir",
                    "removedirs", "rename", "replace"):
            if isinstance(func, ast.Attribute):
                return f"os.{name}()"

        is_subprocess = (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        )
        if is_subprocess:
            for kw in node.keywords:
                if kw.arg == "shell" and not (
                    isinstance(kw.value, ast.Constant) and kw.value.value is False
                ):
                    return "subprocess con shell=True"

            if not node.args:
                return "subprocess sin un comando fijo"

            first = node.args[0]
            program = None
            if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
                first = first.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                program = first.value.strip().split()[0] if first.value.strip() else ""
            if program is None:
                return "subprocess con un programa que no es fijo"

            program = os.path.basename(program.strip('"')).lower()
            program = os.path.splitext(program)[0]
            if program in self.SHELL_PROGRAMS:
                return f"abrir {program} desde una habilidad"

        return None

    # =========================================================
    # GUARDAR HABILIDAD
    # =========================================================

    def save_skill(self, function_name, code, description):
        directory = os.path.dirname(self.skills_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(self.skills_file, "a", encoding="utf-8") as f:
            f.write("\n\n")
            f.write("# =====================================================\n")
            f.write("# HABILIDAD APRENDIDA\n")
            f.write("# =====================================================\n")
            f.write(f"# Descripción: {description}\n")
            f.write("# Fecha: " + datetime.now().isoformat(timespec="seconds") + "\n")
            f.write(code.strip() + "\n")

        registry = self._read_registry()
        registry[self.normalize(description)] = {
            "function": function_name,
            "description": description,
            "learned_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write_registry(registry)

    # =========================================================
    # CARGAR HABILIDADES
    # =========================================================

    def _load_skills_module(self):
        module_name = "eco_learned_skills"
        spec = importlib.util.spec_from_file_location(module_name, self.skills_file)

        if spec is None:
            raise ImportError("No pude crear el módulo.")
        if spec.loader is None:
            raise ImportError("No pude cargar el módulo.")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # =========================================================
    # EJECUTAR HABILIDAD
    # =========================================================

    def run_skill(self, function_name, target=""):
        try:
            module = self._load_skills_module()
        except Exception as error:
            return f"No pude cargar las habilidades aprendidas: {error}"

        func = getattr(module, function_name, None)
        if not func:
            return f"No encontré la función {function_name}."

        try:
            result = func(target)
            if result is None:
                return "La habilidad terminó sin devolver una respuesta."
            return str(result)
        except Exception as error:
            return f"La habilidad aprendida falló al ejecutarse: {error}"

    # =========================================================
    # RESUMEN
    # =========================================================

    def summarize_code(self, code, description):
        risky_signals = {
            "subprocess": "puede ejecutar comandos de Windows",
            "webbrowser": "puede abrir páginas web",
            "requests.get": "puede consultar internet",
            "requests.post": "puede enviar información a internet",
            "requests.put": "puede enviar información a internet",
            "requests.delete": "puede eliminar información mediante internet",
        }

        found = []
        for signal, message in risky_signals.items():
            if signal in code:
                found.append(message)

        summary = "Generé una función para: " + description + "."
        if found:
            summary += " El código " + ", y ".join(found) + "."

        return summary

    # =========================================================
    # PREPARAR HABILIDAD (paso 1 de 2 — NO ejecuta nada)
    # =========================================================

    def prepare_skill(self, description, target=""):

        function_name = self._make_function_name(description)

        print()
        print("APRENDIZAJE: investigando ->", description)

        try:
            research_text = self.research(description)
        except Exception as error:
            print("APRENDIZAJE: error investigando ->", error)
            research_text = ""

        print("APRENDIZAJE: generando código ->", function_name)

        try:
            code = self.generate_code(description, research_text, function_name)
        except Exception as error:
            print("APRENDIZAJE: error generando código ->", error)
            return None, "No pude generar una forma de hacer eso."

        if not code:
            return None, "No pude generar una habilidad."

        if "def " not in code:
            return None, "El cerebro no generó una función válida."

        valid, syntax_error = self.validate_syntax(code)
        if not valid:
            print("APRENDIZAJE: código inválido ->", syntax_error)
            return None, "El código generado tiene errores de sintaxis."

        safe, safety_error = self.validate_safety(code)
        if not safe:
            print("APRENDIZAJE: código bloqueado ->", safety_error)
            return None, (
                "Bloqueé el código porque contiene una acción "
                f"potencialmente peligrosa: {safety_error}."
            )

        print()
        print("=" * 60)
        print("CÓDIGO GENERADO (pendiente de confirmación, NO se ha ejecutado):")
        print("=" * 60)
        print(code)
        print("=" * 60)

        prepared = {
            "function_name": function_name,
            "code": code,
            "description": description,
            "target": target,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        summary = self.summarize_code(code, description)

        return prepared, summary

    # =========================================================
    # CONFIRMAR + GUARDAR + EJECUTAR (paso 2 de 2)
    #
    # Este método SOLO debe llamarse después de que un humano haya
    # visto el código (impreso por prepare_skill) y haya dado una
    # confirmación explícita en un turno de conversación aparte —
    # nunca automáticamente justo después de prepare_skill().
    # =========================================================

    def confirm_and_save(self, prepared):

        if not prepared:
            return "No hay ninguna habilidad pendiente."

        function_name = prepared.get("function_name")
        code = prepared.get("code")
        description = prepared.get("description")
        target = prepared.get("target", "")

        if not function_name or not code:
            return "La habilidad pendiente no es válida."

        valid, error = self.validate_syntax(code)
        if not valid:
            return f"No guardé la habilidad porque el código tiene errores: {error}"

        safe, safety_error = self.validate_safety(code)
        if not safe:
            return f"No guardé la habilidad porque fue bloqueada: {safety_error}"

        try:
            self.save_skill(function_name, code, description)
        except Exception as error:
            return f"No pude guardar la habilidad: {error}"

        print()
        print("APRENDIZAJE: habilidad guardada.")
        print("APRENDIZAJE: ejecutando...")

        return self.run_skill(function_name, target)

    # =========================================================
    # FLUJO DIRECTO — SOLO PARA USO MANUAL/DE PRUEBA
    #
    # ADVERTENCIA: encadena prepare_skill() y confirm_and_save()
    # SIN pausa real de confirmación. NO conectar esto a un flujo
    # de voz/texto en vivo del asistente.
    # =========================================================

    def learn_and_run(self, description, target=""):
        prepared, message = self.prepare_skill(description, target)
        if not prepared:
            return message
        return self.confirm_and_save(prepared)
