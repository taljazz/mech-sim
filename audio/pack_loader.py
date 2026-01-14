"""
Encrypted Asset Pack Loader for MechSimulator Audio System

This module provides seamless integration between the encrypted .sounds pack
and the existing audio system. It can load sounds from either:
- Encrypted pack file (for distribution)
- Raw sound files (for development)

Usage:
    from audio.pack_loader import PackedSoundLoader

    # For encrypted pack
    loader = PackedSoundLoader(audio_manager, pack_file='game.sounds')
    loader.open('encryption-password')

    # For development (raw files)
    loader = PackedSoundLoader(audio_manager, sounds_dir='sounds')

    # Load sounds (works the same either way)
    loader.load_all()
"""

import os
import io
from typing import Optional
from pathlib import Path

# Import the crypto module
try:
    from asset_crypto import AssetPack, CRYPTO_AVAILABLE
except ImportError:
    AssetPack = None
    CRYPTO_AVAILABLE = False


class PackedSoundLoader:
    """Sound loader that supports both encrypted packs and raw files."""

    def __init__(self, audio_manager, pack_file: str = None, sounds_dir: str = 'sounds'):
        """Initialize the loader.

        Args:
            audio_manager: AudioManager instance
            pack_file: Path to .sounds pack file (if using encrypted)
            sounds_dir: Path to raw sounds directory (fallback/development)
        """
        self.audio = audio_manager
        self.pack_file = pack_file
        self.sounds_dir = Path(sounds_dir)
        self._pack: Optional[AssetPack] = None
        self._use_pack = False
        self.sounds = {}

        # Lazy loading flags
        self._drone_sounds_loaded = False

    def open(self, password: str) -> bool:
        """Open the encrypted pack file.

        Args:
            password: Decryption password

        Returns:
            True if successful, False to fall back to raw files
        """
        if not self.pack_file or not CRYPTO_AVAILABLE:
            print("Pack loading not available, using raw files")
            return False

        if not os.path.exists(self.pack_file):
            print(f"Pack file not found: {self.pack_file}, using raw files")
            return False

        self._pack = AssetPack(self.pack_file)
        if self._pack.open(password):
            self._use_pack = True
            print(f"Loaded encrypted sound pack: {self.pack_file}")
            return True
        else:
            print("Failed to open pack, using raw files")
            self._pack = None
            return False

    def close(self):
        """Close the pack file if open."""
        if self._pack:
            self._pack.close()
            self._pack = None
        self._use_pack = False

    def _get_file_bytes(self, rel_path: str) -> Optional[bytes]:
        """Get file bytes from pack or disk.

        Args:
            rel_path: Relative path like 'Movement/footsteps_001.wav'

        Returns:
            File bytes or None
        """
        if self._use_pack and self._pack:
            return self._pack.get(rel_path)
        else:
            # Load from disk
            full_path = self.sounds_dir / rel_path
            if full_path.exists():
                with open(full_path, 'rb') as f:
                    return f.read()
        return None

    def _load_sound_from_bytes(self, data: bytes, name: str, loop: bool = False) -> object:
        """Load a sound from memory bytes into FMOD.

        Args:
            data: Audio file bytes
            name: Sound name for reference
            loop: Whether to loop

        Returns:
            Sound object or None
        """
        try:
            # FMOD can load from memory using OPENMEMORY mode
            import pyfmodex
            from pyfmodex.flags import MODE

            mode = MODE.DEFAULT | MODE.OPENMEMORY
            if loop:
                mode |= MODE.LOOP_NORMAL

            # Create CREATESOUNDEXINFO for memory loading
            from pyfmodex.structures import CREATESOUNDEXINFO
            exinfo = CREATESOUNDEXINFO()
            exinfo.length = len(data)

            sound = self.audio.fmod.system.create_sound(
                bytes(data),
                mode=mode,
                exinfo=exinfo
            )

            # Store in fmod's sound dict for later reference
            self.audio.fmod._sounds[name] = sound
            return sound

        except Exception as e:
            print(f"Failed to load sound '{name}' from memory: {e}")
            return None

    def _load_sound(self, rel_path: str, name: str, loop: bool = False):
        """Load a single sound from pack or disk.

        Args:
            rel_path: Relative path in sounds folder
            name: Sound name for reference
            loop: Whether to loop

        Returns:
            Sound object or None
        """
        if self._use_pack:
            data = self._get_file_bytes(rel_path)
            if data:
                return self._load_sound_from_bytes(data, name, loop)
            else:
                print(f"Sound not found in pack: {rel_path}")
                return None
        else:
            # Use standard file loading
            full_path = str(self.sounds_dir / rel_path)
            return self.audio.load_sound(full_path, name, loop=loop)

    def load_all(self) -> bool:
        """Load all game sounds.

        Returns:
            True if essential sounds loaded successfully
        """
        success = True
        success = self._load_footsteps() and success
        success = self._load_ambience() and success
        success = self._load_combat() and success
        success = self._load_fabrication() and success
        success = self._load_powerup() and success
        success = self._load_rotation() and success
        success = self._load_thrusters() and success
        success = self._load_misc() and success
        # Drones loaded lazily
        return success

    def _load_footsteps(self) -> bool:
        """Load footstep sounds."""
        self.sounds['footsteps'] = []
        for i in range(1, 5):
            sound = self._load_sound(f'Movement/footsteps_{i:03d}.wav', f'footstep_{i}')
            if sound:
                self.sounds['footsteps'].append(sound)

        print(f"Loaded {len(self.sounds['footsteps'])} footstep sounds")
        return len(self.sounds['footsteps']) >= 4

    def _load_ambience(self) -> bool:
        """Load ambience sounds."""
        sound = self._load_sound('Ambience/Free_Wind_Ambience.wav', 'ambience', loop=True)
        self.sounds['ambience'] = sound
        if sound:
            print("Loaded ambience")
        return True

    def _load_combat(self) -> bool:
        """Load combat sounds."""
        combat_sounds = [
            ('Combat/ChaingunStart.wav', 'chaingun_start', False),
            ('Combat/ChaingunLoop.wav', 'chaingun_loop', True),
            ('Combat/ChaingunTail.wav', 'chaingun_tail', False),
            ('Combat/SmallMinigunStart.wav', 'small_minigun_start', False),
            ('Combat/SmallMinigunLoop.wav', 'small_minigun_loop', True),
            ('Combat/SmallMinigunEnd.wav', 'small_minigun_end', False),
            ('Combat/MissileInitStart.wav', 'missile_init_start', False),
            ('Combat/MissileInitLoop.wav', 'missile_init_loop', True),
            ('Combat/MissileInitEnd.wav', 'missile_init_end', False),
            ('Combat/BarrageMissileLauncherVerticalMovement.wav', 'missile_movement', False),
            ('Combat/BarrageMissileLaunchers.wav', 'missile_launch', False),
            ('Combat/HandBlaster.wav', 'hand_blaster', False),
            ('Combat/ShieldStartStop.wav', 'shield_startstop', False),
            ('Combat/ShieldLoop.wav', 'shield_loop', True),
            ('Combat/Emp.wav', 'emp_sound', False),
            ('Combat/TargetLock.wav', 'target_lock', False),
        ]

        for path, name, loop in combat_sounds:
            self._load_sound(path, name, loop)

        # Damage sounds
        self.sounds['damaged'] = []
        for i in range(1, 4):
            sound = self._load_sound(f'Combat/Damaged{i}.wav', f'damaged_{i}')
            if sound:
                self.sounds['damaged'].append(sound)

        print(f"Loaded combat sounds including {len(self.sounds['damaged'])} damage sounds")
        return True

    def _load_fabrication(self) -> bool:
        """Load fabrication sounds."""
        fab_sounds = [
            ('Fabrication/DebrisCollection.wav', 'debris_collect', False),
            ('Fabrication/AmmoFabinitialize.wav', 'ammo_fab_init', False),
            ('Fabrication/AmmoFabProcess.wav', 'ammo_fab_process', True),
            ('Fabrication/AmmoFabComplete.wav', 'ammo_fab_complete', False),
            ('Fabrication/DebrisTrash.wav', 'debris_trash', False),
        ]

        for path, name, loop in fab_sounds:
            self._load_sound(path, name, loop)

        print("Loaded fabrication sounds")
        return True

    def _load_powerup(self) -> bool:
        """Load power-up sounds."""
        powerup_sounds = [
            ('Suit Power-Up and Activation/PowerupStart.wav', 'powerup_start', False),
            ('Suit Power-Up and Activation/PowerupLoop.wav', 'powerup_loop', False),
            ('Suit Power-Up and Activation/PowerupEnd.wav', 'powerup_end', False),
            ('Suit Power-Up and Activation/mech_scifi_texture_interface_002.wav', 'thruster_depleted', False),
            ('Flight/ThrusterActivation.wav', 'thruster_activate', False),
        ]

        for path, name, loop in powerup_sounds:
            self._load_sound(path, name, loop)

        print("Loaded power-up sounds")
        return True

    def _load_rotation(self) -> bool:
        """Load rotation sounds."""
        rotation_sounds = [
            ('Movement/RotationStart.wav', 'rotation_start', False),
            ('Movement/RotationLoop.wav', 'rotation_loop', True),
            ('Movement/RotationEnd.wav', 'rotation_end', False),
        ]

        for path, name, loop in rotation_sounds:
            self._load_sound(path, name, loop)

        print("Loaded rotation sounds")
        return True

    def _load_thrusters(self) -> bool:
        """Load thruster sounds."""
        self.sounds['thrusters'] = []

        for i in range(1, 51):
            sound = self._load_sound(f'Flight/ThrusterPitch_{i:03d}.wav', f'thruster_pitch_{i:03d}', loop=True)
            if sound:
                self.sounds['thrusters'].append(sound)

        # Landing sounds
        self._load_sound('Flight/SoftLanding.wav', 'soft_landing', False)
        self._load_sound('Flight/HardLanding.wav', 'hard_landing', False)
        self._load_sound('Flight/Crash.wav', 'crash_landing', False)

        print(f"Loaded {len(self.sounds['thrusters'])} thruster pitch sounds")
        return True

    def _load_misc(self) -> bool:
        """Load misc sounds."""
        misc_sounds = [
            ('Misc/chaingunExtend.wav', 'chaingun_extend', False),
            ('Misc/ChaingunReady.wav', 'chaingun_ready', False),
            ('Misc/Weapon1Extend.wav', 'weapon1_extend', False),
            ('Misc/Weapon1Ready.wav', 'weapon1_ready', False),
            ('Misc/Weapon2Extend.wav', 'weapon2_extend', False),
            ('Misc/Weapon2Ready.wav', 'weapon2_ready', False),
        ]

        for path, name, loop in misc_sounds:
            self._load_sound(path, name, loop)

        print("Loaded misc sounds")
        return True

    # Accessor methods matching SoundLoader interface
    def get_footstep(self, index: int):
        footsteps = self.sounds.get('footsteps', [])
        if 0 <= index < len(footsteps):
            return footsteps[index]
        return None

    def get_random_footstep(self, is_left_foot: bool):
        import random
        from state.constants import LEFT_FOOT_INDICES, RIGHT_FOOT_INDICES
        footsteps = self.sounds.get('footsteps', [])
        indices = LEFT_FOOT_INDICES if is_left_foot else RIGHT_FOOT_INDICES
        valid = [i for i in indices if i < len(footsteps)]
        if valid:
            return footsteps[random.choice(valid)]
        return None

    def get_thruster_sound(self, index: int):
        thrusters = self.sounds.get('thrusters', [])
        if 0 <= index < len(thrusters):
            return thrusters[index]
        return None

    def get_damaged_sound(self):
        import random
        damaged = self.sounds.get('damaged', [])
        if damaged:
            return random.choice(damaged)
        return None

    @property
    def has_ambience(self) -> bool:
        return self.sounds.get('ambience') is not None
