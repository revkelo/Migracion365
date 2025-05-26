# ---------------------------------------------------------------
# Archivo de Utilidades de Migración
# Autor: Kevin Gonzalez
# Descripción:
#   Contiene funciones auxiliares para gestionar el progreso de migración,
#   sanitizar nombres de archivos y formatear tamaños de datos.
# ---------------------------------------------------------------

import re
import json
import os
from pathlib import Path


def load_progress(progress_file: str) -> dict:
    """
    Carga el progreso de migración desde un archivo JSON.

    - Abre `progress_file` si existe y parsea la lista de IDs migrados.
    - Devuelve un diccionario con la clave 'migrated_files' como un set de IDs.
    - Si ocurre un error al leer o parsear, retorna un set vacío.
    """
    if Path(progress_file).exists():
        try:
            data = json.loads(Path(progress_file).read_text(encoding='utf-8'))
            return {'migrated_files': set(data.get('migrated_files', []))}
        except Exception:
            return {'migrated_files': set()}
    return {'migrated_files': set()}


def save_progress(progress_file: str, data: dict):
    """
    Guarda el progreso de migración en un archivo JSON.

    - Serializa el set 'migrated_files' en una lista JSON.
    - Escribe el contenido con indentación de 2 espacios.
    - Captura y descarta excepciones para no interrumpir el proceso.
    """
    to_save = {'migrated_files': list(data.get('migrated_files', []))}
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2)
    except Exception:
        pass


def sanitize_filename(filename: str) -> str:
    """
    Reemplaza caracteres inválidos en un nombre de archivo y limita su longitud.

    - Sustituye caracteres reservados (\\ / * ? : " < > |) por '_'.
    - Si el nombre excede 250 caracteres, recorta el nombre a 245 caracteres y conserva la extensión.
    - Retorna el nombre resultante sin espacios al inicio o final.
    """
    sanitized = re.sub(r'[\\/*?:"<>|#]', '_', filename)
    if len(sanitized) > 250:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:245] + ext
    return sanitized.strip()


def format_size(size_bytes: int) -> str:
    """
    Convierte un tamaño en bytes a una cadena legible con unidad apropiada.

    - Itera por unidades: B, KB, MB, GB.
    - Cuando el tamaño sea menor a 1024, formatea con una decimal.
    - Para tamaños mayores a GB, utiliza TB como unidad final.
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
