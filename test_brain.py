from core.brain import Brain


brain = Brain()


while True:

    text = input("Tú: ")

    if text.lower() == "salir":
        break

    result = brain.think(text)

    print()
    print("RESULTADO:")
    print(result)
    print()