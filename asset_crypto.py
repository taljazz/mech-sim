"""
Encrypted Asset Pack System for MechSimulator

This module provides strong encryption for game audio assets using:
- AES-256-GCM (authenticated encryption with associated data)
- PBKDF2-SHA256 key derivation (600,000 iterations)
- Random salt and nonce per pack
- Zlib compression before encryption
- Custom binary format

Usage:
    # Packing (run once, offline):
    python asset_crypto.py pack

    # Loading (runtime):
    from asset_crypto import AssetPack
    pack = AssetPack('sounds.dat')
    pack.open('your-secret-key')
    audio_bytes = pack.get('Movement/footsteps_001.wav')
"""

import os
import sys
import zlib
import struct
import hashlib
import secrets
import json
from typing import Dict, Optional, BinaryIO
from pathlib import Path

# Use cryptography library for strong encryption
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("WARNING: 'cryptography' package not installed.")
    print("Install with: pip install cryptography")


# =============================================================================
# Configuration
# =============================================================================

# File format magic bytes (obscured, not obvious)
MAGIC = b'\x89SND\r\n\x1a\n'  # Similar to PNG magic but different
VERSION = 2

# Encryption parameters
SALT_SIZE = 32          # 256-bit salt
NONCE_SIZE = 12         # 96-bit nonce for AES-GCM
KEY_SIZE = 32           # 256-bit key (AES-256)
KDF_ITERATIONS = 600000 # OWASP 2023 recommendation for PBKDF2-SHA256

# Compression level (0-9, higher = smaller but slower)
COMPRESSION_LEVEL = 6


# =============================================================================
# Key Derivation
# =============================================================================

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit encryption key from password using PBKDF2.

    Args:
        password: User-provided password/passphrase
        salt: Random salt bytes

    Returns:
        32-byte derived key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))


# =============================================================================
# Encryption/Decryption
# =============================================================================

