import re
import json
import os
from pathlib import Path

def load_progress(progress_file: str) -> dict:
    """Carga progreso previo desde JSON."""
    if Path(progress_file).exists():
        try:
            data = json.loads(Path(progress_file).read_text(encoding='utf-8'))
            return {'migrated_files': set(data.get('migrated_files', []))}
        except Exception:
            return {'migrated_files': set()}
    return {'migrated_files': set()}


def save_progress(progress_file: str, data: dict):
    """Guarda progreso (IDs migrados) en JSON."""
    to_save = {'migrated_files': list(data.get('migrated_files', []))}
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2)
    except Exception:
        pass


def sanitize_filename(filename: str) -> str:
    """Reemplaza caracteres inválidos y limita longitud."""
    sanitized = re.sub(r'[\\/*?:\"<>|]', '_', filename)
    if len(sanitized) > 250:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:245] + ext
    return sanitized.strip()


def format_size(size_bytes: int) -> str:
    """Convierte bytes a una cadena legible (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"