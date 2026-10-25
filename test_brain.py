"""Prueba manual del cerebro; no forma parte de la suite automatizada."""


def main():
    from core.brain import Brain

    brain = Brain()

    while True:
        text = input("Tú: ")
        if text.lower() == "salir":
            break
        print("\nRESULTADO:")
        print(brain.think(text))


if __name__ == "__main__":
    main()
