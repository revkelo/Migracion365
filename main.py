# ---------------------------------------------------------------
# Punto de entrada de la aplicación
# Autor: Kevin Gonzalez
# Descripción:
#   Inicializa y ejecuta la interfaz gráfica de Migración365.
# ---------------------------------------------------------------

if __name__ == "__main__":
    """
    Crea una instancia de MigrationApp y arranca el bucle principal
    de la interfaz gráfica.
    """
    from gui import MigrationApp

    app = MigrationApp()
    app.mainloop()
