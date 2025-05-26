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
from config import GOOGLE_EXPORT_FORMATS

"""
    Señaliza que el usuario ha cancelado el proceso de migración.
"""
class MigrationCancelled(Exception):
    pass


"""
    Clase principal encargada de transferir archivos de Google Drive a OneDrive.

    - `migrate`: recorre archivos, gestiona descarga y subida.
    - Controla progreso mediante JSON y permite reanudar.
    - Registra tiempos y errores en log.
"""
class DirectMigrator:
    ERROR_LOG = 'migration_errors.txt'

    def __init__(
        self,
        onedrive_folder: str = '',
        cancel_event: Optional[threading.Event] = None
    ):
        
        self.onedrive_folder = onedrive_folder.strip('/')
        self.cancel_event = cancel_event
        self.google = GoogleService()
        self.one = OneDriveService()
        self.progress = load_progress(PROGRESS_FILE)
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


    """
        Ejecuta la migración de archivos.

        - Itera sobre todos los archivos de Drive.
        - Opción de omitir los ya migrados.
        - Reporta progreso global y por archivo.
        - Captura y guarda errores en un log.
    """
    def migrate(
        self,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        self.logger.info("Iniciando migración...")
        folders, files, _ = self.google.list_files_and_folders()
        entries = list(files.values())
        total_files = len(entries)
        processed = 0

        for info in entries:
    
            if info['mimeType'] not in GOOGLE_EXPORT_FORMATS:
                continue
          
            if self.cancel_event and self.cancel_event.is_set():
                self.logger.info("Migración cancelada por usuario")
                return

            fid = info['id']
            name = info['name']

            if progress_callback:
                progress_callback(processed + 1, total_files, name)

            parents = info.get('parents') or []
            path_parts = (
                self.google.get_folder_path(parents[0], folders)
                if parents else []
            )
    
            folder_path = '/'.join(path_parts)

            drive_path = f"{folder_path}/{name}" if folder_path else name

            if skip_existing and fid in self.progress.get('migrated_files', set()):
                processed += 1
                continue

            try:
   
                t0 = time.perf_counter()
                data, ext_name = self.google.download_file(info)
                t1 = time.perf_counter()
                self.logger.info(f"Descarga {name}: {t1-t0:.2f}s")

                if data is None:
                    raise RuntimeError("Descarga fallida")

 
                data.seek(0, 2)
                total_bytes = data.tell()
                data.seek(0)

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


                self.progress.setdefault('migrated_files', set()).add(fid)
                save_progress(PROGRESS_FILE, self.progress)

            except Exception as e:
                raw_msg = str(e)
                mensaje_final = raw_msg  

                if 'exportSizeLimitExceeded' in raw_msg:
                    mensaje_final = (
                        "Este archivo es demasiado grande para ser exportado desde Google Docs. "
                        "Considere descargarlo manualmente desde Google Drive."
                    )
                elif '403' in raw_msg and 'export' in raw_msg:
                    mensaje_final = (
                        "No tienes permiso para exportar este archivo desde Google Docs. "
                        "Verifica si eres el propietario o si tienes permisos suficientes."
                    )
                elif '404' in raw_msg:
                    mensaje_final = (
                        "Archivo no encontrado. Puede haber sido eliminado o movido en Google Drive."
                    )
                elif 'ConnectionError' in raw_msg or 'Failed to establish a new connection' in raw_msg:
                    mensaje_final = (
                        "Hubo un error de red al intentar descargar o subir el archivo. "
                        "Verifica tu conexión a Internet."
                    )
                elif 'invalid_grant' in raw_msg or 'Token has been expired or revoked' in raw_msg:
                    mensaje_final = (
                        "Tu sesión de autenticación ha expirado. Por favor, vuelve a iniciar sesión."
                    )
                elif 'rateLimitExceeded' in raw_msg:
                    mensaje_final = (
                        "Se excedió el límite de solicitudes a la API. Intenta de nuevo en unos minutos."
                    )
                elif 'Backend Error' in raw_msg:
                    mensaje_final = (
                        "Error temporal de Google Drive. Intenta nuevamente más tarde."
                    )

                self._log_error(drive_path, mensaje_final)



            processed += 1

        if progress_callback:
            progress_callback(total_files, total_files, '')

    """
        Añade una entrada en el archivo de errores con timestamp y ruta.

        - `drive_path`: ruta relativa del archivo en Drive.
        - `message`: descripción del error.
    """
    def _log_error(self, drive_path: str, message: str) -> None:
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {drive_path} - {message}\n"
        try:
            with open(self.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            self.logger.error(f"Imposible escribir error en {self.ERROR_LOG}")