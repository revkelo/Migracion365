import msal
import requests
import tkinter as tk
from tkinter import filedialog
import os

# Datos de tu app registrada en Azure
CLIENT_ID = "d8227c52-3dde-4198-81a8-60f1347357ab"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Files.ReadWrite.All"]

def get_access_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

    # Elimina cuentas guardadas para forzar selección
    for account in app.get_accounts():
        app.remove_account(account)

    # Fuerza pantalla de selección de cuenta
    result = app.acquire_token_interactive(SCOPES, prompt="select_account")

    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Error obteniendo token: {result.get('error_description')}")

def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()  # Oculta la ventana principal
    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)
    archivo = filedialog.askopenfilename(title="Selecciona un archivo para subir")
    root.destroy()
    return archivo


def subir_archivo(access_token, archivo):
    nombre = os.path.basename(archivo)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream"
    }

    with open(archivo, "rb") as f:
        data = f.read()

    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{nombre}:/content"
    response = requests.put(url, headers=headers, data=data)

    if response.status_code in [200, 201]:
        print(f"✅ Archivo '{nombre}' subido correctamente.")
    else:
        print(f"❌ Error al subir el archivo: {response.status_code} {response.text}")

if __name__ == "__main__":
    print("🔐 Solicitando token nuevo...")
    token = get_access_token()

    print("📂 Abriendo selector de archivos...")
    archivo = seleccionar_archivo()
    if archivo:
        print(f"📤 Subiendo archivo: {archivo}")
        subir_archivo(token, archivo)
    else:
        print("🚫 No se seleccionó ningún archivo.")
