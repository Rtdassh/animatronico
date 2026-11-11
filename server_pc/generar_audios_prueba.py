#!/usr/bin/env python3
"""
Script de generacion de audios Loquendo para pruebas.
Genera archivos en animatronico/server_pc/audio/ tanto con nombres legibles
como con las claves de cache para la interfaz web.
"""

import sys
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from tts_loquendo import generate_loquendo_speech, AUDIO_DIR

TEST_AUDIOS = [
    {
        "alias": "prueba_saludo_jorge.mp3",
        "voice": "jorge",
        "text": "Hola, soy el animatronico. Todos mis sistemas estan en linea y listos para operar."
    },
    {
        "alias": "prueba_sensores_jorge.mp3",
        "voice": "jorge",
        "text": "Segun mi sensor digital DHT11, la temperatura actual en el laboratorio es de 23.5 grados Celsius, con una humedad del 50 por ciento."
    },
    {
        "alias": "prueba_identificacion_jorge.mp3",
        "voice": "jorge",
        "text": "Soy el Animatronico, una cabeza animatronica con inteligencia artificial local. Utilizo tu dispositivo como microfono y altavoz, mientras mi Arduino y ESP32 controlan mis expresiones faciales y sensores."
    },
    {
        "alias": "prueba_luz_on_jorge.mp3",
        "voice": "jorge",
        "text": "Entendido. He encendido la luz del laboratorio conectada al pin D7 de mi Arduino."
    },
    {
        "alias": "prueba_luz_off_jorge.mp3",
        "voice": "jorge",
        "text": "Listo, acabo de apagar la luz del laboratorio."
    },
    {
        "alias": "prueba_movimiento_carlos.mp3",
        "voice": "carlos",
        "text": "Iniciando secuencia de calibracion de servomotores. Mandibula a noventa grados y orientacion ocular al centro."
    },
    {
        "alias": "prueba_saludo_carlos.mp3",
        "voice": "carlos",
        "text": "Hola a todos. Soy el animatronico transmitiendo con la voz de Carlos de Loquendo."
    },
    {
        "alias": "prueba_chiste_carmen.mp3",
        "voice": "carmen",
        "text": "¿Por que los robots nunca se deprimen? Porque tenemos un algoritmo optimista y cables resistentes al desanimo."
    },
    {
        "alias": "prueba_saludo_carmen.mp3",
        "voice": "carmen",
        "text": "Hola, soy Carmen. Audio de prueba para el altavoz del animatronico."
    }
]

def main():
    print("Iniciando sintesis de audios de prueba con Loquendo...")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    for item in TEST_AUDIOS:
        alias = item["alias"]
        voice = item["voice"]
        text = item["text"]

        print(f"Generando [{voice}] -> {alias}...")
        try:
            audio_bytes, cache_filename = generate_loquendo_speech(text, voice_key=voice)
            if not audio_bytes:
                print(f"Error: audio vacio para {alias}")
                continue

            # Guardar tambien con el nombre legible de prueba
            target_path = AUDIO_DIR / alias
            with open(target_path, "wb") as f:
                f.write(audio_bytes)

            print(f"  OK: {alias} ({len(audio_bytes)} bytes) | Cache: {cache_filename}")
        except Exception as e:
            print(f"  Fallo al generar {alias}: {e}")

    print("Proceso de generacion finalizado.")

if __name__ == "__main__":
    main()

