import html
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import requests
from ddgs import DDGS


_SPANISH_WORDS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "que", "y", "en",
    "es", "son", "fue", "por", "para", "con", "como", "más", "pero", "su",
    "sus", "al", "se", "lo", "este", "esta", "también", "sobre", "entre",
}
_ENGLISH_WORDS = {
    "the", "of", "and", "is", "are", "was", "were", "to", "in", "for",
    "with", "that", "this", "from", "by", "on", "as", "an", "it", "its",
    "has", "have", "which", "be", "at", "or", "you", "your",
}
_QUESTION_WORDS = {
    "que", "quien", "quienes", "como", "cuando", "donde", "cual", "cuales",
    "cuanto", "cuanta", "cuantos", "cuantas", "por", "para", "dime", "busca",
    "buscar", "buscame", "sobre", "acerca", "del", "las", "los", "una",
    "uno", "unos", "unas", "con", "fue", "son", "era", "hay", "esta", "este",
    "google", "internet", "quiero", "saber",
}


def _plain(text):
    text = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def is_spanish(text):
    """Cuenta palabras muy comunes de cada idioma; en empate, es español."""
    words = re.findall(r"[a-záéíóúüñ]+", str(text or "").lower())
    spanish = sum(word in _SPANISH_WORDS for word in words)
    english = sum(word in _ENGLISH_WORDS for word in words)
    return spanish >= english


def keywords(query):
    """Las palabras de la pregunta que de verdad dicen de qué trata."""
    return {
        word for word in re.findall(r"[a-z0-9ñ]+", _plain(query))
        if (len(word) >= 3 or word.isdigit()) and word not in _QUESTION_WORDS
    }


