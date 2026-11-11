# Firmware del Arduino Uno R3

El [sketch del Uno](../firmware/arduino_uno_animatronico/arduino_uno_animatronico.ino) lee el DHT11 en D4 y controla el PCA9685 en la dirección I²C 0x40. Consulta el mapa de cables y la calibración en la [guía de armado](GUIA_ARMADO_EYEMECH.md).

- **UART hacia el ESP32.** SoftwareSerial en D2 (RX) y D3 (TX), 38400 bps, 8N1. El USB del Uno usa 115200 bps para diagnóstico y pruebas locales. Ambos reciben tramas terminadas en CR o LF.
- **Comandos.** `CMD:EH=90,EV=90,B=1,L=1` asigna mirada horizontal y vertical, solicita un parpadeo y enciende el LED D7. `E` se acepta como alias de `EH`. Los ángulos se limitan por canal y los parámetros omitidos conservan el estado correspondiente. Desde el USB, `CMD:O=0` a `CMD:O=100` ajusta la apertura para pruebas.
- **Hold y Move.** Con D8 abierto, el Uno aplica la pose de montaje y omite órdenes de movimiento. Al cerrar D8 a GND durante 50 ms habilita Move. El retorno a Hold cancela el parpadeo y restablece la pose. Telemetría y LED funcionan en ambos modos.
- **Servos.** El PCA9685 genera PWM a 50 Hz. La tabla `SERVOS` define por canal los topes de ángulo, las posiciones de Hold y apertura y la conversión a microsegundos. Los cuatro párpados tienen sus propios límites. Si el PCA no responde en el arranque, el Uno informa el error por USB y mantiene deshabilitados los movimientos hasta reiniciar.
- **Telemetría.** Cada 3,5 s emite `SENS:T=24.5,H=57.0` por UART y USB. `NA` indica lectura ausente. El servidor presenta ese campo como no disponible.
