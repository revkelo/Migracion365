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
        self._is_indeterminate = False
        self._pulsing = False
        self._paused = False
        self._cancelled = False

        self._create_widgets()
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
        btn_frame = ctk.CTkFrame(self, fg_color=self.COLORS['background'])
        btn_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="Iniciar",
            fg_color=self.COLORS['primary'], hover_color=self.COLORS['primary_hover'],
            command=self.start_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.start_btn.grid(row=0, column=0, padx=5)

        self.pause_btn = ctk.CTkButton(
            btn_frame, text="Pausar",
            fg_color=self.COLORS['primary_light'], hover_color=self.COLORS['primary_hover'],
            command=self.pause_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.pause_btn.grid(row=0, column=1, padx=5)

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancelar",
            fg_color='#D70000', hover_color='#BE0000',
            command=self.cancel_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.cancel_btn.grid(row=0, column=2, padx=5)

        # Progress and icons
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

        # Error log button bottom right
        self.error_btn = ctk.CTkButton(
            self, text="Ver errores",
            fg_color=self.COLORS['primary_light'], hover_color=self.COLORS['primary_hover'],
            command=self.open_error_log, width=120, height=30
        )
        self.error_btn.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor='se')

    def start_migration(self):
        self._paused = False
        self._cancelled = False
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(text="Pausar")
        self.status_lbl.configure(text="Iniciando migración...")
        self.size_lbl.configure(text="Tamaño: —")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._is_indeterminate = True
        self._start_pulse()

        thread = threading.Thread(target=self._run_thread, daemon=True)
        thread.start()

    def pause_migration(self):
        if not self._paused:
            self._paused = True
            self.pause_btn.configure(text="Reanudar")
            self.status_lbl.configure(text="Pausado")
        else:
            self._paused = False
            self.pause_btn.configure(text="Pausar")
            self.status_lbl.configure(text="Reanudando...")

    def cancel_migration(self):
        self._cancelled = True
        self.status_lbl.configure(text="Cancelando...")
        self.pause_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")

    def open_error_log(self):
        log = DirectMigrator.ERROR_LOG
        if os.path.exists(log):
            try:
                os.startfile(log)
            except Exception:
                mb.showinfo("Errores", f"Abrir: {log}")
        else:
            mb.showinfo("Errores", "No hay errores registrados.")

    def _start_pulse(self):
        self._pulsing = True
        self.after(0, self._pulse)

    def _pulse(self):
        if not self._pulsing or self._paused:
            return
        curr = self.progress.cget('progress_color')
        nxt = self.COLORS['primary_light'] if curr == self.COLORS['primary'] else self.COLORS['primary']
        self.progress.configure(progress_color=nxt)
        self.after(300, self._pulse)

    def _run_thread(self):
        migrator = DirectMigrator(onedrive_folder="")
        def on_global(proc, total, name):
            if self._cancelled: return
            while self._paused:
                time.sleep(0.1)
            pct = proc / total
            self.after(0, lambda: self._update_global(pct, name))
        def on_file(sent, total_bytes, name):
            if self._cancelled: return
            while self._paused:
                time.sleep(0.1)
            pctf = sent / total_bytes
            size_mb = total_bytes / (1024 * 1024)
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
        mb.showinfo("Migración", "Transferencia finalizada.")
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="normal", text="Pausar")
        self.cancel_btn.configure(state="normal")

    def run(self):
        self.mainloop()

if __name__ == "__main__":
    app = MigrationApp()
    app.run()
