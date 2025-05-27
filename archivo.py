# ---------------------------------------------------------------
# ErrorApp - Ventana de Archivos Problemáticos
# Autor: Kevin Gonzalez
# Descripción:
#   Proporciona una interfaz para mostrar los archivos que tuvieron errores
#   durante la migración. Lee el archivo de log "migration_errors.txt" y
#   presenta los detalles en una tabla, permitiendo copiar cualquier campo.
#   Implementa un patrón singleton para evitar múltiples instancias.
# ---------------------------------------------------------------

import os
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

class ErrorApp(ctk.CTkToplevel):
    """
    Ventana emergente única para mostrar los archivos con errores de migración.

    Implementa el patrón singleton para asegurar que solo exista una instancia
    activa. Permite visualizar los detalles de los errores guardados en un archivo
    de log y copiar celdas al portapapeles.
    """
    _instance = None

    def __new__(cls, master=None):
        """
        Controla la creación de instancias para implementar el singleton.
        Si ya existe una ventana abierta, la trae al frente en lugar de crear una nueva.
        """
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            return cls._instance
        cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, master=None):
        """
        Inicializa la ventana y configura aspectos visuales y de ubicación.

        Parámetros:
            master (widget, opcional): Widget padre de la ventana.
        """

        if getattr(self, '_initialized', False):
            return
        
        super().__init__(master)
        self._initialized = True
        self.title("Archivos problemáticos")
        width, height = 900, 400
        ico_path = os.path.join("gui", "assets", "icono.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:

                pass
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(True, True)
        ctk.set_appearance_mode("light")

        self._create_error_table()

    def _create_error_table(self):
        """
        Carga el archivo de errores y muestra su contenido en un Treeview.
        Si no hay errores, muestra un mensaje y cierra la ventana.
        """
        log_file = "migration_errors.txt"
        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
            messagebox.showinfo("Sin errores", "No hay errores registrados.")
            self.destroy()
            type(self)._instance = None
            return

        with open(log_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        cols = ("#", "Fecha/Hora", "Archivo", "Ruta", "Mensaje")
        tree = ttk.Treeview(self, columns=cols, show='headings')
        widths = {"#": 50, "Fecha/Hora": 150, "Archivo": 200, "Ruta": 250, "Mensaje": 250}
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 100), anchor='w')


        for idx, line in enumerate(lines, start=1):

            left, msg = line.rsplit(' - ', 1)

            fecha, ruta = left.split(' - ', 1)


            fecha = fecha.strip()
            ruta  = ruta.strip()

            msg   = msg.replace('\n', ' ').replace('\r', '').strip()

            archivo = os.path.basename(ruta)
            tree.insert('', 'end', values=(idx, fecha, archivo, ruta, msg))


        vsb = ttk.Scrollbar(self, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        tree.pack(expand=True, fill='both', side='left')

        def copy_cell(event=None):
            item = tree.selection()
            if not item:
                return
            values = tree.item(item[0], 'values')
            col = tree.identify_column(event.x) if event else None
            if col:
                idx_col = int(col.replace('#', '')) - 1
                val = values[idx_col]
            else:
                val = ' '.join(str(v) for v in values)
            self.clipboard_clear()
            self.clipboard_append(val)

        tree.bind('<Double-1>', lambda e: (copy_cell(e), messagebox.showinfo('Copiado', 'Celda copiada al portapapeles.')))
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Copiar celda', command=copy_cell)
        tree.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))

        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_close(self):
        """
        Maneja el evento de cierre de la ventana, destruye la instancia
        y libera el singleton.
        """
        self.destroy()
        type(self)._instance = None
