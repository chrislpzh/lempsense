import os
import time
import tkinter as tk
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk

from comandos_voz import ComandosVoz
from reconocimiento import ReconocedorBilletes
from voz import Voz


class LempiraApp:
    MENU = "MENU"
    RECONOCER = "RECONOCER"
    CONTAR = "CONTAR"
    CAMBIO_PRECIO = "CAMBIO_PRECIO"
    CAMBIO_CONFIRMAR = "CAMBIO_CONFIRMAR"
    CAMBIO_PAGO = "CAMBIO_PAGO"

    def __init__(self):
        self.ventana = tk.Tk()
        self.ventana.title("Lempsense")
        self.ventana.geometry("940x900")
        self.ventana.resizable(False, False)
        self.centrar_ventana(940, 900)

        self.reconocedor = ReconocedorBilletes("referencias")
        self.voz = Voz()
        self.comandos_voz = None
        self.camara = None
        self.frame_actual = None

        self.estado = self.MENU
        self.resultado_actual = "Todavía no hay resultado."
        self.modo_automatico = True
        self.ultimo_analisis = 0
        self.intervalo_analisis = 0.7
        self.confirmaciones_necesarias = 3
        self.ausencias_necesarias = 3

        self.denominacion_anterior = None
        self.conteo_estable = 0
        self.conteo_ausente = 0
        self.billete_registrado = False

        self.billetes = []
        self.precio_compra = None
        self.ultimo_mensaje_hablado = ""

        self.crear_carpetas()
        self.crear_interfaz()
        self.configurar_teclas()
        self.iniciar_comandos_voz()

        self.ventana.after(700, self.presentar_menu)

    def centrar_ventana(self, ancho, alto):
        """Coloca la ventana en el centro de la pantalla disponible."""
        ancho_pantalla = self.ventana.winfo_screenwidth()
        alto_pantalla = self.ventana.winfo_screenheight()
        posicion_x = max(0, (ancho_pantalla - ancho) // 2)
        posicion_y = max(0, (alto_pantalla - alto) // 2)
        self.ventana.geometry(
            f"{ancho}x{alto}+{posicion_x}+{posicion_y}"
        )

    def crear_carpetas(self):
        os.makedirs("capturas", exist_ok=True)
        os.makedirs("referencias", exist_ok=True)

    def crear_interfaz(self):
        tk.Label(
            self.ventana, text="Lempsense", font=("Arial", 28, "bold")
        ).pack(pady=6)
        tk.Label(
            self.ventana,
            text="Asistente auditivo para reconocimiento de billetes hondureños",
            font=("Arial", 13),
        ).pack(pady=2)

        self.label_estado_voz = tk.Label(
            self.ventana, text="Comandos de voz: iniciando...",
            font=("Arial", 10), fg="gray"
        )
        self.label_estado_voz.pack(pady=2)

        self.label_modo = tk.Label(
            self.ventana, text="Modo: menú principal",
            font=("Arial", 14, "bold"), fg="#315a8a"
        )
        self.label_modo.pack(pady=3)

        self.frame_video = tk.Frame(
            self.ventana, width=640, height=440, bg="black"
        )
        self.frame_video.pack(pady=7)
        self.frame_video.pack_propagate(False)
        self.label_video = tk.Label(
            self.frame_video,
            bg="black",
            fg="white",
            text="La cámara se activará al elegir una función",
            font=("Arial", 14),
        )
        self.label_video.pack(fill="both", expand=True)

        self.label_resultado = tk.Label(
            self.ventana, text="Elija una opción",
            font=("Arial", 19, "bold"), fg="blue", wraplength=860
        )
        self.label_resultado.pack(pady=4)
        self.label_detalle = tk.Label(
            self.ventana, text="Reconocer billete | Contar dinero | Calcular cambio",
            font=("Arial", 12), wraplength=860
        )
        self.label_detalle.pack(pady=2)

        opciones = tk.Frame(self.ventana)
        opciones.pack(pady=8)
        tk.Button(
            opciones, text="Reconocer billete", font=("Arial", 12, "bold"),
            width=19, command=self.iniciar_modo_reconocer
        ).grid(row=0, column=0, padx=5, pady=3)
        tk.Button(
            opciones, text="Contar dinero", font=("Arial", 12, "bold"),
            width=19, command=self.iniciar_modo_contar
        ).grid(row=0, column=1, padx=5, pady=3)
        tk.Button(
            opciones, text="Calcular cambio", font=("Arial", 12, "bold"),
            width=19, command=self.iniciar_modo_cambio
        ).grid(row=0, column=2, padx=5, pady=3)

        acciones = tk.Frame(self.ventana)
        acciones.pack(pady=3)
        tk.Button(
            acciones, text="Menú principal", font=("Arial", 11),
            width=16, command=self.presentar_menu
        ).grid(row=0, column=0, padx=4, pady=3)
        tk.Button(
            acciones, text="Eliminar último", font=("Arial", 11),
            width=16, command=self.eliminar_ultimo
        ).grid(row=0, column=1, padx=4, pady=3)
        tk.Button(
            acciones, text="Repetir", font=("Arial", 11),
            width=13, command=self.repetir_resultado
        ).grid(row=0, column=2, padx=4, pady=3)
        tk.Button(
            acciones, text="Terminar / calcular", font=("Arial", 11),
            width=18, command=self.terminar_accion
        ).grid(row=0, column=3, padx=4, pady=3)
        tk.Button(
            acciones, text="Ayuda", font=("Arial", 11),
            width=10, command=self.mostrar_ayuda
        ).grid(row=0, column=4, padx=4, pady=3)
        tk.Button(
            acciones, text="Salir", font=("Arial", 11),
            width=10, command=self.cerrar
        ).grid(row=0, column=5, padx=4, pady=3)

        precio = tk.Frame(self.ventana)
        precio.pack(pady=4)
        tk.Label(precio, text="Precio de compra:", font=("Arial", 11)).grid(
            row=0, column=0, padx=4
        )
        self.entrada_precio = tk.Entry(precio, width=12, font=("Arial", 12))
        self.entrada_precio.grid(row=0, column=1, padx=4)
        tk.Button(
            precio, text="Aceptar precio", font=("Arial", 10),
            command=self.aceptar_precio_escrito
        ).grid(row=0, column=2, padx=4)

        tk.Label(
            self.ventana,
            text="En cualquier momento puede decir: ayuda, repetir, cancelar o menú principal",
            font=("Arial", 10), fg="gray"
        ).pack(pady=3)

    def configurar_teclas(self):
        self.ventana.bind("<Return>", lambda event: self.aceptar_precio_escrito())
        self.ventana.bind("<space>", lambda event: self.repetir_resultado())
        self.ventana.bind("<Escape>", lambda event: self.cerrar())

    def iniciar_comandos_voz(self):
        def callback(comando, texto):
            self.ventana.after(
                0, lambda: self.procesar_comando_voz(comando, texto)
            )

        try:
            self.comandos_voz = ComandosVoz(callback, "modelo_vosk")
            self.comandos_voz.iniciar()
            self.label_estado_voz.config(
                text="Comandos de voz: activos", fg="green"
            )
        except FileNotFoundError:
            self.label_estado_voz.config(
                text="Comandos de voz: modelo no encontrado", fg="orange"
            )
        except Exception as error:
            self.label_estado_voz.config(
                text="Comandos de voz: no disponibles", fg="red"
            )
            print("No se pudieron iniciar los comandos de voz:", error)

    def procesar_comando_voz(self, comando, texto):
        # Mientras habla, el micrófono puede captar fragmentos del altavoz.
        # Solo una orden válida debe interrumpir; el ruido no reconocido se ignora.
        if comando == "NO_ENTENDIDO" and self.voz.esta_hablando:
            return

        # La orden del usuario siempre tiene prioridad sobre lo que Lempsense
        # estuviera diciendo en ese momento.
        self.voz.detener()
        self.label_estado_voz.config(
            text=f"Comando escuchado: {texto}", fg="green"
        )

        if comando == "RECONOCER_BILLETE":
            self.iniciar_modo_reconocer()
        elif comando == "CONTAR_DINERO":
            self.iniciar_modo_contar()
        elif comando == "CALCULAR_CAMBIO":
            self.iniciar_modo_cambio()
        elif comando in ("MENU_PRINCIPAL", "CANCELAR"):
            self.presentar_menu()
        elif comando == "INICIAR_CAMARA":
            self.iniciar_camara()
        elif comando == "NUEVO_BILLETE":
            self.preparar_siguiente_billete()
        elif comando == "REPETIR":
            self.repetir_resultado()
        elif comando == "REPETIR_TOTAL":
            self.repetir_total()
        elif comando == "ELIMINAR_ULTIMO":
            self.eliminar_ultimo()
        elif comando == "TERMINAR_CONTEO":
            self.finalizar_conteo()
        elif comando == "CALCULAR_RESULTADO":
            self.calcular_resultado_cambio()
        elif comando == "CONFIRMAR":
            self.confirmar_precio()
        elif comando == "CORREGIR":
            self.solicitar_precio()
        elif comando.startswith("NUMERO:"):
            self.recibir_numero(int(comando.split(":", 1)[1]))
        elif comando == "AYUDA":
            self.mostrar_ayuda()
        elif comando == "SALIR":
            self.cerrar()
        elif comando == "NO_ENTENDIDO":
            self.comando_no_entendido()

    def decir(self, texto, permitir_interrupcion=False):
        self.resultado_actual = texto
        if self.comandos_voz is not None:
            # La bienvenida usa frases que no coinciden literalmente con los
            # comandos, por lo que puede mantener el micrófono disponible. En
            # las demás respuestas se conserva la protección contra autoescucha.
            if permitir_interrupcion:
                duracion = 0.25
            else:
                duracion = max(2.5, min(9, len(texto) / 17))
            self.comandos_voz.pausar(duracion)
        self.voz.hablar(texto)

    def presentar_menu(self):
        self.estado = self.MENU
        self.billetes = []
        self.precio_compra = None
        self.reiniciar_deteccion()
        self.label_modo.config(text="Modo: menú principal")
        self.label_resultado.config(text="Elija una opción", fg="blue")
        self.label_detalle.config(
            text="Reconocer billete | Contar dinero | Calcular cambio"
        )
        # Se evitan aquí las frases literales que activan comandos. El usuario
        # sí puede decir "reconocer billete", "contar dinero" o
        # "calcular cambio" mientras escucha esta introducción.
        self.decir(
            "Bienvenido a Lempsens. Puedo reconocer billetes, "
            "contar dinero o calcular cambio. "
            "Diga la opción que desea.",
            permitir_interrupcion=True,
        )

    def iniciar_modo_reconocer(self):
        self.estado = self.RECONOCER
        self.billetes = []
        self.reiniciar_deteccion()
        self.label_modo.config(text="Modo: reconocer billete")
        self.label_resultado.config(text="Buscando billete...", fg="orange")
        self.label_detalle.config(text="Coloque un billete frente a la cámara")
        if self.asegurar_camara():
            self.decir(
                "Modo reconocer billete. Coloque un billete frente a la cámara."
            )

    def iniciar_modo_contar(self):
        self.estado = self.CONTAR
        self.billetes = []
        self.reiniciar_deteccion()
        self.label_modo.config(text="Modo: contar dinero")
        self.label_resultado.config(text="Total: 0 lempiras", fg="blue")
        self.label_detalle.config(text="Coloque el primer billete")
        if self.asegurar_camara():
            self.decir(
                "Modo contar dinero. Coloque los billetes uno por uno. "
                "Diga terminar conteo cuando haya finalizado."
            )

    def iniciar_modo_cambio(self):
        self.estado = self.CAMBIO_PRECIO
        self.billetes = []
        self.precio_compra = None
        self.reiniciar_deteccion()
        self.solicitar_precio()

    def solicitar_precio(self):
        self.estado = self.CAMBIO_PRECIO
        self.precio_compra = None
        self.label_modo.config(text="Modo: calcular cambio")
        self.label_resultado.config(text="Diga el precio de la compra", fg="blue")
        self.label_detalle.config(
            text="También puede escribir el precio y presionar Aceptar precio"
        )
        self.decir(
            "Modo calcular cambio. Diga el precio de la compra en lempiras."
        )

    def recibir_numero(self, numero):
        if self.estado not in (self.CAMBIO_PRECIO, self.CAMBIO_CONFIRMAR):
            return
        if numero <= 0:
            self.decir("El precio debe ser mayor que cero. Diga el precio nuevamente.")
            return
        self.precio_compra = numero
        self.estado = self.CAMBIO_CONFIRMAR
        self.label_resultado.config(
            text=f"Precio: {numero} lempiras. ¿Confirmar?", fg="blue"
        )
        self.label_detalle.config(text="Diga confirmar o corregir")
        self.decir(
            f"El precio es {numero} lempiras. Diga confirmar o corregir."
        )

    def aceptar_precio_escrito(self):
        if self.estado not in (self.CAMBIO_PRECIO, self.CAMBIO_CONFIRMAR):
            self.iniciar_modo_cambio()
        try:
            numero = int(self.entrada_precio.get().strip())
        except ValueError:
            self.decir("Escriba un precio válido en números.")
            return
        self.recibir_numero(numero)

    def confirmar_precio(self):
        if self.estado != self.CAMBIO_CONFIRMAR or self.precio_compra is None:
            return
        self.estado = self.CAMBIO_PAGO
        self.billetes = []
        self.reiniciar_deteccion()
        self.label_resultado.config(text="Pago registrado: 0 lempiras", fg="blue")
        self.label_detalle.config(text="Coloque el primer billete del pago")
        if self.asegurar_camara():
            self.decir(
                "Precio confirmado. Muestre uno por uno los billetes que entregará. "
                "Diga calcular cuando termine."
            )

    def iniciar_camara(self):
        if self.estado == self.MENU:
            self.iniciar_modo_reconocer()
            return
        if self.asegurar_camara():
            self.decir("Cámara activada. Coloque el billete frente a la cámara.")

    def asegurar_camara(self):
        if self.camara is not None:
            return True
        self.camara = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.camara.isOpened():
            self.camara = cv2.VideoCapture(0)
        if not self.camara.isOpened():
            self.camara = None
            messagebox.showerror("Error", "No se pudo abrir la cámara.")
            self.decir("No se pudo abrir la cámara.")
            return False
        self.modo_automatico = True
        self.actualizar_video()
        return True

    def actualizar_video(self):
        if self.camara is None:
            return
        ret, frame = self.camara.read()
        if ret:
            self.frame_actual = frame
            mostrado = cv2.resize(frame, (640, 440))
            rgb = cv2.cvtColor(mostrado, cv2.COLOR_BGR2RGB)
            imagen_tk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.label_video.imgtk = imagen_tk
            self.label_video.configure(image=imagen_tk, text="")
            self.detectar_automaticamente()
        self.ventana.after(15, self.actualizar_video)

    def detectar_automaticamente(self):
        if not self.modo_automatico or self.estado not in (
            self.RECONOCER, self.CONTAR, self.CAMBIO_PAGO
        ):
            return
        ahora = time.time()
        if ahora - self.ultimo_analisis < self.intervalo_analisis:
            return
        self.ultimo_analisis = ahora
        denominacion, confianza, mensaje, detalle = self.reconocedor.reconocer(
            self.frame_actual
        )

        if denominacion is None or confianza < 75:
            self.denominacion_anterior = None
            self.conteo_estable = 0
            self.conteo_ausente += 1
            if self.conteo_ausente >= self.ausencias_necesarias:
                self.billete_registrado = False
            self.mostrar_espera()
            return

        self.conteo_ausente = 0
        if denominacion == self.denominacion_anterior:
            self.conteo_estable += 1
        else:
            self.denominacion_anterior = denominacion
            self.conteo_estable = 1

        score = detalle.get("score", "--")
        if self.conteo_estable < self.confirmaciones_necesarias:
            self.label_detalle.config(
                text=f"Confirmando... Coincidencias: {score}"
            )
            return
        if self.billete_registrado:
            self.label_detalle.config(
                text="Billete ya registrado. Retírelo antes de colocar el siguiente."
            )
            return

        self.billete_registrado = True
        self.registrar_billete(int(denominacion), confianza, mensaje)

    def registrar_billete(self, valor, confianza, mensaje):
        if self.estado == self.RECONOCER:
            texto = f"{mensaje}. Retire el billete para reconocer otro."
            self.label_resultado.config(text=mensaje, fg="green")
            self.label_detalle.config(
                text=f"Confianza: {confianza}%. Retire el billete para continuar."
            )
        else:
            self.billetes.append(valor)
            total = sum(self.billetes)
            tipo = "Total" if self.estado == self.CONTAR else "Pago registrado"
            texto = (
                f"Billete de {valor} lempiras registrado. {tipo}: {total} lempiras. "
                "Retire el billete y coloque el siguiente."
            )
            self.label_resultado.config(
                text=f"{tipo}: {total} lempiras", fg="green"
            )
            self.label_detalle.config(
                text=f"Último billete: {valor}. Cantidad de billetes: {len(self.billetes)}"
            )
        self.decir(texto)

    def mostrar_espera(self):
        if self.estado == self.RECONOCER:
            texto = "Buscando billete..."
        elif self.estado == self.CONTAR:
            texto = f"Total: {sum(self.billetes)} lempiras"
        else:
            texto = f"Pago registrado: {sum(self.billetes)} lempiras"
        self.label_resultado.config(text=texto, fg="orange")
        if not self.billete_registrado:
            self.label_detalle.config(text="Coloque un billete frente a la cámara")

    def preparar_siguiente_billete(self):
        self.reiniciar_deteccion()
        self.label_detalle.config(text="Coloque el siguiente billete")
        self.decir("Listo. Coloque el siguiente billete frente a la cámara.")

    def reiniciar_deteccion(self):
        self.denominacion_anterior = None
        self.conteo_estable = 0
        self.conteo_ausente = 0
        self.billete_registrado = False
        self.ultimo_mensaje_hablado = ""

    def repetir_total(self):
        if self.estado not in (self.CONTAR, self.CAMBIO_PAGO):
            self.repetir_resultado()
            return
        self.decir(f"El total registrado es {sum(self.billetes)} lempiras.")

    def eliminar_ultimo(self):
        if self.estado not in (self.CONTAR, self.CAMBIO_PAGO):
            self.decir("Esta opción solo está disponible al contar dinero.")
            return
        if not self.billetes:
            self.decir("Todavía no hay billetes registrados.")
            return
        eliminado = self.billetes.pop()
        total = sum(self.billetes)
        self.reiniciar_deteccion()
        self.label_resultado.config(text=f"Total: {total} lempiras", fg="blue")
        self.decir(
            f"Se eliminó el billete de {eliminado} lempiras. "
            f"El nuevo total es {total} lempiras."
        )

    def finalizar_conteo(self):
        if self.estado != self.CONTAR:
            return
        total = sum(self.billetes)
        cantidad = len(self.billetes)
        self.label_resultado.config(
            text=f"Conteo final: {total} lempiras", fg="green"
        )
        self.decir(
            f"Conteo finalizado. Registró {cantidad} billetes. "
            f"Tiene {total} lempiras. Diga menú principal para continuar."
        )

    def calcular_resultado_cambio(self):
        if self.estado != self.CAMBIO_PAGO or self.precio_compra is None:
            return
        pago = sum(self.billetes)
        diferencia = pago - self.precio_compra
        if diferencia > 0:
            resultado = f"Debe recibir {diferencia} lempiras de cambio."
        elif diferencia == 0:
            resultado = "El pago está completo. No debe recibir cambio."
        else:
            resultado = f"Faltan {-diferencia} lempiras para completar el pago."
        self.label_resultado.config(text=resultado, fg="green")
        self.label_detalle.config(
            text=f"Precio: {self.precio_compra} | Entregado: {pago}"
        )
        self.decir(
            f"El precio es {self.precio_compra} lempiras y entregó {pago}. "
            f"{resultado} Diga menú principal para continuar."
        )

    def terminar_accion(self):
        if self.estado == self.CONTAR:
            self.finalizar_conteo()
        elif self.estado == self.CAMBIO_PAGO:
            self.calcular_resultado_cambio()
        else:
            self.decir("No hay un conteo pendiente para finalizar.")

    def repetir_resultado(self):
        self.decir(self.resultado_actual)

    def mostrar_ayuda(self):
        if self.estado == self.MENU:
            texto = (
                "Diga reconocer billete, contar dinero o calcular cambio. "
                "También puede elegir una opción con los botones."
            )
        elif self.estado == self.RECONOCER:
            texto = (
                "Coloque un billete frente a la cámara. Cuando lo reconozca, "
                "retírelo antes de colocar otro."
            )
        elif self.estado == self.CONTAR:
            texto = (
                "Coloque los billetes uno por uno y retírelos después de cada "
                "confirmación. Puede decir repetir total, eliminar último o terminar conteo."
            )
        elif self.estado in (self.CAMBIO_PRECIO, self.CAMBIO_CONFIRMAR):
            texto = (
                "Diga el precio de la compra. Luego diga confirmar o corregir."
            )
        else:
            texto = (
                "Muestre uno por uno los billetes que entregará. Puede decir "
                "repetir total, eliminar último o calcular."
            )
        self.decir(texto + " En cualquier momento puede decir cancelar o menú principal.")

    def comando_no_entendido(self):
        if self.estado == self.MENU:
            texto = (
                "No entendí la opción. Diga reconocer billete, contar dinero, "
                "calcular cambio o ayuda."
            )
        elif self.estado == self.CAMBIO_PRECIO:
            texto = "No entendí el precio. Dígalo nuevamente en lempiras."
        elif self.estado == self.CAMBIO_CONFIRMAR:
            texto = "Diga confirmar o corregir."
        else:
            texto = "No entendí el comando. Diga ayuda para escuchar las opciones."
        self.decir(texto)

    def cerrar(self):
        self.voz.detener()
        if self.comandos_voz is not None:
            self.comandos_voz.detener()
        if self.camara is not None:
            self.camara.release()
            self.camara = None
        self.voz.sonido_salida()
        self.ventana.destroy()

    def ejecutar(self):
        self.ventana.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.ventana.mainloop()