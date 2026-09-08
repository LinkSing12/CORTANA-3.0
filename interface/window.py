import tkinter as tk


class CortanaWindow:

    # =========================================================
    # ESTADOS DEL "ROSTRO" (indicador visual de ánimo/actividad)
    # Cada estado tiene un texto y un color. assistant.py llama
    # a set_face_state("ready"/"listening"/"thinking"/"speaking"/
    # "waiting"/"processing"/"error") en cada paso del flujo.
    # =========================================================

    FACE_STATES = {
        "ready": ("● CORTANA LISTA", "#00ff88"),
        "listening": ("● ESCUCHANDO", "#00d9ff"),
        "processing": ("● PROCESANDO", "#ffd166"),
        "thinking": ("● PENSANDO", "#ffd166"),
        "speaking": ("● HABLANDO", "#00d9ff"),
        "waiting": ("● ESPERANDO CONFIRMACIÓN", "#ff9f1c"),
        "error": ("● ERROR", "#ff4d4d"),
    }

    def __init__(self):

        self.root = tk.Tk()

        self.root.title("CORTANA 3.0")
        self.root.geometry("700x650")
        self.root.configure(bg="#0b0f14")
        self.root.resizable(False, False)

        # =====================================================
        # TITULO
        # =====================================================

        self.title = tk.Label(
            self.root,
            text="CORTANA 3.0",
            font=("Segoe UI", 28, "bold"),
            fg="#00d9ff",
            bg="#0b0f14"
        )

        self.title.pack(pady=(25, 2))

        self.subtitle = tk.Label(
            self.root,
            text="IA LOCAL",
            font=("Segoe UI", 11),
            fg="#7f8c9a",
            bg="#0b0f14"
        )

        self.subtitle.pack()

        # =====================================================
        # ESTADO
        # =====================================================

        self.status = tk.Label(
            self.root,
            text="● CORTANA LISTA",
            font=("Segoe UI", 16, "bold"),
            fg="#00ff88",
            bg="#0b0f14"
        )

        self.status.pack(pady=20)

        # =====================================================
        # ESCUCHADO
        # =====================================================

        self.listened_title = tk.Label(
            self.root,
            text="ESCUCHADO",
            font=("Segoe UI", 10, "bold"),
            fg="#7f8c9a",
            bg="#0b0f14"
        )

        self.listened_title.pack(
            anchor="w",
            padx=50
        )

        self.listened = tk.Label(
            self.root,
            text="Esperando una orden...",
            font=("Segoe UI", 13),
            fg="white",
            bg="#151b23",
            anchor="w",
            padx=15
        )

        self.listened.pack(
            fill="x",
            padx=50,
            pady=(5, 12),
            ipady=8
        )

        # =====================================================
        # ANALIZANDO
        # =====================================================

        self.analysis_title = tk.Label(
            self.root,
            text="ANALIZANDO",
            font=("Segoe UI", 10, "bold"),
            fg="#7f8c9a",
            bg="#0b0f14"
        )

        self.analysis_title.pack(
            anchor="w",
            padx=50
        )

        self.analysis = tk.Label(
            self.root,
            text="Esperando...",
            font=("Segoe UI", 13),
            fg="white",
            bg="#151b23",
            anchor="w",
            padx=15
        )

        self.analysis.pack(
            fill="x",
            padx=50,
            pady=(5, 12),
            ipady=8
        )

        # =====================================================
        # INTENCION
        # =====================================================

        self.intent_title = tk.Label(
            self.root,
            text="INTENCIÓN",
            font=("Segoe UI", 10, "bold"),
            fg="#7f8c9a",
            bg="#0b0f14"
        )

        self.intent_title.pack(
            anchor="w",
            padx=50
        )

        self.intent = tk.Label(
            self.root,
            text="Esperando...",
            font=("Segoe UI", 12),
            fg="white",
            bg="#151b23",
            anchor="w",
            padx=15
        )

        self.intent.pack(
            fill="x",
            padx=50,
            pady=(5, 8),
            ipady=5
        )

        # =====================================================
        # OBJETIVO
        # =====================================================

        self.target_title = tk.Label(
            self.root,
            text="OBJETIVO",
            font=("Segoe UI", 10, "bold"),
            fg="#7f8c9a",
            bg="#0b0f14"
        )

        self.target_title.pack(
            anchor="w",
            padx=50
        )

        self.target = tk.Label(
            self.root,
            text="Esperando...",
            font=("Segoe UI", 12),
            fg="white",
            bg="#151b23",
            anchor="w",
            padx=15
        )

        self.target.pack(
            fill="x",
            padx=50,
            pady=(5, 12),
            ipady=5
        )

        # =====================================================
        # RESPUESTA
        # =====================================================

        self.response_title = tk.Label(
            self.root,
            text="CORTANA",
            font=("Segoe UI", 10, "bold"),
            fg="#7f8c9a",
            bg="#0b0f14"
        )

        self.response_title.pack(
            anchor="w",
            padx=50
        )

        self.response = tk.Label(
            self.root,
            text="¿Qué quieres hacer?",
            font=("Segoe UI", 13),
            fg="#00d9ff",
            bg="#151b23",
            anchor="w",
            padx=15
        )

        self.response.pack(
            fill="x",
            padx=50,
            pady=(5, 12),
            ipady=8
        )

        # =====================================================
        # PIE
        # =====================================================

        self.footer = tk.Label(
            self.root,
            text="● SISTEMA OPERATIVO",
            font=("Segoe UI", 9),
            fg="#5f6b78",
            bg="#0b0f14"
        )

        self.footer.pack(
            side="bottom",
            pady=10
        )

    # =========================================================
    # ESTADO
    # =========================================================

    def set_status(self, text):

        self.root.after(
            0,
            lambda: self.status.config(text=text)
        )

    # =========================================================
    # ROSTRO (indicador de estado/ánimo)
    # =========================================================
    # Reutiliza el mismo label de "ESTADO" (self.status), cambiando
    # texto y color según la etapa del flujo. Si assistant.py llama
    # a set_status() y set_face_state() en la misma respuesta, gana
    # la última llamada — es el comportamiento esperado, ya que
    # ambas reflejan lo mismo (el estado actual de Cortana).
    # =========================================================

    def set_face_state(self, state):

        text, color = self.FACE_STATES.get(
            str(state).lower().strip(),
            (f"● {str(state).upper()}", "#7f8c9a")
        )

        self.root.after(
            0,
            lambda: self.status.config(text=text, fg=color)
        )

    # =========================================================
    # ESCUCHADO
    # =========================================================

    def set_listened(self, text):

        self.root.after(
            0,
            lambda: self.listened.config(text=text)
        )

    # =========================================================
    # ANALISIS
    # =========================================================

    def set_analysis(self, text):

        self.root.after(
            0,
            lambda: self.analysis.config(text=text)
        )

    # =========================================================
    # INTENCION
    # =========================================================

    def set_intent(self, text):

        self.root.after(
            0,
            lambda: self.intent.config(text=text)
        )

    # =========================================================
    # OBJETIVO
    # =========================================================

    def set_target(self, text):

        self.root.after(
            0,
            lambda: self.target.config(text=text)
        )

    # =========================================================
    # RESPUESTA
    # =========================================================

    def set_response(self, text):

        self.root.after(
            0,
            lambda: self.response.config(text=text)
        )

    # =========================================================
    # LISTA
    # =========================================================

    def ready(self):

        self.set_status("● CORTANA LISTA")


    # =========================================================
    # EJECUTAR INTERFAZ
    # =========================================================

    def run(self):

        self.root.mainloop()


if __name__ == "__main__":

    app = CortanaWindow()

    app.ready()

    app.run()