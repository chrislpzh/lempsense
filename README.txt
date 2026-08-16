# LempSense

## Descripción del proyecto

LempSense es una aplicación que reconoce billetes de lempiras (Honduras) a través de la cámara y anuncia el resultado por voz. Está pensada como una herramienta de apoyo para identificar denominaciones de billetes de forma rápida y accesible.

## Instalación y ejecución

### Requisitos previos

- Python 3
- Cámara web

### Instalación de dependencias

```bash
pip install opencv-python edge-tts pyttsx3 vosk
```

### Ejecución

```bash
python main.py
```

Esto abre la interfaz principal de la aplicación (`LempiraApp`).

## Cómo navegar en la interfaz

1. **Iniciar cámara**: activa la cámara para comenzar a detectar billetes.
2. **Detección automática**: cuando un billete es reconocido, el sistema muestra el resultado en pantalla y lo anuncia por voz.
3. **Comandos por voz**: la app puede recibir instrucciones habladas (usando Vosk) para controlar funciones básicas sin necesidad de usar el mouse o teclado.
4. **Salir**: cierra la ventana o usa la opción de salir en el menú para terminar el programa.

## Tecnologías utilizadas

- **Python 3** — lenguaje principal del proyecto
- **OpenCV (ORB)** — detección y reconocimiento de billetes por cámara
- **edge-tts** — voz principal (texto a voz neuronal)
- **pyttsx3** — voz de respaldo cuando no hay conexión a internet
- **Vosk** — reconocimiento de voz para comandos hablados

## Notas

- Pensado para ejecutarse en Windows.
- Si `edge-tts` no está disponible (sin conexión a internet), la app usa `pyttsx3` o la voz nativa de Windows como respaldo.