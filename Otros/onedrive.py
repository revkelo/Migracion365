import msal
import requests

# Datos de tu app registrada en Azure
CLIENT_ID = "d8227c52-3dde-4198-81a8-60f1347357ab"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Files.Read"]

def get_access_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

    # 🔥 Elimina cuentas guardadas para forzar selección
    for account in app.get_accounts():
        app.remove_account(account)

    # 🔐 Fuerza pantalla de selección de cuenta
    result = app.acquire_token_interactive(SCOPES, prompt="select_account")

    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Error obteniendo token: {result.get('error_description')}")

def listar_archivos(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        for item in data.get("value", []):
            tipo = f"{item['folder']['childCount']} elementos" if 'folder' in item else "Archivo"
            print(f"{item['name']} - {tipo}")
    else:
        print(f"Error al listar archivos: {response.status_code} {response.text}")

if __name__ == "__main__":
    print("Solicitando token nuevo...")
    token = get_access_token()
    print("Listando archivos en OneDrive:")
    listar_archivos(token)
