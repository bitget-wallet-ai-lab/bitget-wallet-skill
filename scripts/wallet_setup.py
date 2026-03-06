#!/usr/bin/env python3
"""
Wallet setup and key derivation for Bitget Wallet Skill.

Commands:
  generate                        Generate a new BIP-39 mnemonic (24 words)
  derive --mnemonic <words>       Derive EVM + Solana keys, print addresses (keys NOT printed)
  derive-key --mnemonic <words> --chain <evm|sol>
                                  Derive and print a single chain's private key (for piping to order_sign.py)

Security model:
  - Mnemonic stored in 1Password (only persistent secret)
  - Private keys derived on-the-fly, used, then discarded
  - Keys never written to disk or stored persistently

Derivation paths:
  EVM:    m/44'/60'/0'/0/0   (secp256k1)
  Solana: m/44'/501'/0'/0'   (Ed25519, SLIP-0010)
"""

import argparse
import hashlib
import hmac
import json
import struct
import sys


def generate_mnemonic(strength: int = 256) -> str:
    """Generate a BIP-39 mnemonic (24 words for 256-bit, 12 words for 128-bit)."""
    from mnemonic import Mnemonic
    m = Mnemonic("english")
    return m.generate(strength)


def _bip39_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """Convert mnemonic to BIP-39 seed (512 bits)."""
    from mnemonic import Mnemonic
    m = Mnemonic("english")
    if not m.check(mnemonic):
        raise ValueError("Invalid mnemonic")
    return m.to_seed(mnemonic, passphrase)


def derive_evm(mnemonic: str) -> dict:
    """
    Derive EVM private key and address from mnemonic.
    Path: m/44'/60'/0'/0/0
    """
    from eth_account import Account
    Account.enable_unaudited_hdwallet_features()
    acct = Account.from_mnemonic(mnemonic)
    return {
        "chain": "evm",
        "path": "m/44'/60'/0'/0/0",
        "address": acct.address,
        "private_key": acct.key.hex(),
    }


def derive_solana(mnemonic: str) -> dict:
    """
    Derive Solana private key and address from mnemonic.
    Path: m/44'/501'/0'/0' (SLIP-0010 Ed25519)
    """
    from solders.keypair import Keypair

    seed = _bip39_seed(mnemonic)

    # SLIP-0010: Ed25519 master key
    I = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    key, chain = I[:32], I[32:]

    # Derive m/44'/501'/0'/0' (all hardened)
    for index in [
        44 | 0x80000000,
        501 | 0x80000000,
        0 | 0x80000000,
        0 | 0x80000000,
    ]:
        data = b"\x00" + key + struct.pack(">I", index)
        I = hmac.new(chain, data, hashlib.sha512).digest()
        key, chain = I[:32], I[32:]

    kp = Keypair.from_seed(key)
    return {
        "chain": "sol",
        "path": "m/44'/501'/0'/0'",
        "address": str(kp.pubkey()),
        "private_key": key.hex(),
    }


def derive_all(mnemonic: str) -> list[dict]:
    """Derive keys for all supported chains."""
    return [derive_evm(mnemonic), derive_solana(mnemonic)]


def main():
    parser = argparse.ArgumentParser(description="Wallet setup and key derivation")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate a new BIP-39 mnemonic")
    gen.add_argument("--words", type=int, choices=[12, 24], default=24,
                     help="Word count (12 or 24, default: 24)")

    # derive (addresses only, for setup verification)
    der = sub.add_parser("derive", help="Derive addresses from mnemonic (no keys printed)")
    der.add_argument("--mnemonic", required=True, help="BIP-39 mnemonic phrase")

    # derive-key (single chain key, for signing pipeline)
    dk = sub.add_parser("derive-key", help="Derive private key for one chain (stdout)")
    dk.add_argument("--mnemonic", required=True, help="BIP-39 mnemonic phrase")
    dk.add_argument("--chain", required=True, choices=["evm", "sol"],
                    help="Chain to derive key for")

    args = parser.parse_args()

    if args.command == "generate":
        strength = 256 if args.words == 24 else 128
        mnemonic = generate_mnemonic(strength)
        print(mnemonic)

    elif args.command == "derive":
        results = derive_all(args.mnemonic)
        # Print addresses only, never keys
        output = []
        for r in results:
            output.append({
                "chain": r["chain"],
                "path": r["path"],
                "address": r["address"],
            })
        print(json.dumps(output, indent=2))

    elif args.command == "derive-key":
        if args.chain == "evm":
            result = derive_evm(args.mnemonic)
        else:
            result = derive_solana(args.mnemonic)
        # Print only the private key (for piping)
        print(result["private_key"])


if __name__ == "__main__":
    main()