class WebSearch:

    # Los buscadores a veces responden "sin resultados" a una búsqueda
    # normal; se prueba el siguiente antes de darse por vencido.
    BACKENDS = ("auto", "google", "brave", "mojeek")

    # Videos, redes y documentos con muro: sin texto que se pueda leer.
    NO_TEXT_SITES = (
        "youtube.com", "youtu.be", "facebook.com", "instagram.com",
        "tiktok.com", "x.com/", "twitter.com", "scribd.com", "pinterest.",
    )

    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    MAX_PAGE_BYTES = 1_500_000

    def __init__(self):

        self.max_results = 10
        self.timeout = 8
        self.page_timeout = 5

    def search(self, query):

        query = query.strip()

        if not query:
            return []

        print()
        print("🌐 BUSCANDO EN INTERNET:")
        print(query)

        for backend in self.BACKENDS:

            results = self._search_backend(query, backend)

            if results:
                ranked = self.rank(query, results)
                print(f"✅ RESULTADOS ÚTILES: {len(ranked)} ({backend})")
                if ranked:
                    return ranked

        ranked = self.rank(query, self._search_wikipedia(query))
        if ranked:
            print(f"✅ RESULTADOS ÚTILES: {len(ranked)} (Wikipedia)")
            return ranked

        print("❌ No encontré resultados.")
        return []

    def _search_wikipedia(self, query):
        """Último recurso: los buscadores a veces bloquean por un rato."""
        try:
            response = requests.get(
                "https://es.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search", "format": "json",
                    "srsearch": " ".join(keywords(query)) or query,
                    "srlimit": 5,
                },
                headers=self.HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()
            found = response.json().get("query", {}).get("search", [])
        except Exception as error:
            print("⚠️ BÚSQUEDA (Wikipedia):", error)
            return []

        return [
            {
                "title": item.get("title", ""),
                "body": html.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", ""))),
                "url": "https://es.wikipedia.org/wiki/"
                       + item.get("title", "").replace(" ", "_"),
            }
            for item in found
        ]

    def _search_backend(self, query, backend):

        try:

            results = DDGS(
                timeout=self.timeout
            ).text(
                query,
                # Antes "wt-wt" (mundial, sin idioma): DuckDuckGo podía
                # traer el resultado mejor rankeado en inglés aunque
                # preguntaras en español (pasaba seguido con temas de
                # videojuegos y personajes históricos). "es-es" le da
                # preferencia a resultados en español.
                region="es-es",
                safesearch="moderate",
                max_results=self.max_results,
                backend=backend
            )

        except Exception as error:

            print(f"⚠️ BÚSQUEDA ({backend}):", error)
            return []

        cleaned = []

        for result in results or []:

            title = result.get("title", "")
            body = result.get("body", "")
            url = result.get("href", "")

            if title or body:
                cleaned.append({"title": title, "body": body, "url": url})

        return cleaned

    # =========================================================
    # QUEDARSE CON LO QUE RESPONDE LA PREGUNTA, EN ESPAÑOL
    # =========================================================

    def rank(self, query, results):
        """
        Saca los resultados en inglés y ordena el resto por cuántas
        palabras de la pregunta contienen. Si TODOS están en inglés
        devuelve vacío: mejor decir que no se encontró que leer inglés.
        """
        wanted = keywords(query)
        scored = []

        for result in results:

            title = result.get("title", "")
            body = result.get("body", "")

            if not is_spanish(f"{title} {body}"):
                continue

            if any(site in result.get("url", "") for site in self.NO_TEXT_SITES):
                continue

            title_words = keywords(title)
            body_words = keywords(body)

            hits = 2 * len(wanted & title_words) + len(wanted & body_words)

            if wanted and not wanted & (title_words | body_words):
                continue

            if "es.wikipedia.org" in result.get("url", ""):
                hits += 2

            scored.append((hits, result))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [result for _, result in scored]

    # =========================================================
    # LEER LAS PÁGINAS
    #
    # El fragmento del buscador suele hablar del tema sin decir el
    # dato; el dato está dentro de la página.
    # =========================================================

    def add_page_details(self, query, results, pages=3):

        wanted = keywords(query)

        def read(result):
            result["details"] = self._page_sentences(result.get("url", ""), wanted)

        with ThreadPoolExecutor(max_workers=pages) as pool:
            list(pool.map(read, results[:pages]))

        return results

    def _page_sentences(self, url, wanted, limit=5):

        if not url.startswith(("http://", "https://")):
            return []

        try:

            response = requests.get(
                url,
                headers=self.HEADERS,
                timeout=self.page_timeout,
                stream=True
            )
            response.raise_for_status()

            if "html" not in response.headers.get("Content-Type", ""):
                return []

            raw = b""
            for chunk in response.iter_content(65536):
                raw += chunk
                if len(raw) > self.MAX_PAGE_BYTES:
                    break

            try:
                page = raw.decode("utf-8")
            except UnicodeDecodeError:
                page = raw.decode("latin-1")

        except Exception as error:

            print("⚠️ NO PUDE LEER LA PÁGINA:", url, error)
            return []

        return self._best_sentences(page, wanted, limit)

    def _best_sentences(self, page, wanted, limit):

        page = re.sub(
            r"(?is)<(script|style|nav|footer|header|aside|table)\b.*?</\1>",
            " ",
            page
        )
        paragraphs = re.findall(r"(?is)<(?:p|li)\b[^>]*>(.*?)</(?:p|li)>", page)

        scored = []

        for position, paragraph in enumerate(paragraphs):

            text = html.unescape(re.sub(r"<[^>]+>", " ", paragraph))
            text = re.sub(r"\[\s*\d+\s*\]", "", text)
            text = re.sub(r"\s+", " ", text).strip()

            for sentence in re.split(r"(?<=[.!?])\s+", text):

                if not 40 <= len(sentence) <= 350:
                    continue
                if not is_spanish(sentence):
                    continue

                hits = len(wanted & keywords(sentence))

                if hits:
                    # A igual relevancia gana lo que sale antes: las
                    # páginas suelen empezar por lo más importante.
                    scored.append((-hits, position, sentence))

        scored.sort()
        return [sentence for _, _, sentence in scored[:limit]]

    def format_results(self, results):

        if not results:
            return ""

        text = ""

        for index, result in enumerate(
            results,
            1
        ):

            text += (
                f"\nRESULTADO {index}\n"
            )

            text += (
                f"TÍTULO: "
                f"{result.get('title', '')}\n"
            )

            text += (
                f"CONTENIDO: "
                f"{result.get('body', '')}\n"
            )

            text += (
                f"URL: "
                f"{result.get('url', '')}\n"
            )

        return text
