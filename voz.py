import asyncio
import os
import sys
import tempfile
import threading
import subprocess
import time
import io
import math
import struct
import wave


class Voz:
    def __init__(self):
        # Voz neuronal femenina, en español de Honduras.
        self.voz_principal = "es-HN-KarlaNeural"
        self.velocidad = "-6%"
        self.tono = "+1Hz"
        self.lock = threading.Lock()
        self.control_lock = threading.Lock()
        self.esta_hablando = False
        self.solicitud_actual = 0
        self.alias_activo = None
        self.engine_activo = None
        self.proceso_activo = None

    def hablar(self, texto):
        print("VOZ:", texto)

        # Una instrucción nueva reemplaza inmediatamente cualquier frase
        # anterior. Así la voz nunca queda atrasada respecto a la interfaz.
        self.detener()
        with self.control_lock:
            solicitud = self.solicitud_actual

        hilo = threading.Thread(
            target=self._hablar_en_hilo,
            args=(texto, solicitud),
            daemon=True
        )
        hilo.start()

    def detener(self):
        """Cancela la locución actual y las solicitudes que estén esperando."""
        with self.control_lock:
            self.solicitud_actual += 1
            alias = self.alias_activo
            engine = self.engine_activo
            proceso = self.proceso_activo

        if alias and sys.platform == "win32":
            try:
                mci = __import__("ctypes").windll.winmm.mciSendStringW
                mci(f"stop {alias}", None, 0, None)
                mci(f"close {alias}", None, 0, None)
            except Exception:
                pass

        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

        if proceso is not None and proceso.poll() is None:
            try:
                proceso.terminate()
            except Exception:
                pass

    def sonido_salida(self):
        """Dos golpes cortos tipo 'tac-tac' al cerrar el sistema."""
        if sys.platform != "win32":
            return
        try:
            import winsound

            frecuencia_muestreo = 44100
            muestras = []

            def agregar_golpe(frecuencia, duracion, volumen):
                cantidad = int(frecuencia_muestreo * duracion)
                for indice in range(cantidad):
                    tiempo_golpe = indice / frecuencia_muestreo
                    # Ataque instantáneo y caída rápida: sonido percusivo,
                    # corto y seco en lugar de una nota musical sostenida.
                    envolvente = math.exp(-42 * tiempo_golpe)
                    onda = (
                        math.sin(2 * math.pi * frecuencia * tiempo_golpe)
                        + 0.45 * math.sin(
                            2 * math.pi * frecuencia * 2.7 * tiempo_golpe
                        )
                    )
                    muestras.append(int(volumen * envolvente * onda))

            agregar_golpe(720, 0.085, 10500)
            muestras.extend([0] * int(frecuencia_muestreo * 0.045))
            agregar_golpe(520, 0.11, 12000)

            memoria = io.BytesIO()
            with wave.open(memoria, "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(frecuencia_muestreo)
                audio.writeframes(
                    b"".join(struct.pack("<h", muestra) for muestra in muestras)
                )

            winsound.PlaySound(
                memoria.getvalue(), winsound.SND_MEMORY | winsound.SND_SYNC
            )
        except Exception:
            self._reproducir_tonos([
                (700, 45), (500, 65)
            ])

    def _reproducir_tonos(self, tonos):
        """Reproduce una pequeña secuencia sin archivos externos."""
        if sys.platform != "win32":
            return
        try:
            import winsound
            for frecuencia, duracion in tonos:
                winsound.Beep(frecuencia, duracion)
        except Exception:
            try:
                __import__("winsound").MessageBeep()
            except Exception:
                pass

    def _solicitud_vigente(self, solicitud):
        with self.control_lock:
            return solicitud == self.solicitud_actual

    def _hablar_en_hilo(self, texto, solicitud):
        with self.lock:
            if not self._solicitud_vigente(solicitud):
                return
            self.esta_hablando = True
            try:
                try:
                    asyncio.run(self._hablar_con_edge_tts(texto, solicitud))
                    return
                except Exception as error:
                    if not self._solicitud_vigente(solicitud):
                        return
                    print("Edge TTS falló; usando voz local:", error)

                try:
                    self._hablar_con_pyttsx3(texto, solicitud)
                    return
                except Exception as error:
                    if not self._solicitud_vigente(solicitud):
                        return
                    print("pyttsx3 falló:", error)

                try:
                    self._hablar_con_windows(texto, solicitud)
                except Exception as error:
                    print("Windows Speech falló:", error)
            finally:
                self.esta_hablando = False

    async def _hablar_con_edge_tts(self, texto, solicitud):
        """
        Usa voz neuronal hondureña.
        Requiere conexión a internet.
        """

        import edge_tts

        archivo_temporal = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3"
        )

        ruta_audio = archivo_temporal.name
        archivo_temporal.close()

        comunicador = edge_tts.Communicate(
            text=texto,
            voice=self.voz_principal,
            rate=self.velocidad,
            pitch=self.tono,
            volume="+0%",
        )

        await comunicador.save(ruta_audio)

        try:
            if self._solicitud_vigente(solicitud):
                self._reproducir_audio(ruta_audio, solicitud)
        finally:
            try:
                os.remove(ruta_audio)
            except Exception:
                pass

    def _reproducir_audio(self, ruta_audio, solicitud):
        if sys.platform != "win32":
            raise RuntimeError("La reproducción automática está configurada para Windows.")

        # MCI reproduce el MP3 neuronal usando componentes incluidos en
        # Windows; no hace falta instalar otro reproductor.
        import ctypes

        mci = ctypes.windll.winmm.mciSendStringW
        alias = f"lempsense_{threading.get_ident()}"
        ruta_segura = os.path.abspath(ruta_audio).replace('"', '')

        abrir = mci(
            f'open "{ruta_segura}" type mpegvideo alias {alias}',
            None, 0, None
        )
        if abrir != 0:
            raise RuntimeError(f"Windows no pudo abrir el audio (MCI {abrir}).")

        try:
            with self.control_lock:
                if solicitud != self.solicitud_actual:
                    mci(f"close {alias}", None, 0, None)
                    return
                self.alias_activo = alias
            # No usamos "play ... wait": algunas versiones de MCI no aceptan
            # correctamente un stop desde otro hilo mientras esa llamada está
            # bloqueada. Consultar el estado permite cancelar en pocos
            # milisegundos cuando llega un comando de voz.
            reproducir = mci(f"play {alias}", None, 0, None)
            if reproducir != 0 and self._solicitud_vigente(solicitud):
                raise RuntimeError(
                    f"Windows no pudo reproducir el audio (MCI {reproducir})."
                )

            estado = ctypes.create_unicode_buffer(32)
            while self._solicitud_vigente(solicitud):
                consulta = mci(
                    f"status {alias} mode", estado, len(estado), None
                )
                if consulta != 0 or estado.value.lower() in (
                    "stopped", "not ready", ""
                ):
                    break
                time.sleep(0.03)

            if not self._solicitud_vigente(solicitud):
                mci(f"stop {alias}", None, 0, None)
        finally:
            mci(f"close {alias}", None, 0, None)
            with self.control_lock:
                if self.alias_activo == alias:
                    self.alias_activo = None

    def _hablar_con_pyttsx3(self, texto, solicitud):
        """
        Voz offline de respaldo.
        """

        import pyttsx3

        engine = pyttsx3.init()
        with self.control_lock:
            if solicitud != self.solicitud_actual:
                engine.stop()
                return
            self.engine_activo = engine
        engine.setProperty("rate", 145)
        engine.setProperty("volume", 1.0)

        voices = engine.getProperty("voices")

        # Si no hay conexión, prioriza explícitamente voces locales
        # femeninas en español.
        candidatas_femeninas = ("sabina", "helena", "laura", "paulina")

        for voice in voices:
            nombre = voice.name.lower()
            identificador = voice.id.lower()

            if any(nombre_femenino in nombre
                   for nombre_femenino in candidatas_femeninas):
                engine.setProperty("voice", voice.id)
                break

        try:
            engine.say(texto)
            engine.runAndWait()
        finally:
            engine.stop()
            with self.control_lock:
                if self.engine_activo is engine:
                    self.engine_activo = None

    def _hablar_con_windows(self, texto, solicitud):
        """
        Último respaldo usando la voz básica de Windows.
        """

        if sys.platform != "win32":
            return

        texto = texto.replace("'", " ")

        comando = (
            "Add-Type -AssemblyName System.Speech; "
            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$speak.SelectVoice('Microsoft Sabina Desktop'); "
            "$speak.Volume = 100; "
            "$speak.Rate = -1; "
            f"$speak.Speak('{texto}');"
        )

        if not self._solicitud_vigente(solicitud):
            return

        proceso = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", comando],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        with self.control_lock:
            if solicitud != self.solicitud_actual:
                proceso.terminate()
                return
            self.proceso_activo = proceso
        try:
            proceso.wait()
        finally:
            with self.control_lock:
                if self.proceso_activo is proceso:
                    self.proceso_activo = None
