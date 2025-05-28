# ---------------------------------------------------------------
# Archivo de la Aplicación de Migración GUI
# Autor: Kevin Gonzalez
# Descripción:
#   Contiene la clase MigrationApp que define la interfaz gráfica
#   de usuario para Migrador365. Gestiona la inicialización,
#   eventos de inicio y cancelación de la migración, actualiza
#   el progreso y muestra archivos problemáticos.
# ---------------------------------------------------------------

import os
import threading
import customtkinter as ctk
import tkinter.messagebox as mb
from PIL import Image, ImageTk
from migrator import DirectMigrator, MigrationCancelled,ConnectionLost
from onedrive_service import OneDriveTokenExpired
from archivo import ErrorApp
from utils import resource_path


"""
    Clase principal de la GUI para la aplicación Migrador365.

    Atributos:
        WINDOW_SIZE (str): Tamaño de la ventana en formato "<ancho>x<alto>".
        BUTTON_SIZE (tuple): Dimensiones de los botones (ancho, alto).
        ICON_SIZE (tuple): Tamaño de los iconos (ancho, alto).
        COLORS (dict): Colores usados en la interfaz.
        error_win (ErrorApp | None): Ventana de errores, si está abierta.
        _cancel_event (threading.Event): Evento para señalizar cancelación.
        _last_size_mb (float): Último tamaño de archivo calculado en MB.
        _ui_started (bool): Controla si ya se mostró el botón "Cancelar".
"""
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
    
    """
        Inicializa la ventana principal, carga iconos y crea widgets.

        - Configura la apariencia, tamaño y posición de la ventana.
        - Carga iconos de Google Drive y OneDrive.
        - Construye los widgets de control (botones, labels, progressbar).
    """
    def __init__(self):
        super().__init__()
        self.error_win = None
        self.title("Migracion365")

        self._cancel_event = threading.Event()
        self._last_size_mb = 0.0
        self._ui_started = False

        ctk.set_appearance_mode("light")
        ico_path = resource_path("gui/assets/icono.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.geometry(self.WINDOW_SIZE)
        self.resizable(False, False)
        self.configure(fg_color=self.COLORS['background'])

        self.google_icon = self._load_icon(resource_path("gui/assets/googledrive.png"))
        self.onedrive_icon = self._load_icon(resource_path("gui/assets/onedrive.png"))

        self._create_widgets()
        self.after(0, self._center_window)
        self.after(200, self._show_welcome_message) 

        
    """
        Centra la ventana en la pantalla según WINDOW_SIZE.
    """
    def _center_window(self):
        width, height = map(int, self.WINDOW_SIZE.split('x'))
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")


    def _show_welcome_message(self):
        mb.showinfo(
            "Bienvenido",
            "Bienvenido a Migracion365\n\n"
            "Esta herramienta migrará tus archivos de Google Drive a OneDrive.\n\n"
            "Antes de comenzar, por favor:\n"
            "1. Verifique que tiene conexión a internet estable.\n"
            "2. Asegúrese de que su dispositivo esté cargado o conectado a la corriente.\n"
            "3. No suspenda ni apague su equipo durante la migración"
        )




    """
        Intenta cargar una imagen y convertirla en CTkImage.

        Args:
            path (str): Ruta al archivo de imagen.

        Returns:
            CTkImage: Imagen cargada o un placeholder transparente.
    """
    def _load_icon(self, path):
        try:
            img = Image.open(path)
            return ctk.CTkImage(img, size=self.ICON_SIZE)
        except Exception as e:
            mb.showerror("Error de Recursos", f"No se encontró la imagen:\n{path}\n\n{e}")
            blank = Image.new("RGBA", self.ICON_SIZE, (255,255,255,0))
            return ctk.CTkImage(blank, size=self.ICON_SIZE)


    """
        Construye y posiciona todos los widgets de la interfaz.

        - Botones: Iniciar, Cancelar, Ver archivos problemáticos.
        - Barra de progreso y labels de estado y tamaño.
    """
    def _create_widgets(self):

        self.status_lbl = ctk.CTkLabel(self, text="Oprime iniciar...", text_color=self.COLORS['text'])
        self.status_lbl.pack(pady=(10, 0))

        self.size_lbl = ctk.CTkLabel(self, text="Tamaño: —", text_color=self.COLORS['text'])
        self.size_lbl.pack(pady=(0, 5))


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

 
        self.error_btn = ctk.CTkButton(
            self, text="Ver archivos problemáticos",
            fg_color=self.COLORS['primary_light'], hover_color=self.COLORS['primary_hover'],
            command=self.open_error_log, width=160, height=30
        )
        self.error_btn.place_forget()

  
        btn_frame = ctk.CTkFrame(self, fg_color=self.COLORS['background'])
        btn_frame.pack(pady=(10, 15))

        self.start_btn = ctk.CTkButton(
            btn_frame, text="Iniciar",
            fg_color=self.COLORS['primary'], hover_color=self.COLORS['primary_hover'],
            command=self.start_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.start_btn.grid(row=0, column=0, padx=5)

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancelar",
            fg_color="#636363", hover_color="#030303",
            command=self.cancel_migration, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.cancel_btn.grid(row=0, column=1, padx=5)
        self.cancel_btn.grid_remove()



    """
        Inicia el proceso de migración en un hilo separado.

        - Cierra ventana de errores si está abierta.
        - Limpia archivos temporales y registros previos.
        - Configura la UI (botones, estado, progreso).
        - Inicia animación de pulso y lanza el hilo de migración.
    """
    def start_migration(self):

        if self.error_win and self.error_win.winfo_exists():
            self.error_win.destroy()
            self.error_win = None

        self._ui_started = False
        self.cancel_btn.grid_remove()
        self.error_btn.place_forget()

        for f in ["token.pickle"]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

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
        self._cancel_event.clear()
        self.start_btn.configure(state="disabled")
        self.status_lbl.configure(text="Iniciando migración...")
        self.size_lbl.configure(text="Tamaño: —")

        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._is_indeterminate = True
        self._start_pulse()
        thread = threading.Thread(target=self._run_thread, daemon=True)
        thread.start()


    """
        Señaliza la cancelación y restablece la UI.

        - Establece el evento de cancelación.
        - Elimina archivos de progreso y token.
        - Llama a _reset_ui para actualizar la interfaz.
    """
    def cancel_migration(self):

        self._cancel_event.set()
        for f in ["migration_progress.json", "token.pickle"]:
            try:
                if os.path.exists(f): os.remove(f)
            except Exception:
                pass
        self.after(0, self._reset_ui)


    """
        Restablece los widgets de UI tras cancelación.

        - Detiene animación y configura progressbar a determinate.
        - Oculta botón Cancelar y habilita Iniciar.
        - Actualiza labels de estado y tamaño.
        - Resetea flag _ui_started.
    """
    def _reset_ui(self):
        try:
            self.progress.stop()
        except Exception:
            pass

        self.progress.configure(mode="determinate")
        self.progress.set(0)

        self.cancel_btn.grid_remove()
        self.start_btn.configure(state="normal")

        self.status_lbl.configure(text="Cancelado")
        self.size_lbl.configure(text="Tamaño: —")

        self._ui_started = False


    """
        Abre la ventana de errores si existe un registro.

        - Muestra mensaje si no hay errores.
        - Si ya está abierta, la eleva; si no, crea una nueva.
    """
    def open_error_log(self):
        log = DirectMigrator.ERROR_LOG
        
        if not os.path.exists(log) or os.path.getsize(log) == 0:
            mb.showinfo("Sin archivos problemáticos", "No hay archivos problemáticos.")
            return
        else:

            if not self.error_win or not self.error_win.winfo_exists():
                self.error_win = ErrorApp()
            else:

                self.error_win.lift()
            return
        
        

    """
        Hilo de ejecución que llama a DirectMigrator.migrate().

        - Define callbacks on_global y on_file para actualizar la UI.
        - Gestiona excepciones de cancelación y finalización.
    """
    def _run_thread(self):
        migrator = DirectMigrator(
            onedrive_folder="",
            cancel_event=self._cancel_event
        )

        def on_global(proc, total, name):
            if self._cancel_event.is_set():
                return
            if not self._ui_started:
                self.after(0, self.cancel_btn.grid)
                self._ui_started = True
            pct = proc / total
            self.after(0, lambda: self._update_global(pct, name))

        def on_file(sent, total_bytes, name):
            if self._cancel_event.is_set():
                raise MigrationCancelled()
            pctf = sent / total_bytes
            size_mb = total_bytes / (1024 * 1024)
            self._last_size_mb = size_mb
            self.after(0, lambda: self.size_lbl.configure(text=f"Tamaño: {size_mb:.2f} MB"))
            text = f"Subiendo '{name}': {pctf*100:.0f}%"
            self.after(0, lambda: self.status_lbl.configure(text=text))

        try:
            migrator.migrate(
                skip_existing=True,
                progress_callback=on_global,
                file_progress_callback=on_file
            )
            
        except OneDriveTokenExpired as e:

            self.after(0, lambda: mb.showerror(
                "Autenticación expirada",
                str(e)
            ))

            return
        except ConnectionLost as e:
            # Alertamos al usuario y restablecemos la UI
            self.after(0, lambda: mb.showerror(
                "Conexión perdida",
                f"Se perdió la conexión a Internet:\n{e}"
            ))
            self.after(0, self._reset_ui)
            return
        except MigrationCancelled:
            self.after(0, self._reset_ui)
            return
        

        if not self._cancel_event.is_set():
            self.after(0, self._on_complete)


    """
        Actualiza la progressbar y el label global.

        Args:
            pct (float): Porcentaje completado (0.0 a 1.0).
            name (str): Nombre del archivo o lote actual.
    """
    def _update_global(self, pct, name):
        if self.progress.cget('mode') == 'indeterminate':
            self.progress.stop()
            self.progress.configure(mode="determinate")
        if self._last_size_mb > 0:
            self.size_lbl.configure(text=f"Tamaño: {self._last_size_mb:.2f} MB")
        self.progress.set(pct)
        self.status_lbl.configure(text=f"Migrando: {name} ({pct*100:.0f}%)")
        


    """
        Lógica a ejecutar cuando la migración finaliza correctamente.

        - Detiene animación, muestra botón de errores si existen.
        - Muestra un mensaje de información y habilita el botón Iniciar.
    """
    def _on_complete(self):
        if self.progress.cget('mode') == 'indeterminate':
            self.progress.stop()
        self.progress.set(1)
        self.cancel_btn.grid_remove()
        self._stop_pulse()
        self.status_lbl.configure(text="Oprime iniciar...")
        self.size_lbl.configure(text="Tamaño: —")
        log = DirectMigrator.ERROR_LOG
        if os.path.exists(log) and os.path.getsize(log) > 0:
            self.error_btn.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor='se')
        mb.showinfo("Migración", "Transferencia finalizada. Revisa tu OneDrive.")
        self.start_btn.configure(state="normal")
        
    """
        Inicia la animación pulsante en la progressbar.
    """
    def _start_pulse(self):
        self._pulsing = True
        self.after(0, self._pulse)


    """
        Alterna el color de la progressbar cada 300 ms mientras _pulsing sea True.
    """
    def _pulse(self):

        if not self._pulsing:
            return
        current = self.progress.cget('progress_color')
        new_color = (
            self.COLORS['primary_light']
            if current == self.COLORS['primary']
            else self.COLORS['primary']
        )
        self.progress.configure(progress_color=new_color)
        self.after(300, self._pulse)

    """
        Detiene la animación de pulso y restaura el color original.
    """
    def _stop_pulse(self):
        self._pulsing = False
        self.progress.configure(progress_color=self.COLORS['primary'])

    """
        Inicia el loop principal de la aplicación.
    """
    def run(self):
        self.mainloop()
