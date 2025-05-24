import os
import threading
import customtkinter as ctk
import tkinter.messagebox as mb
from PIL import Image, ImageTk
from migrator import DirectMigrator

class MigrationApp(ctk.CTk):
    WINDOW_SIZE = "800x200"
    BUTTON_SIZE = (150, 50)
    ICON_SIZE = (64, 64)
    COLORS = {
        'primary': '#0078D7',
        'primary_hover': '#106EBE',
        'primary_light': '#4898E7',
        'background': 'white',
        'text': '#333333',
        'progress_bg': '#E5E5E5'
    }

    def __init__(self):
        super().__init__()
        self.title("Migrador365")

        ctk.set_appearance_mode("light")
        ico_path = os.path.join("gui", "assets", "icono.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.geometry(self.WINDOW_SIZE)
        self.resizable(False, False)
        self.configure(fg_color=self.COLORS['background'])

        self.google_icon   = self._load_icon(os.path.join("gui", "assets", "googledrive.png"))
        self.onedrive_icon = self._load_icon(os.path.join("gui", "assets", "onedrive.png"))
        self._is_indeterminate = False
        self._pulsing = False

        self._create_widgets()
        # Centramos al final, tras construir todo
        self.after(0, self._center_window)

    def _center_window(self):
        width, height = map(int, self.WINDOW_SIZE.split('x'))
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _load_icon(self, path):
        try:
            img = Image.open(path)
            return ctk.CTkImage(img, size=self.ICON_SIZE)
        except (FileNotFoundError, IOError) as e:
            mb.showerror("Error de Recursos", f"No se encontró la imagen:\n{path}\n\n{e}")
            blank = Image.new("RGBA", self.ICON_SIZE, (255,255,255,0))
            return ctk.CTkImage(blank, size=self.ICON_SIZE)

    def _create_widgets(self):
        # Botón de inicio
        self.start_btn = ctk.CTkButton(
            self, text="Iniciar Migración",
            fg_color=self.COLORS['primary'],
            hover_color=self.COLORS['primary_hover'],
            command=self.start_migration,
            width=self.BUTTON_SIZE[0],
            height=self.BUTTON_SIZE[1]
        )
        self.start_btn.pack(pady=10)

        # Frame con iconos y barra
        frame = ctk.CTkFrame(self, fg_color=self.COLORS['background'])
        frame.pack(pady=10, padx=20, fill='x')
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, image=self.google_icon, text="").grid(row=0, column=0, padx=10)
        self.progress = ctk.CTkProgressBar(
            frame, width=400,
            fg_color=self.COLORS['progress_bg'],
            progress_color=self.COLORS['primary']
        )
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=10, sticky='ew')
        ctk.CTkLabel(frame, image=self.onedrive_icon, text="").grid(row=0, column=2, padx=10)

        # Etiqueta de estado
        self.status_lbl = ctk.CTkLabel(
            self,
            text="Oprime el botón para iniciar la migración",
            text_color=self.COLORS['text']
        )
        self.status_lbl.pack(pady=5)

    def start_migration(self):
        self.start_btn.configure(state="disabled")
        self.status_lbl.configure(text="Iniciando migración...")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._is_indeterminate = True
        self._start_pulse()

        thread = threading.Thread(target=self._run_thread, daemon=True)
        thread.start()

    def _start_pulse(self):
        self._pulsing = True
        self.after(0, self._pulse)

    def _pulse(self):
        if not self._pulsing:
            return
        curr = self.progress.cget('progress_color')
        nxt = self.COLORS['primary_light'] if curr == self.COLORS['primary'] else self.COLORS['primary']
        self.progress.configure(progress_color=nxt)
        self.after(300, self._pulse)

    def _run_thread(self):
        migrator = DirectMigrator(onedrive_folder="")
        def on_global(proc, total, name):
            pct = proc / total
            self.after(0, lambda: self._update_global(pct, name))
        def on_file(sent, total_bytes, name):
            pctf = sent / total_bytes
            size_mb = total_bytes / (1024 * 1024)
            # Mostramos nombre del archivo, porcentaje y tamaño total en MB
            text = f"Subiendo '{name}': {pctf*100:.0f}% de {size_mb:.1f} MB"
            self.after(0, lambda: self.status_lbl.configure(text=text))
        migrator.migrate(
            skip_existing=True,
            progress_callback=on_global,
            file_progress_callback=on_file
        )
        self.after(0, self._on_complete)

    def _update_global(self, pct, name):
        if self._is_indeterminate:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self._is_indeterminate = False
        self.progress.set(pct)
        self.status_lbl.configure(text=f"Migrando: {name} ({pct*100:.0f}%)")

    def _stop_pulse(self):
        self._pulsing = False
        self.progress.configure(progress_color=self.COLORS['primary'])

    def _on_complete(self):
        if self._is_indeterminate:
            self.progress.stop()
        self._stop_pulse()
        self.progress.set(1)
        mb.showinfo("Migración", "Todos los archivos se han transferido con éxito.")
        self.start_btn.configure(state="normal")

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    app = MigrationApp()
    app.run()
