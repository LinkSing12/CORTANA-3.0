import ctypes


class MediaController:

    # =========================================================
    # WINDOWS AUDIO
    # =========================================================

    def _send_key(self, key):

        ctypes.windll.user32.keybd_event(
            key,
            0,
            0,
            0
        )

        ctypes.windll.user32.keybd_event(
            key,
            0,
            2,
            0
        )

    # =========================================================
    # VOLUMEN EXACTO
    # =========================================================

    def volume_set(self, percentage):

        try:

            percentage = int(percentage)

            if percentage < 0:
                percentage = 0

            if percentage > 100:
                percentage = 100

            for _ in range(50):
                self._send_key(0xAE)

            steps = round(percentage / 2)

            for _ in range(steps):
                self._send_key(0xAF)

            return f"Volumen establecido en {percentage}%."

        except Exception as error:

            print(
                "Error estableciendo volumen:",
                error
            )

            return "No pude establecer el volumen."

    # =========================================================
    # VOLUMEN ARRIBA
    # =========================================================

    def volume_up(self):

        try:

            for _ in range(2):

                self._send_key(0xAF)

            return "Volumen aumentado."

        except Exception as error:

            print(
                "Error subiendo volumen:",
                error
            )

            return "No pude subir el volumen."

    # =========================================================
    # VOLUMEN ABAJO
    # =========================================================

    def volume_down(self):

        try:

            for _ in range(2):

                self._send_key(0xAE)

            return "Volumen reducido."

        except Exception as error:

            print(
                "Error bajando volumen:",
                error
            )

            return "No pude bajar el volumen."

    # =========================================================
    # SILENCIO
    # =========================================================

    def volume_mute(self):

        try:

            self._send_key(0xAD)

            return "Silencio activado."

        except Exception as error:

            print(
                "Error activando silencio:",
                error
            )

            return "No pude activar el silencio."

    # =========================================================
    # QUITAR SILENCIO
    # =========================================================

    def volume_unmute(self):

        try:

            self._send_key(0xAD)

            return "Silencio desactivado."

        except Exception as error:

            print(
                "Error quitando silencio:",
                error
            )

            return "No pude quitar el silencio."

    # =========================================================
    # PLAY
    # =========================================================

    def play(self):

        try:

            self._send_key(0xB3)

            return "Reproducción iniciada."

        except Exception as error:

            print(
                "Error reproduciendo:",
                error
            )

            return "No pude iniciar la reproducción."

    # =========================================================
    # PAUSA
    # =========================================================

    def pause(self):

        try:

            self._send_key(0xB3)

            return "Reproducción pausada."

        except Exception as error:

            print(
                "Error pausando:",
                error
            )

            return "No pude pausar."

    # =========================================================
    # SIGUIENTE
    # =========================================================

    def next(self):

        try:

            self._send_key(0xB0)

            return "Siguiente."

        except Exception as error:

            print(
                "Error pasando al siguiente:",
                error
            )

            return "No pude pasar al siguiente."

    # =========================================================
    # ANTERIOR
    # =========================================================

    def previous(self):

        try:

            self._send_key(0xB1)

            return "Anterior."

        except Exception as error:

            print(
                "Error volviendo al anterior:",
                error
            )

            return "No pude volver al anterior."
