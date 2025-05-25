import os
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

class ErrorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Errores de Migración")
        self.geometry("300x100")
        self.resizable(False, False)
        ctk.set_appearance_mode("light")

        self.error_win = None

        # Contenedor para el botón y el badge
        self.btn_container = ctk.CTkFrame(self, fg_color="transparent", width=200, height=40)
        self.btn_container.pack(expand=True, pady=20)
        self.btn_container.pack_propagate(False)

        # Botón para mostrar errores
        self.btn = ctk.CTkButton(
            self.btn_container, text="Mostrar errores",
            command=self.show_errors,
            width=200, height=40
        )
        self.btn.pack()

        # Badge de notificación (círculo rojo)
        self.badge = ctk.CTkFrame(
            self.btn_container,
            fg_color="red",
            width=12, height=12,
            corner_radius=6
        )

        # Después de renderizar, comprobar si hay errores
        self.after(100, self.update_badge)

    def center_window(self, win, width, height):
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

    def update_badge(self):
        """Muestra el badge si el log existe y no está vacío."""
        log_file = "migration_errors.txt"
        if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
            w = self.btn_container.winfo_width()
            # Coloca el badge en la esquina superior derecha del botón
            self.badge.place(x=w-12, y=0)
        else:
            self.badge.place_forget()

    def show_errors(self):
        log_file = "migration_errors.txt"
        if not os.path.exists(log_file):
            messagebox.showinfo("Sin errores", "No se encontró el archivo de errores.")
            return

        with open(log_file, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]

        if not lines:
            messagebox.showinfo("Sin errores", "El archivo de errores está vacío.")
            return

        # Si ya hay ventana abierta, la trae al frente
        if self.error_win and self.error_win.winfo_exists():
            self.error_win.lift()
            self.error_win.focus_force()
            return

        # Crear ventana de tabla
        self.error_win = tk.Toplevel(self)
        self.error_win.title("Registro de Errores")
        width, height = 900, 400
        self.center_window(self.error_win, width, height)
        self.error_win.resizable(True, True)

        # Columnas: #, Fecha/Hora, Archivo, Ruta, Mensaje
        cols = ("#", "Fecha/Hora", "Archivo", "Ruta", "Mensaje")
        tree = ttk.Treeview(self.error_win, columns=cols, show='headings')
        for c in cols:
            tree.heading(c, text=c)
            if c == "#":
                tree.column(c, width=50, anchor="center")
            elif c == "Fecha/Hora":
                tree.column(c, width=150, anchor="w")
            elif c == "Archivo":
                tree.column(c, width=200, anchor="w")
            elif c == "Ruta":
                tree.column(c, width=250, anchor="w")
            else:  # Mensaje
                tree.column(c, width=250, anchor="w")

        # Rellenar filas y extraer sólo el nombre de archivo
        for idx, line in enumerate(lines, 1):
            fecha, ruta, msg = (line.split(" - ", 2) + ["", "", ""])[:3]
            archivo = os.path.basename(ruta)
            tree.insert("", "end", values=(idx, fecha, archivo, ruta, msg))

        vsb = ttk.Scrollbar(self.error_win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tree.pack(expand=True, fill="both", side="left")

        # Funciones para copiar celdas
        def copy_cell():
            row = getattr(tree, '_row', None)
            col = getattr(tree, '_col', None)
            if not row or not col:
                return
            idx_col = int(col.replace('#','')) - 1
            col_name = cols[idx_col]
            valor = tree.set(row, col_name)
            self.clipboard_clear()
            self.clipboard_append(valor)

        def on_click(event):
            if tree.identify_region(event.x, event.y) == "cell":
                tree._row = tree.identify_row(event.y)
                tree._col = tree.identify_column(event.x)

        def on_double_click(event):
            on_click(event)
            copy_cell()
            messagebox.showinfo("Copiado", "Celda copiada al portapapeles.")

        tree.bind("<Button-1>", on_click)
        tree.bind("<Double-1>", on_double_click)

        # Menú contextual para copiar
        context_menu = tk.Menu(self.error_win, tearoff=0)
        context_menu.add_command(label="Copiar celda", command=copy_cell)
        def on_right_click(event):
            if tree.identify_region(event.x, event.y) == "cell":
                on_click(event)
                context_menu.tk_popup(event.x_root, event.y_root)
        tree.bind("<Button-3>", on_right_click)

        # Al cerrar, limpiar referencia
        self.error_win.protocol("WM_DELETE_WINDOW", self._on_error_win_close)

    def _on_error_win_close(self):
        self.error_win.destroy()
        self.error_win = None

if __name__ == "__main__":
    app = ErrorApp()
    app.mainloop()
