#!/usr/bin/env python3
"""
Generador del Plano Eléctrico y Diagrama de Conexiones
Proyecto: Cabeza Animatrónica con IA Local
Mecanismo Ocular: Epsilon 3.2 (Will Cogley - MakerWorld #1184807)
Arquitectura: ESP32 DevKit V1 + Arduino Uno R3 + Controlador I2C PCA9685 (16 CH)
              + 6x Servos Mecanismo Ocular E3.2 + Módulo de Audio & Altavoz 3W
              + Sensor I2C LM75A + DHT11 + Fuente Externa 5V 4A
Distribución Espacial: 5 Columnas y 4 Corredores de Enrutamiento de Alta Claridad (KiCad / Altium Style)
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PNG = BASE_DIR.parent / "docs" / "plano_circuito_animatronico.png"
OUTPUT_E32_PNG = BASE_DIR.parent / "docs" / "plano_circuito_e3_2.png"

def get_font(size, bold=False):
    """Carga fuentes tipográficas disponibles en Linux o Windows."""
    paths = [
        "/usr/share/fonts/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Bold.ttf" if bold else "/usr/share/fonts/TTF/JetBrainsMonoNLNerdFontPropo-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\consola.ttf" if bold else "C:\\Windows\\Fonts\\consolab.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_wire(draw, points, color, width=3):
    """Dibuja cables ortogonales limpios."""
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=color, width=width)

def draw_junction(draw, pt, color, r=5):
    """Dibuja un nodo o punto de soldadura/unión eléctrica."""
    draw.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=color, outline="#0f172a", width=1)

def draw_label(draw, text, x, y, font, fg_color, bg_color="#ffffff", border_color=None, padding=3):
    """Dibuja una etiqueta tipo net-badge con fondo protector contra cruce de cables."""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    if bg_color:
        rect = [x - padding, y - padding, x + tw + padding, y + th + padding]
        draw.rectangle(rect, fill=bg_color, outline=border_color if border_color else bg_color, width=1)
    draw.text((x, y), text, fill=fg_color, font=font)

def draw_ic(draw, x, y, w, h, title, subtitle="", header_color="#0284c7", body_color="#ffffff", border_color="#334155", header_h=38):
    """Dibuja un bloque modular de circuito integrado / placa electrónica."""
    draw.rectangle([x+4, y+4, x+w+4, y+h+4], fill="#cbd5e1")
    draw.rectangle([x, y, x+w, y+h], fill=body_color, outline=border_color, width=2)
    draw.rectangle([x, y, x+w, y+header_h], fill=header_color, outline=border_color, width=2)
    
    font_h = get_font(15, bold=True)
    font_sub = get_font(11, bold=False)
    
    draw.text((x + 14, y + (header_h - 20) // 2), title, fill="#ffffff", font=font_h)
    
    if subtitle:
        bbox_title = font_h.getbbox(title)
        title_w = bbox_title[2] - bbox_title[0]
        bbox_sub = font_sub.getbbox(subtitle)
        sub_w = bbox_sub[2] - bbox_sub[0]
        if (w - title_w - sub_w) > 40:
            draw.text((x + w - sub_w - 14, y + (header_h - 16) // 2), subtitle, fill="#f1f5f9", font=font_sub)

def render_schematic():
    W, H = 3800, 2250
    bg_color = "#f8fafc"
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Cuadrícula técnica de fondo
    grid_major = "#e2e8f0"
    grid_minor = "#f1f5f9"
    for x in range(0, W, 25):
        c = grid_major if x % 100 == 0 else grid_minor
        draw.line([x, 0, x, H], fill=c, width=1)
    for y in range(0, H, 25):
        c = grid_major if y % 100 == 0 else grid_minor
        draw.line([0, y, W, y], fill=c, width=1)

    # Fuentes
    f_title = get_font(23, bold=True)
    f_sub = get_font(13, bold=False)
    f_pin = get_font(13, bold=True)
    f_pin_small = get_font(11, bold=True)
    f_text = get_font(12, bold=False)
    f_text_bold = get_font(12, bold=True)
    f_tag = get_font(12, bold=True)
    f_box_title = get_font(14, bold=True)

    # Colores normalizados
    c_pwr_ext = "#dc2626"   # Rojo: 5V Externa Servos
    c_pwr_5v  = "#ea580c"   # Naranja: 5V Lógica Arduino
    c_gnd     = "#0f172a"   # Negro: GND común
    c_i2c_sda = "#16a34a"   # Verde: I2C SDA
    c_i2c_scl = "#ca8a04"   # Amarillo oro: I2C SCL
    c_pwm_eye = "#d97706"   # Ámbar: Ojos E3.2 (CH0 / CH1)
    c_pwm_lid = "#1d4ed8"   # Azul real: Párpados Sup (CH2 / CH4)
    c_pwm_low = "#0284c7"   # Celeste: Párpados Inf (CH3 / CH5)
    c_audio   = "#9333ea"   # Morado: Audio
    c_dht_dat = "#a855f7"   # Púrpura suave: DHT11 Data
    c_uart_tx = "#3b82f6"   # Azul: UART TX (ESP32 a Arduino)
    c_uart_rx = "#06b6d4"   # Cian: UART RX (Arduino a ESP32 atenuado)
    c_led     = "#059669"   # Esmeralda: Control LED / Luz

    # =========================================================================
    # ENCABEZADO Y CAJETÍN TÉCNICO OFICIAL
    # =========================================================================
    draw.rectangle([40, 25, W - 40, 115], fill="#0f172a", outline="#334155", width=2)
    draw.text((65, 38), "SISTEMA ANIMATRONICO - MECANISMO OCULAR E3.2 (WILL COGLEY) CON CONTROLADOR PCA9685", fill="#38bdf8", font=f_title)
    draw.text((65, 75), "Arquitectura I2C Desacoplada: Arduino Uno R3 + PCA9685 (16 Canales) + ESP32 Wi-Fi + Smartphone Manos Libres (Alexa/WakeNet) + LM75A + DHT11", fill="#94a3b8", font=f_sub)
    draw.text((W - 600, 42), "Modelo 3D: MakerWorld #1184807 (E3.2)", fill="#f8fafc", font=f_pin)
    draw.text((W - 600, 70), "Audio: Smartphone Manos Libres (Sin Lipsync)", fill="#4ade80", font=f_pin)

    # =========================================================================
    # COLUMNA 1: ESP32 DEVKIT V1, LEYENDA Y NOTAS TÉCNICAS
    # x = 60 a 480 (ancho: 420 px)
    # =========================================================================
    esp_x, esp_y, esp_w, esp_h = 60, 160, 420, 430
    draw_ic(draw, esp_x, esp_y, esp_w, esp_h, "ESP32 DevKit V1", "Puente Wi-Fi / Servidor", header_color="#0369a1")

    # Mapeo de pines perfectamente alineado con los componentes de la Columna 2
    esp_pins = [
        ("3V3", "Salida 3.3V Regulada", 210),
        ("GPIO 17 (TX2)", "Salida Serie UART (3.3V)", 280),
        ("GPIO 16 (RX2)", "Entrada Serie UART (Max 3.3V)", 360),
        ("GND", "Tierra comun logica (0V)", 450),
        ("VIN (5V USB)", "Alimentacion por puerto USB", 520),
    ]
    for pname, pdesc, py in esp_pins:
        px = esp_x + esp_w
        draw.rectangle([px - 14, py - 12, px, py + 12], fill="#e2e8f0", outline="#475569", width=1)
        draw.text((px - 135, py - 9), pname, fill="#0f172a", font=f_pin)
        draw.text((esp_x + 16, py - 7), pdesc, fill="#64748b", font=f_text)
        draw.line([px, py, px + 20, py], fill="#475569", width=3)

    draw.rectangle([esp_x + 16, esp_y + esp_h - 45, esp_x + esp_w - 16, esp_y + esp_h - 12], fill="#fef2f2", outline="#ef4444", width=1)
    draw.text((esp_x + 24, esp_y + esp_h - 38), "!ALERTA: GPIO tolera 3.3V max. RX2 protegido con divisor resistivo.", fill="#b91c1c", font=f_pin_small)

    # Leyenda de Colores
    leg_x, leg_y, leg_w, leg_h = 60, 615, 420, 575
    draw_ic(draw, leg_x, leg_y, leg_w, leg_h, "CODIGO DE COLORES & SENALES", "Estandar IEC", header_color="#1e293b")

    legend_items = [
        (c_pwr_ext, "Rojo (+5V Ext)", "Potencia Servos (Bornera PCA9685 4A)"),
        (c_pwr_5v,  "Naranja (+5V)", "VCC Logica (Arduino a Sensores/PCA)"),
        (c_gnd,     "Negro (GND)", "Tierra Comun Unificada (Lazo 0V)"),
        (c_i2c_sda, "Verde (SDA)", "Bus I2C Datos (Arduino A4 -> PCA & LM75)"),
        (c_i2c_scl, "Amarillo (SCL)", "Bus I2C Reloj (Arduino A5 -> PCA & LM75)"),
        (c_pwm_eye, "Ambar (PWM Ojos)", "CH0 Horizontal / CH1 Vertical (E3.2)"),
        (c_pwm_lid, "Azul Real (PWM Parp)", "CH2 Sup. Izq / CH4 Sup. Der (E3.2)"),
        (c_pwm_low, "Celeste (PWM Inf)", "CH3 Inf. Izq / CH5 Inf. Der (E3.2)"),
        ("#4f46e5",  "Indigo (Wi-Fi)", "Audio Manos Libres Celular <-> PC"),
        (c_uart_tx, "Azul (UART TX)", "ESP32 GPIO 17 (3.3V) -> Arduino D2"),
        (c_uart_rx, "Cian (UART RX)", "Arduino D3 (5V) -> Divisor -> ESP32"),
        (c_led,     "Verde Oscuro (LED)", "Control de iluminacion en Arduino D7"),
    ]

    for idx, (col, title, desc) in enumerate(legend_items):
        item_y = leg_y + 46 + idx * 43
        draw.line([leg_x + 16, item_y + 8, leg_x + 55, item_y + 8], fill=col, width=5)
        draw_junction(draw, (leg_x + 35, item_y + 8), col, r=5)
        draw.text((leg_x + 65, item_y - 4), title, fill="#0f172a", font=f_pin_small)
        draw.text((leg_x + 65, item_y + 14), desc, fill="#64748b", font=f_text)

    # Notas Técnicas
    spec_x, spec_y, spec_w, spec_h = 60, 1215, 420, 955
    draw_ic(draw, spec_x, spec_y, spec_w, spec_h, "NOTAS TECNICAS: E3.2 & PCA9685", "Will Cogley #1184807", header_color="#1e293b", header_h=38)

    specs = [
        ("• Modulo Controlador PCA9685:", "Generador PWM por hardware de 16 canales y 12 bits en bus I2C (0x40). Elimina por completo el jitter en servos."),
        ("• Alimentacion Externa en Bornera:", "La bornera V+ / GND del PCA9685 se alimenta desde la fuente externa de 5V 4A. Los 6 servos no drenan corriente del Arduino."),
        ("• Audio Manos Libres tipo Alexa:", "El celular es el unico microfono y altavoz del sistema. Detecta 'Oye Robot'/'Alexa', responde '¿En que te ayudo?' y habla por su bocina."),
        ("• Cero Interaccion de Pantalla:", "Dispositivo 100% manos libres. La IA responde por voz y activa movimientos fisicos en el animatronico sin tocar el movil."),
        ("• Eje Horizontal (CH0 Pan / Yaw):", "Mecanismo de 4 barras: giro coordinado de ojos. Rango seguro: 60 a 120 deg (neutro 90 deg)."),
        ("• Eje Vertical (CH1 Tilt / Pitch):", "Varilla vertical con rotula universal (Gimbal). Rango seguro: 70 a 110 deg (neutro 90 deg)."),
        ("• Parpados Superiores (CH2 / CH4):", "Apertura completa a 100 deg, neutro reposo a 90 deg, parpadeo o guino a 45 deg."),
        ("• Parpados Inferiores (CH3 / CH5):", "Posicion reposo a 80 deg, elevacion de expresion (sonrisa) a 110 deg."),
        ("• Pines D10 y D11 Liberados:", "Al delegar el audio de forma inalambrica al celular, los pines D10 y D11 del Arduino Uno quedan libres para expansion."),
        ("• Calibracion Esencial de Servos:", "Centrar electricamente TODOS los canales a 90 deg (pulso 1500 us) ANTES de ensamblar varillas del modelo 3D."),
        ("• Lazo Unificado de Tierra Comun:", "El pin GND del Arduino, GND del ESP32 y borne (-) de la fuente de 5V forman un solo lazo equipotencial de 0V."),
    ]

    sy_cursor = spec_y + 48
    for tag, desc in specs:
        draw.text((spec_x + 14, sy_cursor), tag, fill="#0284c7", font=f_text_bold)
        words = desc.split(" ")
        line1, line2 = "", ""
        for w in words:
            if len(line1 + w) < 42 and not line2:
                line1 += w + " "
            else:
                line2 += w + " "
        draw.text((spec_x + 22, sy_cursor + 18), line1.strip(), fill="#334155", font=f_text)
        if line2:
            draw.text((spec_x + 22, sy_cursor + 35), line2.strip(), fill="#334155", font=f_text)
            sy_cursor += 64
        else:
            sy_cursor += 48

    # =========================================================================
    # COLUMNA 2: DIVISOR RESISTIVO, SENSOR DHT11 Y ACTUADOR LED
    # x = 700 a 1100 (ancho: 400 px)
    # =========================================================================

    # 1. Divisor Resistivo (5V -> 3.3V)
    div_x, div_y, div_w, div_h = 700, 160, 400, 360
    draw_ic(draw, div_x, div_y, div_w, div_h, "DIVISOR RESISTIVO (5V -> 3.3V)", "Atenuador Pasivo UART", header_color="#0284c7")

    # Pin de entrada en el lado derecho de la caja (recibe D3 a y = 285)
    div_in_y = 285
    draw.rectangle([div_x + div_w - 14, div_in_y - 12, div_x + div_w, div_in_y + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((div_x + div_w - 105, div_in_y - 24), "IN (5V TX)", fill=c_uart_rx, font=f_pin_small)
    draw.line([div_x + div_w, div_in_y, div_x + div_w + 20, div_in_y], fill=c_uart_rx, width=3)

    # R1: 1 kOhm (ancho 140, colocado a div_x + 120 -> termina en 960, dejando 140px libres al pin)
    r1_x, r1_y, r_w, r_h = div_x + 120, div_y + 55, 140, 46
    draw.rectangle([r1_x, r1_y, r1_x + r_w, r1_y + r_h], fill="#fed7aa", outline="#c2410c", width=2)
    draw.text((r1_x + 20, r1_y + 12), "R1: 1 k Ohm", fill="#9a3412", font=f_pin)

    # Conexión entrada IN -> R1 (entra por el lado derecho de R1)
    r_center_x = r1_x + r_w // 2
    draw_wire(draw, [
        (div_x + div_w - 14, div_in_y),
        (r1_x + r_w + 25, div_in_y),
        (r1_x + r_w + 25, r1_y + r_h // 2),
        (r1_x + r_w, r1_y + r_h // 2)
    ], c_uart_rx, width=3)

    # Cable vertical desde R1 hacia R2
    draw_wire(draw, [(r_center_x, r1_y + r_h), (r_center_x, div_y + 230)], c_uart_rx, width=3)

    # Nodo Central (3.33V) alineado a y = 360 (exacto con ESP32 RX2)
    node_y = 360
    draw_junction(draw, (r_center_x, node_y), c_uart_rx, r=6)

    # R2: 2 kOhm debajo del nodo
    r2_x, r2_y = div_x + 120, div_y + 230
    draw.rectangle([r2_x, r2_y, r2_x + r_w, r2_y + r_h], fill="#fed7aa", outline="#c2410c", width=2)
    draw.text((r2_x + 20, r2_y + 12), "R2: 2 k Ohm", fill="#9a3412", font=f_pin)

    # Etiqueta nodo central protegida con badge
    draw.rectangle([div_x + 215, node_y - 12, div_x + 360, node_y + 14], fill="#e0f2fe", outline="#0284c7")
    draw.text((div_x + 225, node_y - 8), "Nodo: 3.33 V", fill="#0369a1", font=f_pin)

    # Pin de salida OUT hacia ESP32 RX2 (sale por la izquierda a y = 360)
    draw.rectangle([div_x, node_y - 12, div_x + 14, node_y + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((div_x + 20, node_y - 24), "OUT (3.33V)", fill=c_uart_rx, font=f_pin_small)
    draw_wire(draw, [(r_center_x, node_y), (div_x, node_y)], c_uart_rx, width=3)
    draw.line([div_x - 20, node_y, div_x, node_y], fill=c_uart_rx, width=3)

    # Conexión inferior R2 a Tierra GND (alineado a y = 450, exacto con ESP32 GND)
    div_gnd_y = 450
    draw.rectangle([div_x, div_gnd_y - 12, div_x + 14, div_gnd_y + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((div_x + 20, div_gnd_y - 24), "GND Retorno", fill=c_gnd, font=f_pin_small)
    draw_wire(draw, [
        (r_center_x, r2_y + r_h),
        (r_center_x, div_gnd_y),
        (div_x, div_gnd_y)
    ], c_gnd, width=3)
    draw.line([div_x - 20, div_gnd_y, div_x, div_gnd_y], fill=c_gnd, width=3)

    # 2. Sensor DHT11
    dht_x, dht_y, dht_w, dht_h = 700, 560, 400, 240
    draw_ic(draw, dht_x, dht_y, dht_w, dht_h, "SENSOR DHT11 (HUMEDAD)", "Bus Propietario 1-Wire", header_color="#7c3aed")

    dht_pins = [
        ("VCC (+)", "Alimentacion 5V Arduino", 620, c_pwr_5v),
        ("DAT", "Datos Digitales a D4", 680, c_dht_dat),
        ("GND (-)", "Retorno a Tierra Comun", 740, c_gnd),
    ]
    for pnum, pdesc, py, pcol in dht_pins:
        px = dht_x + dht_w
        draw.rectangle([px - 14, py - 12, px, py + 12], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((px - 105, py - 9), pnum, fill=pcol, font=f_pin)
        draw.text((dht_x + 16, py - 7), pdesc, fill="#64748b", font=f_text)
        draw.line([px, py, px + 20, py], fill=pcol, width=3)

    # 3. Actuador LED Iluminación
    led_x, led_y, led_w, led_h = 700, 840, 400, 160
    draw_ic(draw, led_x, led_y, led_w, led_h, "ACTUADOR: LED ILUMINACION", "Control por Pin D7", header_color="#059669")

    # Pin ánodo en lado derecho
    led_in_y = 920
    draw.rectangle([led_x + led_w - 14, led_in_y - 12, led_x + led_w, led_in_y + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((led_x + led_w - 90, led_in_y - 24), "ANODO (+)", fill=c_led, font=f_pin_small)
    draw.line([led_x + led_w, led_in_y, led_x + led_w + 20, led_in_y], fill=c_led, width=3)

    # Resistencia 220 Ohm
    draw.rectangle([led_x + 200, led_in_y - 18, led_x + 280, led_in_y + 18], fill="#a7f3d0", outline="#047857", width=2)
    draw.text((led_x + 210, led_in_y - 8), "220 R", fill="#065f46", font=f_pin)
    draw.line([led_x + led_w - 14, led_in_y, led_x + 280, led_in_y], fill=c_led, width=3)

    # Símbolo Diodo LED
    draw.line([led_x + 200, led_in_y, led_x + 150, led_in_y], fill=c_led, width=3)
    draw.ellipse([led_x + 105, led_in_y - 20, led_x + 150, led_in_y + 20], fill="#10b981", outline="#047857", width=2)
    draw.text((led_x + 116, led_in_y - 8), "LED", fill="#ffffff", font=f_pin_small)

    # Pin cátodo hacia GND (lado izquierdo)
    draw.rectangle([led_x, led_in_y - 12, led_x + 14, led_in_y + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((led_x + 20, led_in_y - 24), "CATODO (-)", fill=c_gnd, font=f_pin_small)
    draw_wire(draw, [(led_x + 105, led_in_y), (led_x, led_in_y)], c_gnd, width=3)
    draw.line([led_x - 20, led_in_y, led_x, led_in_y], fill=c_gnd, width=3)

    # =========================================================================
    # COLUMNA 3: ARDUINO UNO R3, LM75A, AUDIO Y FUENTE EXTERNA 5V 4A
    # x = 1300 a 1880 (ancho: 580 px)
    # =========================================================================

    # 1. Arduino Uno R3
    ard_x, ard_y, ard_w, ard_h = 1300, 160, 580, 620
    draw_ic(draw, ard_x, ard_y, ard_w, ard_h, "ARDUINO UNO R3 (ATmega328P)", "Maestro I2C & Coordinador de Tiempo Real", header_color="#0f766e")

    # Pines lado izquierdo
    ard_left_pins = [
        ("D2", "SoftwareSerial RX (3.3V)", 215, c_uart_tx),
        ("D3", "SoftwareSerial TX (5.0V)", 285, c_uart_rx),
        ("D4", "DATA Sensor DHT11", 365, c_dht_dat),
        ("D7", "Control LED Iluminacion", 445, c_led),
        ("5V", "VCC Logica Sensores/PCA", 515, c_pwr_5v),
        ("GND", "Tierra Comun Logica (0V)", 585, c_gnd),
    ]
    for pnum, pdesc, py, pcol in ard_left_pins:
        draw.rectangle([ard_x, py - 12, ard_x + 16, py + 12], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((ard_x + 24, py - 9), pnum, fill=pcol, font=f_pin)
        draw.text((ard_x + 75, py - 7), pdesc, fill="#64748b", font=f_text)
        draw.line([ard_x - 20, py, ard_x, py], fill=pcol, width=3)

    # Pines lado derecho
    ard_right_pins = [
        ("A4 (SDA)", "Bus I2C Datos (PCA & LM75)", 230, c_i2c_sda, True),
        ("5V (Logica)", "VCC Salida a PCA9685 y LM75A", 270, c_pwr_5v, True),
        ("A5 (SCL)", "Bus I2C Reloj (PCA & LM75)", 310, c_i2c_scl, True),
        ("D10 (NC)", "Pin Libre (Audio transferido al Movil)", 390, "#94a3b8", False),
        ("D11 (NC)", "Pin Libre (Audio transferido al Movil)", 470, "#94a3b8", False),
        ("GND (2)", "Tierra Comun Salida (0V)", 550, c_gnd, True),
    ]
    for pnum, pdesc, py, pcol, is_connected in ard_right_pins:
        px = ard_x + ard_w
        draw.rectangle([px - 16, py - 12, px, py + 12], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((px - 95, py - 9), pnum, fill=pcol, font=f_pin)
        draw.text((px - 350, py - 7), pdesc, fill="#64748b", font=f_text)
        if is_connected:
            draw.line([px, py, px + 20, py], fill=pcol, width=3)
        else:
            draw.line([px, py, px + 12, py], fill="#94a3b8", width=2)
            draw_label(draw, "NC (Libre)", px + 18, py - 8, f_pin_small, "#64748b", bg_color="#f1f5f9", border_color="#cbd5e1")

    # Banner informativo interior
    draw.rectangle([ard_x + 20, ard_y + ard_h - 60, ard_x + ard_w - 20, ard_y + ard_h - 15], fill="#f0fdf4", outline="#22c55e", width=1)
    draw.text((ard_x + 28, ard_y + ard_h - 50), "GESTION DETERMINISTA DE BUS I2C A 400 kHz", fill="#15803d", font=f_tag)
    draw.text((ard_x + 28, ard_y + ard_h - 32), "Gobierna PCA9685 (0x40) y LM75A (0x48). Audio delegado al Celular manos libres.", fill="#166534", font=f_text)

    # 2. Sensor LM75A (I2C)
    lm_x, lm_y, lm_w, lm_h = 1300, 810, 420, 250
    draw_ic(draw, lm_x, lm_y, lm_w, lm_h, "MODULO LM75A (I2C)", "Termometro Digital (0.5 deg C)", header_color="#059669")

    lm_pins = [
        ("VCC", "5V desde Arduino 5V", 860, c_pwr_5v),
        ("GND", "A tierra comun", 910, c_gnd),
        ("SDA", "Datos I2C (Addr 0x48)", 960, c_i2c_sda),
        ("SCL", "Reloj I2C sincrono", 1010, c_i2c_scl),
    ]
    for pnum, pdesc, py, pcol in lm_pins:
        px = lm_x + lm_w
        draw.rectangle([px - 14, py - 10, px, py + 10], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((px - 90, py - 8), pnum, fill=pcol, font=f_pin)
        draw.text((lm_x + 16, py - 6), pdesc, fill="#64748b", font=f_text)
        draw.line([px, py, px + 20, py], fill=pcol, width=3)

    # 3. Smartphone: Nodo Transductor de Voz Manos Libres (Tipo Alexa / WakeNet)
    ph_x, ph_y, ph_w, ph_h = 1300, 1090, 580, 320
    draw_ic(draw, ph_x, ph_y, ph_w, ph_h, "SMARTPHONE: AUDIO MANOS LIBRES (TIPO ALEXA)", "Transductor Inalambrico Wi-Fi: Microfono + Altavoz", header_color="#4338ca")

    # Dibujo de silueta de Smartphone (aspecto técnico limpio)
    phone_box_x = ph_x + 25
    phone_box_y = ph_y + 48
    phone_box_w = 115
    phone_box_h = 252
    draw.rounded_rectangle([phone_box_x, phone_box_y, phone_box_x + phone_box_w, phone_box_y + phone_box_h], radius=16, fill="#0f172a", outline="#6366f1", width=2)
    # Pantalla apagada en modo headless
    draw.rounded_rectangle([phone_box_x + 6, phone_box_y + 14, phone_box_x + phone_box_w - 6, phone_box_y + phone_box_h - 18], radius=10, fill="#1e293b", outline="#334155", width=1)
    
    # Auricular / Altavoz superior
    draw.line([phone_box_x + 40, phone_box_y + 8, phone_box_x + 75, phone_box_y + 8], fill="#94a3b8", width=2)
    # Cámara frontal
    draw.ellipse([phone_box_x + 30, phone_box_y + 6, phone_box_x + 34, phone_box_y + 10], fill="#64748b")
    
    # Círculos concéntricos de audio / radar WakeNet
    cx, cy = phone_box_x + phone_box_w // 2, phone_box_y + 105
    draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline="#3730a3", width=1)
    draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], outline="#4f46e5", width=1)
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill="#38bdf8")
    
    draw.text((phone_box_x + 16, cy + 38), "WAKENET", fill="#38bdf8", font=f_pin_small)
    draw.text((phone_box_x + 12, cy + 54), "MANOS LIBRES", fill="#94a3b8", font=f_tag)
    draw.text((phone_box_x + 12, cy + 70), "(SIN PANTALLA)", fill="#64748b", font=f_pin_small)

    # Micrófono y altavoz físico en borde inferior
    draw.ellipse([phone_box_x + 25, phone_box_y + phone_box_h - 10, phone_box_x + 29, phone_box_y + phone_box_h - 6], fill="#38bdf8")
    draw.line([phone_box_x + 55, phone_box_y + phone_box_h - 8, phone_box_x + 90, phone_box_y + phone_box_h - 8], fill="#94a3b8", width=2)

    # Detalle funcional del asistente
    tx_x = ph_x + 155
    draw.text((tx_x, ph_y + 50), "ESPECIFICACION FUNCIONAL ASISTENTE TIPO ALEXA:", fill="#312e81", font=f_tag)
    
    draw.text((tx_x, ph_y + 72), "1. Microfono Continuo (WakeNet / Hotword):", fill="#4338ca", font=f_text_bold)
    draw.text((tx_x + 14, ph_y + 90), "• Escucha activa permanente: 'Oye Robot' o 'Alexa'.", fill="#334155", font=f_text)
    draw.text((tx_x + 14, ph_y + 108), "• Cero interaccion con pantalla (100% manos libres).", fill="#334155", font=f_text)

    draw.text((tx_x, ph_y + 130), "2. Alerta Inmediata y Saludo de Bienvenida:", fill="#4338ca", font=f_text_bold)
    draw.text((tx_x + 14, ph_y + 148), "• Emite vocalmente: '¿En que te ayudo?' por su altavoz.", fill="#334155", font=f_text)
    draw.text((tx_x + 14, ph_y + 166), "• Notifica al robot: ojos centrados (90 deg) y LED luz activa.", fill="#334155", font=f_text)

    draw.text((tx_x, ph_y + 188), "3. Altavoz de Salida de Alta Potencia:", fill="#4338ca", font=f_text_bold)
    draw.text((tx_x + 14, ph_y + 206), "• Reproduce la sintesis vocal de la IA local (Loquendo).", fill="#334155", font=f_text)
    draw.text((tx_x + 14, ph_y + 224), "• Al terminar el audio, reanuda la escucha automaticamente.", fill="#334155", font=f_text)

    draw.text((tx_x, ph_y + 248), "4. Conectividad: Wi-Fi WebSocket hacia PC (Puerto 8000)", fill="#059669", font=f_text_bold)
    draw.text((tx_x + 14, ph_y + 268), "• Libera fisicamente los pines D10 y D11 del Arduino Uno.", fill="#059669", font=f_text)

    # 4. Fuente Externa Regulada 5V 4A
    pwr_x, pwr_y, pwr_w, pwr_h = 1300, 1440, 580, 420
    draw_ic(draw, pwr_x, pwr_y, pwr_w, pwr_h, "FUENTE EXTERNA REGULADA 5V (4A)", "Alimentacion Aislada para Servos E3.2", header_color="#b91c1c")

    draw.text((pwr_x + 24, pwr_y + 50), "Entrada: 110V/220V AC -> Salida 5.0V DC (4.0 A continuos)", fill="#0f172a", font=f_pin)
    draw.text((pwr_x + 24, pwr_y + 75), "Capacidad: 20W de potencia para los 6 servos SG90 / MG90S", fill="#dc2626", font=f_text_bold)

    # Banco de desacoplo
    draw.rectangle([pwr_x + 20, pwr_y + 95, pwr_x + 560, pwr_y + 240], fill="#fef2f2", outline="#f87171", width=1)
    draw.text((pwr_x + 30, pwr_y + 105), "BANCO DE FILTRO CAPACITIVO (DESACOPLO DE PICOS)", fill="#991b1b", font=f_tag)

    cap_x, cap_y = pwr_x + 40, pwr_y + 140
    draw.rectangle([cap_x, cap_y, cap_x + 90, cap_y + 80], fill="#334155", outline="#0f172a", width=2)
    draw.text((cap_x + 12, cap_y + 20), "2200 uF", fill="#ffffff", font=f_pin)
    draw.text((cap_x + 28, cap_y + 48), "16 V", fill="#94a3b8", font=f_text)
    draw.rectangle([cap_x + 70, cap_y, cap_x + 90, cap_y + 80], fill="#94a3b8")
    draw.text((cap_x + 75, cap_y + 28), "-", fill="#ffffff", font=f_pin)

    cap2_x, cap2_y = pwr_x + 160, pwr_y + 155
    draw.rectangle([cap2_x, cap2_y, cap2_x + 40, cap2_y + 48], fill="#f59e0b", outline="#b45309", width=2)
    draw.text((cap2_x + 8, cap2_y + 14), "104", fill="#ffffff", font=f_pin_small)
    draw.text((cap2_x - 6, cap2_y + 56), "100 nF", fill="#92400e", font=f_text)

    draw.text((pwr_x + 230, pwr_y + 145), "(+) Salida Potencia +5V (Cable Rojo)", fill="#dc2626", font=f_pin)
    draw.text((pwr_x + 230, pwr_y + 175), "(-) Salida Tierra GND (Cable Negro)", fill="#0f172a", font=f_pin)
    draw.text((pwr_x + 230, pwr_y + 205), "Conecta directo a la bornera V+ / GND del PCA9685", fill="#64748b", font=f_text)

    draw.rectangle([pwr_x + 20, pwr_y + 250, pwr_x + 560, pwr_y + 310], fill="#fff7ed", outline="#f97316", width=1)
    draw.text((pwr_x + 28, pwr_y + 260), "!PRECAUCION: NUNCA alimentar servos desde el pin 5V de Arduino ni ESP32!", fill="#c2410c", font=f_pin_small)
    draw.text((pwr_x + 28, pwr_y + 282), "Las corrientes inductivas pico reinician el microcontrolador y danan pistas.", fill="#9a3412", font=f_text)

    # Salidas derecha de la fuente
    draw.rectangle([pwr_x + pwr_w - 16, 1720 - 12, pwr_x + pwr_w, 1720 + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((pwr_x + pwr_w - 95, 1720 - 24), "+5V EXT", fill=c_pwr_ext, font=f_pin_small)
    draw.line([pwr_x + pwr_w, 1720, pwr_x + pwr_w + 20, 1720], fill=c_pwr_ext, width=5)

    draw.rectangle([pwr_x + pwr_w - 16, 1800 - 12, pwr_x + pwr_w, 1800 + 12], fill="#e2e8f0", outline="#334155", width=1)
    draw.text((pwr_x + pwr_w - 95, 1800 - 24), "GND EXT", fill=c_gnd, font=f_pin_small)
    draw.line([pwr_x + pwr_w, 1800, pwr_x + pwr_w + 20, 1800], fill=c_gnd, width=5)

    # =========================================================================
    # COLUMNA 4: CONTROLADOR I2C PCA9685 (16 CANALES PWM)
    # x = 2100 a 2580 (ancho: 480 px)
    # =========================================================================
    pca_x, pca_y, pca_w, pca_h = 2100, 160, 480, 2010
    draw_ic(draw, pca_x, pca_y, pca_w, pca_h, "CONTROLADOR I2C PCA9685 (16 CH PWM)", "Driver Hardware 12-Bit (I2C: 0x40)", header_color="#0284c7")

    # Pines lado izquierdo (Interfaz I2C lógica)
    pca_in_pins = [
        ("VCC", "5V Logico Arduino", 230, c_pwr_5v),
        ("GND", "Tierra Logica", 310, c_gnd),
        ("SDA", "Datos I2C (Bus A4)", 390, c_i2c_sda),
        ("SCL", "Reloj I2C (Bus A5)", 470, c_i2c_scl),
        ("OE", "Output Enable (A GND)", 550, c_gnd),
    ]
    for pnum, pdesc, py, pcol in pca_in_pins:
        draw.rectangle([pca_x, py - 10, pca_x + 14, py + 10], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((pca_x + 20, py - 8), pnum, fill=pcol, font=f_pin)
        draw.text((pca_x + 75, py - 6), pdesc, fill="#64748b", font=f_text)
        draw.line([pca_x - 20, py, pca_x, py], fill=pcol, width=3)

    # Salidas de canales a la derecha: PERFECTAMENTE ALINEADAS CON CADA SERVO E3.2
    pca_channels = [
        ("CH 0", "M1: Ojos Pan/Yaw", 280, c_pwm_eye),
        ("CH 1", "M2: Ojos Tilt/Pitch", 560, c_pwm_eye),
        ("CH 2", "M3: Parpado Sup Izq", 840, c_pwm_lid),
        ("CH 3", "M4: Parpado Inf Izq", 1120, c_pwm_low),
        ("CH 4", "M5: Parpado Sup Der", 1400, c_pwm_lid),
        ("CH 5", "M6: Parpado Inf Der", 1680, c_pwm_low),
    ]

    for ch_name, ch_desc, cy, col_sig in pca_channels:
        box_y = cy - 25
        draw.rectangle([pca_x + pca_w - 240, box_y, pca_x + pca_w - 10, box_y + 80], fill="#f1f5f9", outline="#94a3b8", width=1)
        draw.text((pca_x + pca_w - 230, box_y + 8), f"{ch_name} · {ch_desc}", fill="#0284c7", font=f_pin_small)

        # Pin PWM
        draw.rectangle([pca_x + pca_w - 16, cy - 8, pca_x + pca_w, cy + 8], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((pca_x + pca_w - 60, cy - 7), "PWM", fill=col_sig, font=f_pin_small)
        draw.line([pca_x + pca_w, cy, pca_x + pca_w + 20, cy], fill=col_sig, width=3)

        # Pin V+
        draw.rectangle([pca_x + pca_w - 16, cy + 12, pca_x + pca_w, cy + 28], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((pca_x + pca_w - 50, cy + 13), "V+", fill=c_pwr_ext, font=f_pin_small)
        draw.line([pca_x + pca_w, cy + 20, pca_x + pca_w + 20, cy + 20], fill=c_pwr_ext, width=3)

        # Pin GND
        draw.rectangle([pca_x + pca_w - 16, cy + 32, pca_x + pca_w, cy + 48], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((pca_x + pca_w - 55, cy + 33), "GND", fill=c_gnd, font=f_pin_small)
        draw.line([pca_x + pca_w, cy + 40, pca_x + pca_w + 20, cy + 40], fill=c_gnd, width=3)

    # Bornera de potencia del PCA9685 ubicada debajo de CH 5 (en y = 1860..2030)
    bor_y = 1860
    draw.rectangle([pca_x + 20, bor_y, pca_x + pca_w - 20, bor_y + 170], fill="#f8fafc", outline="#0284c7", width=2)
    draw.rectangle([pca_x + 20, bor_y, pca_x + pca_w - 20, bor_y + 32], fill="#0284c7")
    draw.text((pca_x + 28, bor_y + 7), "BORNERA DE ALIMENTACION (V+ / GND SERVOS)", fill="#ffffff", font=f_tag)

    # Borne V+ en el borde del módulo con terminal de tornillo
    bor_v_y = bor_y + 60
    draw.rectangle([pca_x - 14, bor_v_y - 12, pca_x, bor_v_y + 12], fill="#fee2e2", outline="#ef4444", width=2)
    draw.rectangle([pca_x + 25, bor_v_y - 18, pca_x + 130, bor_v_y + 18], fill="#fee2e2", outline="#ef4444", width=1)
    draw.text((pca_x + 35, bor_v_y - 8), "Borne V+", fill="#b91c1c", font=f_pin)

    # Borne GND en el borde del módulo con terminal de tornillo
    bor_gnd_y = bor_y + 115
    draw.rectangle([pca_x - 14, bor_gnd_y - 12, pca_x, bor_gnd_y + 12], fill="#f1f5f9", outline="#475569", width=2)
    draw.rectangle([pca_x + 25, bor_gnd_y - 18, pca_x + 130, bor_gnd_y + 18], fill="#f1f5f9", outline="#475569", width=1)
    draw.text((pca_x + 35, bor_gnd_y - 8), "Borne GND", fill="#0f172a", font=f_pin)

    draw.text((pca_x + 150, bor_v_y - 8), "Capacitor 1000 uF a bordo", fill="#64748b", font=f_text)
    draw.text((pca_x + 150, bor_v_y + 14), "Conexion directa desde fuente 5V 4A", fill="#0284c7", font=f_text_bold)
    draw.text((pca_x + 150, bor_gnd_y - 8), "Alimenta exclusivamente las lineas V+", fill="#dc2626", font=f_text)

    # =========================================================================
    # COLUMNA 5: LOS 6 SERVOMOTORES DEL MECANISMO OCULAR E3.2 (WILL COGLEY)
    # x = 2740 a 3740 (ancho: 1000 px)
    # =========================================================================
    cont_x, cont_y, cont_w, cont_h = 2740, 160, 1000, 2010
    draw.rectangle([cont_x+4, cont_y+4, cont_x+cont_w+4, cont_y+cont_h+4], fill="#cbd5e1")
    draw.rectangle([cont_x, cont_y, cont_x+cont_w, cont_y+cont_h], fill="#f8fafc", outline="#0284c7", width=2)
    draw.rectangle([cont_x, cont_y, cont_x+cont_w, cont_y+42], fill="#0284c7")
    draw.text((cont_x + 18, cont_y + 10), "ACTUADORES: MECANISMO OCULAR E3.2 (WILL COGLEY - MAKERWORLD #1184807)", fill="#ffffff", font=f_box_title)

    servos_e32 = [
        ("M1: SERVO OJOS - HORIZONTAL (PAN / YAW)", "Giro lateral conjunto (horquilla transversal)", 200, "#d97706", c_pwm_eye, "CH 0", "60 a 120 deg (Neutro 90 deg)", 280),
        ("M2: SERVO OJOS - VERTICAL (PITCH / TILT)", "Inclinacion arriba/abajo (varilla y rotula Gimbal)", 480, "#d97706", c_pwm_eye, "CH 1", "70 a 110 deg (Neutro 90 deg)", 560),
        ("M3: SERVO PARPADO SUPERIOR IZQUIERDO", "Apertura palpebral y parpadeo ojo izquierdo", 760, "#1d4ed8", c_pwm_lid, "CH 2", "45 deg (Cerrado) a 100 deg (Abierto)", 840),
        ("M4: SERVO PARPADO INFERIOR IZQUIERDO", "Elevacion inferior (expresion de sonrisa)", 1040, "#0284c7", c_pwm_low, "CH 3", "80 deg (Reposo) a 110 deg (Elevado)", 1120),
        ("M5: SERVO PARPADO SUPERIOR DERECHO", "Apertura palpebral y parpadeo ojo derecho", 1320, "#1d4ed8", c_pwm_lid, "CH 4", "45 deg (Cerrado) a 100 deg (Abierto)", 1400),
        ("M6: SERVO PARPADO INFERIOR DERECHO", "Elevacion inferior (expresion de sonrisa)", 1600, "#0284c7", c_pwm_low, "CH 5", "80 deg (Reposo) a 110 deg (Elevado)", 1680),
    ]

    servo_w, servo_h = 940, 210
    servo_x = cont_x + 30

    for sname, sdesc, sy, head_col, sig_col, ch_label, range_info, p_center_y in servos_e32:
        draw.rectangle([servo_x+3, sy+3, servo_x+servo_w+3, sy+servo_h+3], fill="#cbd5e1")
        draw.rectangle([servo_x, sy, servo_x+servo_w, sy+servo_h], fill="#ffffff", outline=head_col, width=2)
        draw.rectangle([servo_x, sy, servo_x+servo_w, sy+36], fill=head_col)
        draw.text((servo_x + 16, sy + 8), sname, fill="#ffffff", font=f_box_title)
        draw.text((servo_x + servo_w - 280, sy + 9), range_info, fill="#ffffff", font=f_pin_small)

        draw.text((servo_x + 18, sy + 45), f"Cinematica: {sdesc} · [Conectado a PCA9685 Canal {ch_label}]", fill="#475569", font=f_text)

        # Conector estándar de 3 pines Dupont
        servo_pins = [
            ("NARANJA (Senal PWM)", f"Pulso PWM desde Canal {ch_label}", p_center_y, sig_col),
            ("ROJO (+5V Potencia)", "Alimentacion desde Bornera V+ del PCA9685", p_center_y + 20, c_pwr_ext),
            ("MARRON / NEGRO (GND)", "Retorno a Tierra Comun PCA9685", p_center_y + 40, c_gnd),
        ]
        for p_label, p_info, py, col in servo_pins:
            draw.rectangle([servo_x, py - 10, servo_x + 14, py + 10], fill="#e2e8f0", outline="#334155", width=1)
            draw.text((servo_x + 22, py - 8), p_label, fill=col, font=f_pin)
            draw.text((servo_x + 240, py - 6), p_info, fill="#64748b", font=f_text)
            draw.line([servo_x - 20, py, servo_x, py], fill=col, width=3)

    # =========================================================================
    # CORREDOR 4: CABLEADO DIRECTO Y HORIZONTAL (SALIDAS PCA9685 -> SERVOS E3.2)
    # Líneas 100% horizontales sin cruces ni curvas
    # =========================================================================
    for idx, (_, _, cy, col_sig) in enumerate(pca_channels):
        # Señal PWM
        draw_wire(draw, [(pca_x + pca_w + 20, cy), (servo_x - 20, cy)], col_sig, width=3)
        # V+ (+5V)
        draw_wire(draw, [(pca_x + pca_w + 20, cy + 20), (servo_x - 20, cy + 20)], c_pwr_ext, width=3)
        # GND
        draw_wire(draw, [(pca_x + pca_w + 20, cy + 40), (servo_x - 20, cy + 40)], c_gnd, width=3)

    # =========================================================================
    # CORREDOR 1 (x: 480 a 700, ancho: 220 px): ESP32 <-> DIVISOR / GND
    # =========================================================================

    # 1. ESP32 GPIO 16 (RX2) (y = 360) recibe directamente desde Divisor OUT (y = 360)
    # LÍNEA 100% HORIZONTAL PERFECTA
    draw_wire(draw, [(div_x - 20, 360), (esp_x + esp_w + 20, 360)], c_uart_rx, width=3)
    draw_label(draw, "3.33V Atenuado -> RX2", 515, 340, f_pin_small, "#0369a1", bg_color="#ffffff", border_color=c_uart_rx)

    # 2. ESP32 GND (y = 450) se une con Divisor GND (y = 450)
    # LÍNEA 100% HORIZONTAL PERFECTA
    draw_wire(draw, [(div_x - 20, 450), (esp_x + esp_w + 20, 450)], c_gnd, width=3)
    draw_label(draw, "GND ESP32 -> Tierra Comun", 500, 430, f_pin_small, c_gnd, bg_color="#ffffff", border_color=c_gnd)

    # Derivación hacia abajo a tierra común (en x = 600)
    draw_junction(draw, (600, 450), c_gnd, r=5)
    draw_wire(draw, [(600, 450), (600, 780), (1260, 780)], c_gnd, width=3)
    draw_junction(draw, (1260, 780), c_gnd, r=5)

    # 3. ESP32 GPIO 17 (TX2 - 3.3V) (y = 280) hacia Arduino D2 (y = 215)
    # Sube por el canal superior libre (y = 125) sin tocar ningún componente
    draw_wire(draw, [
        (esp_x + esp_w + 20, 280),
        (580, 280),
        (580, 125),
        (1160, 125),
        (1160, 215),
        (ard_x - 20, 215)
    ], c_uart_tx, width=3)
    draw_label(draw, "TX2 (3.3V) -> D2", 520, 260, f_pin_small, c_uart_tx, bg_color="#ffffff", border_color=c_uart_tx)

    # =========================================================================
    # CORREDOR 2 (x: 1100 a 1300, ancho: 200 px): SENSORES / INTERFACES <-> ARDUINO
    # =========================================================================

    # 1. Arduino D3 (y = 285) hacia Entrada Divisor IN (y = 285)
    # LÍNEA 100% HORIZONTAL PERFECTA
    draw_wire(draw, [(ard_x - 20, 285), (div_x + div_w + 20, 285)], c_uart_rx, width=3)
    draw_label(draw, "D3 (5V TX) -> Divisor", 1120, 265, f_pin_small, c_uart_rx, bg_color="#ffffff", border_color=c_uart_rx)

    # 2. DHT11 DATA (y = 680) hacia Arduino D4 (y = 365)
    draw_wire(draw, [
        (dht_x + dht_w + 20, 680),
        (1140, 680),
        (1140, 365),
        (ard_x - 20, 365)
    ], c_dht_dat, width=3)
    draw_label(draw, "DHT11 DAT -> D4", 1110, 655, f_pin_small, c_dht_dat, bg_color="#ffffff", border_color=c_dht_dat)

    # 3. Arduino D7 (y = 445) hacia LED Ánodo (y = 920)
    draw_wire(draw, [
        (ard_x - 20, 445),
        (1180, 445),
        (1180, 920),
        (led_x + led_w + 20, 920)
    ], c_led, width=3)
    draw_label(draw, "D7 -> LED Luz", 1140, 895, f_pin_small, c_led, bg_color="#ffffff", border_color=c_led)

    # 4. Bus de 5V Lógica desde Arduino 5V (y = 515) EXCLUSIVAMENTE hacia abajo (DHT11)
    # CERO cruces verticales hacia arriba
    draw_wire(draw, [
        (ard_x - 20, 515),
        (1220, 515),
        (1220, 620),
        (dht_x + dht_w + 20, 620)
    ], c_pwr_5v, width=3)
    draw_junction(draw, (1220, 515), c_pwr_5v, r=5)
    draw_label(draw, "+5V Logica", 1140, 495, f_pin_small, c_pwr_5v, bg_color="#ffffff", border_color=c_pwr_5v)

    # 5. Bus de Tierra GND Lógica desde Arduino GND (y = 585)
    draw_wire(draw, [
        (ard_x - 20, 585),
        (1260, 585),
        (1260, 740),
        (dht_x + dht_w + 20, 740)
    ], c_gnd, width=3)
    draw_junction(draw, (1260, 585), c_gnd, r=5)

    # Tierra hacia LED Cátodo (en y = 920)
    draw_wire(draw, [
        (led_x - 20, 920),
        (600, 920),
        (600, 780)
    ], c_gnd, width=3)
    draw_junction(draw, (600, 920), c_gnd, r=5)

    # =========================================================================
    # CORREDOR 3 (x: 1880 a 2100, ancho: 220 px): I2C, FUENTE Y POTENCIA
    # Pista 1 (x = 1960): Bus I2C SDA (Arduino A4 -> PCA9685 y LM75A)
    # Pista 2 (x = 1990): Bus I2C SCL (Arduino A5 -> PCA9685 y LM75A)
    # Pista 3 (x = 2020): 5V Logica (Arduino 5V -> PCA9685 VCC y LM75A VCC)
    # Pista 4 (x = 2050): Tierra Comun Unificada (Lazo 0V)
    # =========================================================================

    # 1. Bus I2C SDA (Arduino A4 y = 230)
    draw_wire(draw, [
        (ard_x + ard_w + 20, 230),
        (1960, 230),
        (1960, 960),
        (lm_x + lm_w + 20, 960)
    ], c_i2c_sda, width=3)
    draw_junction(draw, (1960, 230), c_i2c_sda, r=6)

    # Derivación SDA hacia PCA9685 (y = 390)
    draw_wire(draw, [(1960, 390), (pca_x - 20, 390)], c_i2c_sda, width=3)
    draw_junction(draw, (1960, 390), c_i2c_sda, r=6)
    draw_label(draw, "I2C SDA (0x40)", 1980, 370, f_pin_small, c_i2c_sda, bg_color="#ffffff", border_color=c_i2c_sda)
    draw_label(draw, "I2C SDA (0x48)", 1750, 940, f_pin_small, c_i2c_sda, bg_color="#ffffff", border_color=c_i2c_sda)

    # 3. Bus I2C SCL (Arduino A5 y = 310)
    draw_wire(draw, [
        (ard_x + ard_w + 20, 310),
        (1990, 310),
        (1990, 1010),
        (lm_x + lm_w + 20, 1010)
    ], c_i2c_scl, width=3)
    draw_junction(draw, (1990, 310), c_i2c_scl, r=6)

    # Derivación SCL hacia PCA9685 (y = 470)
    draw_wire(draw, [(1990, 470), (pca_x - 20, 470)], c_i2c_scl, width=3)
    draw_junction(draw, (1990, 470), c_i2c_scl, r=6)
    draw_label(draw, "I2C SCL", 2005, 450, f_pin_small, c_i2c_scl, bg_color="#ffffff", border_color=c_i2c_scl)
    draw_label(draw, "I2C SCL", 1750, 990, f_pin_small, c_i2c_scl, bg_color="#ffffff", border_color=c_i2c_scl)

    # 4. 5V Lógica hacia PCA9685 VCC (y = 230) y LM75A VCC (y = 860)
    # Sale directamente desde Arduino pin "5V (Logica)" a y = 270
    draw_wire(draw, [
        (ard_x + ard_w + 20, 270),
        (2020, 270),
        (2020, 230),
        (pca_x - 20, 230)
    ], c_pwr_5v, width=3)
    draw_junction(draw, (2020, 270), c_pwr_5v, r=5)
    draw_label(draw, "5V Logico PCA", 2025, 210, f_pin_small, c_pwr_5v, bg_color="#ffffff", border_color=c_pwr_5v)

    draw_wire(draw, [
        (2020, 270),
        (2020, 860),
        (lm_x + lm_w + 20, 860)
    ], c_pwr_5v, width=3)
    draw_junction(draw, (2020, 860), c_pwr_5v, r=5)

    # 5. Lazo de Tierra Común Unificada (GND 0V)
    draw_wire(draw, [
        (ard_x + ard_w + 20, 550),
        (2050, 550),
        (2050, 310),
        (pca_x - 20, 310)
    ], c_gnd, width=5)
    draw_junction(draw, (pca_x - 20, 310), c_gnd, r=6)

    # Derivación OE (Output Enable) del PCA9685 a GND
    draw_wire(draw, [
        (pca_x - 20, 550),
        (2070, 550),
        (2070, 310)
    ], c_gnd, width=3)
    draw_junction(draw, (2070, 310), c_gnd, r=5)

    # Tierra hacia LM75A GND (y = 910)
    draw_wire(draw, [
        (2050, 550),
        (2050, 910),
        (lm_x + lm_w + 20, 910)
    ], c_gnd, width=3)
    draw_junction(draw, (lm_x + lm_w + 20, 910), c_gnd, r=5)

    # Tierra unida a GND de Fuente Externa (y = 1800)
    draw_wire(draw, [
        (2050, 910),
        (2050, 1800),
        (pwr_x + pwr_w + 20, 1800)
    ], c_gnd, width=5)
    draw_junction(draw, (2050, 1800), c_gnd, r=7)
    draw_label(draw, "LAZO TIERRA COMUN (0V)", 1910, 530, f_pin_small, c_gnd, bg_color="#ffffff", border_color=c_gnd)

    # =========================================================================
    # POTENCIA DEDICADA: FUENTE EXTERNA 5V 4A -> BORNERA PCA9685
    # Trazos limpios hacia los terminales de tornillo ubicados en y = bor_v_y y bor_gnd_y
    # =========================================================================
    # +5V Potencia (y = 1720) baja libre y entra a Borne V+ (y = bor_v_y = 1920)
    draw_wire(draw, [
        (pwr_x + pwr_w + 20, 1720),
        (2075, 1720),
        (2075, bor_v_y),
        (pca_x - 14, bor_v_y)
    ], c_pwr_ext, width=5)
    draw_label(draw, "+5V Potencia Servos", 1885, 1695, f_pin_small, c_pwr_ext, bg_color="#ffffff", border_color=c_pwr_ext)

    # GND Potencia (y = 1800) baja libre y entra a Borne GND (y = bor_gnd_y = 1975)
    draw_wire(draw, [
        (2050, 1800),
        (2050, bor_gnd_y),
        (pca_x - 14, bor_gnd_y)
    ], c_gnd, width=5)
    draw_label(draw, "GND Potencia Servos", 1885, 1775, f_pin_small, c_gnd, bg_color="#ffffff", border_color=c_gnd)

    # =========================================================================
    # GUARDAR IMAGEN EN ALTA RESOLUCIÓN
    # =========================================================================
    os.makedirs(OUTPUT_PNG.parent, exist_ok=True)
    img.save(OUTPUT_PNG, "PNG", dpi=(300, 300))
    img.save(OUTPUT_E32_PNG, "PNG", dpi=(300, 300))
    file_size_kb = os.path.getsize(OUTPUT_PNG) / 1024
    print(f"[EXITO] Plano esquematico expandido generado con exito: {OUTPUT_PNG} ({file_size_kb:.1f} KB)")

if __name__ == "__main__":
    render_schematic()
