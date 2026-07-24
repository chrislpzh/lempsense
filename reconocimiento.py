import os
import cv2
import numpy as np


class ReconocedorBilletes:
    def __init__(self, carpeta_referencias="referencias", debug=True):
        self.carpeta_referencias = carpeta_referencias
        self.debug = debug

        # Un cuadro con una persona y fondo contiene muchos puntos de interés.
        # Reservar más características evita que todos se gasten fuera del
        # billete cuando este ocupa una porción pequeña de la imagen.
        self.orb = cv2.ORB_create(nfeatures=1800, fastThreshold=12)
        self.ancho_maximo_referencia = 800

        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        self.referencias = []

        # candidato para aceptar un keypoint. Más bajo = más estricto.
        # 0.75 es el valor estándar recomendado por Lowe.
        self.ratio_lowe = 0.75

        # score_minimo: cantidad mínima de "buenas" coincidencias para aceptar
        # un resultado. Con knnMatch + ratio test este número es MUCHO más bajo
        # que con el método viejo (antes 50, ahora arrancamos en 15).
        # Si reconoce cosas falsas, subilo. Si no reconoce nada, bajalo.
        self.score_minimo = 14

        # No basta con encontrar puntos parecidos: deben conservar la misma
        # geometría que tienen en el billete de referencia. Esto evita que
        # vigas, cortinas, rostros u otros fondos produzcan un falso positivo.
        self.inliers_minimos = 8
        self.proporcion_inliers_minima = 0.35

        self.cargar_referencias()

    def cargar_referencias(self):
        if not os.path.exists(self.carpeta_referencias):
            os.makedirs(self.carpeta_referencias)

        archivos = os.listdir(self.carpeta_referencias)
        extensiones_validas = (".jpg", ".jpeg", ".png")

        for archivo in archivos:
            if not archivo.lower().endswith(extensiones_validas):
                continue

            ruta = os.path.join(self.carpeta_referencias, archivo)
            imagen = cv2.imread(ruta)

            if imagen is None:
                continue

            # Las fotografías originales rondan los 1600 px de ancho, pero
            # un billete sostenido suele ocupar solo 250-500 px en la webcam.
            # Normalizar la referencia mantiene ambas escalas dentro del rango
            # en el que ORB puede relacionarlas de forma confiable.
            alto_original, ancho_original = imagen.shape[:2]
            if ancho_original > self.ancho_maximo_referencia:
                escala = self.ancho_maximo_referencia / float(ancho_original)
                imagen = cv2.resize(
                    imagen,
                    (self.ancho_maximo_referencia, int(alto_original * escala)),
                    interpolation=cv2.INTER_AREA,
                )

            denominacion = self.obtener_denominacion_desde_nombre(archivo)

            gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            gris = self.mejorar_imagen(gris)

            puntos, descriptores = self.orb.detectAndCompute(gris, None)

            if descriptores is None:
                print(f"No se encontraron características en: {archivo}")
                continue

            self.referencias.append({
                "archivo": archivo,
                "ruta": ruta,
                "denominacion": denominacion,
                "puntos": puntos,
                "descriptores": descriptores,
                "alto": imagen.shape[0],
                "ancho": imagen.shape[1]
            })

        print(f"Referencias cargadas: {len(self.referencias)}")

    def obtener_denominacion_desde_nombre(self, nombre_archivo):
        nombre = os.path.splitext(nombre_archivo)[0]
        partes = nombre.replace("-", "_").split("_")

        for parte in partes:
            parte_limpia = parte.upper().replace("L", "")

            if parte_limpia.isdigit():
                return parte_limpia

        return "desconocida"

    def mejorar_imagen(self, gris):
        # CLAHE (ecualización adaptativa por regiones) es más robusto que
        # equalizeHist cuando en el frame hay fondo (mesa, mano, sombras)
        # además del billete, porque no ecualiza toda la imagen de una,
        # sino en bloques pequeños.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gris = clahe.apply(gris)
        gris = cv2.GaussianBlur(gris, (3, 3), 0)
        return gris

    def reconocer(self, imagen_bgr):
        if len(self.referencias) == 0:
            return None, 0, "No hay imágenes en la carpeta referencias.", {}

        gris = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
        gris = self.mejorar_imagen(gris)

        puntos_captura, descriptores_captura = self.orb.detectAndCompute(gris, None)

        if descriptores_captura is None or len(descriptores_captura) < 2:
            return None, 0, "No se detectaron suficientes características.", {}

        mejores_resultados = []

        for referencia in self.referencias:
            descriptores_ref = referencia["descriptores"]

            if descriptores_ref is None or len(descriptores_ref) < 2:
                continue

            try:
                coincidencias = self.matcher.knnMatch(
                    descriptores_captura, descriptores_ref, k=2
                )
            except cv2.error:
                continue

            if not coincidencias:
                continue

            # Ratio test de Lowe: solo cuenta un match si el mejor candidato
            # es claramente mejor que el segundo (evita matches ambiguos).
            buenas = []
            for par in coincidencias:
                if len(par) == 2:
                    m, n = par
                    if m.distance < self.ratio_lowe * n.distance:
                        buenas.append(m)

            score = len(buenas)

            # La homografía es una de las operaciones más costosas. Si una
            # referencia ni siquiera alcanza el score mínimo, no puede ganar,
            # por lo que no vale la pena calcularla.
            if score >= self.score_minimo:
                inliers, proporcion_inliers, geometria_valida = (
                    self.validar_geometria(
                        buenas,
                        puntos_captura,
                        referencia,
                        imagen_bgr.shape,
                    )
                )
            else:
                inliers, proporcion_inliers, geometria_valida = 0, 0.0, False

            distancia_promedio = (
                np.mean([m.distance for m in buenas])
                if buenas else 999
            )

            mejores_resultados.append({
                "denominacion": referencia["denominacion"],
                "archivo": referencia["archivo"],
                "score": score,
                "inliers": inliers,
                "proporcion_inliers": proporcion_inliers,
                "geometria_valida": geometria_valida,
                "distancia_promedio": distancia_promedio
            })

            if self.debug:
                print(f"[DEBUG] {referencia['archivo']:20s} "
                      f"score={score:3d} inliers={inliers:3d} "
                      f"ratio_geo={proporcion_inliers:.2f} "
                      f"dist_prom={distancia_promedio:.1f}")

        if not mejores_resultados:
            return None, 0, "No se encontraron coincidencias con las referencias.", {}

        mejores_resultados = sorted(
            mejores_resultados,
            # Una referencia geométricamente válida siempre tiene prioridad
            # sobre otra con más matches sueltos pero incoherentes.
            key=lambda x: (
                x["geometria_valida"],
                x["inliers"],
                x["score"],
                -x["distancia_promedio"],
            ),
            reverse=True
        )

        mejor = mejores_resultados[0]
        # Hay varias fotos de cada valor. Una segunda foto del mismo billete
        # confirma el resultado; no debe reducir su confianza como si fuera una
        # denominación rival.
        segundo = next(
            (
                resultado for resultado in mejores_resultados[1:]
                if resultado["denominacion"] != mejor["denominacion"]
            ),
            None,
        )

        score_mejor = mejor["score"]
        score_segundo = segundo["score"] if segundo else 0

        if self.debug:
            print(f"[DEBUG] >> MEJOR={mejor['archivo']} score={score_mejor} | "
                  f"SEGUNDO={segundo['archivo'] if segundo else '-'} score={score_segundo} | "
                  f"umbral_actual={self.score_minimo}")

        if score_mejor < self.score_minimo or not mejor["geometria_valida"]:
            detalle = {
                "mejor_archivo": mejor["archivo"],
                "score": score_mejor,
                "segundo_score": score_segundo,
                "inliers": mejor["inliers"],
                "proporcion_inliers": round(mejor["proporcion_inliers"], 2)
            }

            return (
                None,
                0,
                "No estoy seguro. Acerque el billete o mejore la iluminación.",
                detalle
            )

        confianza = self.calcular_confianza(score_mejor, score_segundo)

        detalle = {
            "mejor_archivo": mejor["archivo"],
            "score": score_mejor,
            "segundo_score": score_segundo,
            "inliers": mejor["inliers"],
            "proporcion_inliers": round(mejor["proporcion_inliers"], 2),
            "distancia_promedio": round(float(mejor["distancia_promedio"]), 2)
        }

        texto = self.texto_denominacion(mejor["denominacion"])
        mensaje = f"Billete de {texto}"

        return mejor["denominacion"], confianza, mensaje, detalle

    def validar_geometria(self, coincidencias, puntos_captura, referencia,
                          forma_captura):
        """Comprueba que los matches describan un mismo billete plano."""
        if len(coincidencias) < 4:
            return 0, 0.0, False

        puntos_ref = np.float32([
            referencia["puntos"][m.trainIdx].pt for m in coincidencias
        ]).reshape(-1, 1, 2)
        puntos_cam = np.float32([
            puntos_captura[m.queryIdx].pt for m in coincidencias
        ]).reshape(-1, 1, 2)

        homografia, mascara = cv2.findHomography(
            puntos_ref, puntos_cam, cv2.RANSAC, 4.0
        )
        if homografia is None or mascara is None:
            return 0, 0.0, False

        inliers = int(mascara.ravel().sum())
        proporcion = inliers / len(coincidencias)

        esquinas_ref = np.float32([[
            [0, 0],
            [referencia["ancho"] - 1, 0],
            [referencia["ancho"] - 1, referencia["alto"] - 1],
            [0, referencia["alto"] - 1],
        ]])
        try:
            esquinas_cam = cv2.perspectiveTransform(
                esquinas_ref, homografia
            )[0]
        except cv2.error:
            return inliers, proporcion, False

        alto_cam, ancho_cam = forma_captura[:2]
        area = abs(cv2.contourArea(esquinas_cam))
        proporcion_area = area / float(alto_cam * ancho_cam)
        contorno = esquinas_cam.astype(np.float32).reshape(-1, 1, 2)

        geometria_valida = (
            inliers >= self.inliers_minimos
            and proporcion >= self.proporcion_inliers_minima
            and 0.01 <= proporcion_area <= 0.95
            and cv2.isContourConvex(contorno)
        )
        return inliers, proporcion, geometria_valida

    def calcular_confianza(self, score_mejor, score_segundo):
        if score_mejor <= 0:
            return 0

        diferencia = score_mejor - score_segundo
        confianza = 60 + diferencia * 4

        # Umbrales reescalados: con knnMatch + ratio test los scores
        # suelen ser más bajos que con el método viejo (antes 120/80/50).
        if score_mejor >= 60:
            confianza += 20
        elif score_mejor >= 35:
            confianza += 12
        elif score_mejor >= 15:
            confianza += 6

        confianza = max(0, min(confianza, 99))

        return int(confianza)

    def texto_denominacion(self, denominacion):
        nombres = {
            "1": "un lempira",
            "2": "dos lempiras",
            "5": "cinco lempiras",
            "10": "diez lempiras",
            "20": "veinte lempiras",
            "50": "cincuenta lempiras",
            "100": "cien lempiras",
            "200": "doscientos lempiras",
            "500": "quinientos lempiras"
        }

        return nombres.get(str(denominacion), f"{denominacion} lempiras")


if __name__ == "__main__":

    reconocedor = ReconocedorBilletes(carpeta_referencias="referencias", debug=True)

    camara = cv2.VideoCapture(0)

    if not camara.isOpened():
        print("No se pudo abrir la cámara.")
    else:
        print("Presioná ESPACIO para analizar el frame actual, ESC para salir.")

        while True:
            ok, frame = camara.read()
            if not ok:
                break

            cv2.imshow("Reconocedor de billetes", frame)
            tecla = cv2.waitKey(1) & 0xFF

            if tecla == 27:  # ESC
                break
            elif tecla == 32:  # ESPACIO
                denominacion, confianza, mensaje, detalle = reconocedor.reconocer(frame)
                print(f">>> {mensaje} (confianza={confianza}%)")
                print(f">>> detalle: {detalle}")

        camara.release()
        cv2.destroyAllWindows()
