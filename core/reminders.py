"""
Recordatorios, alarmas y temporizadores por voz.

Ejemplos que entiende:
    "recuérdame en 20 minutos sacar la ropa"
    "recuérdame mañana a las 9 llamar a mamá"
    "pon una alarma a las 7 y media"  /  "despiértame a las 6"
    "pon un temporizador de 10 minutos para la pasta"
    "qué recordatorios tengo"  /  "cuánto falta del temporizador"
    "cancela la alarma"  /  "borra todos los recordatorios"
    "pospón la alarma 10 minutos"

Se guardan en data/reminders.json, así que sobreviven a cerrar Eco.
Si Eco estaba cerrado cuando tocaba avisar, al abrirlo avisa de los
recordatorios atrasados; las alarmas y temporizadores con más de
LATE_LIMIT_SECONDS de atraso se descartan (ya no sirven).
"""

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta


# Quita tildes SIN cambiar el largo del texto: así las posiciones que
# encuentran las expresiones regulares sirven también para el original.
_ACCENTS = str.maketrans("áéíóúü", "aeiouu")

_WORD_NUMBERS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veinticinco": 25, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "noventa": 90,
    "media": 0.5, "medio": 0.5,
}

_NUM = (
    r"(?:\d+(?:[.,]\d+)?|"
    + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True))
    + r")"
)
_UNIT = r"(?:segundos?|segs?|minutos?|mins?|horas?|hrs?|dias?)"
_PART = rf"\b{_NUM}\s+{_UNIT}\b(?:\s+y\s+medi[ao]\b)?"

# "en 1 hora y 30 minutos", "dentro de media hora", "de 10 minutos"
_DURATION = re.compile(
    rf"(?:\b(?:en|dentro\s+de|de|por|durante)\s+)?"
    rf"(?P<dur>{_PART}(?:\s*(?:,|\by\b)\s*{_PART})*)"
)
_DURATION_PART = re.compile(
    rf"\b(?P<n>{_NUM})\s+(?P<u>{_UNIT})\b(?P<half>\s+y\s+medi[ao]\b)?"
)

_HOUR_WORDS = (
    "una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce"
)
_MIN_WORDS = "cinco|diez|quince|veinte|veinticinco|treinta|cuarenta|cincuenta"

# "a las 7", "a las 7:30", "a la una y media", "a las 8 menos cuarto",
# "a las 5 de la tarde", "a las 9 pm"
_TIME = re.compile(
    rf"\b(?:para\s+(?:a\s+)?|a\s+|de\s+)las?\s+(?P<h>\d{{1,2}}|{_HOUR_WORDS})\b"
    rf"(?:(?::|\.|h)(?P<m>\d{{2}})"
    rf"|\s+y\s+(?P<mw>media|cuarto|\d{{1,2}}|{_MIN_WORDS})\b(?:\s+minutos?)?)?"
    rf"(?:\s+menos\s+(?P<menos>cuarto|\d{{1,2}}|{_MIN_WORDS})\b)?"
    rf"(?:\s*(?P<ampm>a\.?\s?m\.?|p\.?\s?m\.?)(?![a-z])"
    rf"|\s+(?P<part>de\s+la\s+(?:ma[nñ]ana|tarde|noche|madrugada)|del\s+mediodia)\b"
    rf"|\s+en\s+punto\b)*"
)

_WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
_DAY = re.compile(
    r"\b(?:(?P<pasado>pasado\s+ma[nñ]ana)|(?P<manana>ma[nñ]ana)|(?P<hoy>hoy)"
    r"|(?P<noche>esta\s+noche)"
    r"|(?:el\s+)?(?:proximo\s+)?(?P<wd>lunes|martes|miercoles|jueves|"
    r"viernes|sabado|domingo))\b"
)

