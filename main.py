import threading

from core.assistant import Cortana
from interface.window import CortanaWindow


def main():

    window = CortanaWindow()

    cortana = Cortana()
    cortana.set_interface(window)

    # Lo que escribas en la ventana se procesa exactamente igual
    # que un comando por voz o por consola (mismo respond()).
    window.set_on_submit(cortana.respond)

    # Cortana (consola + hilo de voz) corre en su propio hilo,
    # porque Tkinter (la ventana) solo puede correr su mainloop
    # en el hilo principal.
    cortana_thread = threading.Thread(
        target=cortana.start,
        daemon=True
    )
    cortana_thread.start()

    window.ready()
    window.run()


if __name__ == "__main__":
    main()
