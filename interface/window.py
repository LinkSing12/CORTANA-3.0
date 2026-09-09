import tkinter as tk


class CortanaWindow:

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
        # ESCRIBIR ORDEN (texto, además de voz)
        # =====================================================

        # Se guarda como callback externo (asignado con
        # set_on_submit) para no acoplar la ventana a Cortana.
        self._on_submit = None

        self.input_frame = tk.Frame(
            self.root,
            bg="#0b0f14"
        )

        self.input_frame.pack(
            fill="x",
            padx=50,
            pady=(0, 10)
        )

        self.input_entry = tk.Entry(
            self.input_frame,
            font=("Segoe UI", 13),
            bg="#151b23",
            fg="white",
            insertbackground="white",
            relief="flat"
        )

        self.input_entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=8,
            padx=(0, 8)
        )

        self.input_entry.bind(
            "<Return>",
            self._handle_submit
        )

        self.send_button = tk.Button(
            self.input_frame,
            text="Enviar",
            font=("Segoe UI", 11, "bold"),
            bg="#00d9ff",
            fg="#0b0f14",
            relief="flat",
            command=self._handle_submit
        )

        self.send_button.pack(
            side="left",
            ipady=6,
            ipadx=10
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
    # ENTRADA DE TEXTO
    # =========================================================

    def set_on_submit(self, callback):
        """
        Registra la función que se llama cuando el usuario escribe
        algo y presiona Enter o el botón "Enviar". La función se
        ejecuta en un hilo aparte para no congelar la ventana
        mientras Cortana procesa la orden (puede tardar por Ollama,
        internet, o la voz hablando la respuesta).
        """
        self._on_submit = callback

    def _handle_submit(self, event=None):

        text = self.input_entry.get().strip()

        if not text:
            return

        self.input_entry.delete(0, tk.END)

        if not self._on_submit:
            return

        import threading

        threading.Thread(
            target=self._on_submit,
            args=(text,),
            daemon=True
        ).start()

    # =========================================================
    # ESTADO
    # =========================================================

    def set_status(self, text):

        self.root.after(
            0,
            lambda: self.status.config(text=text)
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
