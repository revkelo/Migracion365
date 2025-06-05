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
from PIL import Image
from google_service import GoogleService
from migrator import DirectMigrator, MigrationCancelled,ConnectionLost
from onedrive_service import OneDriveTokenExpired
from archivo import ErrorApp
from utils import ruta_absoluta
import pygame



"""
Clase principal de la GUI para la aplicación Migrador365.

Atributos:
    WINDOW_SIZE (str): Tamaño de la ventana en formato "<ancho>x<alto>".
    BUTTON_SIZE (tuple): Dimensiones de los botones (ancho, alto).
    ICON_SIZE (tuple): Tamaño de los íconos (ancho, alto).
    COLORS (dict): Colores usados en la interfaz.
    error_win (ErrorApp | None): Ventana de errores, si está abierta.
    _cancel_event (threading.Event): Evento para señalizar cancelación.
    _last_size_mb (float): Último tamaño de archivo calculado en MB.
    _ui_started (bool): Controla si ya se mostró el botón "Cancelar".
    _google_auth_url (str | None): URL de autenticación de Google (temporal).
    _google_flow: Objeto de flujo OAuth de Google (si se usa).
    boton_reabrir_link: Widget para reabrir enlace de autenticación (si se quiere).
    _auth_url (str | None): URL genérica de autenticación (por ejemplo, Google o OneDrive).
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

    - Crea instancias de variables de estado.
    - Carga íconos de Google Drive y OneDrive.
    - Llama a _create_widgets para construir la UI.
    - Centra la ventana y muestra un mensaje de bienvenida.
    """
    def __init__(self):
        super().__init__()
        self.error_win = None
        self.title("Migracion365")
        self._google_auth_url = None    
        self._google_flow = None      
        self.boton_reabrir_link = None 
        self._cancel_event = threading.Event()
        self._is_running = False
        self._auth_url = None
        self._last_size_mb = 0.0
        self._ui_started = False

        ctk.set_appearance_mode("light")
        ico_path = ruta_absoluta("gui/assets/icono.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.geometry(self.WINDOW_SIZE)
        self.resizable(False, False)
        self.configure(fg_color=self.COLORS['background'])

        self.google_icon = self.cargar_icono(ruta_absoluta("gui/assets/googledrive.png"))
        self.onedrive_icon = self.cargar_icono(ruta_absoluta("gui/assets/onedrive.png"))

        self.crear_widgets()
        try:
            pygame.mixer.init()
        except Exception:
            pass
        self.after(0, self._centrar_ventana)
        self.after(200, self.mensaje_bienvenida) 





    def _play_notification(self, ruta_mp3: str):
        """Reproduce el MP3 en un hilo para no congelar la GUI."""
        def _play():
            try:
                # Cargar el MP3; si está sonando otro, lo detiene y reproduce éste.
                pygame.mixer.music.load(ruta_mp3)
                pygame.mixer.music.set_volume(0.3)
                pygame.mixer.music.play()
            except Exception:
                pass

        # Lo lanzamos en daemon para que no bloquee la ventana
        threading.Thread(target=_play, daemon=True).start()

    """
    Centra la ventana en la pantalla según WINDOW_SIZE.

    Calcula el offset (x, y) basado en el tamaño real de pantalla
    y el tamaño deseado de la ventana.
    """
    def _centrar_ventana(self):
        width, height = map(int, self.WINDOW_SIZE.split('x'))
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    """
    Mensaje de bienvenida al iniciar el aplicativo
    """
    def mensaje_bienvenida(self):
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
    Intenta cargar una imagen desde disco y convertirla en CTkImage.

    Args:
        path (str): Ruta al archivo de imagen.

    Returns:
        CTkImage: Imagen cargada o un placeholder transparente
                    si ocurre algún error.
    """
    def cargar_icono(self, path):
        try:
            img = Image.open(path)
            return ctk.CTkImage(img, size=self.ICON_SIZE)
        except Exception as e:
            mb.showerror("Error de Recursos", f"No se encontró la imagen:\n{path}\n\n{e}")
            blank = Image.new("RGBA", self.ICON_SIZE, (255,255,255,0))
            return ctk.CTkImage(blank, size=self.ICON_SIZE)


    """
    Construye y posiciona todos los widgets de la interfaz.

    - status_lbl: Label para mostrar mensajes de estado.
    - size_lbl: Label para mostrar el tamaño actual de archivo.
    - ProgressBar: Barra de progreso con iconos de Google Drive y OneDrive.
    - Buttons: Iniciar, Cancelar y Ver archivos problemáticos.
    - auth_url_lbl: Label informativo para reautenticación.
    """
    def crear_widgets(self):

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
            command=self.iniciar_migracion, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.start_btn.grid(row=0, column=0, padx=5)

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancelar",
            fg_color="#636363", hover_color="#030303",
            command=self.cancelar_migracion, width=self.BUTTON_SIZE[0], height=self.BUTTON_SIZE[1]
        )
        self.cancel_btn.grid(row=0, column=1, padx=5)
        self.cancel_btn.grid_remove()
        
        self.auth_url_lbl = ctk.CTkLabel(
            self,
            text="Reinicia la aplicación si no autenticaste correctamente",
            text_color="#000000",
            fg_color="#E5F0FF",
            corner_radius=8,
            padx=2,
            pady=2,
            wraplength=1000,
            justify="center"
        )
        self.auth_url_lbl.place_forget()


    """
    Inicia el proceso de migración en un hilo separado.

    Pasos:
    1. Si ya está corriendo, retorna sin hacer nada.
    2. Cierra ventana de errores si existe.
    3. Limpia archivos de token y progreso previos.
    4. Configura la UI: deshabilita "Iniciar", oculta botón de errores,
        muestra "Cancelar" cuando corresponda.
    5. Cambia la barra de progreso a modo indeterminado y la inicia.
    6. Crea un hilo daemonizado que ejecuta _run_thread().
    7. Muestra el label de reautenticación (auth_url_lbl).
    """

        
    def iniciar_migracion(self):

        if self._is_running:
            return

        self._is_running = True
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
        self.pulsos_carga()
        thread = threading.Thread(target=self._run_hilo, daemon=True)
        thread.start()
        self.auth_url_lbl.place(relx=0.5, rely=0.90, anchor="center")


    """
    Señaliza la cancelación de la migración y restablece la UI.

    - Establece el evento de cancelación (self._cancel_event.set()).
    - Elimina archivos de token (token.pickle) para reiniciar autenticación.
    - Llama a _reset_ui usando after(0) para asegurar que la UI se actualice
        en el hilo principal de Tkinter.
    """
    def cancelar_migracion(self):

        self._cancel_event.set()
        for f in [ "token.pickle"]:
            try:
                if os.path.exists(f): os.remove(f)
            except Exception:
                pass
        self.after(0, self.resetear_ui)


    """
    Restablece los widgets de UI tras cancelación o error.

    - Detiene animación de progressbar y cambia a modo determinate.
    - Oculta el botón Cancelar, habilita el botón Iniciar.
    - Actualiza labels de estado y tamaño.
    - Resetea el flag _ui_started para futuros procesos.
    """
    def resetear_ui(self):
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
        try:
            self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
        except Exception:
            pass
        self._bring_to_front
        self.auth_url_lbl.place_forget()
        self._ui_started = False


    """
    Abre la ventana de errores (ErrorApp) si existe un registro de errores.

    - Verifica que DirectMigrator.ERROR_LOG exista y no esté vacío.
    - Si no hay errores, muestra un messagebox informativo.
    - Si ya está abierta la ventana de errores, la trae al frente (lift).
    - Si no está abierta, crea una nueva instancia de ErrorApp.
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
    Llama la ventana al frente
    """
    def _bring_to_front(self):
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(100, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    """
    Hilo de ejecución que llama a DirectMigrator.migrate().

    - Define callbacks on_global y on_file para actualizar la UI.
    - Gestiona excepciones de OneDriveTokenExpired, ConnectionLost o MigrationCancelled.
    - Al finalizar, restablece el flag _is_running y, si fue exitoso, llama a _on_complete.
    """
    def _run_hilo(self):

        """
        Callback para progreso global.

        Args:
            proc (int): Cantidad de elementos migrados hasta el momento.
            total (int): Total de elementos a migrar.
            name (str): Nombre del archivo o carpeta actual.
        """
        def en_general(proc, total, name):
            if self._cancel_event.is_set():
                return
            if not self._ui_started:
                self.after(0, self.cancel_btn.grid)
                self._ui_started = True
            pct = proc / total
            self.after(0, lambda: self._subida_global(pct, name))


        """
        Callback para progreso de archivo individual.

        Args:
            sent (int): Bytes enviados hasta el momento.
            total_bytes (int): Tamaño total del archivo en bytes.
            name (str): Nombre del archivo.
        """
        def en_archivo(sent, total_bytes, name):
            if self._cancel_event.is_set():
                raise MigrationCancelled()
            pctf = sent / total_bytes
            size_mb = total_bytes / (1024 * 1024)
            self._last_size_mb = size_mb
            self.after(0, lambda: self.size_lbl.configure(text=f"Tamaño: {size_mb:.2f} MB"))
            text = f"Subiendo '{name}': {pctf*100:.0f}%"
            self.after(0, lambda: self.status_lbl.configure(text=text))

        try:
            self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
        except Exception:
            pass

        try: 
            
            self.auth_url_lbl.place(relx=0.5, rely=0.90, anchor="center")
            migrator = DirectMigrator(
                onedrive_folder="",
                cancel_event=self._cancel_event,
                status_callback=lambda text: self.after(0, lambda: self.status_lbl.configure(text=text))
            )
            # Autenticación completada → traemos la ventana al frente
            try:
                self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
            except Exception:
                pass

            self.after(0, self._bring_to_front)
            self.auth_url_lbl.place_forget()
            migrator.migrar(
                skip_existing=True,
                progress_callback=en_general,
                file_progress_callback=en_archivo
            )

            
        except OneDriveTokenExpired as e:
            self._bring_to_front
            try:
                self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
            except Exception:
                pass
            self.after(0, lambda: mb.showerror(
                "Autenticación expirada",
                str(e)
            ))
            
            return
        except ConnectionLost as e:
            try:
                self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
            except Exception:
                pass
            self.after(0, lambda: mb.showerror(
                "Conexión perdida",
                f"Se perdió la conexión a Internet:\n{e}"
            ))
            self.after(0, self.resetear_ui)
            return
        except MigrationCancelled:
            try:
                self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
            except Exception:
                pass
            mb.showwarning("Migracion365", "Migración cancelada")
            self.after(0, self.resetear_ui)
            return
        
        finally:
            self._is_running = False
        

        if not self._cancel_event.is_set():
            self.after(0, self._completado)


    """
    Actualiza la barra de progreso global y el label de estado.

    Args:
        pct (float): Porcentaje completado (0.0 a 1.0).
        name (str): Nombre del archivo o lote actual.
    """
    def _subida_global(self, pct, name):
        if self.progress.cget('mode') == 'indeterminate':
            self.progress.stop()
            self.progress.configure(mode="determinate")
        if self._last_size_mb > 0:
            self.size_lbl.configure(text=f"Tamaño: {self._last_size_mb:.2f} MB")
        self.progress.set(pct)
        self.status_lbl.configure(text=f"Migrando: {name} ({pct*100:.0f}%)")
        
    """
    Lógica a ejecutar cuando la migración finaliza correctamente.

    - Detiene animación de progressbar.
    - Muestra el botón de errores si el log de errores no está vacío.
    - Muestra un messagebox informativo.
    - Habilita nuevamente el botón "Iniciar" y resetea labels.
    """
    def _completado(self):
        if self.progress.cget('mode') == 'indeterminate':
            self.progress.stop()
        self.progress.set(1)
        self.cancel_btn.grid_remove()
        self._parar_pulso()
        self.status_lbl.configure(text="Oprime iniciar...")
        self.size_lbl.configure(text="Tamaño: —")
        log = DirectMigrator.ERROR_LOG
        if os.path.exists(log) and os.path.getsize(log) > 0:
            self.error_btn.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor='se')

        try:
            self._play_notification(ruta_absoluta("./gui/assets/bell.mp3"))
        except Exception:
            pass
        mb.showinfo("Migracion365", "Transferencia finalizada. Revisa tu OneDrive.")
        self.start_btn.configure(state="normal")
        self._bring_to_front
        
    """
    Inicia la animación pulsante en la progressbar.

    - Cambia el flag _pulsing a True.
    - Llama inmediatamente a _pulse para alternar colores.
    """
    def pulsos_carga(self):
        self._pulsing = True
        self.after(0, self._pulso)


    """
    Alterna el color de la progressbar cada 300 ms mientras _pulsing sea True.

    - Si current color es 'primary', lo cambia a 'primary_light', y viceversa.
    - Utiliza after(300) para llamar recursivamente.
    """
    def _pulso(self):

        if not self._pulsing:
            return
        current = self.progress.cget('progress_color')
        new_color = (
            self.COLORS['primary_light']
            if current == self.COLORS['primary']
            else self.COLORS['primary']
        )
        self.progress.configure(progress_color=new_color)
        self.after(300, self._pulso)

    """
        Detiene la animación de pulso y restaura el color original.
    """
    def _parar_pulso(self):
        self._pulsing = False
        self.progress.configure(progress_color=self.COLORS['primary'])

    """
        Inicia el loop principal de la aplicación.
    """
    def run(self):
        self.mainloop()