def encrypt_data(data: bytes, key: bytes) -> tuple:
    """Encrypt data using AES-256-GCM.

    Args:
        data: Plaintext bytes to encrypt
        key: 32-byte encryption key

    Returns:
        Tuple of (nonce, ciphertext) where ciphertext includes auth tag
    """
    nonce = secrets.token_bytes(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce, ciphertext


def decrypt_data(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-256-GCM.

    Args:
        nonce: 12-byte nonce used during encryption
        ciphertext: Encrypted data with auth tag
        key: 32-byte encryption key

    Returns:
        Decrypted plaintext bytes

    Raises:
        cryptography.exceptions.InvalidTag: If authentication fails
    """
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# =============================================================================
# Asset Packer
# =============================================================================

class AssetPacker:
    """Packs and encrypts game assets into a single .sounds file."""

    def __init__(self, source_dir: str, output_file: str = 'game.sounds'):
        """Initialize the packer.

        Args:
            source_dir: Directory containing assets to pack
            output_file: Output pack file path
        """
        self.source_dir = Path(source_dir)
        self.output_file = Path(output_file)
        self.files: Dict[str, bytes] = {}

    def collect_files(self, extensions: tuple = ('.wav', '.ogg', '.mp3')):
        """Collect all audio files from source directory.

        Args:
            extensions: File extensions to include
        """
        print(f"Scanning {self.source_dir}...")

        for root, dirs, files in os.walk(self.source_dir):
            # Skip the banks directory
            if 'banks' in root:
                continue

            for filename in files:
                if filename.lower().endswith(extensions):
                    filepath = Path(root) / filename
                    # Create relative path as key
                    rel_path = filepath.relative_to(self.source_dir)
                    key = str(rel_path).replace('\\', '/')

                    with open(filepath, 'rb') as f:
                        self.files[key] = f.read()

                    print(f"  Added: {key} ({len(self.files[key]):,} bytes)")

        print(f"Collected {len(self.files)} files")

    def pack(self, password: str) -> bool:
        """Pack and encrypt all collected files.

        Args:
            password: Encryption password

        Returns:
            True if successful
        """
        if not CRYPTO_AVAILABLE:
            print("ERROR: cryptography package required")
            return False

        if not self.files:
            print("ERROR: No files collected")
            return False

        print(f"\nPacking {len(self.files)} files...")

        # Generate random salt
        salt = secrets.token_bytes(SALT_SIZE)

        # Derive encryption key
        print("Deriving encryption key (this may take a moment)...")
        key = derive_key(password, salt)

        # Build file table and data blob
        file_table = {}
        data_blob = b''

        for rel_path, content in self.files.items():
            # Compress the content
            compressed = zlib.compress(content, COMPRESSION_LEVEL)
            compression_ratio = len(compressed) / len(content) * 100

            # Encrypt the compressed content
            nonce, ciphertext = encrypt_data(compressed, key)

            # Record position in blob
            offset = len(data_blob)
            file_table[rel_path] = {
                'offset': offset,
                'size': len(ciphertext),
                'nonce': nonce.hex(),
                'original_size': len(content),
                'compressed_size': len(compressed)
            }

            data_blob += ciphertext

            print(f"  Encrypted: {rel_path} ({compression_ratio:.1f}% of original)")

        # Encrypt the file table itself
        table_json = json.dumps(file_table).encode('utf-8')
        table_compressed = zlib.compress(table_json, COMPRESSION_LEVEL)
        table_nonce, table_encrypted = encrypt_data(table_compressed, key)

        # Write the pack file
        print(f"\nWriting {self.output_file}...")

        with open(self.output_file, 'wb') as f:
            # Header
            f.write(MAGIC)                              # 8 bytes
            f.write(struct.pack('<H', VERSION))         # 2 bytes
            f.write(salt)                               # 32 bytes
            f.write(table_nonce)                        # 12 bytes
            f.write(struct.pack('<I', len(table_encrypted)))  # 4 bytes
            f.write(table_encrypted)                    # Variable
            f.write(data_blob)                          # Variable

        file_size = os.path.getsize(self.output_file)
        original_size = sum(len(c) for c in self.files.values())

        print(f"\nPack complete!")
        print(f"  Original size:  {original_size:,} bytes")
        print(f"  Pack size:      {file_size:,} bytes")
        print(f"  Compression:    {file_size / original_size * 100:.1f}%")
        print(f"  Output:         {self.output_file}")

        return True


# =============================================================================
# Asset Loader (Runtime)
# =============================================================================

class AssetPack:
    """Loads and decrypts assets from a .sounds pack file at runtime."""

    def __init__(self, pack_file: str):
        """Initialize the loader.

        Args:
            pack_file: Path to the .sounds pack file
        """
        self.pack_file = Path(pack_file)
        self.file_table: Dict = {}
        self.data_offset: int = 0
        self._key: Optional[bytes] = None
        self._file: Optional[BinaryIO] = None
        self._cache: Dict[str, bytes] = {}

    def open(self, password: str) -> bool:
        """Open the pack file and decrypt the file table.

        Args:
            password: Decryption password

        Returns:
            True if successful
        """
        if not CRYPTO_AVAILABLE:
            print("ERROR: cryptography package required")
            return False

        if not self.pack_file.exists():
            print(f"ERROR: Pack file not found: {self.pack_file}")
            return False

        try:
            self._file = open(self.pack_file, 'rb')

            # Read and verify header
            magic = self._file.read(8)
            if magic != MAGIC:
                print("ERROR: Invalid pack file format")
                return False

            version = struct.unpack('<H', self._file.read(2))[0]
            if version > VERSION:
                print(f"ERROR: Unsupported pack version {version}")
                return False

            # Read encryption parameters
            salt = self._file.read(SALT_SIZE)
            table_nonce = self._file.read(NONCE_SIZE)
            table_size = struct.unpack('<I', self._file.read(4))[0]
            table_encrypted = self._file.read(table_size)

            # Remember where data starts
            self.data_offset = self._file.tell()

            # Derive key
            self._key = derive_key(password, salt)

            # Decrypt file table
            table_compressed = decrypt_data(table_nonce, table_encrypted, self._key)
            table_json = zlib.decompress(table_compressed)
            self.file_table = json.loads(table_json.decode('utf-8'))

            return True

        except Exception as e:
            print(f"ERROR: Failed to open pack: {e}")
            self.close()
            return False

    def close(self):
        """Close the pack file."""
        if self._file:
            self._file.close()
            self._file = None
        self._key = None
        self._cache.clear()

    def get(self, path: str, use_cache: bool = True) -> Optional[bytes]:
        """Get decrypted asset data.

        Args:
            path: Asset path (e.g., 'Movement/footsteps_001.wav')
            use_cache: Whether to cache decrypted data

        Returns:
            Decrypted asset bytes, or None if not found
        """
        # Normalize path
        path = path.replace('\\', '/')

        # Check cache first
        if use_cache and path in self._cache:
            return self._cache[path]

        if path not in self.file_table:
            return None

        if not self._file or not self._key:
            print("ERROR: Pack not opened")
            return None

        try:
            entry = self.file_table[path]

            # Seek to data position
            self._file.seek(self.data_offset + entry['offset'])
            ciphertext = self._file.read(entry['size'])

            # Decrypt
            nonce = bytes.fromhex(entry['nonce'])
            compressed = decrypt_data(nonce, ciphertext, self._key)

            # Decompress
            data = zlib.decompress(compressed)

            # Cache if requested
            if use_cache:
                self._cache[path] = data

            return data

        except Exception as e:
            print(f"ERROR: Failed to decrypt {path}: {e}")
            return None

    def list_files(self) -> list:
        """List all files in the pack.

        Returns:
            List of file paths
        """
        return list(self.file_table.keys())

    def __contains__(self, path: str) -> bool:
        """Check if a file exists in the pack."""
        return path.replace('\\', '/') in self.file_table

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# =============================================================================
# Command Line Interface
# =============================================================================

def main():
    """Command line interface for packing assets."""
    import getpass

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python asset_crypto.py pack [source_dir] [output_file]")
        print("  python asset_crypto.py list <pack_file>")
        print("  python asset_crypto.py test <pack_file> <asset_path>")
        print("")
        print("Examples:")
        print("  python asset_crypto.py pack sounds game.sounds")
        print("  python asset_crypto.py list game.sounds")
        print("  python asset_crypto.py test game.sounds Movement/footsteps_001.wav")
        return

    command = sys.argv[1].lower()

    if command == 'pack':
        source_dir = sys.argv[2] if len(sys.argv) > 2 else 'sounds'
        output_file = sys.argv[3] if len(sys.argv) > 3 else 'game.sounds'

        print("=" * 60)
        print("MechSimulator Asset Packer")
        print("=" * 60)
        print(f"Source:  {source_dir}")
        print(f"Output:  {output_file}")
        print("")

        # Get password securely
        password = getpass.getpass("Enter encryption password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            print("ERROR: Passwords do not match")
            return

        if len(password) < 8:
            print("ERROR: Password must be at least 8 characters")
            return

        packer = AssetPacker(source_dir, output_file)
        packer.collect_files()
        packer.pack(password)

    elif command == 'list':
        if len(sys.argv) < 3:
            print("ERROR: Pack file required")
            return

        pack_file = sys.argv[2]
        password = getpass.getpass("Enter password: ")

        pack = AssetPack(pack_file)
        if pack.open(password):
            print(f"\nFiles in {pack_file}:")
            for path in sorted(pack.list_files()):
                entry = pack.file_table[path]
                print(f"  {path} ({entry['original_size']:,} bytes)")
            print(f"\nTotal: {len(pack.list_files())} files")
            pack.close()

    elif command == 'test':
        if len(sys.argv) < 4:
            print("ERROR: Pack file and asset path required")
            return

        pack_file = sys.argv[2]
        asset_path = sys.argv[3]
        password = getpass.getpass("Enter password: ")

        pack = AssetPack(pack_file)
        if pack.open(password):
            data = pack.get(asset_path)
            if data:
                print(f"\nSuccessfully decrypted: {asset_path}")
                print(f"Size: {len(data):,} bytes")
                print(f"First 32 bytes: {data[:32].hex()}")
            else:
                print(f"ERROR: Asset not found: {asset_path}")
            pack.close()
    else:
        print(f"Unknown command: {command}")


if __name__ == '__main__':
    main()
