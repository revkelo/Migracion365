# ---------------------------------------------------------------
# Punto de entrada de la aplicación
# Autor: Kevin Gonzalez
# Descripción:
#   Inicializa y ejecuta la interfaz gráfica de Migración365.
#   Implementa un sistema de bloqueo para evitar múltiples instancias.
# ---------------------------------------------------------------


from gui import MigrationApp
"""
Cuando se ejecuta este archivo como script principal:
1. Se crea una instancia de MigrationApp (ventana principal de la GUI).
2. Se invoca mainloop() para iniciar el bucle de eventos de Tkinter.
"""
if __name__ == "__main__":
    
        app = MigrationApp()
        app.mainloop()
