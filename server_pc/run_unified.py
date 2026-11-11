"""Una web HTTPS sobre el Wi-Fi del ESP32. Sin túneles públicos."""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent / 'tools'))
from preparar_web_unificada import certificates, CERTS

def connect_esp32_wifi():
    if sys.platform != 'win32':
        return
    profile = 'Animatronico-Asistente-ESP32'
    config = BASE.parent / 'build/esp32-wifi.xml'
    config.parent.mkdir(exist_ok=True)
    config.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"><name>{profile}</name>
<SSIDConfig><SSID><name>Asistente-ESP32</name></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>manual</connectionMode>
<MSM><security><authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption>
<sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>arquitectura123</keyMaterial></sharedKey></security></MSM></WLANProfile>''', encoding='utf-8')
    subprocess.run(['netsh', 'wlan', 'add', 'profile', f'filename={config}', 'user=current'], check=True,
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    subprocess.run(['netsh', 'wlan', 'connect', f'name={profile}', 'ssid=Asistente-ESP32'], check=True,
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(20):
        try:
            esp32_ip()
            return
        except RuntimeError:
            time.sleep(0.5)
    raise RuntimeError('No se pudo conectar a Asistente-ESP32. Revisa que la placa esté encendida.')

def esp32_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.connect(('192.168.4.1', 80))
        ip = connection.getsockname()[0]
    if not ip.startswith('192.168.4.') or ip == '192.168.4.1':
        raise RuntimeError('Conecta primero esta computadora a la red Asistente-ESP32.')
    return ip

def setup_app(ip, fingerprint):
    setup = FastAPI()
    @setup.get('/certificado.crt')
    def certificate():
        return FileResponse(CERTS / 'asistente-ca.crt', media_type='application/x-x509-ca-cert', filename='asistente-ca.crt')
    @setup.get('/')
    @setup.get('/setup', response_class=HTMLResponse)
    def instructions():
        metadata = CERTS / 'metadata.json'
        current_ip = json.loads(metadata.read_text(encoding='utf-8'))['ip'] if metadata.exists() else ip
        return HTMLResponse(f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar el micrófono del celular</title><style>body{{font:17px system-ui;background:#080a0f;color:#f1f5f9;max-width:700px;margin:40px auto;padding:24px;line-height:1.6}}a{{color:#38bdf8}}code{{overflow-wrap:anywhere}}</style>
<h1>Micrófono seguro en tu red</h1><p>Conecta el celular a <b>Asistente-ESP32</b>. Instala este certificado local una sola vez para confiar en la web de tu computadora.</p>
<p><a href="/certificado.crt">Descargar certificado del asistente</a></p>
<p>Android: Ajustes → Seguridad → Cifrado y credenciales → Instalar certificado → Certificado de CA. La ruta puede variar según la marca.</p>
<p>iPhone: instala el perfil descargado desde Ajustes → General → VPN y gestión de dispositivos. Luego activa su confianza en General → Información → Ajustes de confianza de certificados.</p>
<p>Comprueba que la huella SHA256 coincida con la consola de la computadora:</p><code>{fingerprint}</code>
<p>Esta CA permite a quien posea su clave firmar certificados que tu celular confiará. Su clave queda solo en server_pc/certs de esta computadora; no se publica.</p>
<p>Después de instalar y confiar en el certificado, abre:</p><p><a href="https://{current_ip}:8443">Abrir asistente, visión y controles</a></p>
<p>Si aparece una advertencia, completa la instalación de confianza; no continúes saltando la advertencia. Al dejar de usar el proyecto puedes retirar esta CA en los ajustes del celular.</p></html>''')
    return setup

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip')
    parser.add_argument('--connect-wifi', action='store_true')
    parser.add_argument('--service', action='store_true')
    args = parser.parse_args()
    os.environ['ANIMATRONICO_LOCAL_NETWORK'] = '1'
    if args.service:
        log = BASE.parent / 'build/unified-service.log'
        log.parent.mkdir(exist_ok=True)
        sys.stdout = sys.stderr = log.open('a', encoding='utf-8', buffering=1)
    if args.connect_wifi:
        try:
            connect_esp32_wifi()
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            print(f'[Red] Conexión inicial pendiente: {exc}', flush=True)
    try:
        ip = args.ip or esp32_ip()
    except (RuntimeError, OSError):
        metadata = CERTS / 'metadata.json'
        ip = json.loads(metadata.read_text(encoding='utf-8'))['ip'] if metadata.exists() else '192.168.4.2'
        print(f'[Red] Servidor disponible; esperando el Wi-Fi del ESP32 para publicar {ip}.', flush=True)
    fingerprint = certificates(ip)
    url = f'https://{ip}:8443'
    session = requests.Session()
    session.trust_env = False
    from app import app
    tls_config = uvicorn.Config(app, host='0.0.0.0', port=8443,
                                ssl_keyfile=str(CERTS/'server-key.pem'), ssl_certfile=str(CERTS/'server.pem'),
                                log_level='info')
    tls_config.load()
    def register():
        nonlocal ip, url
        while True:
            try:
                if args.connect_wifi:
                    try:
                        current_ip = esp32_ip()
                    except RuntimeError:
                        print('[Red] Se perdió el Wi-Fi del ESP32; reconectando para mantener el acceso del celular.', flush=True)
                        connect_esp32_wifi()
                        current_ip = esp32_ip()
                    if current_ip != ip:
                        certificates(current_ip)
                        tls_config.ssl.load_cert_chain(str(CERTS/'server.pem'), str(CERTS/'server-key.pem'))
                        ip = current_ip
                        url = f'https://{ip}:8443'
                        print(f'[Red] IP actualizada; certificado y enlaces listos en {url}.', flush=True)
                session.post('http://192.168.4.1/api/assistant', data={'url': url}, timeout=2).raise_for_status()
                network = session.get('http://192.168.4.1/api/network', timeout=2)
                if network.ok:
                    os.environ['ANIMATRONICO_INTERNET_SHARED'] = '1' if network.json().get('shared') else '0'
            except (requests.RequestException, RuntimeError, subprocess.SubprocessError, OSError) as exc:
                print(f'[Red] No se pudo registrar el asistente: {exc}', flush=True)
            time.sleep(10)
    threading.Thread(target=register, daemon=True).start()
    # El mismo objeto app, sin un segundo lifespan ni un segundo puerto serie.
    # Loopback es contexto seguro para la cámara y el micrófono de la PC.
    threading.Thread(target=lambda: uvicorn.run(app, host='127.0.0.1', port=8002, lifespan='off',
                                               log_level='warning'), daemon=True).start()
    threading.Thread(target=lambda: uvicorn.run(setup_app(ip, fingerprint), host='0.0.0.0', port=8001,
                                               log_level='warning'), daemon=True).start()
    print(f'Web unificada: {url}\nConfigurar celular: http://{ip}:8001/setup\nSHA256 CA: {fingerprint}', flush=True)
    uvicorn.Server(tls_config).run()

if __name__ == '__main__':
    main()
