# 🚀 Migrador365

Aplicación para migrar archivos desde Google Drive hacia OneDrive, preservando la estructura de carpetas y exportando formatos de Google Workspace.

⚠️ No suspendas el equipo durante la migración para evitar errores de red.
---

## 💻 Ejecutable para Windows

Dentro de la carpeta `exe/` se encuentra:

```
exe/
└── Migracion365.exe
```

Este archivo es totalmente ejecutable en cualquier sistema **Windows 10 o superior**, **sin necesidad de tener Python instalado**.

---

## 📁 Archivos requeridos junto al `.exe`

Para que el ejecutable funcione correctamente, debes copiar junto a `Migracion365.exe` los siguientes archivos y carpetas:

- `credentials.json.enc`
- Carpeta `gui/assets`

Asegúrate de mantener la misma estructura que en el desarrollo.

---

## ✅ Requisitos previos

1. Tener **Python 3.12 o superior** instalado.
2. Instalar las dependencias con pip:

```bash
pip install customtkinter Pillow google-api-python-client google-auth google-auth-oauthlib msal requests tqdm python-docx
```

---

## ▶️ Ejecutar la aplicación (modo desarrollo)

```bash
python main.py
```

Esto iniciará la interfaz gráfica para comenzar la migración.

---

© 2024 Kevin Gonzalez
