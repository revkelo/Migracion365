import customtkinter as ctk
from PIL import Image
from PIL import Image, ImageTk

ctk.set_appearance_mode("light")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.iconbitmap("./Gui/icono.ico")
        self.title("Migración con progreso")
        self.geometry("1000x300")
        self.resizable(False, False)
        self.configure(fg_color="white")

        icono_izq = ctk.CTkImage(Image.open("./Gui/googledrive.png"), size=(128, 128))
        icono_der = ctk.CTkImage(Image.open("./Gui/onedrive.png"), size=(128, 128))

        # Imagen izquierda
        ctk.CTkLabel(self, image=icono_izq, text="", fg_color="white").pack(side="left", padx=40, pady=40)

        # Contenedor central
        centro = ctk.CTkFrame(self, fg_color="white")
        centro.pack(side="left", expand=True)

        self.boton = ctk.CTkButton(
            centro,
            text="Migración",
            fg_color="#0078D7",
            hover_color="#106EBE",
            text_color="white",
            width=150,
            height=50,
            command=self.iniciar_migracion
        )
        self.boton.pack(pady=(0, 10))

        # Crear barra y label, pero no mostrar aún
        self.barra = ctk.CTkProgressBar(centro, width=300, height=12, fg_color="#E5E5E5", progress_color="#0078D7")
        self.barra.set(0)

        self.label_archivo = ctk.CTkLabel(centro, text="", text_color="#333333", fg_color="white")

        # Imagen derecha
        ctk.CTkLabel(self, image=icono_der, text="", fg_color="white").pack(side="right", padx=40, pady=40)

        self.files = ["Formulario.docx", "Presentación.pptx", "Datos.xlsx"]
        self.idx_actual = 0
        self.valor_barra = 0.0

    def iniciar_migracion(self):
        self.boton.configure(state="disabled")
        self.idx_actual = 0
        self.barra.pack(pady=(0, 10))
        self.label_archivo.pack()
        self.simular_archivo()

    def simular_archivo(self):
        if self.idx_actual >= len(self.files):
            self.migracion_completada()
            return

        self.label_archivo.configure(text=f"Subiendo: {self.files[self.idx_actual]}")
        self.valor_barra = 0.0
        self.avanzar_barra()

    def avanzar_barra(self):
        incremento = 0.02
        intervalo = 100

        if self.valor_barra < 1.0:
            self.valor_barra += incremento
            self.barra.set(self.valor_barra)
            self.after(intervalo, self.avanzar_barra)
        else:
            self.idx_actual += 1
            self.after(300, self.simular_archivo)

    def migracion_completada(self):
        self.label_archivo.configure(text="Migración completada")
        self.after(1000, lambda: self.label_archivo.pack_forget())  # Ocultar después de 1 segundo
        self.barra.pack_forget()
        self.boton.configure(state="normal")
        self.barra.set(0)

if __name__ == "__main__":
    app = App()
    app.mainloop()
