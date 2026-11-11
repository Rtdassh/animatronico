"""Configura el Wi-Fi por USB, sin imprimir ni guardar la contraseña en archivos."""
import argparse
import getpass
import json
import re
import subprocess
import time
import serial

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM8')
    parser.add_argument('--windows-profile', help='Usar una clave guardada; requiere autorización explícita del usuario.')
    parser.add_argument('--ssid')
    args = parser.parse_args()
    if args.windows_profile:
        result = subprocess.run(['netsh', 'wlan', 'show', 'profile', f'name={args.windows_profile}', 'key=clear'],
                                capture_output=True, check=True)
        text = result.stdout.decode('cp850', errors='replace')
        match = re.search(r'^\s*(?:Key Content|Contenido de la clave)\s*:\s*(.+)$', text, re.M)
        if not match:
            raise RuntimeError('Windows no entregó una clave guardada para ese perfil.')
        password = match.group(1).rstrip('\r')
        ssid = args.ssid or args.windows_profile
        del text, result, match
    else:
        ssid = args.ssid or input('Nombre de la red Wi-Fi: ')
        password = getpass.getpass('Contraseña Wi-Fi (no se muestra): ')
    if any(c in ssid + password for c in '\r\n\t') or len(ssid.encode()) > 32 or len(password.encode()) > 63:
        raise ValueError('Nombre o contraseña fuera del formato admitido por Wi-Fi.')
    with serial.Serial(port=None, baudrate=115200, timeout=0.3) as connection:
        connection.port = args.port
        connection.dtr = False
        connection.rts = False
        connection.open()
        connection.reset_input_buffer()
        connection.write(('WIFI_CONFIG:' + ssid + '\t' + password + '\n').encode())
        del password
        deadline = time.monotonic() + 45
        last_query = 0
        configured = False
        while time.monotonic() < deadline:
            if time.monotonic() - last_query > 2:
                connection.write(b'NET_STATUS\n')
                last_query = time.monotonic()
            line = connection.readline().decode(errors='replace').strip()
            if line == 'WIFI_CONFIG_OK':
                configured = True
            if line.startswith('{"stationConnected":'):
                network = json.loads(line)
                if network.get('stationConnected') and network.get('shared'):
                    print(json.dumps({'configured': configured, **network}, indent=2), flush=True)
                    return
        raise RuntimeError('No se confirmó la conexión y NAPT. Revisa señal y credenciales; la clave no se imprimió.')

if __name__ == '__main__':
    main()
