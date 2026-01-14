"""
Asset Pack Key Storage (Obfuscated)

This module stores the decryption key for the game.sounds pack file.
The key is obfuscated to make casual extraction more difficult.

NOTE: This is NOT cryptographically secure against determined reverse engineering.
It only deters casual browsing of the source code.
"""

import base64
import zlib

# Obfuscated key data (compressed + base64 + reversed + split)
# Do not modify these values
_K1 = "UdShCrQ5gMzxJe"
_K2 = "34yyKYHTPEvTW9"
_K3 = "8NoM3iyRHNuqQr"
_K4 = "==QMKosoAIAdPp"


def _deobfuscate() -> str:
    """Reconstruct the key from obfuscated parts."""
    # Reverse and join
    joined = _K4 + _K3 + _K2 + _K1
    reversed_data = joined[::-1]

    # Base64 decode
    decoded = base64.b64decode(reversed_data)

    # Decompress
    decompressed = zlib.decompress(decoded)

    return decompressed.decode('utf-8')


def get_pack_key() -> str:
    """Get the decryption key for game.sounds.

    Returns:
        The decryption password string
    """
    return _deobfuscate()


# For verification during development only
if __name__ == '__main__':
    print("Key retrieved successfully" if get_pack_key() else "Failed")
