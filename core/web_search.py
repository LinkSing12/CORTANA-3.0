from ddgs import DDGS


class WebSearch:

    def __init__(self):

        self.max_results = 5
        self.timeout = 8

    def search(self, query):

        query = query.strip()

        if not query:
            return []

        print()
        print("🌐 BUSCANDO EN INTERNET:")
        print(query)

        try:

            results = DDGS(
                timeout=self.timeout
            ).text(
                query,
                region="wt-wt",
                safesearch="moderate",
                max_results=self.max_results
            )

            if not results:
                print("❌ No encontré resultados.")
                return []

            cleaned = []

            for result in results:

                title = result.get(
                    "title",
                    ""
                )

                body = result.get(
                    "body",
                    ""
                )

                url = result.get(
                    "href",
                    ""
                )

                if not title and not body:
                    continue

                cleaned.append({
                    "title": title,
                    "body": body,
                    "url": url
                })

            print(
                f"✅ RESULTADOS ENCONTRADOS: {len(cleaned)}"
            )

            return cleaned

        except Exception as error:

            print()
            print(
                "❌ ERROR BUSCANDO EN INTERNET:",
                error
            )

            return []

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
