#!/usr/bin/env python3
"""
=============================================================================
HERRAMIENTA DE PRUEBA DE VISIÓN ARTIFICIAL Y CALIBRACIÓN DE SERVOS
Proyecto: Cabeza Animatrónica con IA Local
=============================================================================
Abre la cámara del dispositivo en una ventana gráfica de OpenCV en vivo,
detecta el rostro humano en tiempo real y calcula los ángulos de los servos.
Permite enviar los comandos directamente al servidor central por WebSocket
o simplemente monitorear los comandos calculados en consola.

Controles en ventana:
  [Q]       - Salir
  [I]       - Invertir eje horizontal (Pan / Espejo)
  [V]       - Invertir eje vertical (Tilt)
  [C]       - Centrar servos a 90°
  [+] / [-] - Ajustar factor de suavizado
"""

import sys
import time
import argparse
import cv2
from pathlib import Path

# Agregar ruta local para importar el módulo de visión
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from vision_tracker import FaceTracker


def main():
    parser = argparse.ArgumentParser(description="Prueba visual de seguimiento de rostros y calibración.")
    parser.add_argument("--camera", type=int, default=0, help="Índice de la cámara (por defecto 0)")
    parser.add_argument("--no-invert-x", action="store_true", help="Desactivar inversión horizontal")
    parser.add_argument("--invert-y", action="store_true", help="Activar inversión vertical")
    parser.add_argument("--smooth", type=float, default=0.25, help="Factor de suavizado EMA (0.05 a 0.5)")
    args = parser.parse_args()

    print("=" * 65)
    print(" 🤖 CÍCLOPE AI - VISOR DE PRUEBA DE VISIÓN ARTIFICIAL")
    print("=" * 65)
    print(f" • Índice de Cámara : {args.camera}")
    print(f" • Invertir Eje X   : {not args.no_invert_x}")
    print(f" • Invertir Eje Y   : {args.invert_y}")
    print(f" • Factor Suavizado : {args.smooth}")
    print("=" * 65)
    print("Presiona [Q] en la ventana de video para salir.\n")

    latest_command = ""

    def on_servo_callback(eh: int, ev: int):
        nonlocal latest_command
        latest_command = f"CMD:EH={eh},EV={ev},B=0,L=1"
        print(f"\r[SERVO ENVIADO] {latest_command}    ", end="", flush=True)

    tracker = FaceTracker(
        camera_index=args.camera,
        on_servo_update=on_servo_callback,
        invert_x=not args.no_invert_x,
        invert_y=args.invert_y,
        smooth_factor=args.smooth
    )

    if not tracker.start():
        print("[ERROR] No se pudo iniciar el rastreador de visión.")
        return

    tracker.register_viewer()
    window_name = "Animatronico - Seguimiento Facial en Tiempo Real"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    try:
        while tracker.is_running:
            # Obtener el último frame JPEG y decodificar para mostrar en ventana OpenCV
            jpeg_bytes = tracker.get_latest_jpeg()
            if jpeg_bytes is not None:
                import numpy as np
                nparr = np.frombuffer(jpeg_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    # Instrucciones de teclas superpuestas en el pie de imagen
                    h, w = img.shape[:2]
                    cv2.rectangle(img, (0, h - 25), (w, h), (15, 15, 15), -1)
                    cv2.putText(
                        img,
                        "[Q] Salir | [I] Invertir X | [V] Invertir Y | [C] Centrar",
                        (10, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.42,
                        (180, 180, 180),
                        1
                    )
                    cv2.imshow(window_name, img)

            key = cv2.waitKey(15) & 0xFF
            if key == ord('q') or key == 27:  # 'q' o Escape
                break
            elif key == ord('i'):
                status = tracker.get_status()
                new_inv = not status["invert_x"]
                tracker.set_config(invert_x=new_inv)
                print(f"\n[CONFIG] Invertir X: {new_inv}")
            elif key == ord('v'):
                status = tracker.get_status()
                new_inv = not status["invert_y"]
                tracker.set_config(invert_y=new_inv)
                print(f"\n[CONFIG] Invertir Y: {new_inv}")
            elif key == ord('c'):
                tracker.set_config(smooth_factor=0.9)
                tracker.target_eh = 90.0
                tracker.target_ev = 90.0
                print("\n[CONFIG] Servos centrados a 90°")
            elif key == ord('+') or key == ord('='):
                status = tracker.get_status()
                new_smooth = min(0.8, status["smooth_factor"] + 0.05)
                tracker.set_config(smooth_factor=new_smooth)
                print(f"\n[CONFIG] Suavizado aumentado: {new_smooth:.2f}")
            elif key == ord('-') or key == ord('_'):
                status = tracker.get_status()
                new_smooth = max(0.05, status["smooth_factor"] - 0.05)
                tracker.set_config(smooth_factor=new_smooth)
                print(f"\n[CONFIG] Suavizado reducido: {new_smooth:.2f}")

    except KeyboardInterrupt:
        print("\n[Interrupción por teclado]")
    finally:
        tracker.unregister_viewer()
        tracker.stop()
        cv2.destroyAllWindows()
        print("\nVisor finalizado con éxito.")


if __name__ == "__main__":
    main()

