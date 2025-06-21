# ---------------------------------------------------------------
# Migrador Directo de Google Drive a OneDrive (Incluye Unidades Compartidas)
# Autor: Kevin Gonzalez
# Descripción:
#   Orquesta el proceso de migración de archivos desde Google Drive 
#   (tanto "Mi unidad" como Unidades Compartidas donde el usuario 
#   es organizador) hacia OneDrive.
#   - Gestiona autenticación y servicios de Google y OneDrive.
#   - Descarga, exporta y sube archivos, preservando estructura de carpetas.
#   - Control de progreso y capacidad de reanudar.
#   - Registro de errores y soporte para cancelar la operación.
#   - Genera roles.txt y acceso.txt para cada Unidad Compartida.
# ---------------------------------------------------------------

import io
from config import MAX_FILE_SIZE_BYTES
import time
import logging
from typing import Callable, Optional
import threading
from config import PROGRESS_FILE, LOG_FILE, GOOGLE_EXPORT_FORMATS,OFFICE_MIME_TYPES
from utils import cargar_proceso, guardar_progreso, limpiar_archivos
from google_service import GoogleService
from onedrive_service import OneDriveService




class MigrationCancelled(Exception):
    """Señaliza que el usuario ha cancelado el proceso de migración."""
    pass


class ConnectionLost(Exception):
    """Señaliza que se perdió la conexión a Internet durante la migración."""
    pass


