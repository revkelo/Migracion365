# ---------------------------------------------------------------
# Punto de entrada de la aplicación
# Autor: Kevin Gonzalez
# Descripción:
#   Inicializa y ejecuta la interfaz gráfica de Migración365.
#   Implementa un sistema de bloqueo para evitar múltiples instancias.
# ---------------------------------------------------------------

import os
import sys
import tkinter.messagebox as mb
from gui import MigrationApp

LOCK_FILE = "app.lock"

def is_already_running() -> bool:
    """
    Verifica si la aplicación ya está en ejecución mediante un archivo de bloqueo.

    - Si el archivo 'app.lock' existe, se asume que otra instancia está corriendo.
    - Si no existe, se crea con el PID del proceso actual.
    - Retorna True si ya hay una instancia; False si se puede continuar.
    """
    if os.path.exists(LOCK_FILE):
        return True
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return False
    except Exception:
        return True

def cleanup_lock_file():
    """
    Elimina el archivo de bloqueo 'app.lock' al cerrar la aplicación.

    - Se ejecuta incluso si hay errores para evitar archivos huérfanos.
    """
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

if __name__ == "__main__":
    """
    Punto de inicio del programa.

    - Verifica si ya existe una instancia en ejecución.
    - Si no, crea y muestra la interfaz gráfica principal.
    - Asegura limpieza del archivo de bloqueo al salir.
    """
    if is_already_running():
        mb.showwarning("Ya está en ejecución", "La aplicación Migrador365 ya está abierta.")
        sys.exit(0)

    try:
        app = MigrationApp()
        app.mainloop()
    finally:
        cleanup_lock_file()
