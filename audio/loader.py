"""
Sound Loader for MechSimulator.

Handles loading all game audio assets organized by category.
Supports both encrypted pack files and raw sound files.
"""

import os
import random
from typing import Dict, List, Optional

# Import encrypted pack support
try:
    from asset_crypto import AssetPack, CRYPTO_AVAILABLE
except ImportError:
    AssetPack = None
    CRYPTO_AVAILABLE = False


class SoundLoader:
    """Loads and organizes all game sound assets.

    Supports loading from:
    - Encrypted .sounds pack file (for distribution)
    - Raw sound files (for development)
    """

    def __init__(self, audio_manager):
        """Initialize the sound loader.

        Args:
            audio_manager: AudioManager instance for loading sounds
        """
        self.audio = audio_manager
        self.sounds = {}  # Categorized sound storage
        self._sounds_base_path = 'sounds'

        # Encrypted pack support
        self._pack: Optional[AssetPack] = None
        self._use_pack = False

        # OPTIMIZATION: Lazy loading flags for drone sounds
        self._drone_sounds_loaded = False
        self._drone_dir = None

    def init_pack(self, pack_file: str = 'game.sounds') -> bool:
        """Initialize encrypted pack loading.

        Args:
            pack_file: Path to the .sounds pack file

        Returns:
            True if pack opened successfully
        """
        if not CRYPTO_AVAILABLE:
            print("Pack loading: cryptography package not available")
            return False

        if not os.path.exists(pack_file):
            print(f"Pack loading: {pack_file} not found, using raw files")
            return False

        try:
            # Get the decryption key
            from audio.pack_key import get_pack_key
            password = get_pack_key()

            self._pack = AssetPack(pack_file)
            if self._pack.open(password):
                self._use_pack = True
                file_count = len(self._pack.list_files())
                print(f"Loaded encrypted sound pack: {pack_file} ({file_count} files)")
                return True
            else:
                print("Failed to open encrypted pack, using raw files")
                self._pack = None
                return False

        except Exception as e:
            print(f"Pack loading error: {e}, using raw files")
            self._pack = None
            return False

    def cleanup_pack(self):
        """Close the pack file if open."""
        if self._pack:
            self._pack.close()
            self._pack = None
        self._use_pack = False

    def _load_from_pack(self, rel_path: str, name: str, loop: bool = False, is_3d: bool = False, compressed: bool = False):
        """Load a sound from the encrypted pack into FMOD memory.

        Args:
            rel_path: Relative path like 'Movement/footsteps_001.wav'
            name: Sound name for reference
            loop: Whether to loop
            is_3d: Whether to use 3D spatialization
            compressed: Whether to use compressed sample mode

        Returns:
            Sound object or None
        """
        data = self._pack.get(rel_path)
        if not data:
            print(f"Sound not found in pack: {rel_path}")
            return None

        try:
            import pyfmodex
            from pyfmodex.flags import MODE
            from pyfmodex.structures import CREATESOUNDEXINFO

            # Build mode flags
            mode = MODE.OPENMEMORY
            if loop:
                mode |= MODE.LOOP_NORMAL
            else:
                mode |= MODE.LOOP_OFF

            if is_3d:
                mode |= MODE.THREED | MODE.THREED_LINEARROLLOFF
            else:
                mode |= MODE.DEFAULT

            if compressed:
                mode |= MODE.CREATECOMPRESSEDSAMPLE

            # Create sound info for memory loading
            exinfo = CREATESOUNDEXINFO()
            exinfo.length = len(data)

            sound = self.audio.fmod.system.create_sound(
                bytes(data),
                mode=mode,
                exinfo=exinfo
            )

            # Set 3D distance parameters for 3D sounds
            if is_3d:
                sound.min_distance = 2.0
                sound.max_distance = 60.0

            # Store in FMOD's sound dict
            self.audio.fmod.sounds[name] = sound
            return sound

        except Exception as e:
            print(f"Failed to load sound '{name}' from pack: {e}")
            return None

    def _load_sound(self, rel_path: str, name: str, loop: bool = False, is_3d: bool = False, compressed: bool = False):
        """Load a sound from pack or disk.

        Args:
            rel_path: Relative path within sounds folder
            name: Sound name for reference
            loop: Whether to loop
            is_3d: Whether to use 3D spatialization
            compressed: Whether to use compressed sample mode

        Returns:
            Sound object or None
        """
        if self._use_pack:
            return self._load_from_pack(rel_path, name, loop, is_3d, compressed)
        else:
            # Load from disk using existing methods
            full_path = os.path.join(self._sounds_base_path, rel_path)
            if is_3d:
                return self.audio.load_sound_3d(full_path, name, is_3d=True)
            elif compressed:
                return self.audio.load_sound_compressed(full_path, name, loop=loop)
            else:
                return self.audio.load_sound(full_path, name, loop=loop)

    def load_all(self) -> bool:
        """Load all game sounds.

        Returns:
            True if essential sounds loaded successfully
        """
        success = True

        # Load all sound categories
        success = self._load_footsteps() and success
        success = self._load_ambience() and success
        success = self._load_combat() and success
        success = self._load_fabrication() and success
        success = self._load_powerup() and success
        success = self._load_rotation() and success
        success = self._load_thrusters() and success
        success = self._load_drones() and success
        success = self._load_misc() and success

        return success

    def _get_path(self, *parts) -> str:
        """Build path from parts."""
        return os.path.join(self._sounds_base_path, *parts)

    def _check_dir(self, path: str, name: str) -> bool:
        """Check if directory exists."""
        if not os.path.exists(path):
            print(f"ERROR: {name} not found at {path}")
            return False
        return True

    def _load_footsteps(self) -> bool:
        """Load footstep sounds."""
        if self._use_pack:
            # Load from pack - we know the file names
            self.sounds['footsteps'] = []
            for i in range(1, 5):  # footsteps_001.wav through footsteps_004.wav
                rel_path = f'Movement/footsteps_{i:03d}.wav'
                sound = self._load_sound(rel_path, f'footstep_{i-1}')
                if sound:
                    self.sounds['footsteps'].append(sound)
            print(f"Loaded {len(self.sounds['footsteps'])} footstep sounds from pack")
            return len(self.sounds['footsteps']) >= 4
        else:
            # Load from disk - scan directory
            footsteps_dir = self._get_path('Movement')
            if not self._check_dir(footsteps_dir, 'sounds/Movement/'):
                return False

            all_footstep_files = sorted([
                f for f in os.listdir(footsteps_dir)
                if f.startswith('footsteps_') and f.endswith('.wav')
            ])

            print(f"Found {len(all_footstep_files)} footstep sounds")

            if len(all_footstep_files) < 4:
                print("Need at least 4 footsteps! Add .wav files to sounds/Movement/")
                return False

            self.sounds['footsteps'] = []
            for i, filename in enumerate(all_footstep_files):
                rel_path = f'Movement/{filename}'
                sound = self._load_sound(rel_path, f'footstep_{i}')
                if sound:
                    self.sounds['footsteps'].append(sound)

            print(f"Loaded {len(self.sounds['footsteps'])} footstep sounds")
            return True

    def _load_ambience(self) -> bool:
        """Load ambience sounds."""
        if self._use_pack:
            # Load from pack - use known ambience file
            rel_path = 'Ambience/Free_Wind_Ambience.wav'
            self.sounds['ambience'] = self._load_sound(rel_path, 'ambience', loop=True)
            if self.sounds['ambience']:
                print("Loaded ambience from pack")
            return True
        else:
            # Load from disk - pick random ambience
            ambience_dir = self._get_path('Ambience')
            if not self._check_dir(ambience_dir, 'sounds/Ambience/'):
                return False

            ambience_files = [
                f for f in os.listdir(ambience_dir)
                if f.endswith('.wav')
            ]

            print(f"Found {len(ambience_files)} ambience sounds")

            if ambience_files:
                filename = random.choice(ambience_files)
                rel_path = f'Ambience/{filename}'
                self.sounds['ambience'] = self._load_sound(rel_path, 'ambience', loop=True)
                print(f"Loaded ambience: {filename}")
            else:
                print("No ambience found!")
                self.sounds['ambience'] = None

            return True

    def _load_combat(self) -> bool:
        """Load combat/weapon sounds."""
        if not self._use_pack:
            combat_dir = self._get_path('Combat')
            if not self._check_dir(combat_dir, 'sounds/Combat/'):
                return False

            # Verify chaingun files exist
            chaingun_files = ['ChaingunStart.wav', 'ChaingunLoop.wav', 'ChaingunTail.wav']
            for f in chaingun_files:
                path = os.path.join(combat_dir, f)
                if not os.path.exists(path):
                    print(f"ERROR: {f} not found in sounds/Combat/")
                    return False

        # Chaingun sounds
        self._load_sound('Combat/ChaingunStart.wav', 'chaingun_start')
        self._load_sound('Combat/ChaingunLoop.wav', 'chaingun_loop', loop=True)
        self._load_sound('Combat/ChaingunTail.wav', 'chaingun_tail')

        # Minigun variant
        self._load_sound('Combat/SmallMinigunStart.wav', 'small_minigun_start')
        self._load_sound('Combat/SmallMinigunLoop.wav', 'small_minigun_loop', loop=True)
        self._load_sound('Combat/SmallMinigunEnd.wav', 'small_minigun_end')

        # Other weapons
        self._load_sound('Combat/MissileInitStart.wav', 'missile_init_start')
        self._load_sound('Combat/MissileInitLoop.wav', 'missile_init_loop', loop=True)
        self._load_sound('Combat/MissileInitEnd.wav', 'missile_init_end')
        self._load_sound('Combat/BarrageMissileLauncherVerticalMovement.wav', 'missile_movement')
        self._load_sound('Combat/BarrageMissileLaunchers.wav', 'missile_launch')
        self._load_sound('Combat/HandBlaster.wav', 'hand_blaster')
        self._load_sound('Combat/ShieldStartStop.wav', 'shield_startstop')
        self._load_sound('Combat/ShieldLoop.wav', 'shield_loop', loop=True)
        self._load_sound('Combat/Emp.wav', 'emp_sound')
        self._load_sound('Combat/TargetLock.wav', 'target_lock')

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
        if not self._use_pack:
            fab_dir = self._get_path('Fabrication')
            if not self._check_dir(fab_dir, 'sounds/Fabrication/'):
                return False

        self._load_sound('Fabrication/DebrisCollection.wav', 'debris_collect')
        self._load_sound('Fabrication/AmmoFabinitialize.wav', 'ammo_fab_init')
        self._load_sound('Fabrication/AmmoFabProcess.wav', 'ammo_fab_process', loop=True)
        self._load_sound('Fabrication/AmmoFabComplete.wav', 'ammo_fab_complete')
        self._load_sound('Fabrication/DebrisTrash.wav', 'debris_trash')

        print("Loaded fabrication sounds")
        return True

    def _load_powerup(self) -> bool:
        """Load power-up sequence sounds."""
        if not self._use_pack:
            powerup_dir = self._get_path('Suit Power-Up and Activation')
            if not self._check_dir(powerup_dir, 'sounds/Suit Power-Up and Activation/'):
                return False

        self._load_sound('Suit Power-Up and Activation/PowerupStart.wav', 'powerup_start')
        self._load_sound('Suit Power-Up and Activation/PowerupLoop.wav', 'powerup_loop')
        self._load_sound('Suit Power-Up and Activation/PowerupEnd.wav', 'powerup_end')
        self._load_sound('Suit Power-Up and Activation/mech_scifi_texture_interface_002.wav', 'thruster_depleted')

        # Load thruster activation from Flight folder
        self._load_sound('Flight/ThrusterActivation.wav', 'thruster_activate')

        print("Loaded power-up sounds")
        return True

    def _load_rotation(self) -> bool:
        """Load rotation sounds."""
        self._load_sound('Movement/RotationStart.wav', 'rotation_start')
        self._load_sound('Movement/RotationLoop.wav', 'rotation_loop', loop=True)
        self._load_sound('Movement/RotationEnd.wav', 'rotation_end')

        print("Loaded rotation sounds")
        return True

    def _load_thrusters(self) -> bool:
        """Load thruster pitch sounds (50 stages) and landing sounds.

        OPTIMIZATION: Uses compressed samples to reduce memory from ~9MB to ~2-3MB.
        Compressed samples decode in realtime but can play multiple instances.
        """
        if not self._use_pack:
            flight_dir = self._get_path('Flight')
            if not self._check_dir(flight_dir, 'sounds/Flight/'):
                return False

        self.sounds['thrusters'] = []
        for i in range(1, 51):
            rel_path = f"Flight/ThrusterPitch_{i:03d}.wav"
            # OPTIMIZATION: Use compressed samples for thruster sounds
            sound = self._load_sound(rel_path, f'thruster_pitch_{i:03d}', loop=True, compressed=True)
            if sound:
                self.sounds['thrusters'].append(sound)

        # Load landing sounds
        self._load_sound('Flight/SoftLanding.wav', 'soft_landing')
        self._load_sound('Flight/HardLanding.wav', 'hard_landing')
        self._load_sound('Flight/Crash.wav', 'crash_landing')

        print(f"Loaded {len(self.sounds['thrusters'])} thruster pitch sounds (compressed)")
        print("Loaded landing sounds")
        return True

    def _load_misc(self) -> bool:
        """Load miscellaneous sounds (weapon extend/ready)."""
        if not self._use_pack:
            misc_dir = self._get_path('Misc')
            if not self._check_dir(misc_dir, 'sounds/Misc/'):
                return False

        self._load_sound('Misc/chaingunExtend.wav', 'chaingun_extend')
        self._load_sound('Misc/ChaingunReady.wav', 'chaingun_ready')
        self._load_sound('Misc/Weapon1Extend.wav', 'weapon1_extend')
        self._load_sound('Misc/Weapon1Ready.wav', 'weapon1_ready')
        self._load_sound('Misc/Weapon2Extend.wav', 'weapon2_extend')
        self._load_sound('Misc/Weapon2Ready.wav', 'weapon2_ready')

        print("Loaded misc sounds")
        return True

    def _load_drones(self) -> bool:
        """Prepare for lazy loading of drone sounds.

        OPTIMIZATION: Drone sounds are now loaded lazily on first access.
        This reduces initial load time and memory usage until drones spawn.
        """
        if self._use_pack:
            # Check if pack has drone sounds
            drone_files = [f for f in self._pack.list_files() if f.startswith('Drones/')]
            if not drone_files:
                print("WARNING: No drone sounds in pack - drone system disabled")
                self.sounds['drones'] = {}
                self._drone_sounds_loaded = True
                return True

            self._drone_dir = 'Drones'  # Virtual path for pack mode
            self.sounds['drones'] = {}
            self._drone_sounds_loaded = False
            print("Drone sound system ready (lazy loading from pack)")
        else:
            drone_dir = self._get_path('Drones')
            if not os.path.exists(drone_dir):
                print("WARNING: sounds/Drones/ not found - drone system disabled")
                self.sounds['drones'] = {}
                self._drone_sounds_loaded = True
                return True  # Not critical

            # Store directory for lazy loading
            self._drone_dir = drone_dir
            self.sounds['drones'] = {}
            self._drone_sounds_loaded = False
            print("Drone sound system ready (lazy loading enabled)")

        return True

    def _ensure_drone_sounds_loaded(self):
        """Lazily load drone sounds on first access.

        OPTIMIZATION: Only loads when first drone spawns.
        """
        if self._drone_sounds_loaded:
            return

        if self._drone_dir is None:
            self._drone_sounds_loaded = True
            return

        print("Loading drone sounds (lazy)...")

        if self._use_pack:
            self._load_drone_sounds_from_pack()
        else:
            self._load_drone_sounds_from_disk()

        self._drone_sounds_loaded = True
        print("Drone sounds loaded")

    def _load_drone_sounds_from_pack(self):
        """Load drone sounds from encrypted pack."""
        # Get all drone files from pack
        all_files = self._pack.list_files()
        drone_files = sorted([f for f in all_files if f.startswith('Drones/')])

        def load_from_subdir(subdir: str, key: str, is_3d: bool = True):
            """Load sounds from a subdirectory in pack."""
            prefix = f'Drones/{subdir}/'
            files = sorted([f for f in drone_files if f.startswith(prefix) and f.endswith('.wav')])
            sounds = []
            for i, rel_path in enumerate(files):
                sound = self._load_sound(rel_path, f'drone_{key}_{i}', is_3d=is_3d)
                if sound:
                    sounds.append(sound)
            self.sounds['drones'][key] = sounds
            if sounds:
                print(f"  Loaded {len(sounds)} {key} drone sounds from pack" + (" (3D)" if is_3d else ""))

        # Load all drone sound categories
        load_from_subdir('Ambience', 'ambience')
        load_from_subdir('Beacons', 'beacons')
        load_from_subdir('Scans', 'scans')
        load_from_subdir('PassBys', 'passbys')
        load_from_subdir('SuperSonics', 'supersonics')
        load_from_subdir('SonicBooms', 'sonicbooms')
        load_from_subdir('Takeoffs', 'takeoffs')
        load_from_subdir('Hits', 'hits')
        load_from_subdir('Debris', 'debris')
        load_from_subdir('Weapons', 'weapons')
        load_from_subdir('Explosions', 'explosions')
        load_from_subdir('Malfunctions', 'malfunctions')
        load_from_subdir('Transmissions', 'transmissions')
        load_from_subdir('Interfaces', 'interfaces')

        # Load weapon sounds
        self._load_drone_weapon_sounds_from_pack(drone_files)

    def _load_drone_weapon_sounds_from_pack(self, drone_files):
        """Load drone weapon sounds from pack."""
        weapons_prefix = 'Drones/Weapons/'
        weapon_files = [f for f in drone_files if f.startswith(weapons_prefix)]

        if not weapon_files:
            return

        self.sounds['drones']['pulse_cannon'] = []
        self.sounds['drones']['plasma_launcher'] = []
        self.sounds['drones']['rail_gun'] = []

        # Pulse cannon uses shots 001 and 003
        for shot_num in ['001', '003']:
            rel_path = f'{weapons_prefix}Bluezone_BC0288_combat_drone_weapon_scifi_shot_{shot_num}.wav'
            if rel_path in drone_files:
                sound = self._load_sound(rel_path, f'drone_pulse_{shot_num}', is_3d=True)
                if sound:
                    self.sounds['drones']['pulse_cannon'].append(sound)

        # Plasma launcher uses shots 002 and 004
        for shot_num in ['002', '004']:
            rel_path = f'{weapons_prefix}Bluezone_BC0288_combat_drone_weapon_scifi_shot_{shot_num}.wav'
            if rel_path in drone_files:
                sound = self._load_sound(rel_path, f'drone_plasma_{shot_num}', is_3d=True)
                if sound:
                    self.sounds['drones']['plasma_launcher'].append(sound)

        # Rail gun uses all sounds
        for shot_num in ['001', '002', '003', '004']:
            rel_path = f'{weapons_prefix}Bluezone_BC0288_combat_drone_weapon_scifi_shot_{shot_num}.wav'
            if rel_path in drone_files:
                sound = self._load_sound(rel_path, f'drone_rail_{shot_num}', is_3d=True)
                if sound:
                    self.sounds['drones']['rail_gun'].append(sound)

        # Projectile hit
        hit_path = f'{weapons_prefix}Bluezone_BC0288_combat_drone_weapon_scifi_shot_003.wav'
        if hit_path in drone_files:
            self.sounds['drones']['projectile_hit'] = self._load_sound(hit_path, 'drone_projectile_hit', is_3d=True)

        print("  Drone weapon types loaded from pack (3D)")

    def _load_drone_sounds_from_disk(self):
        """Load drone sounds from filesystem."""
        drone_dir = self._drone_dir

        def load_from_subdir(subdir: str, key: str, is_3d: bool = True):
            """Load sounds from a subdirectory."""
            path = os.path.join(drone_dir, subdir)
            if os.path.exists(path):
                files = sorted([f for f in os.listdir(path) if f.endswith('.wav')])
                sounds = []
                for i, filename in enumerate(files):
                    rel_path = f'Drones/{subdir}/{filename}'
                    sound = self._load_sound(rel_path, f'drone_{key}_{i}', is_3d=is_3d)
                    if sound:
                        sounds.append(sound)
                self.sounds['drones'][key] = sounds
                print(f"  Loaded {len(sounds)} {key} drone sounds" + (" (3D)" if is_3d else ""))
            else:
                self.sounds['drones'][key] = []

        # Load all drone sound categories
        load_from_subdir('Ambience', 'ambience')
        load_from_subdir('Beacons', 'beacons')
        load_from_subdir('Scans', 'scans')
        load_from_subdir('PassBys', 'passbys')
        load_from_subdir('SuperSonics', 'supersonics')
        load_from_subdir('SonicBooms', 'sonicbooms')
        load_from_subdir('Takeoffs', 'takeoffs')
        load_from_subdir('Hits', 'hits')
        load_from_subdir('Debris', 'debris')
        load_from_subdir('Weapons', 'weapons')
        load_from_subdir('Explosions', 'explosions')
        load_from_subdir('Malfunctions', 'malfunctions')
        load_from_subdir('Transmissions', 'transmissions')
        load_from_subdir('Interfaces', 'interfaces')

        # Load weapon sounds
        self._load_drone_weapon_sounds_from_disk()

    def _load_drone_weapon_sounds_from_disk(self):
        """Load drone weapon sounds from filesystem."""
        weapons_path = os.path.join(self._drone_dir, 'Weapons')
        if not os.path.exists(weapons_path):
            return

        self.sounds['drones']['pulse_cannon'] = []
        self.sounds['drones']['plasma_launcher'] = []
        self.sounds['drones']['rail_gun'] = []

        # Pulse cannon uses shots 001 and 003
        for shot_num in ['001', '003']:
            rel_path = f'Drones/Weapons/Bluezone_BC0288_combat_drone_weapon_scifi_shot_{shot_num}.wav'
            sound = self._load_sound(rel_path, f'drone_pulse_{shot_num}', is_3d=True)
            if sound:
                self.sounds['drones']['pulse_cannon'].append(sound)

        # Plasma launcher uses shots 002 and 004
        for shot_num in ['002', '004']:
            rel_path = f'Drones/Weapons/Bluezone_BC0288_combat_drone_weapon_scifi_shot_{shot_num}.wav'
            sound = self._load_sound(rel_path, f'drone_plasma_{shot_num}', is_3d=True)
            if sound:
                self.sounds['drones']['plasma_launcher'].append(sound)

        # Rail gun uses all sounds
        for shot_num in ['001', '002', '003', '004']:
            rel_path = f'Drones/Weapons/Bluezone_BC0288_combat_drone_weapon_scifi_shot_{shot_num}.wav'
            sound = self._load_sound(rel_path, f'drone_rail_{shot_num}', is_3d=True)
            if sound:
                self.sounds['drones']['rail_gun'].append(sound)

        # Projectile hit
        rel_path = 'Drones/Weapons/Bluezone_BC0288_combat_drone_weapon_scifi_shot_003.wav'
        self.sounds['drones']['projectile_hit'] = self._load_sound(rel_path, 'drone_projectile_hit', is_3d=True)

        print("  Drone weapon types loaded (3D)")

    def get_footstep(self, index: int):
        """Get a footstep sound by index."""
        footsteps = self.sounds.get('footsteps', [])
        if 0 <= index < len(footsteps):
            return footsteps[index]
        return None

    def get_random_footstep(self, is_left_foot: bool):
        """Get a random footstep sound for the specified foot."""
        from state.constants import LEFT_FOOT_INDICES, RIGHT_FOOT_INDICES

        footsteps = self.sounds.get('footsteps', [])
        indices = LEFT_FOOT_INDICES if is_left_foot else RIGHT_FOOT_INDICES

        valid_indices = [i for i in indices if i < len(footsteps)]
        if valid_indices:
            return footsteps[random.choice(valid_indices)]
        return None

    def get_thruster_sound(self, index: int):
        """Get a thruster pitch sound by index (0-49)."""
        thrusters = self.sounds.get('thrusters', [])
        if 0 <= index < len(thrusters):
            return thrusters[index]
        return None

    def get_drone_sound(self, category: str, index: int = None):
        """Get a drone sound by category and optional index.

        Args:
            category: Sound category (beacons, explosions, etc.)
            index: Specific index, or None for random

        Returns:
            Sound object or None
        """
        # OPTIMIZATION: Lazy load drone sounds on first access
        self._ensure_drone_sounds_loaded()

        drones = self.sounds.get('drones', {})
        sounds = drones.get(category)

        if sounds is None:
            return None

        # Single sound (like pulse_cannon)
        if not isinstance(sounds, list):
            return sounds

        # List of sounds
        if not sounds:
            return None

        if index is None:
            return random.choice(sounds)

        if 0 <= index < len(sounds):
            return sounds[index]

        return None

    def get_damaged_sound(self):
        """Get a random damage sound."""
        damaged = self.sounds.get('damaged', [])
        if damaged:
            return random.choice(damaged)
        return None

    @property
    def has_drone_sounds(self) -> bool:
        """Check if drone sounds are available (may trigger lazy load)."""
        # Check if drone directory was found
        return self._drone_dir is not None or bool(self.sounds.get('drones'))

    @property
    def has_ambience(self) -> bool:
        """Check if ambience is loaded."""
        return self.sounds.get('ambience') is not None
