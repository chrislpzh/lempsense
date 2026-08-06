import json
import os
import queue
import threading
import time
import unicodedata
import re

import sounddevice as sd
from vosk import Model, KaldiRecognizer


class ComandosVoz:
    def __init__(self, callback, modelo_path="modelo_vosk", sample_rate=16000):
        self.callback = callback
        self.modelo_path = modelo_path
        self.sample_rate = sample_rate

        self.activo = False
        self.suspendido = False
        self.pausado_hasta = 0

        self.cola_audio = queue.Queue()
        self.modelo = None
        self.reconocedor = None
        self.reconocedor_lock = threading.Lock()
        self.hilo = None

    def iniciar(self):
        if not os.path.exists(self.modelo_path):
            raise FileNotFoundError(
                f"No se encontró la carpeta del modelo Vosk: {self.modelo_path}"
            )

        self.modelo = Model(self.modelo_path)
        self.reconocedor = KaldiRecognizer(self.modelo, self.sample_rate)
        self.reconocedor.SetWords(False)

        self.activo = True

        self.hilo = threading.Thread(
            target=self._escuchar,
            daemon=True
        )

        self.hilo.start()

    def detener(self):
        self.activo = False
        self.cola_audio.put(None)

    def pausar(self, segundos=2.5):
        """
        Pausa temporalmente la interpretación de comandos.
        Sirve para evitar que la app escuche su propia voz.
        """
        self.pausado_hasta = time.time() + segundos

    def suspender(self):
        """Descarta audio pendiente y bloquea nuevas capturas para Vosk."""
        self.suspendido = True
        self._vaciar_cola_audio()
        with self.reconocedor_lock:
            if self.reconocedor is not None:
                self.reconocedor.Reset()

    def reanudar(self):
        """Reinicia Vosk antes de aceptar audio nuevo del micrófono."""
        self._vaciar_cola_audio()
        with self.reconocedor_lock:
            if self.reconocedor is not None:
                self.reconocedor.Reset()
            # Ignora cualquier final de palabra pronunciada justo al reactivar.
            self.pausado_hasta = time.time() + 0.5
            self.suspendido = False

    def _vaciar_cola_audio(self):
        while True:
            try:
                self.cola_audio.get_nowait()
            except queue.Empty:
                break

    def _callback_audio(self, indata, frames, tiempo, status):
        if status:
            print("Estado del micrófono:", status)

        # Durante una exposición no se conserva ni se acumula lo hablado.
        if self.suspendido:
            return

        self.cola_audio.put(bytes(indata))

    def _escuchar(self):
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._callback_audio
            ):
                print("Comandos de voz activados.")

                while self.activo:
                    data = self.cola_audio.get()

                    if data is None:
                        break

                    with self.reconocedor_lock:
                        if self.suspendido:
                            continue

                        if time.time() < self.pausado_hasta:
                            self.reconocedor.AcceptWaveform(data)
                            continue

                        resultado_completo = self.reconocedor.AcceptWaveform(data)
                        if resultado_completo:
                            resultado = json.loads(self.reconocedor.Result())
                            texto = resultado.get("text", "").strip().lower()
                        else:
                            texto = ""

                    if texto:
                        print("Texto escuchado:", texto)

                    comando = self._interpretar_comando(texto)

                    if comando:
                        self.callback(comando, texto)
                    elif texto:
                        self.callback("NO_ENTENDIDO", texto)

        except Exception as error:
            print("Error en reconocimiento de voz:", error)

    def _normalizar(self, texto):
        texto = texto.lower()
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(
            caracter for caracter in texto
            if unicodedata.category(caracter) != "Mn"
        )
        return texto

    def _interpretar_comando(self, texto):
        texto = self._normalizar(texto)

        if not texto:
            return None

        comandos_iniciar = [
            "iniciar camara",
            "abrir camara",
            "activar camara",
            "prender camara",
            "encender camara"
        ]

        comandos_reconocer = [
            "reconocer billete",
            "leer billete",
            "detectar billete",
            "identificar billete",
            "reconocer",
            "leer"
        ]

        comandos_contar = [
            "contar dinero", "contar billetes", "sumar dinero",
            "sumar billetes", "cuanto tengo", "conteo de dinero"
        ]

        comandos_cambio = [
            "calcular cambio", "calcular un cambio", "cuanto cambio",
            "saber el cambio", "modo cambio"
        ]

        comandos_menu = [
            "menu principal", "volver al menu", "regresar al menu", "menu"
        ]

        comandos_cancelar = ["cancelar", "cancela", "volver", "regresar"]
        comandos_confirmar = ["confirmar", "confirmo", "correcto", "si"]
        comandos_corregir = ["corregir", "cambiar precio", "otro precio", "no"]
        comandos_total = ["repetir total", "decir total", "cuanto llevo", "total"]
        comandos_eliminar = [
            "eliminar ultimo", "borrar ultimo", "quitar ultimo", "deshacer"
        ]
        comandos_terminar_conteo = [
            "terminar conteo", "finalizar conteo", "terminar de contar"
        ]
        comandos_calcular = [
            "calcular", "calcular ahora", "terminar pago", "finalizar pago"
        ]

        comandos_nuevo = [
            "nuevo billete",
            "otro billete",
            "siguiente billete",
            "limpiar",
            "reiniciar"
        ]

        comandos_repetir = [
            "repetir",
            "repite",
            "decir de nuevo",
            "otra vez",
            "escuchar de nuevo"
        ]

        comandos_ayuda = [
            "ayuda",
            "comandos",
            "que puedo decir",
            "instrucciones"
        ]

        comandos_salir = ["salir de la aplicacion", "cerrar aplicacion", "salir"]

        # Las frases específicas se revisan antes que palabras generales.
        if any(comando in texto for comando in comandos_contar):
            return "CONTAR_DINERO"

        if any(comando in texto for comando in comandos_cambio):
            return "CALCULAR_CAMBIO"

        if any(comando in texto for comando in comandos_terminar_conteo):
            return "TERMINAR_CONTEO"

        if any(comando in texto for comando in comandos_calcular):
            return "CALCULAR_RESULTADO"

        if any(comando in texto for comando in comandos_eliminar):
            return "ELIMINAR_ULTIMO"

        if any(comando in texto for comando in comandos_total):
            return "REPETIR_TOTAL"

        if any(comando in texto for comando in comandos_menu):
            return "MENU_PRINCIPAL"

        if texto in comandos_confirmar:
            return "CONFIRMAR"

        if texto in comandos_corregir:
            return "CORREGIR"

        if any(comando in texto for comando in comandos_cancelar):
            return "CANCELAR"

        if any(comando in texto for comando in comandos_iniciar):
            return "INICIAR_CAMARA"

        if any(comando in texto for comando in comandos_reconocer):
            return "RECONOCER_BILLETE"

        if any(comando in texto for comando in comandos_nuevo):
            return "NUEVO_BILLETE"

        if any(comando in texto for comando in comandos_repetir):
            return "REPETIR"

        if any(comando in texto for comando in comandos_ayuda):
            return "AYUDA"

        if any(comando in texto for comando in comandos_salir):
            return "SALIR"

        numero = self._extraer_numero(texto)
        if numero is not None:
            return f"NUMERO:{numero}"

        return None

    def _extraer_numero(self, texto):
        """Convierte cantidades sencillas dichas en español a un entero."""
        coincidencia = re.search(r"\b\d+\b", texto)
        if coincidencia:
            return int(coincidencia.group())

        unidades = {
            "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2,
            "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
            "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
            "once": 11, "doce": 12, "trece": 13, "catorce": 14,
            "quince": 15, "dieciseis": 16, "diecisiete": 17,
            "dieciocho": 18, "diecinueve": 19, "veinte": 20,
            "veintiuno": 21, "veintidos": 22, "veintitres": 23,
            "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
            "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
        }
        decenas = {
            "treinta": 30, "cuarenta": 40, "cincuenta": 50,
            "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
        }
        centenas = {
            "cien": 100, "ciento": 100, "doscientos": 200,
            "trescientos": 300, "cuatrocientos": 400,
            "quinientos": 500, "seiscientos": 600,
            "setecientos": 700, "ochocientos": 800, "novecientos": 900,
        }

        total = 0
        bloque = 0
        encontrado = False
        for palabra in texto.split():
            if palabra in unidades:
                bloque += unidades[palabra]
                encontrado = True
            elif palabra in decenas:
                bloque += decenas[palabra]
                encontrado = True
            elif palabra in centenas:
                bloque += centenas[palabra]
                encontrado = True
            elif palabra == "mil":
                total += max(1, bloque) * 1000
                bloque = 0
                encontrado = True

        return total + bloque if encontrado else None
