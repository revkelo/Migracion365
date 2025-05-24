import os
import threading
import time
import customtkinter as ctk
import tkinter.messagebox as mb
from PIL import Image, ImageTk
from migrator import DirectMigrator

class MigrationApp(ctk.CTk):
    WINDOW_SIZE = "800x250"
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

        # Atributo para guardar el último tamaño (MB) reportado
        self._last_size_mb = 0.0

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

        # Control flags
        self._cancelled = False
        self._ui_started = False  # para mostrar botones al obtener tokens

        self._create_widgets()
        self.error_btn.place_forget()  # ocultar al inicio
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
        except Exception as e:
            mb.showerror("Error de Recursos", f"No se encontró la imagen:\n{path}\n\n{e}")
            blank = Image.new("RGBA", self.ICON_SIZE, (255,255,255,0))
            return ctk.CTkImage(blank, size=self.ICON_SIZE)

    def _create_widgets(self):
        btn_frame = ctk.CTkFrame(self, fg_color=self.COLORS['background'])
        btn_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="Iniciar",
            fg_color=self.COLORS['primary'], hover_color=self.COLORS['primary_hover'],
            command=self.start_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.start_btn.grid(row=0, column=0, padx=5)

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancelar",
            fg_color='#D70000', hover_color='#BE0000',
            command=self.cancel_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.cancel_btn.grid(row=0, column=1, padx=5)
        self.cancel_btn.grid_remove()

        frame = ctk.CTkFrame(self, fg_color=self.COLORS['background'])
        frame.pack(pady=5, padx=20, fill='x')
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, image=self.google_icon, text="").grid(row=0, column=0, padx=10)
        self.progress = ctk.CTkProgressBar(
            frame, width=400,
            fg_color=self.COLORS['progress_bg'], progress_color=self.COLORS['primary']
        )
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=10, sticky='ew')
        ctk.CTkLabel(frame, image=self.onedrive_icon, text="").grid(row=0, column=2, padx=10)

        self.status_lbl = ctk.CTkLabel(self, text="Oprime iniciar...", text_color=self.COLORS['text'])
        self.status_lbl.pack(pady=(5,0))

        self.size_lbl = ctk.CTkLabel(self, text="Tamaño: —", text_color=self.COLORS['text'])
        self.size_lbl.pack(pady=(0,5))

        self.error_btn = ctk.CTkButton(
            self, text="Ver registro",
            fg_color=self.COLORS['primary_light'], hover_color=self.COLORS['primary_hover'],
            command=self.open_error_log, width=120, height=30
        )

    def start_migration(self):
        prog_file = "migration_progress.json"
        if os.path.exists(prog_file) and os.path.getsize(prog_file) > 0:
            continuar = mb.askyesno(
                "Progreso detectado",
                "Se encontró un progreso de migración previo.\n¿Deseas reanudar donde lo dejaste?"
            )
            if not continuar:
                try:
                    with open(prog_file, 'w', encoding='utf-8'):
                        pass
                except Exception as e:
                    mb.showwarning("Aviso", f"No se pudo reiniciar {prog_file}:\n{e}")

        log_file = DirectMigrator.ERROR_LOG
        if os.path.exists(log_file):
            try:
                with open(log_file, 'w', encoding='utf-8'):
                    pass
            except Exception as e:
                mb.showwarning("Aviso", f"No se pudo limpiar {log_file}:\n{e}")

        self._cancelled = False
        self._ui_started = False
        self.start_btn.configure(state="disabled")
        self.status_lbl.configure(text="Iniciando migración...")
        self.size_lbl.configure(text="Tamaño: —")
        self.progress.configure(mode="indeterminate")
        self.progress.start()

        thread = threading.Thread(target=self._run_thread, daemon=True)
        thread.start()

    def cancel_migration(self):
        self._cancelled = True
        for f in ["migration_progress.json", "token.pickle"]:
            try:
                if os.path.exists(f): os.remove(f)
            except Exception:
                pass
        self.status_lbl.configure(text="Cancelado")
        self.cancel_btn.configure(state="disabled")

    def open_error_log(self):
        log = DirectMigrator.ERROR_LOG
        if os.path.exists(log) and os.path.getsize(log) > 0:
            try:
                os.startfile(log)
            except Exception:
                mb.showinfo("Registro de errores", f"Abrir: {log}")

    def _run_thread(self):
        migrator = DirectMigrator(onedrive_folder="")

        def on_global(proc, total, name):
            if self._cancelled: return
            if not self._ui_started:
                self.cancel_btn.grid()
                self._ui_started = True
            pct = proc / total
            self.after(0, lambda: self._update_global(pct, name))

        def on_file(sent, total_bytes, name):
            if self._cancelled: return
            pctf = sent / total_bytes
            size_mb = total_bytes / (1024 * 1024)
            self._last_size_mb = size_mb
            self.after(0, lambda: self.size_lbl.configure(text=f"Tamaño: {size_mb:.2f} MB"))
            text = f"Subiendo '{name}': {pctf*100:.0f}%"
            self.after(0, lambda: self.status_lbl.configure(text=text))

        migrator.migrate(
            skip_existing=True,
            progress_callback=on_global,
            file_progress_callback=on_file
        )
        self.after(0, self._on_complete)

    def _update_global(self, pct, name):
        if self.progress.cget('mode') == 'indeterminate':
            self.progress.stop()
            self.progress.configure(mode="determinate")
        if self._last_size_mb > 0:
            self.size_lbl.configure(text=f"Tamaño: {self._last_size_mb:.2f} MB")
        self.progress.set(pct)
        self.status_lbl.configure(text=f"Migrando: {name} ({pct*100:.0f}%)")

    def _on_complete(self):
        if self.progress.cget('mode') == 'indeterminate':
            self.progress.stop()
        self.progress.set(1)
        self.cancel_btn.grid_remove()
        log = DirectMigrator.ERROR_LOG
        if os.path.exists(log) and os.path.getsize(log) > 0:
            self.error_btn.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor='se')
        mb.showinfo("Migración", "Transferencia finalizada.")
        self.start_btn.configure(state="normal")

    def run(self):
        self.mainloop()

