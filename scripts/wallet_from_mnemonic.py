#!/usr/bin/env python3
"""
Derive multi-chain addresses and private keys (EVM / Solana / Tron) from a mnemonic.
Used by wallet_cli.py (derive-addresses: outputs only addresses) and order_make_sign_send.py
(derives keys in memory for signing; never outputs mnemonic or keys).
Never output mnemonic or private keys to stdout; addresses-only output is for agent context.
"""

import hashlib
import json
import sys
from pathlib import Path

try:
    from eth_account import Account
except ImportError:
    print("Error: missing dependency", file=sys.stderr)
    print("Run: pip install eth-account", file=sys.stderr)
    sys.exit(1)

# Enable HD wallet
Account.enable_unaudited_hdwallet_features()

# Solana / Tron derivation requires bip_utils (optional, for create/import)
def _has_bip_utils():
    try:
        import bip_utils  # noqa: F401
        return True
    except ImportError:
        return False


def _tron_base58check_encode(payload: bytes) -> str:
    """Encode Tron address with Base58Check (same alphabet as Bitcoin)."""
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    data = payload + checksum
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    result = []
    while n > 0:
        n, r = divmod(n, 58)
        result.append(alphabet[r])
    for byte in data:
        if byte == 0:
            result.append("1")
        else:
            break
    return "".join(reversed(result))


def derive_wallets_from_mnemonic(mnemonic: str) -> dict:
    """
    Derive EVM, Solana, and Tron wallets from a mnemonic.
    Returns:
      evm:  { address, private_key }
      sol:  { address, private_key }   # private_key is 32-byte seed as hex
      tron: { address, private_key }
    """
    mnemonic = mnemonic.strip()
    result = {}

    # EVM (BIP44: m/44'/60'/0'/0/0)
    evm_account = Account.from_mnemonic(mnemonic, account_path="m/44'/60'/0'/0/0")
    result["evm"] = {
        "address": evm_account.address,
        "private_key": evm_account.key.hex(),
    }

    if _has_bip_utils():
        from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
        from bip_utils.addr import SolAddrEncoder

        seed = Bip39SeedGenerator(mnemonic).Generate()
        # BIP44 change: 0 = external (some bip_utils versions need Bip44Changes.CHAIN_EXT)
        try:
            from bip_utils.bip.bip44_base.bip44_base import Bip44Changes
            _change = Bip44Changes.CHAIN_EXT
        except (ImportError, AttributeError):
            _change = 0

        # Solana (BIP44: m/44'/501'/0'/0')
        bip_sol = Bip44.FromSeed(seed, Bip44Coins.SOLANA)
        bip_sol = bip_sol.Purpose().Coin().Account(0).Change(_change).AddressIndex(0)
        sol_pk_bytes = bip_sol.PrivateKey().Raw().ToBytes()
        sol_pub = bip_sol.PublicKey().RawCompressed().ToBytes()
        # Solana address is Base58-encoded public key
        sol_address = SolAddrEncoder.EncodeKey(sol_pub[1:] if len(sol_pub) == 33 else sol_pub)
        result["sol"] = {
            "address": sol_address,
            "private_key": sol_pk_bytes.hex(),
        }

        # Tron (BIP44: m/44'/195'/0'/0/0)
        bip_trx = Bip44.FromSeed(seed, Bip44Coins.TRON)
        bip_trx = bip_trx.Purpose().Coin().Account(0).Change(_change).AddressIndex(0)
        tron_address = bip_trx.PublicKey().ToAddress()
        tron_pk = bip_trx.PrivateKey().Raw().ToBytes()
        result["tron"] = {
            "address": tron_address,
            "private_key": tron_pk.hex(),
        }
    else:
        # No bip_utils: Tron only via eth_account + custom Tron address
        tron_account = Account.from_mnemonic(mnemonic, account_path="m/44'/195'/0'/0/0")
        # Tron address = Base58Check(0x41 + keccak256(pubkey)[12:32]), same as ETH
        addr_20 = bytes.fromhex(tron_account.address[2:])
        tron_payload = bytes([0x41]) + addr_20
        result["tron"] = {
            "address": _tron_base58check_encode(tron_payload),
            "private_key": tron_account.key.hex(),
        }
        # Solana cannot be derived; leave empty and prompt to install bip_utils
        result["sol"] = {
            "address": "",
            "private_key": "",
        }

    return result


def generate_mnemonic(strength: int = 256) -> str:
    """Generate BIP-39 mnemonic; default 24 words (256 bits)."""
    if _has_bip_utils():
        from bip_utils import Bip39MnemonicGenerator, Bip39WordsNum
        word_num = Bip39WordsNum.WORDS_NUM_24 if strength == 256 else Bip39WordsNum.WORDS_NUM_12
        return Bip39MnemonicGenerator().FromWordsNumber(word_num)
    try:
        from mnemonic import Mnemonic
        mnemo = Mnemonic("english")
        return mnemo.generate(strength=256 if strength == 256 else 128)
    except ImportError:
        raise RuntimeError("Install bip_utils or mnemonic to generate mnemonic: pip install bip_utils")


def main():
    """Read mnemonic from file and output only addresses as JSON (no mnemonic, no private keys). Prefer: wallet_cli.py --mnemonic-file <path>."""
    import argparse
    parser = argparse.ArgumentParser(description="Derive addresses from mnemonic file (outputs only addresses).")
    parser.add_argument("--mnemonic-file", default=None, help="Path to mnemonic file (default: mnemonic.txt in cwd or project root)")
    args = parser.parse_args()
    if args.mnemonic_file:
        mnemonic_file = Path(args.mnemonic_file).expanduser().resolve()
    else:
        mnemonic_file = Path("mnemonic.txt")
        if not mnemonic_file.exists():
            mnemonic_file = Path(__file__).parent.parent / "mnemonic.txt"
    if not mnemonic_file.exists():
        print("Error: mnemonic file not found. Use --mnemonic-file <path> or create mnemonic.txt", file=sys.stderr)
        sys.exit(1)
    mnemonic = mnemonic_file.read_text(encoding="utf-8").strip()
    words = mnemonic.split()
    if len(words) not in [12, 15, 18, 21, 24]:
        print(f"Error: mnemonic must be 12/15/18/21/24 words, got {len(words)}", file=sys.stderr)
        sys.exit(1)
    wallets = derive_wallets_from_mnemonic(mnemonic)
    out = {
        "evm_address": wallets["evm"]["address"],
        "solana_address": wallets.get("sol", {}).get("address", ""),
        "tron_address": wallets["tron"]["address"],
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
