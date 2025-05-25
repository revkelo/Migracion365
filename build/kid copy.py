import os
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

class ErrorApp(ctk.CTk):
    def __init__(self, log_file=None):
        super().__init__()
        self.title("Archivos problemáticos")
        self.geometry("600x400")
        self.resizable(True, True)
        ctk.set_appearance_mode("light")

        # Determinar archivo de log de errores si no se pasa
        if log_file is None:
            from migrator import DirectMigrator
            log_file = DirectMigrator.ERROR_LOG
        self.log_file = log_file

        # Configurar grilla
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Treeview para mostrar errores
        columns = ("archivo", "error")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("archivo", text="Archivo")
        self.tree.heading("error", text="Error")
        self.tree.column("archivo", width=200, anchor="w")
        self.tree.column("error", width=380, anchor="w")

        # Scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Cargar datos de errores
        self._load_errors()

    def _load_errors(self):
        if not os.path.exists(self.log_file) or os.path.getsize(self.log_file) == 0:
            messagebox.showinfo("Sin archivos problemáticos", "No se encontraron archivos problemáticos.")
            self.destroy()
            return
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Intentar dividir por separador '|' o ':'
                if '|' in line:
                    archivo, error = line.split('|', 1)
                elif ':' in line:
                    archivo, error = line.split(':', 1)
                else:
                    archivo, error = line, ''
                self.tree.insert('', 'end', values=(archivo.strip(), error.strip()))

if __name__ == "__main__":
    app = ErrorApp()
    app.mainloop()
