# ---------------------------------------------------------------
# Punto de entrada de la aplicación
# Autor: Kevin Gonzalez
# Descripción:
#   Inicializa y ejecuta la interfaz gráfica de Migración365.
#   Implementa un sistema de bloqueo para evitar múltiples instancias.
# ---------------------------------------------------------------


from gui import MigrationApp


if __name__ == "__main__":
    
        app = MigrationApp()
        app.mainloop()