"""
Orquesta el proceso de migración directa de Google Drive a OneDrive.

Atributos:
    ERROR_LOG (str): Nombre del archivo donde se anotan errores de migración.
"""
class DirectMigrator:
    ERROR_LOG = 'migration_errors.txt'
    correo_general = ''

    """
    Inicializa el migrador:

    - Configura callbacks y carpeta base en OneDrive.
    - Autentica con GoogleService y OneDriveService.
    - Verifica que el correo de Google y OneDrive coincidan.
    - Carga progreso previo desde PROGRESS_FILE.
    - Inicializa logger.
    
    Args:
        onedrive_folder (str): Ruta de carpeta base en OneDrive (sin slash inicial).
        cancel_event (threading.Event | None): Evento para señalizar cancelación desde la UI.
        status_callback (callable | None): Función para notificar mensajes de estado (por ejemplo, a la GUI).
    """
    def __init__(
        self,
        onedrive_folder: str = '',
        cancel_event: Optional[threading.Event] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        workspace_only: bool = False,

    ):
        self.workspace_only = workspace_only
        self.status_callback = status_callback
        self.onedrive_folder = onedrive_folder.strip('/')

        self.cancel_event = cancel_event
        self.subida_estado("Autenticando con Google Drive...")
        self.google = GoogleService()
        self.subida_estado("Autenticando con OneDrive...")
        self.one = OneDriveService()
        self.subida_estado("Autenticación completa. Preparando migración...")
        self.progress = cargar_proceso(PROGRESS_FILE)

        correo_google = self.google.usuario
        correo_onedrive = self.one.usuario
        if correo_google != correo_onedrive:

            self._init_logger()
            self.logger.error("Los correos de Google y OneDrive no coinciden. Cancelando migración.")
            raise MigrationCancelled("Los correos de autenticación no coinciden.")

        self.correo_general = correo_google
        self.shared_folder_names = self.google.obtener_nombres_carpetas_compartidas_conmigo()
        print(f"Carpetas compartidas encontradas: {self.shared_folder_names}")

        self._init_logger()
        self.logger.info("DirectMigrator inicializado correctamente.")
    
        
    """
    Configura el logger de la clase 'DirectMigrator' solo si aún no tiene handlers.
    Evita duplicar mensajes si se instancian múltiples migrators.
    """
    def _init_logger(self):

        logger = logging.getLogger('DirectMigrator')

        if logger.handlers:
            self.logger = logger
            return


        logger.setLevel(logging.INFO)


        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
        logger.addHandler(ch)


        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
        logger.addHandler(fh)


        self.logger = logger

    """
    Llama al callback de estado si fue provisto (por ejemplo, para actualizar la GUI).

    Args:
        msg (str): Mensaje de estado.
    """
    def subida_estado(self, msg: str):

        if self.status_callback:
            self.status_callback(msg)

    """
    Método principal que migra archivos de 'Mi unidad' y luego lanza 
    la migración de Unidades Compartidas si corresponde.

    Pasos:
    1. Obtener lista de archivos exportables en "Mi unidad" y contarlos.
    2. Obtener lista de archivos exportables en Unidades Compartidas donde el usuario es "organizer".
    3. Calcular total de tareas para la barra de progreso.
    4. Migrar archivos de "Mi unidad": descargar/exportar + subir a OneDrive.
    5. Marcar cada archivo migrado en el progreso y guardarlo.
    6. Migrar Unidades Compartidas en un método separado `_migrar_unidades_compartidas`.
    
    Args:
        skip_existing (bool): Si es True, salta archivos ya migrados según PROGRESS_FILE.
        progress_callback (callable | None): Callback (processed, total, name) para progreso global.
        file_progress_callback (callable | None): Callback (bytes_sent, total_bytes, name) para progreso por archivo.
    """
    def migrar(
        self,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[int, int, str], None]] = None
        
    ):



        # ─── Fase 3: “Unidades Compartidas” ───
        self.logger.info("Contando archivos exportables en Unidades Compartidas...")
        self.subida_estado("Contando archivos en Unidades Compartidas...")
        shared_total = 0
        unidades = self.google.listar_unidades_compartidas()
        for unidad in unidades:
            permisos = self.google.listar_permisos(unidad['id'])
            admins = [
                p.get('emailAddress') or p.get('domain') or p['type']
                for p in permisos
                if p['role'] == 'organizer'
            ]
            if self.google.usuario not in admins:
                continue
            contenido = self.google.listar_contenido_drive(unidad['id'])
            if self.workspace_only:
                shared_total += sum(
                    1 for a in contenido
                    if a['mimeType'] in GOOGLE_EXPORT_FORMATS or a['mimeType'] in OFFICE_MIME_TYPES
                )
            else:
                shared_total += len(contenido)

        total_tasks =  shared_total
        self.logger.info(
            f"Total a migrar: {total_tasks} "
            f"(Unidades Compartidas: {shared_total}"
        )
        self.subida_estado(
            f"Total a migrar: {shared_total})"
        )

        processed = 0

        # ─── Migrar Unidades Compartidas ───
        try:
            self.logger.info("Iniciando migración de Unidades Compartidas...")
            self._migrar_unidades_compartidas(processed, total_tasks, progress_callback)
            self.logger.info("Migración de Unidades Compartidas completada.")
        except Exception as e:
            self.logger.error(f"Error al migrar Unidades Compartidas: {str(e)}")

            
        
    """
    Migra archivos de las Unidades Compartidas donde el usuario es organizador.

    Args:
        processed (int): Cantidad de archivos ya procesados (de "Mi unidad").
        total_tasks (int): Total de archivos a migrar (incluyendo "Mi unidad" y compartidos).
        progress_callback (callable | None): Callback de progreso global.
    """
    def _migrar_unidades_compartidas(
            self,
            processed: int,
            total_tasks: int,
            progress_callback: Optional[Callable[[int, int, str], None]]
        ):

        usuario_actual = self.google.usuario
        unidades = self.google.listar_unidades_compartidas()

        for unidad in unidades:
            if self.cancel_event and self.cancel_event.is_set():
                self.logger.info(
                    "Migración cancelada por usuario (antes de procesar unidad compartida)"
                )
                return

            permisos = self.google.listar_permisos(unidad['id'])
            admins = [
                p.get('emailAddress') or p.get('domain') or p['type']
                for p in permisos
                if p['role'] == 'organizer'
            ]
            if usuario_actual not in admins:
                continue

            nombre_unidad = limpiar_archivos(unidad['name'])
            ruta_onedrive = f"Unidades Compartidas/{nombre_unidad}"
            self.one.crear_carpeta(ruta_onedrive)

            # ─── Generar y subir roles.txt y acceso.txt ───
            lineas_roles = []
            for p in permisos:
                rol_esp = self.google.rol_espanol(p['role'])
                quien = p.get('emailAddress') or p.get('domain') or p['type']
                lineas_roles.append(f"{quien} → {rol_esp}")
            contenidos_roles = "\n".join(lineas_roles)

            identificadores = [
                p.get('emailAddress') or p.get('domain') or p['type']
                for p in permisos
            ]
            contenidos_acceso = ",".join(identificadores)


            buffer_roles = io.BytesIO(contenidos_roles.encode('utf-8'))
            buffer_acceso = io.BytesIO(contenidos_acceso.encode('utf-8'))

            ruta_roles = f"{ruta_onedrive}/roles.txt".lstrip('/')
            self.one.subir(
                file_data=buffer_roles,
                remote_path=ruta_roles,
                size=len(buffer_roles.getvalue())
            )

            ruta_acceso = f"{ruta_onedrive}/acceso.txt".lstrip('/')
            self.one.subir(
                file_data=buffer_acceso,
                remote_path=ruta_acceso,
                size=len(buffer_acceso.getvalue())
            )

            archivos = self.google.listar_contenido_drive(unidad['id'])
            folders_dict = {
                a['id']: a
                for a in archivos
                if a['mimeType'] == 'application/vnd.google-apps.folder'
            }
            if self.workspace_only:
                archivos_dict = {
                    a['id']: a
                    for a in archivos
                    if (
                        a['mimeType'] in GOOGLE_EXPORT_FORMATS
                        or a['mimeType'] in OFFICE_MIME_TYPES
                    )
                }
            else:
                archivos_dict = {
                    a['id']: a
                    for a in archivos
                    if a['mimeType'] != 'application/vnd.google-apps.folder'
                }
            
            for archivo in archivos_dict.values():
                if self.cancel_event and self.cancel_event.is_set():
                    self.logger.info(
                        f"Migración cancelada por usuario (en unidad compartida '{nombre_unidad}')"
                    )
                    return

                if archivo['mimeType'] == 'application/vnd.google-apps.shortcut':
                    self.logger.info(f"Omitido acceso directo: {archivo['name']}")
                    continue
                
                
                size_bytes = int(archivo.get('size', 0) or 0)
                if size_bytes > MAX_FILE_SIZE_BYTES:
                    mensaje = f"Tamaño excede 10 GB ({size_bytes/1024**3:.2f} GB). Se omitirá."
                    drive_path = f"{ruta_completa}/{file_name}"
                    self._log_error(drive_path, mensaje)
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_tasks, file_name)
                    continue

                file_id = archivo['id']
                file_name = archivo['name']
                parents = archivo.get('parents') or []

                if file_id in self.progress.get('migrated_files', set()):
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_tasks, file_name)
                    continue

                if parents:
                    path_parts, _ = self.google.obtener_ruta_carpeta(parents[0], folders_dict)
                else:
                    path_parts = []
                ruta_interna = "/".join(path_parts)
                ruta_completa = f"{ruta_onedrive}/{ruta_interna}".strip("/")

                if ruta_completa:
                    self.one.crear_carpeta(ruta_completa)

                try:
                    data, final_name = self.google.descargar(archivo)
                    if data:
                        data.seek(0, 2)
                        total_bytes = data.tell()
                        data.seek(0)

                        remote_path = f"{ruta_completa}/{final_name}".strip("/")

                        fecha_drive = archivo.get('modifiedTime')
                        fecha_onedrive = self.one.obtener_fecha_modificacion(remote_path)

            
                        if fecha_onedrive >= fecha_drive:
                            self.logger.info(f"Omitido: {remote_path} en OneDrive es igual o más reciente.")
                            self.progress.setdefault('migrated_files', set()).add(file_id)
                            guardar_progreso(PROGRESS_FILE, self.progress)
                            processed += 1
                            if progress_callback:
                                progress_callback(processed, total_tasks, file_name)
                            continue
                        
                        self.one.subir(
                            file_data=data,
                            remote_path=remote_path,
                            size=total_bytes
                        )
                        self.logger.info(
                            f"Compartido - Subida '{file_name}' en '{ruta_completa}'"
                        )

                        self.progress.setdefault('migrated_files', set()).add(file_id)
                        guardar_progreso(PROGRESS_FILE, self.progress)

                except Exception as e:
                    mensaje = str(e)
                    self.logger.error(
                        f"Error al migrar archivo '{file_name}' en '{ruta_completa}': {mensaje}"
                    )

                    drive_path = f"{ruta_completa}/{file_name}"
                    self._log_error(drive_path, mensaje)
                    if "timed out" in mensaje.lower() or "unable to find the server" in mensaje.lower():
                        raise ConnectionLost(mensaje)

                    print(f"[ERROR] En Unidad Compartida '{drive_path}' → {mensaje}")

                processed += 1
                if progress_callback:
                    progress_callback(processed, total_tasks, file_name)


    """
    Añade una entrada en el log de errores (migration_errors.txt).
    Formato de cada línea: 'YYYY-MM-DD HH:MM:SS - ruta - mensaje'

    Args:
        drive_path (str): Ruta interna del archivo que falló.
        message (str): Mensaje de error.
    """
    def _log_error(self, drive_path: str, message: str) -> None:
        """
        Añade una entrada en el log de errores (una sola línea).
        Formato: 'YYYY-MM-DD HH:MM:SS - ruta - mensaje'
        """
        clean_path = drive_path.replace('\r', '').replace('\n', '')
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {clean_path} - {message}\n"
        try:
            with open(self.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            self.logger.error(f"Imposible escribir error en {self.ERROR_LOG}")

    """
    Traduce mensajes de error crudos en algo legible para el usuario.
    """
    def _format_error(self, raw_msg: str) -> str:
        msg = str(raw_msg)

        if 'exportSizeLimitExceeded' in msg:
            return "Este archivo es demasiado grande para ser exportado desde Google Docs."
        if 'cannotExportFile' in msg or 'This file cannot be exported by the user.' in msg:
            return "No tienes permiso para exportar este archivo desde Google Docs."
        if '403' in msg and 'export' in msg:
            return "No tienes permiso para exportar este archivo desde Google Docs."
        if 'fileNotDownloadable' in msg:
            return "Este archivo no puede ser descargado directamente. Usa exportación si es un archivo de Google Workspace."
        if '404' in msg:
            return "Archivo no encontrado."
        if 'timed out' in msg.lower():
            return "Tiempo de espera agotado al leer los datos."
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

        return msg
