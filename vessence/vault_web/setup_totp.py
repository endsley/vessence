#!/usr/bin/env python3
"""setup_totp.py — Display the TOTP QR code for adding Amber Vault to an authenticator app.

Run once, scan with Google Authenticator / Authy / 1Password / etc.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH

load_dotenv(ENV_FILE_PATH)

import pyotp
import qrcode

SECRET = os.getenv("VAULT_TOTP_SECRET", "")
if not SECRET:
    print("ERROR: VAULT_TOTP_SECRET not set in .env")
    sys.exit(1)

totp = pyotp.TOTP(SECRET)
uri = totp.provisioning_uri(name=os.environ.get("USER_NAME", "Vault"), issuer_name="Amber Vault")

print("\n=== Amber Vault — TOTP Setup ===\n")
print(f"Secret (manual entry): {SECRET}\n")
print("Scan this QR code with Google Authenticator, Authy, or 1Password:\n")

qr = qrcode.QRCode(border=1)
qr.add_data(uri)
qr.make(fit=True)
qr.print_ascii(invert=True)

print(f"\nOr add manually:")
print(f"  Account: {os.environ.get('USER_NAME', 'Vault')}")
print(f"  Issuer:  Amber Vault")
print(f"  Secret:  {SECRET}")
print(f"  Type:    Time-based (TOTP)\n")

# Verify immediately
code = input("Enter the 6-digit code from your app to confirm setup: ").strip()
if totp.verify(code, valid_window=1):
    print("✓ Setup confirmed! TOTP is working correctly.")
else:
    print("✗ Code incorrect. Check time sync or try again.")
    sys.exit(1)
