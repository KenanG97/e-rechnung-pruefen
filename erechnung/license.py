"""Server-lose Pro-Lizenzschlüssel (HMAC-signiert).

Vorteil: Kein Lizenzserver, keine Datenbank, keine Kosten. Sie erzeugen Schlüssel lokal
(`python -m erechnung.license neu kunde@firma.de 2027-12-31`) und verschicken sie nach
Zahlungseingang (z. B. automatisch über Lemon Squeezy/Digistore/Stripe-Payment-Link).
Das Secret liegt nur in den Streamlit-Secrets bzw. der Umgebungsvariable LICENSE_SECRET.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys
from datetime import date


def _secret() -> bytes:
    s = os.environ.get("LICENSE_SECRET", "")
    if not s:
        try:
            import streamlit as st
            s = st.secrets.get("LICENSE_SECRET", "")
        except Exception:
            s = ""
    return s.encode()


def make_key(email: str, valid_until: str, secret: bytes | None = None) -> str:
    payload = f"{email.strip().lower()}|{valid_until}".encode()
    sig = hmac.new(secret or _secret(), payload, hashlib.sha256).digest()[:12]
    return base64.urlsafe_b64encode(payload + b"|" + sig).decode().rstrip("=")


def verify_key(key: str, today: date | None = None, secret: bytes | None = None) -> tuple[bool, str]:
    sec = secret or _secret()
    if not sec:
        return False, "Pro-Modus ist auf diesem Server nicht eingerichtet."
    try:
        raw = base64.urlsafe_b64decode(key.strip() + "=" * (-len(key.strip()) % 4))
        email, until, sig = raw.split(b"|", 2)
    except Exception:
        return False, "Ungültiger Schlüssel."
    exp = hmac.new(sec, email + b"|" + until, hashlib.sha256).digest()[:12]
    if not hmac.compare_digest(exp, sig):
        return False, "Ungültiger Schlüssel."
    if date.fromisoformat(until.decode()) < (today or date.today()):
        return False, f"Schlüssel ist am {until.decode()} abgelaufen."
    return True, email.decode()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "neu":
        print(make_key(sys.argv[2], sys.argv[3]))
    else:
        print("Aufruf: LICENSE_SECRET=... python -m erechnung.license neu <email> <JJJJ-MM-TT>")
