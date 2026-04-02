#!/usr/bin/env python3
"""
Social Login Wallet CLI — sign transactions and messages via Bitget Wallet TEE.
Credentials loaded from .social-wallet-secret (same directory as this script).
Dependencies: requests, cryptography
"""
from __future__ import annotations

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

BASE_URL = "https://copenapi.bgwapi.io"
APPID = ""
APPSECRET = ""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_FILE = os.path.join(SCRIPT_DIR, ".social-wallet-secret")

ENDPOINTS = {
    "core": "/social-wallet/agent/core",
    "signMessage": "/social-wallet/agent/signMessage",
    "batchGetAddressAndPubkey": "/social-wallet/agent/batchGetAddressAndPubkey",
    "profile": "/social-wallet/agent/profile",
}


def load_secret():
    global APPID, APPSECRET
    if not os.path.exists(SECRET_FILE):
        return
    try:
        with open(SECRET_FILE, "r") as f:
            data = json.load(f)
        APPID = data.get("appid", "")
        APPSECRET = data.get("appsecret", "")
    except (json.JSONDecodeError, OSError):
        pass


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
    return base64.b64encode(
        hmac_mod.new(bytes.fromhex(APPSECRET), message.encode("utf-8"), hashlib.sha384).digest()
    ).decode("utf-8")


def _gateway_sign(path: str, body_str: str, ts: str) -> str:
    return "0x" + hashlib.sha256(("POST" + path + body_str + ts).encode("utf-8")).hexdigest()


# ── Error Handling ────────────────────────────────────────

def _error_exit(msg: str):
    """Print error to stderr AND structured JSON to stdout, then exit(1).

    This ensures callers that parse stdout with json.loads() always get
    valid JSON instead of an empty string / JSONDecodeError.
    """
    print(f"ERROR: {msg}", file=sys.stderr)
    print(json.dumps({"error": True, "msg": msg}, ensure_ascii=False))
    sys.exit(1)


# ── API Call ──────────────────────────────────────────────

def call_api_return(endpoint: str, param_dict: dict) -> dict:
    """Call API and return decrypted result as dict (importable, no stdout)."""
    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(16)

    param_json = json.dumps(param_dict, separators=(",", ":"), ensure_ascii=False)
    param_encrypted = aes_gcm_encrypt(param_json)
    param_sign = hmac_sha384(f"{param_encrypted}|{timestamp}|{nonce}|{APPID}")

    body = {"param": param_encrypted, "paramSign": param_sign}
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": "toc_agent",
        "X-SIGN": _gateway_sign(endpoint, body_str, timestamp),
        "X-TIMESTAMP": timestamp,
        "x-agent-appid": APPID,
        "x-nonce": nonce,
        "sig": param_sign,
    }

    resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers, data=body_str, timeout=15)
    data = resp.json()

    status = data.get("status", -1)
    if resp.status_code != 200 or status != 0:
        msg = data.get("msg", "unknown")
        raise RuntimeError(f"Social wallet API error [status={status}]: {msg}")

    resp_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    result_encrypted = resp_data.get("result", "")

    if result_encrypted:
        decrypted = aes_gcm_decrypt(result_encrypted)
        try:
            return json.loads(decrypted)
        except json.JSONDecodeError:
            return {"result": decrypted}
    else:
        return data.get("data", data)


def sign_message_return(chain: str, message: str) -> dict:
    """Sign a message via Social Login Wallet TEE. Returns decrypted result dict."""
    load_secret()
    if not APPID or not APPSECRET:
        raise RuntimeError(f"Missing credentials. Create {SECRET_FILE}")
    param = json.dumps({"chain": chain, "message": message}, separators=(",", ":"), ensure_ascii=False)
    return call_api_return(ENDPOINTS["core"], {"operation": "sign_message", "param": param})


