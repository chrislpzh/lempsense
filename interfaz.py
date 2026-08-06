import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

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

    # Paleta de colores centralizada para mantener consistencia visual
    COLOR_BG = "#f2f4f8"
    COLOR_HEADER = "#1d4ed8"
    COLOR_SUBTITLE = "#64748b"
    COLOR_CARD_BG = "#ffffff"
    COLOR_CARD_BORDER = "#e2e8f0"
    COLOR_MODO_BG = "#e0e7ff"
    COLOR_MODO_FG = "#3730a3"
    COLOR_VIDEO_BG = "#0f172a"
    COLOR_VIDEO_BORDER = "#1d4ed8"
    COLOR_TEXT_GRAY = "#475569"
    COLOR_AZUL = "#2563eb"
    COLOR_VERDE = "#16a34a"
    COLOR_NARANJA = "#d97706"
    COLOR_ROJO = "#dc2626"
    COLOR_PRIMARY_BTN = "#2563eb"
    COLOR_PRIMARY_BTN_HOVER = "#1d4ed8"
    COLOR_SECONDARY_BTN = "#e2e8f0"
    COLOR_SECONDARY_BTN_HOVER = "#cbd5e1"
    COLOR_DANGER_BTN = "#fee2e2"
    COLOR_DANGER_BTN_FG = "#b91c1c"

    def __init__(self):
        self.ventana = tk.Tk()
        self.ventana.title("Lempsense")
        self.ventana.geometry("980x900")
        self.ventana.resizable(False, False)
        self.ventana.configure(bg=self.COLOR_BG)
        self.centrar_ventana(980, 900)
        self.configurar_icono()

        # La salida de depuración genera 64 líneas por análisis y también
        # ralentiza la aplicación, especialmente desde una terminal.
        self.reconocedor = ReconocedorBilletes("referencias", debug=False)
        self.voz = Voz()
        self.comandos_voz = None
        self.camara = None
        self.frame_actual = None

        self.estado = self.MENU
        self.resultado_actual = "Todavía no hay resultado."
        self.modo_automatico = True
        self.ultimo_analisis = 0
        self.intervalo_analisis = 0.7
        # Mantiene detalle suficiente cuando el billete está en la mano y
        # ocupa menos espacio que cuando se coloca sobre el escritorio.
        self.ancho_maximo_analisis = 1280
        self.analisis_en_curso = False
        self.resultados_analisis = queue.Queue()
        self.confirmaciones_necesarias = 2
        self.ausencias_necesarias = 3

        self.denominacion_anterior = None
        self.conteo_estable = 0
        self.conteo_ausente = 0
        self.billete_registrado = False

        self.billetes = []
        self.precio_compra = None
        self.ultimo_mensaje_hablado = ""

        self.crear_carpetas()
        self.configurar_estilos()
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

    def configurar_icono(self):

        ICONO_ARCHIVO = "lempira.jpg"
        carpeta_proyecto = os.path.dirname(os.path.abspath(__file__))
        ruta_icono = os.path.join(carpeta_proyecto, ICONO_ARCHIVO)

        if not os.path.isfile(ruta_icono):
            print(f"Aviso: no se encontró el ícono en '{ruta_icono}'.")
            return

        try:
            imagen_icono = Image.open(ruta_icono)
            if imagen_icono.mode not in ("RGB", "RGBA"):
                imagen_icono = imagen_icono.convert("RGBA")
            self._icono_tk = ImageTk.PhotoImage(imagen_icono)
            self.ventana.iconphoto(True, self._icono_tk)
            print(f"Ícono cargado correctamente desde '{ruta_icono}'.")
        except Exception as error:
            print(f"No se pudo cargar el ícono desde '{ruta_icono}':", error)

    def crear_carpetas(self):
        os.makedirs("capturas", exist_ok=True)
        os.makedirs("referencias", exist_ok=True)

    # ------------------------------------------------------------------
    # Estilos
    # ------------------------------------------------------------------
    def configurar_estilos(self):
        """Define los estilos ttk reutilizados por toda la interfaz."""
        estilo = ttk.Style(self.ventana)
        # 'clam' es el único theme base que respeta bien los colores
        # personalizados de fondo/texto en botones en Windows y Linux.
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        fuente_base = ("Segoe UI", 11)
        fuente_boton = ("Segoe UI", 11, "bold")

        estilo.configure(
            "Primary.TButton",
            font=fuente_boton,
            foreground="white",
            background=self.COLOR_PRIMARY_BTN,
            borderwidth=0,
            focusthickness=0,
            padding=(10, 9),
        )
        estilo.map(
            "Primary.TButton",
            background=[("active", self.COLOR_PRIMARY_BTN_HOVER),
                        ("pressed", self.COLOR_PRIMARY_BTN_HOVER)],
        )

        estilo.configure(
            "Secondary.TButton",
            font=fuente_base,
            foreground="#1e293b",
            background=self.COLOR_SECONDARY_BTN,
            borderwidth=0,
            focusthickness=0,
            padding=(8, 7),
        )
        estilo.map(
            "Secondary.TButton",
            background=[("active", self.COLOR_SECONDARY_BTN_HOVER),
                        ("pressed", self.COLOR_SECONDARY_BTN_HOVER)],
        )

        estilo.configure(
            "Danger.TButton",
            font=fuente_base,
            foreground=self.COLOR_DANGER_BTN_FG,
            background=self.COLOR_DANGER_BTN,
            borderwidth=0,
            focusthickness=0,
            padding=(8, 9),
        )
        estilo.map(
            "Danger.TButton",
            background=[("active", "#fecaca"), ("pressed", "#fecaca")],
        )

        estilo.configure(
            "Card.TFrame",
            background=self.COLOR_CARD_BG,
            relief="flat",
        )
        estilo.configure(
            "Fondo.TFrame",
            background=self.COLOR_BG,
        )
        estilo.configure(
            "Precio.TEntry",
            padding=6,
            fieldbackground="white",
        )

    def tarjeta(self, contenedor, **kwargs):
        """Crea un panel tipo 'card' con borde suave, para agrupar contenido."""
        borde = tk.Frame(contenedor, bg=self.COLOR_CARD_BORDER)
        interior = tk.Frame(borde, bg=self.COLOR_CARD_BG, **kwargs)
        interior.pack(fill="both", expand=True, padx=1, pady=1)
        return borde, interior

    def alternar_mute(self):
        self.voz.alternar_mute()

        if self.voz.esta_muteado():
            self.btn_mute.config(text="🔇 Voz")
            if self.comandos_voz is not None:
                self.comandos_voz.suspender()
                self.label_estado_voz.config(
                    text="●  Voz y comandos pausados", fg=self.COLOR_NARANJA
                )
        else:
            self.btn_mute.config(text="🔊 Voz")
            if self.comandos_voz is not None:
                self.comandos_voz.reanudar()
                self.label_estado_voz.config(
                    text="●  Comandos de voz: activos", fg=self.COLOR_VERDE
                )
            # Al reactivar la salida, recupera el mensaje vigente completo.
            # Reiniciarlo es más claro que continuar a mitad de una frase.
            self.decir(self.resultado_actual)

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------
    def crear_interfaz(self):
        contenedor = tk.Frame(self.ventana, bg=self.COLOR_BG)
        contenedor.pack(fill="both", expand=True, padx=22, pady=10)

        # ---- Encabezado ----
        encabezado = tk.Frame(contenedor, bg=self.COLOR_BG)
        encabezado.pack(fill="x", pady=(0, 2))
        tk.Label(
            encabezado, text="Lempsense", font=("Segoe UI", 26, "bold"),
            bg=self.COLOR_BG, fg=self.COLOR_HEADER
        ).pack()
        tk.Label(
            encabezado,
            text="Asistente auditivo para reconocimiento de billetes hondureños",
            font=("Segoe UI", 11), bg=self.COLOR_BG, fg=self.COLOR_SUBTITLE
        ).pack(pady=(1, 0))

        self.label_estado_voz = tk.Label(
            encabezado, text="●  Comandos de voz: iniciando...",
            font=("Segoe UI", 10, "bold"), bg=self.COLOR_BG, fg="gray"
        )
        self.label_estado_voz.pack(pady=(4, 0))

        # ---- Indicador de modo (estilo "pill") ----
        pill = tk.Frame(contenedor, bg=self.COLOR_MODO_BG)
        pill.pack(pady=6)
        self.label_modo = tk.Label(
            pill, text="Modo: menú principal",
            font=("Segoe UI", 12, "bold"),
            bg=self.COLOR_MODO_BG, fg=self.COLOR_MODO_FG,
            padx=16, pady=4,
        )
        self.label_modo.pack()

        # ---- Video ----
        borde_video = tk.Frame(contenedor, bg=self.COLOR_VIDEO_BORDER)
        borde_video.pack(pady=4)
        self.frame_video = tk.Frame(
            borde_video, width=640, height=340, bg=self.COLOR_VIDEO_BG
        )
        self.frame_video.pack(padx=3, pady=3)
        self.frame_video.pack_propagate(False)
        self.label_video = tk.Label(
            self.frame_video,
            bg=self.COLOR_VIDEO_BG,
            fg="#94a3b8",
            text="La cámara se activará al elegir una función",
            font=("Segoe UI", 13),
        )
        self.label_video.pack(fill="both", expand=True)

        # ---- Panel de resultado ----
        borde_resultado, panel_resultado = self.tarjeta(contenedor)
        borde_resultado.pack(fill="x", pady=(6, 4))
        self.label_resultado = tk.Label(
            panel_resultado, text="Elija una opción",
            font=("Segoe UI", 17, "bold"), fg=self.COLOR_AZUL,
            bg=self.COLOR_CARD_BG, wraplength=880, pady=4
        )
        self.label_resultado.pack(fill="x", padx=16)
        self.label_detalle = tk.Label(
            panel_resultado, text="Reconocer billete | Contar dinero | Calcular cambio",
            font=("Segoe UI", 10), bg=self.COLOR_CARD_BG, fg=self.COLOR_TEXT_GRAY,
            wraplength=880
        )
        self.label_detalle.pack(fill="x", padx=16, pady=(0, 6))

        # ---- Opciones principales ----
        tk.Label(
            contenedor, text="OPCIONES PRINCIPALES", font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_BG, fg=self.COLOR_SUBTITLE
        ).pack(pady=(2, 2), anchor="w")
        opciones = tk.Frame(contenedor, bg=self.COLOR_BG)
        opciones.pack(fill="x", pady=(0, 4))
        opciones.grid_columnconfigure((0, 1, 2), weight=1, uniform="op")

        ttk.Button(
            opciones, text="Reconocer billete", style="Primary.TButton",
            command=self.iniciar_modo_reconocer
        ).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(
            opciones, text="Contar dinero", style="Primary.TButton",
            command=self.iniciar_modo_contar
        ).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(
            opciones, text="Calcular cambio", style="Primary.TButton",
            command=self.iniciar_modo_cambio
        ).grid(row=0, column=2, padx=5, pady=2, sticky="ew")

        # ---- Acciones secundarias ----
        tk.Label(
            contenedor, text="ACCIONES", font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_BG, fg=self.COLOR_SUBTITLE
        ).pack(pady=(6, 2), anchor="w")
        acciones = tk.Frame(contenedor, bg=self.COLOR_BG)
        acciones.pack(fill="x")

        acciones2 = tk.Frame(contenedor, bg=self.COLOR_BG)
        acciones2.pack(fill="x", pady=(2, 0))

        opciones_boton = dict(side="left", fill="x", expand=True, padx=3, pady=2)

        self.btn_menu_principal = ttk.Button(
            acciones, text="Menú principal", style="Secondary.TButton",
            command=self.presentar_menu
        )
        self.btn_menu_principal.pack(**opciones_boton)

        # Solo relevantes al contar dinero / registrar pago de cambio; se
        # muestran u ocultan según el estado (ver actualizar_controles_dinamicos).
        self.btn_eliminar_ultimo = ttk.Button(
            acciones2,
            text="Eliminar último",
            style="Secondary.TButton",
            command=self.eliminar_ultimo
        )

        self.btn_repetir = ttk.Button(
            acciones, text="Repetir", style="Secondary.TButton",
            command=self.repetir_resultado
        )
        self.btn_repetir.pack(**opciones_boton)

        self.btn_terminar_calcular = ttk.Button(
            acciones2,
            text="Terminar / calcular",
            style="Secondary.TButton",
            command=self.terminar_accion
        )

        self.btn_ayuda = ttk.Button(
            acciones, text="Ayuda", style="Secondary.TButton",
            command=self.mostrar_ayuda
        )
        self.btn_ayuda.pack(**opciones_boton)

        self.btn_mute = ttk.Button(
    acciones,
    text="🔊 Voz",
    style="Secondary.TButton",
    command=self.alternar_mute
)
        self.btn_mute.pack(**opciones_boton)

        self.btn_salir = ttk.Button(
            acciones, text="Salir", style="Danger.TButton",
            command=self.cerrar
        )
        self.btn_salir.pack(**opciones_boton)

        self._opciones_boton_acciones = opciones_boton

        # ---- Precio (solo visible mientras se pide/confirma en Calcular cambio) ----
        self.borde_precio, panel_precio = self.tarjeta(contenedor)
        precio = tk.Frame(panel_precio, bg=self.COLOR_CARD_BG)
        precio.pack(pady=5)
        tk.Label(
            precio, text="Precio de compra:", font=("Segoe UI", 11),
            bg=self.COLOR_CARD_BG, fg="#1e293b"
        ).grid(row=0, column=0, padx=(4, 8))
        self.entrada_precio = ttk.Entry(
            precio, width=14, font=("Segoe UI", 12), style="Precio.TEntry"
        )
        self.entrada_precio.grid(row=0, column=1, padx=4)
        ttk.Button(
            precio, text="Aceptar precio", style="Primary.TButton",
            command=self.aceptar_precio_escrito
        ).grid(row=0, column=2, padx=(8, 4))

        # ---- Pie de página ----
        self.label_pie = tk.Label(
            contenedor,
            text="En cualquier momento puede decir: ayuda, repetir, cancelar o menú principal",
            font=("Segoe UI", 9, "italic"), bg=self.COLOR_BG, fg=self.COLOR_SUBTITLE
        )
        self.label_pie.pack(pady=(4, 0))

    
        # Aplica la visibilidad inicial (arrancamos en modo menú).
        self.actualizar_controles_dinamicos()

    def actualizar_controles_dinamicos(self):
        """Muestra u oculta los controles que solo aplican a ciertos modos."""
        # "Eliminar último" y "Terminar / calcular" solo tienen sentido
        # mientras se están registrando billetes (contar dinero o pago de cambio).
        mostrar_conteo = self.estado in (
            self.CONTAR,
            self.CAMBIO_PRECIO,
            self.CAMBIO_CONFIRMAR,
            self.CAMBIO_PAGO,
        )
        if mostrar_conteo:
            if not self.btn_eliminar_ultimo.winfo_ismapped():
                self.btn_eliminar_ultimo.pack(**self._opciones_boton_acciones)
            if not self.btn_terminar_calcular.winfo_ismapped():
                self.btn_terminar_calcular.pack(**self._opciones_boton_acciones)
        else:
            self.btn_eliminar_ultimo.pack_forget()
            self.btn_terminar_calcular.pack_forget()

        # El precio de compra solo se pide/confirma en esta etapa de
        # "Calcular cambio"; una vez confirmado, ya no hace falta el campo.
        mostrar_precio = self.estado in (self.CAMBIO_PRECIO, self.CAMBIO_CONFIRMAR)
        if mostrar_precio:
            if not self.borde_precio.winfo_ismapped():
                self.borde_precio.pack(fill="x", pady=(6, 2), before=self.label_pie)
        else:
            self.borde_precio.pack_forget()

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
                text="●  Comandos de voz: activos", fg=self.COLOR_VERDE
            )
        except FileNotFoundError:
            self.label_estado_voz.config(
                text="●  Comandos de voz: modelo no encontrado", fg=self.COLOR_NARANJA
            )
        except Exception as error:
            self.label_estado_voz.config(
                text="●  Comandos de voz: no disponibles", fg=self.COLOR_ROJO
            )
            print("No se pudieron iniciar los comandos de voz:", error)

    def procesar_comando_voz(self, comando, texto):
        # El modo silencio también suspende los comandos. Esta segunda
        # comprobación descarta callbacks que ya estaban en cola al silenciar.
        if self.voz.esta_muteado():
            return

        # Mientras habla, el micrófono puede captar fragmentos del altavoz.
        # Solo una orden válida debe interrumpir; el ruido no reconocido se ignora.
        if comando == "NO_ENTENDIDO" and self.voz.esta_hablando:
            return

        # La orden del usuario siempre tiene prioridad sobre lo que Lempsense
        # estuviera diciendo en ese momento.
        self.voz.detener()
        self.label_estado_voz.config(
            text=f"●  Comando escuchado: {texto}", fg=self.COLOR_VERDE
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
        if self.comandos_voz is not None and not self.voz.esta_muteado():
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

        self.detener_camara()
        self.estado = self.MENU
        self.billetes = []
        self.precio_compra = None
        self.reiniciar_deteccion()
        self.label_modo.config(text="Modo: menú principal")
        self.label_resultado.config(text="Elija una opción", fg=self.COLOR_AZUL)
        self.label_detalle.config(
            text="Reconocer billete | Contar dinero | Calcular cambio"
        )
        self.actualizar_controles_dinamicos()
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
        self.label_resultado.config(text="Buscando billete...", fg=self.COLOR_NARANJA)
        self.label_detalle.config(text="Coloque un billete frente a la cámara")
        self.actualizar_controles_dinamicos()
        if self.asegurar_camara():
            self.decir(
                "Modo reconocer billete. Coloque un billete frente a la cámara."
            )

    def iniciar_modo_contar(self):
        self.estado = self.CONTAR
        self.billetes = []
        self.reiniciar_deteccion()
        self.label_modo.config(text="Modo: contar dinero")
        self.label_resultado.config(text="Total: 0 lempiras", fg=self.COLOR_AZUL)
        self.label_detalle.config(text="Coloque el primer billete")
        self.actualizar_controles_dinamicos()
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
        if self.asegurar_camara():
            self.decir(
            "Modo calcular cambio. Diga el precio de la compra en lempiras."
        )

    def solicitar_precio(self):
        self.estado = self.CAMBIO_PRECIO
        self.precio_compra = None
        self.label_modo.config(text="Modo: calcular cambio")
        self.label_resultado.config(text="Diga el precio de la compra", fg=self.COLOR_AZUL)
        self.label_detalle.config(
            text="También puede escribir el precio y presionar Aceptar precio"
        )
        self.actualizar_controles_dinamicos()
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
            text=f"Precio: {numero} lempiras. ¿Confirmar?", fg=self.COLOR_AZUL
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
        self.label_resultado.config(text="Pago registrado: 0 lempiras", fg=self.COLOR_AZUL)
        self.label_detalle.config(text="Coloque el primer billete del pago")
        self.actualizar_controles_dinamicos()
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

    def detener_camara(self):
        if self.camara is not None:
            self.camara.release()
            self.camara = None

        self.label_video.configure(
            image="",
            text="La cámara se activará al elegir una función"
        )
        self.label_video.imgtk = None

    def actualizar_video(self):
        if self.camara is None:
            return
        ret, frame = self.camara.read()
        if ret:
            self.frame_actual = frame
            # Llena el marco sin deformar la imagen de la cámara. Cuando la
            # proporción del video es distinta, se recortan los bordes de forma
            # centrada en lugar de estirar el frame.
            alto, ancho = frame.shape[:2]
            ancho_destino, alto_destino = 640, 340
            escala = max(
                ancho_destino / float(ancho),
                alto_destino / float(alto),
            )
            nuevo_ancho = int(round(ancho * escala))
            nuevo_alto = int(round(alto * escala))
            redimensionado = cv2.resize(
                frame,
                (nuevo_ancho, nuevo_alto),
                interpolation=cv2.INTER_AREA
                if escala < 1 else cv2.INTER_LINEAR,
            )
            inicio_x = (nuevo_ancho - ancho_destino) // 2
            inicio_y = (nuevo_alto - alto_destino) // 2
            mostrado = redimensionado[
                inicio_y:inicio_y + alto_destino,
                inicio_x:inicio_x + ancho_destino,
            ]
            rgb = cv2.cvtColor(mostrado, cv2.COLOR_BGR2RGB)
            imagen_tk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.label_video.imgtk = imagen_tk
            self.label_video.configure(image=imagen_tk, text="")
            self.procesar_resultados_analisis()
            self.detectar_automaticamente()
        self.ventana.after(15, self.actualizar_video)

    def detectar_automaticamente(self):
        if not self.modo_automatico or self.estado not in (
            self.RECONOCER, self.CONTAR, self.CAMBIO_PAGO
        ):
            return
        if self.analisis_en_curso:
            return
        ahora = time.monotonic()
        if ahora - self.ultimo_analisis < self.intervalo_analisis:
            return
        self.ultimo_analisis = ahora
        frame_analisis = self.preparar_frame_analisis(self.frame_actual)
        self.analisis_en_curso = True
        threading.Thread(
            target=self.analizar_frame_en_segundo_plano,
            args=(frame_analisis,),
            daemon=True,
        ).start()

    def preparar_frame_analisis(self, frame):
        """Reduce el trabajo de ORB sin modificar el video mostrado."""
        alto, ancho = frame.shape[:2]
        if ancho <= self.ancho_maximo_analisis:
            return frame.copy()
        escala = self.ancho_maximo_analisis / float(ancho)
        return cv2.resize(
            frame,
            (self.ancho_maximo_analisis, int(alto * escala)),
            interpolation=cv2.INTER_AREA,
        )

    def analizar_frame_en_segundo_plano(self, frame):
        """Ejecuta OpenCV fuera del hilo que refresca la interfaz."""
        try:
            resultado = self.reconocedor.reconocer(frame)
            self.resultados_analisis.put((resultado, None))
        except Exception as error:
            self.resultados_analisis.put((None, error))

    def procesar_resultados_analisis(self):
        try:
            resultado, error = self.resultados_analisis.get_nowait()
        except queue.Empty:
            return

        self.analisis_en_curso = False
        if error is not None:
            print("Error durante el reconocimiento:", error)
            return
        if self.estado not in (self.RECONOCER, self.CONTAR, self.CAMBIO_PAGO):
            return

        denominacion, confianza, mensaje, detalle = resultado
        self.procesar_deteccion(denominacion, confianza, mensaje, detalle)

    def procesar_deteccion(self, denominacion, confianza, mensaje, detalle):
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
            self.label_resultado.config(text=mensaje, fg=self.COLOR_VERDE)
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
                text=f"{tipo}: {total} lempiras", fg=self.COLOR_VERDE
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
        self.label_resultado.config(text=texto, fg=self.COLOR_NARANJA)
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
        self.label_resultado.config(text=f"Total: {total} lempiras", fg=self.COLOR_AZUL)
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
            text=f"Conteo final: {total} lempiras", fg=self.COLOR_VERDE
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
        self.label_resultado.config(text=resultado, fg=self.COLOR_VERDE)
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

