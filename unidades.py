from google_service import GoogleService
from onedrive_service import OneDriveService
from utils import sanitize_filename
from config import GOOGLE_EXPORT_FORMATS
import io

class SharedDriveMigrator:
    def __init__(self, google_service: GoogleService, onedrive_service: OneDriveService):
        self.google = google_service
        self.onedrive = onedrive_service
        self.usuario = self.google.obtener_usuario()

    def migrar_unidades(self):
        unidades = self.google.listar_unidades_compartidas()

        for unidad in unidades:
            permisos = self.google.listar_permisos(unidad['id'])
            admins = [p.get('emailAddress') or p.get('domain') or p['type']
                      for p in permisos if p['role'] == 'organizer']

            if self.usuario not in admins:
                continue

            nombre_unidad = sanitize_filename(unidad['name'])
            ruta_onedrive = f"Unidades Compartidas/{nombre_unidad}"
            self.onedrive.create_folder(ruta_onedrive)

            # roles.txt
            roles_txt = "Correo                          | Rol\n"
            roles_txt += "-------------------------------|----------------------\n"
            for p in permisos:
                correo = p.get('emailAddress') or p.get('domain') or p['type']
                rol = self.google.rol_espanol(p['role'])
                roles_txt += f"{correo:<31}| {rol}\n"
            self.onedrive.upload(
                file_data=io.BytesIO(roles_txt.encode("utf-8")),
                remote_path=f"{ruta_onedrive}/roles.txt",
                size=len(roles_txt.encode("utf-8"))
            )

            # acceso.txt
            no_admins = [p.get('emailAddress') or p.get('domain') or p['type']
                         for p in permisos if p['role'] != 'organizer']
            acceso_txt = ",".join(no_admins)
            self.onedrive.upload(
                file_data=io.BytesIO(acceso_txt.encode("utf-8")),
                remote_path=f"{ruta_onedrive}/acceso.txt",
                size=len(acceso_txt.encode("utf-8"))
            )

            # Archivos y carpetas
            archivos = self.google.listar_contenido_drive(unidad['id'])

            folders_dict = {
                a['id']: a for a in archivos if a['mimeType'] == 'application/vnd.google-apps.folder'
            }
            archivos_dict = {
                a['id']: a for a in archivos if a['mimeType'] in GOOGLE_EXPORT_FORMATS
            }

            for archivo in archivos_dict.values():
                file_id = archivo['id']
                file_name = archivo['name']
                mime_type = archivo['mimeType']
                parents = archivo.get('parents') or []

                # Reconstruir ruta de carpetas completa como en "Mi unidad"
                if parents:
                    path_parts = self.google.get_folder_path(parents[0], folders_dict)
                else:
                    path_parts = []

                folder_path = "/".join(path_parts)
                ruta_completa = f"{ruta_onedrive}/{folder_path}".strip("/")

                # Crear ruta en OneDrive si es necesario
                if ruta_completa:
                    self.onedrive.create_folder(ruta_completa)

                try:
                    data, final_name = self.google.download_file(archivo)
                    if data:
                        data.seek(0, 2)
                        total_bytes = data.tell()
                        data.seek(0)
                        remote_path = f"{ruta_completa}/{final_name}".strip("/")
                        self.onedrive.upload(
                            file_data=data,
                            remote_path=remote_path,
                            size=total_bytes
                        )
                except Exception as e:
                    print(f"Error al migrar archivo {file_name}: {str(e)}")