_TIMER_WORDS = re.compile(r"\b(?:temporizador(?:es)?|cronometros?|timers?)\b")
_ALARM_WORDS = re.compile(
    r"\b(?:alarmas?|despiertame|despertador|levantame)\b"
)
_REMINDER_WORDS = re.compile(
    r"\b(?:recuerdame|recordarme|recordatorios?|avisame|recuerda\s+que|"
    r"no\s+me\s+dejes\s+olvidar)\b"
)
_CREATE_VERBS = re.compile(
    r"\b(?:pon|ponme|poner|crea|creame|crear|programa|programame|activa|"
    r"agrega|anade|configura|inicia|empieza|arranca|nuevo|nueva)\b"
)
_LIST_WORDS = re.compile(
    r"\b(?:que|cuales|cuantos|cuantas|mis|lista|listame|dime|muestrame|"
    r"tengo|hay|ver|revisa)\b"
)
_REMAINING = re.compile(r"\b(?:cuanto\s+(?:falta|le\s+queda|queda)|cuanto\s+tiempo\s+queda)\b")
_CANCEL_VERBS = re.compile(
    r"\b(?:cancela|cancelar|cancelame|borra|borrar|elimina|eliminar|quita|"
    r"quitar|apaga|apagar|detener|desactiva|desactivar)\b"
    r"|\b(?:para|deten)\s+(?:el|la|los|las)\s+(?:temporizador|alarma|cronometro)"
)
_SNOOZE = re.compile(r"\b(?:pospon|posponer|pospone|posponla|aplaza|aplazar)\b")
_ALL = re.compile(r"\b(?:todos|todas|todo)\b")
_CANCEL_ONLY = {
    "no", "cancela", "cancelar", "mejor no", "olvidalo", "nada", "dejalo",
}

# Palabras que quedan sueltas al quitar la orden y la hora del texto.
_FILLER = re.compile(
    r"^(?:(?:eco|por\s+favor|oye|porfa|y|que|de|a|para|un|una|"
    r"recordatorio|alarma|temporizador|pon|ponme|crea|programa|"
    r"me|te|lo|se|tengo\s+que|hay\s+que|,)(?:\s+|$))+"
    r"|(?:\s+(?:y|que|de|a|para|el|la|por\s+favor|porfa|,))+$"
)

KIND_NAMES = {"reminder": "recordatorio", "alarm": "alarma", "timer": "temporizador"}
KIND_PLURALS = {"reminder": "recordatorios", "alarm": "alarmas", "timer": "temporizadores"}
KIND_NONE = {
    "reminder": "No tienes recordatorios activos.",
    "alarm": "No tienes alarmas activas.",
    "timer": "No tienes temporizadores activos.",
}
LATE_LIMIT_SECONDS = 15 * 60
PENDING_SECONDS = 60


def _number(token):
    token = token.strip()
    if token in _WORD_NUMBERS:
        return _WORD_NUMBERS[token]
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def _unit_seconds(unit):
    return {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit[0]]


def describe_duration(seconds):
    seconds = int(round(seconds))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)

    parts = []
    for value, singular, plural in (
        (days, "día", "días"), (hours, "hora", "horas"),
        (minutes, "minuto", "minutos"), (secs, "segundo", "segundos"),
    ):
        if value:
            parts.append(f"{value} {singular if value == 1 else plural}")

    if not parts:
        return "menos de un segundo"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " y " + parts[-1]


def describe_when(moment, now=None):
    now = now or datetime.now()
    clock = moment.strftime("%H:%M")
    days = (moment.date() - now.date()).days

    if days == 0:
        return f"hoy a las {clock}"
    if days == 1:
        return f"mañana a las {clock}"
    if days == 2:
        return f"pasado mañana a las {clock}"

    weekday = ("lunes", "martes", "miércoles", "jueves", "viernes",
               "sábado", "domingo")[moment.weekday()]
    return f"el {weekday} {moment.day} a las {clock}"


