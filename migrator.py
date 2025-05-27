# ---------------------------------------------------------------
# Migrador Directo de Google Drive a OneDrive
# Autor: Kevin Gonzalez
# Descripción:
#   Orquesta el proceso de migración de archivos desde Google Drive hacia OneDrive.
#   - Gestiona autenticación y servicios de Google y OneDrive.
#   - Descarga, exporta y sube archivos, preservando estructura de carpetas.
#   - Control de progreso y capacidad de reanudar.
#   - Registro de errores y soporte para cancelar la operación.
# ---------------------------------------------------------------

import time
import logging
from typing import Callable, Optional
from config import PROGRESS_FILE, LOG_FILE
from utils import load_progress, save_progress
from google_service import GoogleService
from onedrive_service import OneDriveService
import threading
import re
from config import GOOGLE_EXPORT_FORMATS

class MigrationCancelled(Exception):
    """Señaliza que el usuario ha cancelado el proceso de migración."""
    pass

class ConnectionLost(Exception):
    """Señaliza que se perdió la conexión a Internet durante la migración."""
    pass

class DirectMigrator:
    ERROR_LOG = 'migration_errors.txt'

    def __init__(
        self,
        onedrive_folder: str = '',
        cancel_event: Optional[threading.Event] = None
    ):
        self.onedrive_folder = onedrive_folder.strip('/')
        self.cancel_event   = cancel_event
        self.google         = GoogleService()
        self.one            = OneDriveService()
        self.progress       = load_progress(PROGRESS_FILE)

        self.logger = logging.getLogger('DirectMigrator')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter(
                "%(asctime)s — %(levelname)s — %(message)s"
            ))
            self.logger.addHandler(ch)

            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s — %(levelname)s — %(message)s"
            ))
            self.logger.addHandler(fh)

    def migrate(
        self,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        self.logger.info("Iniciando migración...")

        folders, files, _ = self.google.list_files_and_folders()
        entries = [
            f for f in files.values()
            if f['mimeType'] in GOOGLE_EXPORT_FORMATS
        ]
        total_files = len(entries)
        processed = 0

        for info in entries:
            if self.cancel_event and self.cancel_event.is_set():
                self.logger.info("Migración cancelada por usuario")
                return

            fid     = info['id']
            raw_name = info['name']
            # Limpio saltos de línea y espacios sobrantes
            name    = raw_name.replace('\r', '').replace('\n', ' ').strip()

            # Si ya lo migramos, avanzamos contador y actualizamos UI
            if skip_existing and fid in self.progress.get('migrated_files', set()):
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_files, name)
                continue

            parents = info.get('parents') or []
            path_parts = (
                self.google.get_folder_path(parents[0], folders)
                if parents else []
            )
            folder_path = '/'.join(path_parts)
            drive_path  = f"{folder_path}/{name}" if folder_path else name

            try:
                # Descargar
                t0 = time.perf_counter()
                data, ext_name = self.google.download_file(info)
                t1 = time.perf_counter()
                self.logger.info(f"Descarga {name}: {t1-t0:.2f}s")

                # Si no vino contenido, uso el formateador de errores
                if data is None:
                    raw_msg = getattr(self.google, 'last_error', None)
                    if raw_msg:
                        mensaje = self._format_error(raw_msg)
                    else:
                        mensaje = "Descarga fallida (error desconocido)"
                    
                    print(f"[ERROR] {drive_path} -> {mensaje}") 
                    
                    
                    self._log_error(drive_path, mensaje)         
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_files, name)
                    continue


                # Calcular tamaño y volver al inicio
                data.seek(0, 2)
                total_bytes = data.tell()
                data.seek(0)

                # Subir
                remote_path = f"{self.onedrive_folder}/{folder_path}/{ext_name}".lstrip('/')
                t2 = time.perf_counter()
                self.one.upload(
                    file_data=data,
                    remote_path=remote_path,
                    size=total_bytes,
                    progress_callback=lambda sent, tot, n=name: (
                        file_progress_callback(sent, tot, n)
                        if file_progress_callback else None
                    )
                )
                t3 = time.perf_counter()
                self.logger.info(f"Subida   {name}: {t3-t2:.2f}s")

                # Marcar migrado y guardar progreso
                self.progress.setdefault('migrated_files', set()).add(fid)
                save_progress(PROGRESS_FILE, self.progress)

            except Exception as e:
                raw_msg = str(e)
                mensaje = self._format_error(raw_msg)
                self._log_error(drive_path, mensaje)
                if mensaje in (
                        "Tiempo de espera agotado al leer los datos.",
                        "No se pudo conectar al servidor de Google APIs."
                ):
                    raise ConnectionLost(mensaje)    

            # Actualizar progreso final de archivo
            processed += 1
            if progress_callback:
                progress_callback(processed, total_files, name)

        # Al terminar, llevar la barra al 100%
        if progress_callback:
            progress_callback(total_files, total_files, '')

    def _log_error(self, drive_path: str, message: str) -> None:
        """Añade una entrada en el log de errores (una sola línea)."""
        clean_path = drive_path.replace('\r', '').replace('\n', '')
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {clean_path} - {message}\n"
        try:
            with open(self.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            self.logger.error(f"Imposible escribir error en {self.ERROR_LOG}")

    def _format_error(self, raw_msg: str) -> str:
        # Aseguramos que trabajamos con texto plano
        msg = str(raw_msg)


        if 'exportSizeLimitExceeded' in msg:
            return "Este archivo es demasiado grande para ser exportado desde Google Docs."
        
        if 'cannotExportFile' in msg:
            # extraemos la razón entre comillas para mostrarla textualmente
            match = re.search(r'returned\s+"([^"]+)"', msg)
            if match:
                return match.group(1)  # e.g. "This file cannot be exported by the user."
            return "No tienes permiso para exportar este archivo desde Google Docs."
        
        if '403' in msg and 'export' in msg:
            return "No tienes permiso para exportar este archivo desde Google Docs."
        
        if '404' in msg:
            return "Archivo no encontrado."
        
        # nuevo manejo de timeout
        if 'timed out' in msg.lower():
            return "Tiempo de espera agotado al leer los datos."
        
        # nuevo manejo de fallo DNS u “Unable to find the server”
        if 'unable to find the server' in msg.lower():
            return "No se pudo conectar al servidor de Google APIs."
        
        if 'ConnectionError' in msg or 'Failed to establish a new connection' in msg:
            return "Error de red. Verifica tu conexión a Internet."
        
        if 'invalid_grant' in msg or 'Token has been expired or revoked' in msg:
            return "Tu sesión ha expirado. Inicia sesión nuevamente."
        
        if 'rateLimitExceeded' in msg:
            return "Se excedió el límite de la API. Intenta más tarde."
        
        if 'Backend Error' in msg:
            return "Error temporal de Google Drive."
        
        # Fallback genérico: devolvemos el mensaje original
        return msg
