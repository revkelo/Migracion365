import os
from tkinter import Tk, filedialog, messagebox
from cryptography.fernet import Fernet

def generar_clave():
    key = Fernet.generate_key()
    return key

def encriptar_archivo(ruta_json, ruta_salida, key):
    f = Fernet(key)
    with open(ruta_json, 'rb') as archivo_original:
        datos = archivo_original.read()
        cifrado = f.encrypt(datos)
        with open(ruta_salida, 'wb') as archivo_cifrado:
            archivo_cifrado.write(cifrado)

def guardar_clave_txt(ruta_enc, key):
    ruta_txt = os.path.splitext(ruta_enc)[0] + "_KEY.txt"
    with open(ruta_txt, 'w') as f:
        f.write(key.decode())
    return ruta_txt

def seleccionar_archivo_json():
    Tk().withdraw()
    archivo = filedialog.askopenfilename(
        title="Selecciona el archivo de credenciales JSON",
        filetypes=[("Archivos JSON", "*.json")]
    )
    return archivo

def seleccionar_donde_guardar():
    root = Tk()
    root.withdraw()
    carpeta = filedialog.askdirectory(
        title="Selecciona la carpeta donde guardar 'credentials.json.enc'"
    )
    root.destroy()
    if not carpeta:
        return None
    return os.path.join(carpeta, "credentials.json.enc")


def main():
    ruta_json = seleccionar_archivo_json()
    if not ruta_json:
        messagebox.showinfo("Cancelado", "No se seleccionó ningún archivo JSON.")
        return

    if not ruta_json.endswith(".json"):
        messagebox.showerror("Error", "El archivo debe tener extensión .json")
        return

    ruta_salida = seleccionar_donde_guardar()
    if not ruta_salida:
        messagebox.showinfo("Cancelado", "No se seleccionó ruta de salida.")
        return

    key = generar_clave()
    encriptar_archivo(ruta_json, ruta_salida, key)
    ruta_txt = guardar_clave_txt(ruta_salida, key)

    messagebox.showinfo(
        "✅ Encriptado exitoso",
        f"Archivo encriptado: {ruta_salida}\n\n"
        f"Clave guardada en: {ruta_txt}\n\n"
        f"También se imprimió la clave en la consola."
    )
    print(f"\n🔑 Clave generada:\n{key.decode()}")
    print(f"📁 Ruta archivo encriptado: {ruta_salida}")
    print(f"📝 Clave guardada en: {ruta_txt}")

if __name__ == "__main__":
    main()
