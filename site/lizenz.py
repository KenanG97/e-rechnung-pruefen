"""Lizenzschlüssel für die Browser-Version erzeugen (ECDSA P-256).

Einmalig:   python site/lizenz.py init        -> erzeugt site/lizenz_privat.pem (GEHEIM, nicht committen!)
                                               und schreibt den öffentlichen Schlüssel in site/config.json
Pro Kunde:  python site/lizenz.py neu kanzlei@beispiel.de 2027-12-31

Der Browser prüft die Signatur mit dem öffentlichen Schlüssel. Ehrliche Einordnung: Wer den
JavaScript-Code manipuliert, kann jede clientseitige Sperre umgehen. Für ein günstiges B2B-Tool
ist das akzeptabel – Firmen zahlen für Rechnung, Support und ein gutes Gewissen.
"""
import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

HERE = Path(__file__).parent
PRIV = HERE / "lizenz_privat.pem"
CFG = HERE / "config.json"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def init():
    if PRIV.exists():
        sys.exit("lizenz_privat.pem existiert bereits – nicht überschreiben (sonst werden alle Lizenzen ungültig).")
    key = ec.generate_private_key(ec.SECP256R1())
    PRIV.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    pub = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    cfg = json.loads(CFG.read_text())
    cfg["license_public_key"] = base64.b64encode(pub).decode()
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    print("Schlüsselpaar erzeugt. lizenz_privat.pem sicher aufbewahren und NICHT veröffentlichen.")


def sign(email: str, until: str, key=None) -> str:
    key = key or serialization.load_pem_private_key(PRIV.read_bytes(), None)
    payload = f"{email.strip().lower()}|{until}".encode()
    r, s = decode_dss_signature(key.sign(payload, ec.ECDSA(hashes.SHA256())))
    return b64u(payload) + "." + b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


if __name__ == "__main__":
    if sys.argv[1:2] == ["init"]:
        init()
    elif len(sys.argv) == 4 and sys.argv[1] == "neu":
        print(sign(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
