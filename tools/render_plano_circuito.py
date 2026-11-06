#!/usr/bin/env python3
"""
Generador del Plano Eléctrico y Diagrama de Conexiones
Proyecto: Cabeza Animatrónica con IA Local
Plataforma: ESP32 DevKit V1 + Arduino Uno R3 + LM75A (I2C) + DHT11 + 3x SG90 + Fuente Externa
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PNG = BASE_DIR.parent / "docs" / "plano_circuito_animatronico.png"

def get_font(size, bold=False):
    paths = [
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

def draw_wire(draw, points, color, width=3, is_dashed=False):
    """Dibuja cables en angulos rectos limpios con uniones."""
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=color, width=width)

def draw_junction(draw, pt, color, r=5):
    """Dibuja un nodo/punto de union electrica."""
    draw.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=color, outline="#0f172a", width=1)

def draw_ic(draw, x, y, w, h, title, subtitle, header_color="#0284c7", body_color="#ffffff", border_color="#334155"):
    """Dibuja un bloque modular de circuito integrado / placa."""
    # Sombra suave
    draw.rectangle([x+4, y+4, x+w+4, y+h+4], fill="#cbd5e1")
    # Cuerpo principal
    draw.rectangle([x, y, x+w, y+h], fill=body_color, outline=border_color, width=2)
    # Cabecera
    hh = 38
    draw.rectangle([x, y, x+w, y+hh], fill=header_color, outline=border_color, width=2)
    
    font_h = get_font(16, bold=True)
    font_sub = get_font(11, bold=False)
    
    draw.text((x + 12, y + 8), title, fill="#ffffff", font=font_h)
    if subtitle:
        # Medir ancho para alinear derecha
        bbox = font_sub.getbbox(subtitle)
        sw = bbox[2] - bbox[0]
        draw.text((x + w - sw - 12, y + 12), subtitle, fill="#f1f5f9", font=font_sub)

def render_schematic():
    W, H = 2600, 1650
    # Fondo estilo plano tecnico limpio (papel milimetrado digital)
    bg_color = "#f8fafc"
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Cuadricula milimetrica de referencia
    grid_major = "#e2e8f0"
    grid_minor = "#f1f5f9"
    for x in range(0, W, 25):
        c = grid_major if x % 100 == 0 else grid_minor
        draw.line([x, 0, x, H], fill=c, width=1)
    for y in range(0, H, 25):
        c = grid_major if y % 100 == 0 else grid_minor
        draw.line([0, y, W, y], fill=c, width=1)

    # Fuentes
    f_title = get_font(24, bold=True)
    f_sub = get_font(14, bold=False)
    f_pin = get_font(13, bold=True)
    f_pin_small = get_font(11, bold=True)
    f_text = get_font(12, bold=False)
    f_legend = get_font(13, bold=True)
    f_tag = get_font(12, bold=True)
    f_box_title = get_font(15, bold=True)

    # Codigo de colores de cables estandar
    c_pwr_ext = "#dc2626"   # Rojo intenso: 5V Externa de Servos
    c_pwr_5v  = "#ea580c"   # Naranja rojizo: 5V Arduino Sensores
    c_gnd     = "#0f172a"   # Negro / Azul medianoche: GND comun
    c_pwm     = "#d97706"   # Ambar: Senales PWM de servos
    c_i2c_sda = "#16a34a"   # Verde: I2C SDA
    c_i2c_scl = "#ca8a04"   # Amarillo oro: I2C SCL
    c_dht_dat = "#9333ea"   # Morado: DHT11 Data
    c_uart_tx = "#2563eb"   # Azul real: UART TX (ESP32 a Arduino)
    c_uart_rx = "#0284c7"   # Celeste: UART RX (Arduino a ESP32 acondicionada)
    c_led     = "#059669"   # Esmeralda: Control LED

    # =========================================================================
    # ENCABEZADO Y CAJETIN DE DIBUJO TECNICO
    # =========================================================================
    draw.rectangle([40, 30, W - 40, 110], fill="#0f172a", outline="#334155", width=2)
    draw.text((65, 45), "SISTEMA ANIMATRÓNICO INTELIGENTE · PLANO ELÉCTRICO DE CONEXIONES", fill="#38bdf8", font=f_title)
    draw.text((65, 80), "Arquitectura de 4 Niveles: ESP32 DevKit V1 + Arduino Uno R3 + I2C LM75A + DHT11 + 3x Servos SG90 + Fuente Aislada 5V", fill="#94a3b8", font=f_sub)
    draw.text((W - 380, 50), "Plataforma: Embebidos & IA", fill="#f8fafc", font=f_pin)
    draw.text((W - 380, 75), "Versión: 1.2 Oficial · LM75A I2C", fill="#4ade80", font=f_pin)

    # =========================================================================
    # BLOQUE 1: ESP32 DEVKIT V1 (MAESTRO DE RED / WEBSOCKETS)
    # =========================================================================
    esp_x, esp_y, esp_w, esp_h = 100, 170, 380, 500
    draw_ic(draw, esp_x, esp_y, esp_w, esp_h, "ESP32 DevKit V1", "Puente Wi-Fi / UART2", header_color="#0369a1")
    
    # Pines del ESP32 representados
    esp_pins = [
        ("3V3", "3.3V Reg. Out", 230),
        ("GND", "Tierra común", 280),
        ("GPIO 17 (TX2)", "Salida UART 3.3V", 360),
        ("GPIO 16 (RX2)", "Entrada UART (3.3V Max)", 440),
        ("VIN", "Entrada 5V (USB)", 540),
    ]
    for pname, pdesc, py in esp_pins:
        # Conector a la derecha del ESP32
        px = esp_x + esp_w
        draw.rectangle([px - 14, py - 12, px, py + 12], fill="#e2e8f0", outline="#475569", width=1)
        draw.text((px - 130, py - 9), pname, fill="#0f172a", font=f_pin)
        draw.text((esp_x + 16, py - 7), pdesc, fill="#64748b", font=f_text)
        draw.line([px, py, px + 15, py], fill="#475569", width=2)

    # Nota de no conectar 5V a GPIO
    draw.rectangle([esp_x + 16, esp_y + esp_h - 75, esp_x + esp_w - 16, esp_y + esp_h - 15], fill="#fef2f2", outline="#ef4444", width=1)
    draw.text((esp_x + 24, esp_y + esp_h - 65), "¡ADVERTENCIA DE VOLTAJE!", fill="#b91c1c", font=f_tag)
    draw.text((esp_x + 24, esp_y + esp_h - 45), "GPIO 16/17 no toleran 5V. RX2 requiere divisor.", fill="#991b1b", font=f_text)

    # =========================================================================
    # BLOQUE 2: DIVISOR DE TENSIÓN RESISTIVO (5V -> 3.3V)
    # =========================================================================
    div_x, div_y, div_w, div_h = 560, 360, 240, 240
    draw.rectangle([div_x, div_y, div_x + div_w, div_y + div_h], fill="#ffffff", outline="#0284c7", width=2)
    draw.rectangle([div_x, div_y, div_x + div_w, div_y + 32], fill="#0284c7")
    draw.text((div_x + 10, div_y + 7), "DIVISOR RESISTIVO (5V→3.3V)", fill="#ffffff", font=f_tag)
    
    # Dibujo de resistencias esquematicas
    # R1: 1k
    r1_x, r1_y = div_x + 70, div_y + 55
    draw.rectangle([r1_x, r1_y, r1_x + 80, r1_y + 32], fill="#fed7aa", outline="#c2410c", width=2)
    draw.text((r1_x + 14, r1_y + 7), "R1: 1 kΩ", fill="#9a3412", font=f_pin)
    
    # R2: 2k
    r2_x, r2_y = div_x + 70, div_y + 145
    draw.rectangle([r2_x, r2_y, r2_x + 80, r2_y + 32], fill="#fed7aa", outline="#c2410c", width=2)
    draw.text((r2_x + 14, r2_y + 7), "R2: 2 kΩ", fill="#9a3412", font=f_pin)

    # Nodo intermedio
    node_y = div_y + 115
    draw.line([r1_x + 40, r1_y + 32, r1_x + 40, r2_y], fill="#0284c7", width=3)
    draw_junction(draw, (r1_x + 40, node_y), "#0284c7", r=6)
    draw.text((div_x + 120, node_y - 8), "3.33 V", fill="#0369a1", font=f_pin)

    # =========================================================================
    # BLOQUE 3: ARDUINO UNO R3 (CONTROLADOR MAESTRO DE TIEMPO REAL)
    # =========================================================================
    ard_x, ard_y, ard_w, ard_h = 880, 170, 520, 850
    draw_ic(draw, ard_x, ard_y, ard_w, ard_h, "ARDUINO UNO R3", "Procesador de E/S & Tiempo Real", header_color="#0f766e")

    # Pines lado izquierdo (Comunicaciones y Sensores Digitales)
    ard_left_pins = [
        ("D2", "SoftwareSerial RX (desde ESP32 TX2)", 240, c_uart_tx),
        ("D3", "SoftwareSerial TX (hacia Divisor R1)", 330, c_uart_rx),
        ("D4", "DATA Sensor Humedad DHT11", 420, c_dht_dat),
        ("D7", "Salida Control LED / Relé", 510, c_led),
        ("GND", "Tierra de referencia lógica", 600, c_gnd),
        ("5V", "VCC Sensores lógicos (LM75A / DHT11)", 700, c_pwr_5v),
    ]
    for pnum, pdesc, py, pcol in ard_left_pins:
        draw.rectangle([ard_x, py - 12, ard_x + 16, py + 12], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((ard_x + 24, py - 9), pnum, fill=pcol, font=f_pin)
        draw.text((ard_x + 75, py - 7), pdesc, fill="#64748b", font=f_text)
        draw.line([ard_x - 15, py, ard_x, py], fill=pcol, width=3)

    # Pines lado derecho (I2C y PWM Servos)
    ard_right_pins = [
        ("D9", "PWM Servo 1: Ojos (Horizontal)", 240, c_pwm),
        ("D10", "PWM Servo 2: Párpados (Apertura)", 330, c_pwm),
        ("D11", "PWM Servo 3: Boca (Lip-Sync)", 420, c_pwm),
        ("A4 (SDA)", "I2C Data: Sensor LM75A", 540, c_i2c_sda),
        ("A5 (SCL)", "I2C Clock: Sensor LM75A", 630, c_i2c_scl),
        ("GND (2)", "Tierra común secundaria", 740, c_gnd),
    ]
    for pnum, pdesc, py, pcol in ard_right_pins:
        px = ard_x + ard_w
        draw.rectangle([px - 16, py - 12, px, py + 12], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((px - 95, py - 9), pnum, fill=pcol, font=f_pin)
        draw.text((px - 360, py - 7), pdesc, fill="#64748b", font=f_text)
        draw.line([px, py, px + 15, py], fill=pcol, width=3)

    # =========================================================================
    # BLOQUE 4: SENSOR DE TEMPERATURA DIGITAL LM75A (I2C)
    # =========================================================================
    lm_x, lm_y, lm_w, lm_h = 1000, 1100, 360, 320
    draw_ic(draw, lm_x, lm_y, lm_w, lm_h, "MÓDULO LM75A (I2C)", "Dirección 0x48", header_color="#059669")
    
    lm_pins = [
        ("VCC", "5V desde Arduino 5V", 1160, c_pwr_5v),
        ("GND", "A tierra común", 1210, c_gnd),
        ("SDA", "Línea de datos I2C (hacia A4)", 1260, c_i2c_sda),
        ("SCL", "Línea de reloj I2C (hacia A5)", 1310, c_i2c_scl),
        ("A0,A1,A2", "Conectados a GND (Addr 0x48)", 1360, c_gnd),
    ]
    for pnum, pdesc, py, pcol in lm_pins:
        draw.rectangle([lm_x, py - 10, lm_x + 14, py + 10], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((lm_x + 22, py - 8), pnum, fill=pcol, font=f_pin)
        draw.text((lm_x + 105, py - 6), pdesc, fill="#64748b", font=f_text)
        draw.line([lm_x - 15, py, lm_x, py], fill=pcol, width=2)

    # =========================================================================
    # BLOQUE 5: SENSOR DE HUMEDAD DHT11 (MÓDULO PCB)
    # =========================================================================
    dht_x, dht_y, dht_w, dht_h = 560, 720, 250, 240
    draw_ic(draw, dht_x, dht_y, dht_w, dht_h, "DHT11 (Humedad)", "Módulo 3 Pines", header_color="#7c3aed")
    
    dht_pins = [
        ("VCC (+)", "5V (Arduino)", 780, c_pwr_5v),
        ("DAT (OUT)", "Datos hacia D4", 840, c_dht_dat),
        ("GND (-)", "Tierra común", 900, c_gnd),
    ]
    for pnum, pdesc, py, pcol in dht_pins:
        px = dht_x + dht_w
        draw.rectangle([px - 14, py - 10, px, py + 10], fill="#e2e8f0", outline="#334155", width=1)
        draw.text((px - 90, py - 8), pnum, fill=pcol, font=f_pin)
        draw.line([px, py, px + 15, py], fill=pcol, width=2)

    # =========================================================================
    # BLOQUE 6: LED INDICADOR CON RESISTENCIA LIMITADORA
    # =========================================================================
    led_x, led_y = 560, 1020
    draw.rectangle([led_x, led_y, led_x + 250, led_y + 110], fill="#ffffff", outline="#059669", width=2)
    draw.rectangle([led_x, led_y, led_x + 250, led_y + 30], fill="#059669")
    draw.text((led_x + 10, led_y + 6), "ACTUADOR: LED / LUZ", fill="#ffffff", font=f_tag)
    
    # Resistencia de 220 ohm y LED
    draw.rectangle([led_x + 25, led_y + 50, led_x + 95, led_y + 80], fill="#a7f3d0", outline="#047857", width=2)
    draw.text((led_x + 32, led_y + 58), "220 Ω", fill="#065f46", font=f_pin)
    
    # Simbolo LED
    draw.ellipse([led_x + 140, led_y + 48, led_x + 175, led_y + 83], fill="#10b981", outline="#047857", width=2)
    draw.text((led_x + 185, led_y + 58), "LED 5mm", fill="#0f172a", font=f_pin)
    draw.line([led_x + 95, led_y + 65, led_x + 140, led_y + 65], fill=c_led, width=2)

    # =========================================================================
    # BLOQUE 7: FUENTE DE ALIMENTACIÓN EXTERNA Y FILTRO CAPACITIVO
    # =========================================================================
    pwr_x, pwr_y, pwr_w, pwr_h = 1600, 170, 360, 290
    draw_ic(draw, pwr_x, pwr_y, pwr_w, pwr_h, "FUENTE EXTERNA 5V", "Dedicada a Servomotores", header_color="#b91c1c")
    
    draw.text((pwr_x + 20, pwr_y + 55), "Entrada: Eliminador 5V (2A - 3A)", fill="#0f172a", font=f_pin)
    draw.text((pwr_x + 20, pwr_y + 80), "Picos SG90: Hasta 1.5A combinados", fill="#dc2626", font=f_text)
    
    # Capacitor electrolitico de 1000 uF
    draw.rectangle([pwr_x + 20, pwr_y + 120, pwr_x + 340, pwr_y + 250], fill="#fef2f2", outline="#f87171", width=1)
    draw.text((pwr_x + 35, pwr_y + 130), "FILTRO DE DESACOPLO ELECTROLÍTICO", fill="#991b1b", font=f_tag)
    
    cap_x, cap_y = pwr_x + 60, pwr_y + 165
    draw.rectangle([cap_x, cap_y, cap_x + 70, cap_y + 60], fill="#334155", outline="#0f172a", width=2)
    draw.text((cap_x + 8, cap_y + 15), "1000 µF", fill="#ffffff", font=f_pin)
    draw.text((cap_x + 18, cap_y + 35), "16 V", fill="#94a3b8", font=f_text)
    # Franja negativa
    draw.rectangle([cap_x + 52, cap_y, cap_x + 70, cap_y + 60], fill="#94a3b8")
    draw.text((cap_x + 57, cap_y + 20), "-", fill="#ffffff", font=f_pin)

    draw.text((pwr_x + 150, pwr_y + 175), "(+) Conectado a +5V Ext", fill="#dc2626", font=f_pin)
    draw.text((pwr_x + 150, pwr_y + 205), "(-) Conectado a GND Común", fill="#0f172a", font=f_pin)

    # =========================================================================
    # BLOQUE 8: 3x MICRO-SERVOS SG90 (9g)
    # =========================================================================
    servos = [
        ("M1: SERVO OJOS", "Giro Horizontal (60°-120°)", 540, 240),
        ("M2: SERVO PÁRPADOS", "Apertura / Parpadeo (50°-100°)", 800, 330),
        ("M3: SERVO BOCA", "Mandíbula / Lip-Sync (90°-130°)", 1060, 420),
    ]
    servo_x, servo_w, servo_h = 2060, 460, 210
    
    for sname, sdesc, sy, ard_pwm_y in servos:
        draw.rectangle([servo_x+3, sy+3, servo_x+servo_w+3, sy+servo_h+3], fill="#cbd5e1")
        draw.rectangle([servo_x, sy, servo_x+servo_w, sy+servo_h], fill="#ffffff", outline="#d97706", width=2)
        draw.rectangle([servo_x, sy, servo_x+servo_w, sy+34], fill="#d97706")
        draw.text((servo_x + 14, sy + 7), sname, fill="#ffffff", font=f_box_title)
        draw.text((servo_x + 200, sy + 10), sdesc, fill="#fef3c7", font=f_text)

        # 3 Cables por cada servo
        pins_s = [
            ("NARANJA (Señal)", "PWM desde Arduino", sy + 65, c_pwm),
            ("ROJO (+5V)", "Desde Fuente Externa 5V", sy + 115, c_pwr_ext),
            ("MARRÓN (GND)", "A Tierra Común", sy + 165, c_gnd),
        ]
        for p_label, p_info, py, col in pins_s:
            draw.rectangle([servo_x, py - 10, servo_x + 14, py + 10], fill="#e2e8f0", outline="#334155", width=1)
            draw.text((servo_x + 22, py - 8), p_label, fill=col, font=f_pin)
            draw.text((servo_x + 180, py - 6), p_info, fill="#64748b", font=f_text)
            draw.line([servo_x - 20, py, servo_x, py], fill=col, width=3)

    # =========================================================================
    # RIELES DE POTENCIA Y DISTRIBUCIÓN
    # =========================================================================
    # Riel 5V Externa (Vertical en x = 2010)
    rail_5v_ext_x = 2010
    draw.line([rail_5v_ext_x, 300, rail_5v_ext_x, 1175], fill=c_pwr_ext, width=5)
    draw.text((rail_5v_ext_x - 120, 280), "RIEL +5V EXTERNA (SERVOS)", fill=c_pwr_ext, font=f_tag)

    # Salida de la fuente a riel 5V
    draw_wire(draw, [(pwr_x + pwr_w, 300), (rail_5v_ext_x, 300)], c_pwr_ext, width=5)
    draw_junction(draw, (rail_5v_ext_x, 300), c_pwr_ext, r=7)

    # Riel GND Común (Vertical en x = 1970)
    rail_gnd_x = 1970
    draw.line([rail_gnd_x, 350, rail_gnd_x, 1500], fill=c_gnd, width=5)
    draw.text((rail_gnd_x - 120, 1515), "RIEL DE TIERRA COMÚN (GND UNIFICADO)", fill=c_gnd, font=f_tag)

    # Salida GND fuente a riel GND
    draw_wire(draw, [(pwr_x + pwr_w, 350), (rail_gnd_x, 350)], c_gnd, width=5)
    draw_junction(draw, (rail_gnd_x, 350), c_gnd, r=7)

    # Conectar 5V y GND a cada uno de los 3 servos
    for _, _, sy, _ in servos:
        # Rojo (+5V)
        draw_wire(draw, [(rail_5v_ext_x, sy + 115), (servo_x - 20, sy + 115)], c_pwr_ext, width=3)
        draw_junction(draw, (rail_5v_ext_x, sy + 115), c_pwr_ext, r=5)
        # Marron (GND)
        draw_wire(draw, [(rail_gnd_x, sy + 165), (servo_x - 20, sy + 165)], c_gnd, width=3)
        draw_junction(draw, (rail_gnd_x, sy + 165), c_gnd, r=5)

    # =========================================================================
    # TRAZADO DE CABLES: SEÑALES DE CONTROL
    # =========================================================================
    
    # 1. PWM Servos desde Arduino Uno a Servos
    # Servo 1 (Ojos): D9 -> M1
    draw_wire(draw, [(ard_x + ard_w + 15, 240), (1500, 240), (1500, 605), (servo_x - 20, 605)], c_pwm, width=3)
    
    # Servo 2 (Parpados): D10 -> M2
    draw_wire(draw, [(ard_x + ard_w + 15, 330), (1530, 330), (1530, 865), (servo_x - 20, 865)], c_pwm, width=3)

    # Servo 3 (Boca): D11 -> M3
    draw_wire(draw, [(ard_x + ard_w + 15, 420), (1560, 420), (1560, 1125), (servo_x - 20, 1125)], c_pwm, width=3)

    # 2. UART: ESP32 GPIO 17 (TX2) directo a Arduino D2 (RX)
    draw_wire(draw, [
        (esp_x + esp_w + 15, 360),
        (520, 360),
        (520, 240),
        (ard_x - 15, 240)
    ], c_uart_tx, width=3)
    draw.text((530, 260), "TX2 (3.3V) → D2", fill=c_uart_tx, font=f_pin_small)

    # 3. UART: Arduino D3 (TX) a Divisor de Tension (R1)
    draw_wire(draw, [
        (ard_x - 15, 330),
        (840, 330),
        (840, div_y + 71),
        (r1_x + 80, div_y + 71)
    ], c_uart_rx, width=3)
    draw.text((720, 310), "D3 (5V TX)", fill=c_uart_rx, font=f_pin_small)

    # 4. Divisor nodo central (3.3V) hacia ESP32 GPIO 16 (RX2)
    draw_wire(draw, [
        (r1_x + 40, node_y),
        (510, node_y),
        (510, 440),
        (esp_x + esp_w + 15, 440)
    ], c_uart_rx, width=3)
    draw.text((370, 455), "3.33V Protegido → RX2", fill="#0369a1", font=f_pin_small)

    # 5. Divisor R2 hacia GND
    draw_wire(draw, [
        (r2_x + 40, r2_y + 32),
        (r2_x + 40, div_y + div_h + 30),
        (480, div_y + div_h + 30),
        (480, 280),
        (esp_x + esp_w + 15, 280)
    ], c_gnd, width=3)
    draw_junction(draw, (esp_x + esp_w + 15, 280), c_gnd, r=5)

    # 6. DHT11 Conexiones:
    # VCC a Arduino 5V
    draw_wire(draw, [
        (dht_x + dht_w + 15, 780),
        (840, 780),
        (840, 700),
        (ard_x - 15, 700)
    ], c_pwr_5v, width=3)
    draw_junction(draw, (ard_x - 15, 700), c_pwr_5v, r=5)

    # DATA a Arduino D4
    draw_wire(draw, [
        (dht_x + dht_w + 15, 840),
        (855, 840),
        (855, 420),
        (ard_x - 15, 420)
    ], c_dht_dat, width=3)

    # GND a Riel de Tierra
    draw_wire(draw, [
        (dht_x + dht_w + 15, 900),
        (825, 900),
        (825, 600),
        (ard_x - 15, 600)
    ], c_gnd, width=3)
    draw_junction(draw, (ard_x - 15, 600), c_gnd, r=5)

    # 7. LED Conexiones:
    # D7 a resistencia de 220 ohm
    draw_wire(draw, [
        (ard_x - 15, 510),
        (840, 510),
        (840, 1065),
        (led_x + 25, 1065)
    ], c_led, width=3)
    # Catodo de LED a GND
    draw_wire(draw, [
        (led_x + 175, 1065),
        (led_x + 220, 1065),
        (led_x + 220, 950),
        (825, 950)
    ], c_gnd, width=2)
    draw_junction(draw, (825, 950), c_gnd, r=4)

    # 8. LM75A Conexiones (I2C):
    # SDA a Arduino A4
    draw_wire(draw, [
        (lm_x - 15, 1260),
        (940, 1260),
        (940, 540),
        (ard_x + ard_w + 15, 540)
    ], c_i2c_sda, width=3)
    draw.text((950, 1000), "I2C SDA → A4", fill=c_i2c_sda, font=f_pin_small)

    # SCL a Arduino A5
    draw_wire(draw, [
        (lm_x - 15, 1310),
        (920, 1310),
        (920, 630),
        (ard_x + ard_w + 15, 630)
    ], c_i2c_scl, width=3)
    draw.text((930, 970), "I2C SCL → A5", fill=c_i2c_scl, font=f_pin_small)

    # VCC a Arduino 5V
    draw_wire(draw, [
        (lm_x - 15, 1160),
        (840, 1160),
        (840, 700)
    ], c_pwr_5v, width=3)
    draw_junction(draw, (840, 700), c_pwr_5v, r=5)

    # GND y A0,A1,A2 a Tierra Comun
    draw_wire(draw, [
        (lm_x - 15, 1210),
        (825, 1210),
        (825, 950)
    ], c_gnd, width=3)
    draw_junction(draw, (825, 1210), c_gnd, r=5)

    draw_wire(draw, [
        (lm_x - 15, 1360),
        (825, 1360),
        (825, 1210)
    ], c_gnd, width=3)
    draw_junction(draw, (825, 1360), c_gnd, r=5)

    # 9. UNION OBLIGATORIA DE TIERRAS (Arduino GND hacia Riel GND de Servos)
    draw_wire(draw, [
        (ard_x + ard_w + 15, 740),
        (rail_gnd_x, 740)
    ], c_gnd, width=5)
    draw_junction(draw, (rail_gnd_x, 740), c_gnd, r=8)
    draw.text((1600, 715), "LAZO OBLIGATORIO DE TIERRA COMÚN (0V REFERENCIA)", fill="#0f172a", font=f_pin)

    # =========================================================================
    # CUADRO DE LEYENDA Y ESPECIFICACIONES TÉCNICAS
    # =========================================================================
    leg_x, leg_y, leg_w, leg_h = 100, 720, 420, 520
    draw.rectangle([leg_x, leg_y, leg_x + leg_w, leg_y + leg_h], fill="#ffffff", outline="#334155", width=2)
    draw.rectangle([leg_x, leg_y, leg_x + leg_w, leg_y + 36], fill="#1e293b")
    draw.text((leg_x + 14, leg_y + 8), "CÓDIGO DE COLORES & SEÑALES", fill="#38bdf8", font=f_legend)

    legend_items = [
        (c_pwr_ext, "Rojo Intenso (+5V)", "Alimentación Servos (Fuente Externa)"),
        (c_pwr_5v,  "Naranja Rojizo (+5V)", "VCC Sensores lógicos (Arduino 5V)"),
        (c_gnd,     "Negro / Slate (GND)", "Tierra común de referencia (Unificada)"),
        (c_pwm,     "Ámbar / Naranja (PWM)", "Control de Servomotores (D9, D10, D11)"),
        (c_i2c_sda, "Verde Esmeralda (SDA)", "Línea I2C Datos (LM75A hacia A4)"),
        (c_i2c_scl, "Amarillo Oro (SCL)", "Línea I2C Reloj (LM75A hacia A5)"),
        (c_dht_dat, "Morado Púrpura (DAT)", "Datos Sensor Humedad DHT11 (hacia D4)"),
        (c_uart_tx, "Azul Real (UART TX)", "ESP32 GPIO 17 (3.3V) hacia Arduino D2"),
        (c_uart_rx, "Celeste (UART RX)", "Arduino D3 (5V) atenuado a 3.3V (GPIO 16)"),
        (c_led,     "Verde Oscuro (LED)", "Control de luz / relé en Arduino D7"),
    ]
    
    for idx, (col, title, desc) in enumerate(legend_items):
        item_y = leg_y + 55 + idx * 45
        # Muestra de cable
        draw.line([leg_x + 16, item_y + 8, leg_x + 55, item_y + 8], fill=col, width=5)
        draw_junction(draw, (leg_x + 35, item_y + 8), col, r=5)
        draw.text((leg_x + 65, item_y - 4), title, fill="#0f172a", font=f_pin_small)
        draw.text((leg_x + 65, item_y + 14), desc, fill="#64748b", font=f_text)

    # Guardar imagen final de alta resolucion
    img.save(OUTPUT_PNG, "PNG", dpi=(300, 300))
    print(f"[EXITO] Plano eléctrico de conexiones generado: {OUTPUT_PNG} ({OUTPUT_PNG.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    render_schematic()

