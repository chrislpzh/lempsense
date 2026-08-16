# LempSense

Aplicación que reconoce billetes de lempiras (Honduras) usando la cámara y anuncia el resultado por voz.

## Requisitos

- Python 3
- OpenCV
- edge-tts (voz principal)
- pyttsx3 (voz de respaldo)
- Vosk (reconocimiento de voz)

Instalación de dependencias:

```bash
pip install opencv-python edge-tts pyttsx3 vosk
```

## Cómo ejecutar

```bash
python main.py
```

Esto abre la interfaz principal de la aplicación (`LempiraApp`).

## Cómo navegar en la interfaz

1. **Iniciar cámara**: activa la cámara para comenzar a detectar billetes.
2. **Detección automática**: cuando un billete es reconocido, el sistema muestra el resultado en pantalla y lo anuncia por voz.
3. **Comandos por voz**: la app puede recibir instrucciones habladas (usando Vosk) para controlar funciones básicas sin necesidad de usar el mouse o teclado.
4. **Salir**: cierra la ventana o usa la opción de salir en el menú para terminar el programa.

## Notas

- Pensado para ejecutarse en Windows.
- Si `edge-tts` no está disponible (sin conexión a internet), la app usa `pyttsx3` o la voz nativa de Windows como respaldo.
