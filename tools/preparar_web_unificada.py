"""Prepara certificados locales y el modelo español; no instala raíces de confianza."""
import argparse
import datetime as dt
import ipaddress
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / 'server_pc/certs'
MODEL_URL = 'https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip'

def certificates(ip):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    ipaddress.ip_address(ip)
    CERTS.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    ca_key_file = CERTS / 'ca-key.pem'
    ca_file = CERTS / 'asistente-ca.crt'
    def save_key(key, path):
        path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    if ca_key_file.exists():
        ca_key = serialization.load_pem_private_key(ca_key_file.read_bytes(), password=None)
        ca = x509.load_pem_x509_certificate(ca_file.read_bytes())
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Asistente ESP32 - CA local de Juank')])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(days=1))
              .not_valid_after(now+dt.timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
              .sign(ca_key, hashes.SHA256()))
        save_key(ca_key, ca_key_file)
        ca_file.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sans = [x509.IPAddress(ipaddress.ip_address(ip)), x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
            x509.DNSName('localhost'), x509.DNSName('asistente.local')]
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Asistente local')]))
            .issuer_name(ca.subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-dt.timedelta(days=1)).not_valid_after(now+dt.timedelta(days=180))
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .sign(ca_key, hashes.SHA256()))
    save_key(server_key, CERTS / 'server-key.pem')
    (CERTS / 'server.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    fingerprint = ca.fingerprint(hashes.SHA256()).hex(':').upper()
    (CERTS / 'metadata.json').write_text(json.dumps({'ip': ip, 'fingerprint': fingerprint}), encoding='utf-8')
    return fingerprint

def download_model():
    folder = ROOT / 'server_pc/models'
    if (folder / 'vosk-model-small-es-0.42/am/final.mdl').exists():
        return
    folder.mkdir(parents=True, exist_ok=True)
    archive = ROOT / 'build/vosk-model-small-es-0.42.zip'
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        urllib.request.urlretrieve(MODEL_URL, archive)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            target = (folder / item.filename).resolve()
            if not target.is_relative_to(folder.resolve()):
                raise ValueError('Ruta inválida en el modelo descargado')
        source.extractall(folder)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', default='192.168.4.2')
    parser.add_argument('--download-model', action='store_true')
    args = parser.parse_args()
    if args.download_model:
        download_model()
    print('SHA256 CA:', certificates(args.ip))
