# 🚀 Configuración

## Requisitos previos

Instala los paquetes necesarios con pip:

```bash
pip install customtkinter Pillow google-api-python-client google-auth google-auth-oauthlib msal requests tqdm python-docx
```

## Run Main.py


pyinstaller \
  --onefile \
  --windowed \
  --name Migracion365 \
  --add-data "credentials.json.enc;." \
  --add-data "gui/assets;gui/assets" \
  main.py
