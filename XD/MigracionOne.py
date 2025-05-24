import msal
import requests
import os

# Configuración de tu aplicación en Azure
CLIENT_ID = "d8227c52-3dde-4198-81a8-60f1347357ab"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Files.ReadWrite.All"]

def get_access_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    for account in app.get_accounts():
        app.remove_account(account)
    result = app.acquire_token_interactive(SCOPES, prompt="select_account")
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Error obteniendo token: {result.get('error_description')}")

def subir_archivo(access_token, ruta_local, ruta_remota):
    nombre = os.path.basename(ruta_local)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream"
    }

    with open(ruta_local, "rb") as f:
        data = f.read()

    # Crear ruta remota manteniendo jerarquía
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{ruta_remota.replace(os.sep, '/')}/{nombre}:/content"
    response = requests.put(url, headers=headers, data=data)

    if response.status_code in [200, 201]:
        print(f"✅ Subido: {ruta_remota}/{nombre}")
    else:
        print(f"❌ Error al subir {nombre}: {response.status_code} {response.text}")

def subir_carpeta_recursiva(carpeta_base, access_token, carpeta_remota=""):
    for root, dirs, files in os.walk(carpeta_base):
        for file in files:
            ruta_local = os.path.join(root, file)
            # Calcula ruta remota relativa desde carpeta base
            ruta_relativa = os.path.relpath(root, carpeta_base)
            ruta_remota = os.path.join(carpeta_remota, ruta_relativa)
            subir_archivo(access_token, ruta_local, ruta_remota)

            # Si quieres eliminar el archivo local después de subirlo:
            # os.remove(ruta_local)

if __name__ == "__main__":
    print("🔐 Obteniendo token de acceso a OneDrive...")
    token = get_access_token()

    carpeta_local = "Descarga_GoogleDrive"
    print(f"📤 Subiendo todos los archivos desde: {carpeta_local}")
    subir_carpeta_recursiva(carpeta_local, token)

    # Si deseas eliminar toda la carpeta después de subir:
    # import shutil
    # shutil.rmtree(carpeta_local)
