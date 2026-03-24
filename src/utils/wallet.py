"""SolScout AI — Solana Wallet Generator

Generates a new Solana keypair for the trading agent.
Uses Ed25519 from the BWS order_sign.py (pure Python, no extra deps).
"""

import os
import sys
import json
import base64
import hashlib
import secrets

def generate_solana_wallet():
    """Generate a new Solana Ed25519 keypair."""
    # Try using BWS's built-in Ed25519
    bws_scripts = os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "bitget-wallet-skill", "scripts")
    sys.path.insert(0, os.path.abspath(bws_scripts))
    
    try:
        from order_sign import Ed25519PrivateKey
        # Generate 32 random bytes as seed
        seed = secrets.token_bytes(32)
        private_key = Ed25519PrivateKey.from_seed(seed)
        public_key = private_key.public_key()
        
        # Solana address is the base58-encoded public key
        pub_bytes = public_key.public_bytes_raw()
        priv_bytes = seed + pub_bytes  # Solana format: 64 bytes (32 seed + 32 pubkey)
        
        address = _base58_encode(pub_bytes)
        private_key_b58 = _base58_encode(priv_bytes)
        
        return {
            "address": address,
            "private_key": private_key_b58,
            "private_key_bytes": list(priv_bytes),
        }
    except Exception as e:
        print(f"BWS Ed25519 failed: {e}")
        print("Falling back to nacl-like generation...")
        # Fallback: use hashlib-based Ed25519 seed
        seed = secrets.token_bytes(32)
        # We can't derive pubkey without Ed25519, so just return seed
        return {
            "address": "GENERATE_WITH_SOLANA_CLI",
            "private_key": base64.b64encode(seed).decode(),
            "note": "Use 'solana-keygen new' for full wallet generation"
        }


# Base58 encoding (Bitcoin/Solana alphabet)
_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _base58_encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    result = []
    while n > 0:
        n, remainder = divmod(n, 58)
        result.append(_B58_ALPHABET[remainder:remainder+1])
    # Handle leading zeros
    for byte in data:
        if byte == 0:
            result.append(b"1")
        else:
            break
    return b"".join(reversed(result)).decode("ascii")


if __name__ == "__main__":
    print("🔑 Generating new Solana wallet for SolScout AI...\n")
    wallet = generate_solana_wallet()
    
    print(f"📍 Address:     {wallet['address']}")
    print(f"🔐 Private Key: {wallet['private_key'][:20]}...{wallet['private_key'][-10:]}")
    print()
    print("Add these to your .env file:")
    print(f"SOLANA_WALLET_ADDRESS={wallet['address']}")
    print(f"SOLANA_PRIVATE_KEY={wallet['private_key']}")
    print()
    print("⚠️  SAVE YOUR PRIVATE KEY SECURELY! Never share or commit it.")
    
    # Also save to a JSON file for backup
    backup_file = os.path.join(os.path.dirname(__file__), "..", "..", "agent-wallet.json")
    with open(backup_file, "w") as f:
        json.dump(wallet.get("private_key_bytes", []), f)
    print(f"\n💾 Keypair saved to agent-wallet.json (add to .gitignore!)")
