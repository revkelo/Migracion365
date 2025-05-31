import os
import sys
import json
from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
import msal

# Configuración
KEY = b"HG5GHGW3o9bMUMWUmz7khGjhELzFUJ9W-52s_ZnIC40="
ENC_CRED_FILE = 'credentials.json.enc'
TOKEN_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
ONEDRIVE_CLIENT_ID = "d8227c52-3dde-4198-81a8-60f1347357ab"
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/common"
ONEDRIVE_SCOPES = ["Files.ReadWrite.All", "User.Read"]


def _load_encrypted_blob(filename: str = ENC_CRED_FILE) -> bytes:
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No encontré el archivo cifrado en {path}")
    with open(path, 'rb') as f:
        return f.read()

def _load_credentials(filename: str = ENC_CRED_FILE) -> dict:
    blob = _load_encrypted_blob(filename)
    f = Fernet(KEY)
    plaintext = f.decrypt(blob)
    return json.loads(plaintext)

def obtener_credenciales_google() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            config = _load_credentials()
            flow = InstalledAppFlow.from_client_config(config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    return creds

def autenticar_onedrive():
    app = msal.PublicClientApplication(client_id=ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY)
    for acct in app.get_accounts():
        app.remove_account(acct)
    result = app.acquire_token_interactive(scopes=ONEDRIVE_SCOPES, prompt="select_account")
    if "access_token" in result:
        return result["access_token"]
    raise RuntimeError(f"Error autenticando con OneDrive: {result.get('error_description', 'desconocido')}")

if __name__ == '__main__':
    # Obtener correo de Google Drive
    creds = obtener_credenciales_google()
    drive_svc = build('drive', 'v3', credentials=creds)
    correo_google = drive_svc.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]
    print(f"🔵 Usuario autenticado de Google Drive: {correo_google}")

    # Obtener correo de OneDrive
    token_onedrive = autenticar_onedrive()
    me = requests.get("https://graph.microsoft.com/v1.0/me", headers={
        "Authorization": f"Bearer {token_onedrive}"
    }).json()
    correo_onedrive = me.get("userPrincipalName", "desconocido")
    print(f"🟣 Usuario autenticado de OneDrive: {correo_onedrive}")
