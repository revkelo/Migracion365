# ---------------------------------------------------------------
# Script para Listar Archivos de Google Drive
# Autor: Kevin Gonzalez
# Descripción:
#   Este script lista todos los archivos en Google Drive del usuario
#   autenticado, mostrando su nombre, ID, tipo MIME y ubicación.
# ---------------------------------------------------------------

import os, pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def obtener_credenciales():
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as f:
            cred = pickle.load(f)
    else:
        cred = None
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            cred = flow.run_local_server(port=8089)
        with open('token.pickle', 'wb') as f:
            pickle.dump(cred, f)
    return cred

def listar_todo_drive():
    service = build('drive', 'v3', credentials=obtener_credenciales())
    page_token = None
    archivos = []

    print("📂 Listando todos los archivos en tu Google Drive...\n")
    while True:
        respuesta = service.files().list(
            fields="nextPageToken, files(id, name, mimeType, parents)",
            pageSize=100,
            pageToken=page_token
        ).execute()

        for archivo in respuesta.get('files', []):
            nombre = archivo.get('name', 'Sin nombre')
            mime = archivo.get('mimeType', 'Desconocido')
            file_id = archivo.get('id')
            carpeta = archivo.get('parents', ['Root'])[0]
            print(f"📝 Nombre: {nombre}\n🔑 ID: {file_id}\n📄 Tipo: {mime}\n📁 Carpeta Padre: {carpeta}\n{'-'*40}")

        page_token = respuesta.get('nextPageToken')
        if not page_token:
            break

    print("\n✅ Listado completado.")

# Ejecución principal
if __name__ == "__main__":
    listar_todo_drive()