class ReminderManager:

    def __init__(self, file_path=None, on_fire=None):
        self.file_path = file_path or os.path.join("data", "reminders.json")
        self.on_fire = on_fire

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

        # Recordatorio a medio crear: "recuérdame sacar la ropa" sin
        # hora -> Eco pregunta "¿cuándo?" y la próxima frase lo completa.
        self._pending = None

        # La última alarma que sonó, para poder decir "pospónla".
        self._last_fired = None

        self._items = self._load()

    # =========================================================
    # ARCHIVO
    # =========================================================

    def _load(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            items = data.get("items", []) if isinstance(data, dict) else []
            return [item for item in items if isinstance(item, dict) and "due" in item]
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self):
        directory = os.path.dirname(self.file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        temporary = self.file_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump({"items": self._items}, file, ensure_ascii=False, indent=2)
        os.replace(temporary, self.file_path)

    # =========================================================
    # HILO QUE AVISA
    # =========================================================

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._handle_overdue()

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _handle_overdue(self):
        now = time.time()
        late = []

        with self._lock:
            keep = []
            for item in self._items:
                if item["due"] > now:
                    keep.append(item)
                elif item["kind"] == "reminder" or now - item["due"] <= LATE_LIMIT_SECONDS:
                    late.append(item)
                else:
                    print("RECORDATORIOS: se descarta por atrasado ->", item)
            self._items = keep
            self._save()

        for item in late:
            self._fire(item, late=True)

    def _loop(self):
        while not self._stop.wait(1):
            now = time.time()
            with self._lock:
                due = [item for item in self._items if item["due"] <= now]
                if due:
                    self._items = [item for item in self._items if item["due"] > now]
                    self._save()

            for item in sorted(due, key=lambda item: item["due"]):
                self._fire(item)

    def _fire(self, item, late=False):
        if item["kind"] == "alarm":
            self._last_fired = item

        text = self.fired_text(item, late=late)
        print("RECORDATORIOS: avisando ->", text)

        if self.on_fire:
            try:
                self.on_fire(item, text)
            except Exception as error:
                print("ERROR AVISANDO RECORDATORIO:", error)

    def fired_text(self, item, late=False):
        message = item.get("message", "").strip()

        if item["kind"] == "timer":
            text = f"Terminó el temporizador de {describe_duration(item.get('seconds', 0))}"
            text += f" para {message}." if message else "."
        elif item["kind"] == "alarm":
            clock = datetime.fromtimestamp(item["due"]).strftime("%H:%M")
            text = f"Alarma. Son las {clock}."
            if message:
                text += f" {message[0].upper()}{message[1:]}."
        else:
            text = (
                f"Te recuerdo: {message}." if message
                else "Te aviso, como me pediste."
            )

        if late:
            clock = datetime.fromtimestamp(item["due"]).strftime("%H:%M")
            text = f"Mientras no estaba encendida, a las {clock}: {text}"

        return text

    # =========================================================
    # CREAR / LISTAR / CANCELAR
    # =========================================================

    def add(self, kind, due, message="", seconds=None):
        item = {
            "id": uuid.uuid4().hex[:8],
            "kind": kind,
            "message": message.strip(),
            "due": float(due),
            "created": time.time(),
        }
        if seconds is not None:
            item["seconds"] = int(round(seconds))

        with self._lock:
            self._items.append(item)
            self._save()

        return item

    def upcoming(self, kind=None):
        with self._lock:
            items = [item for item in self._items if kind is None or item["kind"] == kind]
        return sorted(items, key=lambda item: item["due"])

    def remove(self, ids):
        ids = set(ids)
        with self._lock:
            before = len(self._items)
            self._items = [item for item in self._items if item["id"] not in ids]
            self._save()
            return before - len(self._items)

    # =========================================================
    # ENTENDER LA ORDEN
    # =========================================================

    def handle(self, command):
        """
        Devuelve (intent, respuesta) si la orden era de recordatorios,
        alarmas o temporizadores, o None si no tiene que ver.
        """

        original = command.lower().strip()
        text = original.translate(_ACCENTS)
        text = re.sub(r"[¿?¡!]", " ", text)
        original = re.sub(r"[¿?¡!]", " ", original)

        if not text:
            return None

        pending = self._take_pending()
        if pending:
            if text.strip(" .") in _CANCEL_ONLY:
                return "CANCEL_REMINDER", "Está bien, no lo anoto."
            result = self._complete_pending(pending, text)
            if result:
                return result

        timer = bool(_TIMER_WORDS.search(text))
        alarm = bool(_ALARM_WORDS.search(text))
        reminder = bool(_REMINDER_WORDS.search(text))

        if not (timer or alarm or reminder):
            return None

        kind = "timer" if timer else "alarm" if alarm else "reminder"

        if alarm and _SNOOZE.search(text):
            return self._snooze(text)

        if _CANCEL_VERBS.search(text) and not _CREATE_VERBS.search(text):
            return self._cancel(kind, text)

        if _REMAINING.search(text):
            return self._list(kind, remaining=True)

        when = self._parse_when(text, kind)

        is_creation = (
            when is not None
            or _CREATE_VERBS.search(text)
            or re.search(r"\b(?:recuerdame|recordarme|avisame|despiertame|levantame|recuerda\s+que|no\s+me\s+dejes\s+olvidar)\b", text)
        )

        if not is_creation:
            if _LIST_WORDS.search(text) or re.fullmatch(r"\s*(?:mis\s+)?\w+\s*", text):
                return self._list(kind)
            return None

        if when is None:
            # "avísame cuando termine la descarga" no es un recordatorio
            # con hora: se deja pasar al resto de los comandos.
            if kind == "reminder" and not re.search(
                r"\b(?:recuerdame|recordarme|recordatorios?|recuerda\s+que|no\s+me\s+dejes\s+olvidar)\b",
                text,
            ):
                return None
            self._pending = {
                "kind": kind,
                "message": self._extract_message(original, text, []),
                "expires": time.time() + PENDING_SECONDS,
            }
            if kind == "timer":
                return "ASK_REMINDER_TIME", "¿De cuánto tiempo pongo el temporizador?"
            if kind == "alarm":
                return "ASK_REMINDER_TIME", "¿A qué hora pongo la alarma?"
            return "ASK_REMINDER_TIME", "¿Cuándo te lo recuerdo?"

        due, seconds, spans = when
        message = self._extract_message(original, text, spans)
        return self._create(kind, due, seconds, message)

    def _take_pending(self):
        pending, self._pending = self._pending, None
        if pending and pending["expires"] >= time.time():
            return pending
        return None

    def _complete_pending(self, pending, text):
        when = self._parse_when(text, pending["kind"])
        if when is None:
            return None
        due, seconds, _spans = when
        return self._create(pending["kind"], due, seconds, pending["message"])

    def _create(self, kind, due, seconds, message):
        now = datetime.now()

        if kind == "timer" and seconds is None:
            seconds = max(0, (due - now).total_seconds())

        if due <= now:
            return "REMINDER_ERROR", "Esa hora ya pasó. Dime una hora que venga."
        if due - now > timedelta(days=365):
            return "REMINDER_ERROR", "Eso es demasiado lejos; dime algo dentro de un año."

        self.add(kind, due.timestamp(), message, seconds=seconds)

        when_text = describe_when(due, now)

        if kind == "timer":
            response = f"Listo, temporizador de {describe_duration(seconds)}"
            response += f" para {message}." if message else "."
            return "SET_TIMER", response

        if kind == "alarm":
            response = f"Alarma puesta para {when_text}."
            if seconds is not None:
                response = f"Alarma puesta en {describe_duration(seconds)}, {when_text}."
            return "SET_ALARM", response

        if seconds is not None:
            when_text = f"en {describe_duration(seconds)}, {when_text}"
        if message:
            return "SET_REMINDER", f"Te recordaré {message} {when_text}."
        return "SET_REMINDER", f"Te aviso {when_text}."

    def _list(self, kind, remaining=False):
        items = self.upcoming(kind)
        name = KIND_NAMES[kind]

        if not items:
            return "LIST_REMINDERS", KIND_NONE[kind]

        now = datetime.now()
        lines = []
        for item in items[:5]:
            due = datetime.fromtimestamp(item["due"])
            if kind == "timer" or remaining:
                detail = f"quedan {describe_duration((due - now).total_seconds())}"
            else:
                detail = describe_when(due, now)
            message = item.get("message", "")
            lines.append(f"{message}, {detail}" if message else detail)

        if len(items) == 1:
            intro = f"Tienes un {name}" if kind != "alarm" else "Tienes una alarma"
            return "LIST_REMINDERS", f"{intro}: {lines[0]}."

        intro = f"Tienes {len(items)} {KIND_PLURALS[kind]}"
        extra = " Te digo los cinco más cercanos." if len(items) > 5 else ""
        return "LIST_REMINDERS", f"{intro}.{extra} " + "; ".join(lines) + "."

    def _cancel(self, kind, text):
        items = self.upcoming(kind)
        name = KIND_NAMES[kind]
        article = "la" if kind == "alarm" else "el"

        if not items:
            if kind == "alarm" and self._last_fired:
                self._last_fired = None
                return "CANCEL_REMINDER", "Listo, alarma apagada."
            return "CANCEL_REMINDER", KIND_NONE[kind]

        if _ALL.search(text):
            count = self.remove(item["id"] for item in items)
            return "CANCEL_REMINDER", f"Listo, borré {count} en total."

        chosen = None

        when = self._parse_when(text, kind)
        if when:
            target = when[0].timestamp()
            chosen = min(items, key=lambda item: abs(item["due"] - target))
            if abs(chosen["due"] - target) > 120:
                chosen = None

        if chosen is None:
            words = set(re.findall(r"[a-zñ]{4,}", text)) - {
                "cancela", "cancelar", "borra", "borrar", "elimina", "eliminar",
                "quita", "quitar", "apaga", "apagar", "recordatorio",
                "alarma", "temporizador", "desactiva", "detener", "todos",
            }
            if words:
                scored = [
                    (len(words & set(re.findall(r"[a-zñ]{4,}", item.get("message", "").translate(_ACCENTS)))), item)
                    for item in items
                ]
                best_score, best = max(scored, key=lambda pair: pair[0])
                if best_score:
                    chosen = best

        if chosen is None:
            if len(items) > 1:
                return "CANCEL_REMINDER", (
                    f"Tienes {len(items)} {KIND_PLURALS[kind]}. Dime cuál, por ejemplo "
                    f"«cancela {article} {name} de las "
                    f"{datetime.fromtimestamp(items[0]['due']).strftime('%H:%M')}», "
                    "o di «borra todos»."
                )
            chosen = items[0]

        self.remove([chosen["id"]])
        due = datetime.fromtimestamp(chosen["due"])
        message = chosen.get("message", "")
        label = f" de {message}" if message else ""
        return "CANCEL_REMINDER", f"Cancelé {article} {name}{label} de {describe_when(due)}."

    def _snooze(self, text):
        item = self._last_fired
        if not item:
            return "SNOOZE_ALARM", "No hay ninguna alarma sonando para posponer."

        when = self._parse_duration(text)
        seconds = when[0] if when else 5 * 60
        due = datetime.now() + timedelta(seconds=seconds)
        self.add("alarm", due.timestamp(), item.get("message", ""))
        self._last_fired = None
        return "SNOOZE_ALARM", f"Pospuse la alarma {describe_duration(seconds)}, hasta las {due.strftime('%H:%M')}."

    # =========================================================
    # FECHAS Y HORAS
    # =========================================================

    def _parse_duration(self, text):
        match = _DURATION.search(text)
        if not match:
            return None

        total = 0.0
        for part in _DURATION_PART.finditer(match.group("dur")):
            number = _number(part.group("n"))
            if number is None:
                continue
            unit = _unit_seconds(part.group("u"))
            total += number * unit
            if part.group("half"):
                total += 0.5 * unit

        if total <= 0:
            return None
        return total, match.span()

    def _parse_when(self, text, kind, now=None):
        """
        Devuelve (fecha, segundos_si_era_duración, [tramos_usados]) o None.
        Los tramos sirven para sacar la hora del texto del recordatorio.
        """
        now = now or datetime.now()

        duration = self._parse_duration(text)
        time_match = _TIME.search(text)

        if duration and (not time_match or duration[1][0] < time_match.start()):
            seconds, span = duration
            return now + timedelta(seconds=seconds), seconds, [span]

        if not time_match:
            day_match = _DAY.search(text)
            if day_match and kind == "reminder":
                # "recuérdame mañana pagar la luz" -> a las 9:00.
                offset, _ = self._day_offset(day_match, now)
                if offset is None:
                    return None
                due = (now + timedelta(days=offset)).replace(hour=9, minute=0, second=0, microsecond=0)
                if day_match.group("noche"):
                    due = due.replace(hour=21)
                return due, None, [day_match.span()]
            return None

        resolved = self._resolve_clock(time_match)
        if resolved is None:
            return None
        hour, minute, fixed = resolved

        spans = [time_match.span()]
        rest = text[:time_match.start()] + " " * (time_match.end() - time_match.start()) + text[time_match.end():]
        day_match = _DAY.search(rest)

        if day_match:
            spans.append(day_match.span())
            offset, _ = self._day_offset(day_match, now)
            if offset is None:
                return None
            if day_match.group("noche") and not fixed and hour < 12:
                hour += 12
                fixed = True
            if not fixed and kind != "alarm" and 1 <= hour <= 6:
                hour += 12
            base = (now + timedelta(days=offset)).replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
            if base <= now and day_match.group("wd"):
                base += timedelta(days=7)
            return base, None, spans

        if not fixed and kind != "alarm" and 1 <= hour <= 6:
            # "recuérdame a las 3" casi siempre es de la tarde.
            hour += 12

        candidates = [hour] if fixed or kind == "alarm" or hour == 0 or hour >= 12 else [hour, hour + 12]
        options = []
        for candidate in candidates:
            moment = now.replace(hour=candidate % 24, minute=minute, second=0, microsecond=0)
            if moment <= now:
                moment += timedelta(days=1)
            options.append(moment)

        return min(options), None, spans

    def _day_offset(self, match, now):
        if match.group("pasado"):
            return 2, True
        if match.group("manana"):
            return 1, True
        if match.group("hoy") or match.group("noche"):
            return 0, True
        if match.group("wd"):
            target = _WEEKDAYS[match.group("wd")]
            offset = (target - now.weekday()) % 7
            return offset, True
        return None, False

    def _resolve_clock(self, match):
        hour = _number(match.group("h"))
        if hour is None:
            return None
        hour = int(hour)
        minute = 0
        fixed = False

        if match.group("m"):
            minute = int(match.group("m"))
        elif match.group("mw"):
            word = match.group("mw")
            minute = {"media": 30, "cuarto": 15}.get(word)
            if minute is None:
                minute = int(_number(word) or 0)

        if match.group("menos"):
            word = match.group("menos")
            less = 15 if word == "cuarto" else int(_number(word) or 0)
            hour -= 1
            minute = 60 - less

        whole = match.group(0)
        part = re.search(r"de\s+la\s+(ma[nñ]ana|tarde|noche|madrugada)|del\s+mediodia", whole)
        ampm = re.search(r"(?<![a-z])([ap])\.?\s?m\.?(?![a-z])", whole[match.end("h") - match.start():])

        if part:
            fixed = True
            word = (part.group(1) or "").replace("ñ", "n") or None
            if word in ("tarde", "noche") and hour < 12:
                hour += 12
            elif word in ("manana", "madrugada") and hour == 12:
                hour = 0
            elif word is None:
                hour = 12
        elif ampm:
            fixed = True
            if ampm.group(1) == "p" and hour < 12:
                hour += 12
            elif ampm.group(1) == "a" and hour == 12:
                hour = 0
        elif hour > 12:
            fixed = True

        if hour == 24:
            hour = 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        return hour, minute, fixed

    # =========================================================
    # TEXTO DEL RECORDATORIO
    # =========================================================

    def _extract_message(self, original, text, spans):
        """
        Saca lo que hay que recordar: quita la orden ("recuérdame",
        "pon un temporizador"...) y la hora/fecha ya entendida.
        """
        chars = list(original)
        for start, end in spans:
            for index in range(start, min(end, len(chars))):
                chars[index] = " "

        for pattern in (_REMINDER_WORDS, _ALARM_WORDS, _TIMER_WORDS, _CREATE_VERBS, _DAY):
            for match in pattern.finditer(text):
                for index in range(match.start(), min(match.end(), len(chars))):
                    chars[index] = " "

        message = re.sub(r"\s+", " ", "".join(chars)).strip(" ,.")

        previous = None
        while previous != message:
            previous = message
            message = _FILLER.sub("", message).strip(" ,.")

        return message
