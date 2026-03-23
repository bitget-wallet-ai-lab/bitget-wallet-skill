#!/usr/bin/env python3
"""
Social Login Wallet CLI — sign transactions and messages via Bitget Wallet Agent API.

Credentials are loaded from .social-wallet-secret in the same directory as this script,
or overridden with --appid / --appsecret.

Dependencies: pip install requests cryptography
"""

import argparse
import base64
import hashlib
import hmac as hmac_mod
import json
import os
import secrets
import sys
import time

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

BASE_URL  = "https://copenapi.bgwapi.io"
APPID     = ""
APPSECRET = ""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_FILE = os.path.join(SCRIPT_DIR, ".social-wallet-secret")


def load_secret():
    """Load appid and appsecret from .social-wallet-secret if it exists."""
    global APPID, APPSECRET
    if not os.path.exists(SECRET_FILE):
        return
    try:
        with open(SECRET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        APPID = data.get("appid", "")
        APPSECRET = data.get("appsecret", "")
    except (json.JSONDecodeError, OSError):
        pass


# ── Methods ───────────────────────────────────────────────

METHODS = {
    "core": {
        "endpoint": "/social-wallet/agent/core",
        "desc": "Multi-chain wallet operations (sign_transaction, sign_message, get_address, etc.)",
        "params": {
            "operation": "Operation name (e.g. sign_transaction, sign_message, get_address, validate_address)",
            "param":     "Operation params as JSON object (chain-specific, see chain-reference.md)",
        },
    },
    "signMessage": {
        "endpoint": "/social-wallet/agent/signMessage",
        "desc": "Sign a message",
        "params": {
            "chain":   "Chain name (e.g. eth / btc / trx)",
            "message": "The message to sign",
        },
    },
    "batchGetAddressAndPubkey": {
        "endpoint": "/social-wallet/agent/batchGetAddressAndPubkey",
        "desc": "Batch get addresses and public keys",
        "params": {
            "chainList": 'Chain list, e.g. ["eth","btc","sol"] (max 2000)',
        },
    },
}

# ── Crypto ────────────────────────────────────────────────

def aes_gcm_encrypt(plaintext: str) -> str:
    key = bytes.fromhex(APPSECRET)[:32]
    iv = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return base64.b64encode(ct + iv).decode("utf-8")


def aes_gcm_decrypt(encrypted_b64: str) -> str:
    key = bytes.fromhex(APPSECRET)[:32]
    raw = base64.b64decode(encrypted_b64)
    return AESGCM(key).decrypt(raw[-12:], raw[:-12], None).decode("utf-8")


def hmac_sha384(message: str) -> str:
    digest = hmac_mod.new(
        bytes.fromhex(APPSECRET), message.encode("utf-8"), hashlib.sha384,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


# ── API Call ──────────────────────────────────────────────

def _gateway_sign(method: str, path: str, body_str: str, ts: str) -> str:
    """BKHmacAuth signature: SHA256(Method + Path + Body + Timestamp)."""
    message = method + path + body_str + ts
    return "0x" + hashlib.sha256(message.encode("utf-8")).hexdigest()


def call_api(endpoint: str, param_dict: dict) -> dict | None:
    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(16)

    param_json = json.dumps(param_dict, separators=(",", ":"), ensure_ascii=False)
    param_encrypted = aes_gcm_encrypt(param_json)

    sign_message = f"{param_encrypted}|{timestamp}|{nonce}|{APPID}"
    param_sign = hmac_sha384(sign_message)

    body = {"param": param_encrypted, "paramSign": param_sign}
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    gateway_sign = _gateway_sign("POST", endpoint, body_str, timestamp)

    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": "toc_agent",
        "X-SIGN": gateway_sign,
        "X-TIMESTAMP": timestamp,
        "x-agent-appid": APPID,
        "x-nonce": nonce,
        "sig": param_sign,
    }

    try:
        resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers, data=body_str, timeout=15)
    except requests.exceptions.ConnectionError:
        print(f"{RED}ERROR: Cannot connect to {BASE_URL}{RESET}", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"{RED}ERROR: {e}{RESET}", file=sys.stderr)
        return None

    try:
        data = resp.json()
    except Exception:
        print(f"{RED}ERROR: Non-JSON response (HTTP {resp.status_code}){RESET}", file=sys.stderr)
        return None

    status = data.get("status", -1)
    trace = data.get("trace", "")
    if resp.status_code != 200 or status != 0:
        msg = data.get("msg", "unknown error")
        print(f"{RED}ERROR [status={status}] [trace={trace}] {msg}{RESET}", file=sys.stderr)
        return data

    resp_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    result_encrypted = resp_data.get("result", "")

    if result_encrypted:
        try:
            decrypted = aes_gcm_decrypt(result_encrypted)
            try:
                parsed = json.loads(decrypted)
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(decrypted)
        except Exception as e:
            print(f"{RED}Decryption failed: {e}{RESET}", file=sys.stderr)
            print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data.get("data", data), indent=2, ensure_ascii=False))

    return data


