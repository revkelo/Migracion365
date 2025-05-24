import threading
import customtkinter as ctk
import os
from migrator import DirectMigrator

class MigrationApp(ctk.CTk):
    """Interfaz gráfica para la migración usando DirectMigrator."""
    WINDOW_SIZE = "800x300"
    BUTTON_SIZE = (150, 50)
    COLORS = {
        'primary': '#0078D7',
        'primary_hover': '#106EBE',
        'background': 'white',
        'text': '#333333',
        'progress_bg': '#E5E5E5'
    }

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        if os.path.exists("./Gui/icono.ico"): self.iconbitmap("./Gui/icono.ico")
        self.title("Migración Directa")
        self.geometry(self.WINDOW_SIZE)
        self.resizable(False, False)
        self.configure(fg_color=self.COLORS['background'])
        self._create_widgets()

    def _create_widgets(self):
        self.start_btn = ctk.CTkButton(
            self,
            text="Iniciar Migración",
            fg_color=self.COLORS['primary'],
            hover_color=self.COLORS['primary_hover'],
            command=self.start_migration,
            width=self.BUTTON_SIZE[0],
            height=self.BUTTON_SIZE[1]
        )
        self.start_btn.pack(pady=20)

        self.progress = ctk.CTkProgressBar(self, width=600)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.status_lbl = ctk.CTkLabel(self, text="Esperando...")
        self.status_lbl.pack(pady=10)

    def start_migration(self):
        self.start_btn.configure(state="disabled")
        self.status_lbl.configure(text="Iniciando migración...")
        thread = threading.Thread(target=self._run_migration_thread, daemon=True)
        thread.start()

    def _run_migration_thread(self):
        migrator = DirectMigrator(onedrive_folder="")
        # Llamar al método correcto de migración
        migrator.migrate(skip_existing=True)
        self.after(0, self._on_complete)

    def _on_complete(self):
        self.status_lbl.configure(text="Migración completada")
        self.start_btn.configure(state="normal")
        self.progress.set(1)

    def run(self):
        self.mainloop()

# main.py
from gui import MigrationApp

if __name__ == "__main__":
    app = MigrationApp()
    app.run()
