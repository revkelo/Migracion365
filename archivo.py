import os
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

class ErrorApp(ctk.CTkToplevel):
    _instance = None

    def __new__(cls, master=None):
        # Si ya hay una instancia abierta, la trae al frente
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            return cls._instance
        cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, master=None):
        # Evitar re-inicialización en instancias recurrentes
        if getattr(self, '_initialized', False):
            return
        super().__init__(master)
        self._initialized = True

        self.title("Archivos problemáticos")
        # Configurar tamaño y centrar
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

        # Crear y mostrar la tabla de errores
        self._create_error_table()

    def _create_error_table(self):
        log_file = "migration_errors.txt"
        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
            messagebox.showinfo("Sin errores", "No hay errores registrados.")
            self.destroy()
            type(self)._instance = None
            return

        # Leer líneas no vacías
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        # Definir columnas
        cols = ("#", "Fecha/Hora", "Archivo", "Ruta", "Mensaje")
        tree = ttk.Treeview(self, columns=cols, show='headings')
        widths = {"#":50, "Fecha/Hora":150, "Archivo":200, "Ruta":250, "Mensaje":250}
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 100), anchor='w')

        # Insertar datos
        for idx, line in enumerate(lines, start=1):
            parts = line.split(' - ', 2)
            fecha = parts[0] if len(parts) > 0 else ''
            ruta  = parts[1] if len(parts) > 1 else ''
            msg   = parts[2] if len(parts) > 2 else ''
            archivo = os.path.basename(ruta)
            tree.insert('', 'end', values=(idx, fecha, archivo, ruta, msg))

        # Scrollbar vertical
        vsb = ttk.Scrollbar(self, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        tree.pack(expand=True, fill='both', side='left')

        # Función para copiar celda seleccionada
        def copy_cell(event=None):
            item = tree.selection()
            if not item:
                return
            values = tree.item(item[0], 'values')
            col = tree.identify_column(event.x) if event else None
            if col:
                idx_col = int(col.replace('#','')) - 1
                val = values[idx_col]
            else:
                val = ' '.join(str(v) for v in values)
            self.clipboard_clear()
            self.clipboard_append(val)

        # Doble clic o menú contextual
        tree.bind('<Double-1>', lambda e: (copy_cell(e), messagebox.showinfo('Copiado', 'Celda copiada al portapapeles.')))
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Copiar celda', command=copy_cell)
        tree.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))

        # Al cerrar, destruir y limpiar instancia
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_close(self):
        self.destroy()
        type(self)._instance = None