# ── Dispatch ──────────────────────────────────────────────

def parse_json_arg(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"{RED}ERROR: JSON parse failed{RESET}", file=sys.stderr)
        print(f"{YELLOW}Hint: wrap JSON params in single quotes{RESET}", file=sys.stderr)
        sys.exit(1)


def dispatch(method: str, extra_args: list[str]):
    meta = METHODS[method]
    endpoint = meta["endpoint"]

    if method == "core":
        if len(extra_args) < 2:
            print(f"{RED}ERROR: core requires <operation> and <param_json>{RESET}", file=sys.stderr)
            print(f"  Usage: python social-wallet.py core <operation> '<param_json>'", file=sys.stderr)
            sys.exit(1)
        operation = extra_args[0]
        param = parse_json_arg(" ".join(extra_args[1:]))
        if isinstance(param, dict):
            param = json.dumps(param, separators=(",", ":"), ensure_ascii=False)
        call_api(endpoint, {"operation": operation, "param": param})
    else:
        if not extra_args:
            print(f"{RED}ERROR: missing params{RESET}", file=sys.stderr)
            print(f"  Usage: python social-wallet.py {method} '<param_json>'", file=sys.stderr)
            sys.exit(1)
        user_params = parse_json_arg(" ".join(extra_args))
        call_api(endpoint, user_params)


# ── --list ────────────────────────────────────────────────

def print_method_list():
    print(f"\n{BOLD}Available methods:{RESET}\n")
    for name, meta in METHODS.items():
        print(f"  {GREEN}{name}{RESET}  — {meta['desc']}")
        print(f"    endpoint: {meta['endpoint']}")
        print(f"    params:")
        for k, v in meta["params"].items():
            print(f"      {k:20s} {v}")
        print()


# ── CLI ───────────────────────────────────────────────────

def main():
    load_secret()

    parser = argparse.ArgumentParser(
        description="Social Login Wallet CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python social-wallet.py --list
  python social-wallet.py core sign_transaction '{"chain":"eth","to":"0x...","value":0.1,"nonce":0,"gasLimit":21000,"gasPrice":0.0000001}'
  python social-wallet.py core get_address '{"chain":"eth"}'
  python social-wallet.py signMessage '{"chain":"eth","message":"hello"}'
  python social-wallet.py batchGetAddressAndPubkey '{"chainList":["eth","btc","sol"]}'

Note: JSON params must be wrapped in single quotes.
Credentials are loaded from .social-wallet-secret in the script directory.
        """,
    )
    parser.add_argument("method", nargs="?", choices=list(METHODS.keys()), help="Method to call")
    parser.add_argument("args", nargs="*", default=[], help="Args (core: operation param_json; others: param_json)")
    parser.add_argument("--list", action="store_true", help="List all available methods")
    parser.add_argument("--url", default=None, help="Override BASE_URL")
    parser.add_argument("--appid", default=None, help="Override APPID")
    parser.add_argument("--appsecret", default=None, help="Override APPSECRET")

    args = parser.parse_args()

    if args.list:
        print_method_list()
        return

    if not args.method:
        parser.print_help()
        return

    global BASE_URL, APPID, APPSECRET
    if args.url:
        BASE_URL = args.url.rstrip("/")
    if args.appid:
        APPID = args.appid
    if args.appsecret:
        APPSECRET = args.appsecret

    if not APPID or not APPSECRET:
        print(f"{RED}ERROR: Missing credentials.{RESET}", file=sys.stderr)
        print(f"Create {SECRET_FILE} with:", file=sys.stderr)
        print(f'  {{"appid": "bgw_...", "appsecret": "..."}}', file=sys.stderr)
        print(f"Or use --appid and --appsecret flags.", file=sys.stderr)
        sys.exit(1)

    if not APPID.startswith("bgw_") or len(APPID) != 36:
        print(f"{YELLOW}WARNING: APPID format looks wrong{RESET}", file=sys.stderr)
    if len(APPSECRET) != 96:
        print(f"{YELLOW}WARNING: APPSECRET length should be 96 hex chars{RESET}", file=sys.stderr)

    dispatch(args.method, args.args)


if __name__ == "__main__":
    main()