def sign_transaction_return(chain: str, tx_params: dict) -> dict:
    """Sign a transaction via Social Login Wallet TEE. Returns decrypted result dict."""
    load_secret()
    if not APPID or not APPSECRET:
        raise RuntimeError(f"Missing credentials. Create {SECRET_FILE}")
    param = json.dumps(tx_params, separators=(",", ":"), ensure_ascii=False)
    return call_api_return(ENDPOINTS["core"], {"operation": "sign_transaction", "param": param})


def call_api(endpoint: str, param_dict: dict) -> dict | None:
    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(16)

    param_json = json.dumps(param_dict, separators=(",", ":"), ensure_ascii=False)
    param_encrypted = aes_gcm_encrypt(param_json)
    param_sign = hmac_sha384(f"{param_encrypted}|{timestamp}|{nonce}|{APPID}")

    body = {"param": param_encrypted, "paramSign": param_sign}
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": "toc_agent",
        "X-SIGN": _gateway_sign(endpoint, body_str, timestamp),
        "X-TIMESTAMP": timestamp,
        "x-agent-appid": APPID,
        "x-nonce": nonce,
        "sig": param_sign,
    }

    try:
        resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers, data=body_str, timeout=15)
    except requests.exceptions.ConnectionError:
        _error_exit(f"Cannot connect to {BASE_URL}")
    except requests.exceptions.RequestException as e:
        _error_exit(str(e))

    try:
        data = resp.json()
    except Exception:
        _error_exit(f"Non-JSON response (HTTP {resp.status_code})")

    status = data.get("status", -1)
    if resp.status_code != 200 or status != 0:
        msg = data.get("msg", "unknown")
        trace = data.get("trace", "")
        print(f"ERROR [status={status}] [trace={trace}] {msg}", file=sys.stderr)
        # Output structured error to stdout so callers parsing JSON get a valid object
        print(json.dumps({"error": True, "status": status, "msg": msg, "trace": trace}, ensure_ascii=False))
        sys.exit(1)

    resp_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    result_encrypted = resp_data.get("result", "")

    if result_encrypted:
        try:
            decrypted = aes_gcm_decrypt(result_encrypted)
            try:
                print(json.dumps(json.loads(decrypted), indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(decrypted)
        except Exception as e:
            _error_exit(f"Decryption failed: {e} [status={data.get('status','')}] [trace={data.get('trace','')}]")
    else:
        print(json.dumps(data.get("data", data), indent=2, ensure_ascii=False))

    return data


# ── Main ──────────────────────────────────────────────────

def main():
    load_secret()

    if not APPID or not APPSECRET:
        print(f"ERROR: Missing credentials. Create {SECRET_FILE} with:", file=sys.stderr)
        print(f'  {{"appid": "bgw_...", "appsecret": "..."}}', file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2 or sys.argv[1] not in ENDPOINTS:
        print(f"Usage: python {sys.argv[0]} <method> [args...]", file=sys.stderr)
        print(f"Methods: {', '.join(ENDPOINTS.keys())}", file=sys.stderr)
        sys.exit(1)

    method = sys.argv[1]
    endpoint = ENDPOINTS[method]
    extra_args = sys.argv[2:]

    if method == "profile":
        # profile takes no business params — send empty dict
        call_api(endpoint, {})
    elif method == "core":
        if len(extra_args) < 2:
            print("Usage: python social-wallet.py core <operation> '<param_json>'", file=sys.stderr)
            sys.exit(1)
        operation = extra_args[0]
        param = json.loads(" ".join(extra_args[1:]))
        if isinstance(param, dict):
            param = json.dumps(param, separators=(",", ":"), ensure_ascii=False)
        call_api(endpoint, {"operation": operation, "param": param})
    else:
        if not extra_args:
            print(f"Usage: python social-wallet.py {method} '<param_json>'", file=sys.stderr)
            sys.exit(1)
        call_api(endpoint, json.loads(" ".join(extra_args)))


if __name__ == "__main__":
    main()
