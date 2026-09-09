"""
Prueba aislada del control de Winamp, sin pasar por Cortana completa.

Uso (en tu PC, con Winamp ya instalado):

    python test_winamp.py

Ábrelo con Winamp cerrado primero, para probar también que Cortana
lo abre sola.
"""

from windows.winamp import WinampController


def main():

    # AJUSTA esta carpeta a donde tengas tu música real:
    winamp = WinampController(
        music_folders=[r"C:\Users\junel\Music"]
    )

    print("¿Winamp está corriendo?", winamp.is_running())

    print("\n--- Probando abrir Winamp si no está abierto ---")
    print("ensure_open():", winamp.ensure_open())

    print("\n--- Probando reproducir por nombre ---")
    nombre = input("Nombre (o parte del nombre) de una canción que SÍ tengas: ")
    print(winamp.play_by_name(nombre))

    input("\nPresiona Enter cuando quieras probar reproducir por número...")

    print("\n--- Probando reproducir por número ---")
    print("Canciones en la lista actual:", winamp.get_playlist_length())
    numero = input("Número de canción a reproducir: ")
    print(winamp.play_by_number(numero))


if __name__ == "__main__":
    main()
