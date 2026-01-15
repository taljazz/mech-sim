"""
Audio Manager for MechSimulator.

Wraps the fmod_audio.MechAudio class and provides a higher-level interface
for managing game audio, channels, and volume control.
"""

from fmod_audio import MechAudio, FMODChannelWrapper
from state.constants import BASE_VOLUMES, MASTER_VOLUME_DEFAULT


class AudioManager:
    """High-level audio management for the game."""

    def __init__(self):
        self._fmod = MechAudio()
        self.master_volume = MASTER_VOLUME_DEFAULT
        self._channels = {}  # Named channel wrappers
        self._initialized = False

    def init(self, max_channels: int = 64):
        """Initialize the audio system.

        Args:
            max_channels: Maximum simultaneous channels
        """
        if self._initialized:
            return

        self._fmod.init(max_channels=max_channels)
        self._create_channel_wrappers()
        self._initialized = True

    def _create_channel_wrappers(self):
        """Create all named channel wrappers for the game."""
        # Weapon channels
        self._channels['missiles'] = FMODChannelWrapper(self._fmod, 'weapons', 'missiles')
        self._channels['blaster'] = FMODChannelWrapper(self._fmod, 'weapons', 'blaster')
        self._channels['shield'] = FMODChannelWrapper(self._fmod, 'weapons', 'shield')
        self._channels['emp'] = FMODChannelWrapper(self._fmod, 'weapons', 'emp')

        # System channels
        self._channels['fabrication'] = FMODChannelWrapper(self._fmod, 'ui', 'fabrication')
        self._channels['player_damage'] = FMODChannelWrapper(self._fmod, 'ui', 'player_damage')
        self._channels['thruster_pitch'] = FMODChannelWrapper(self._fmod, 'thrusters', 'thruster_pitch')
        self._channels['thruster_activate'] = FMODChannelWrapper(self._fmod, 'thrusters', 'thruster_activate')
        self._channels['rotation'] = FMODChannelWrapper(self._fmod, 'movement', 'rotation')
        self._channels['ambience'] = FMODChannelWrapper(self._fmod, 'ambience', 'ambience')

        # Drone channels (2 drones, each with ambient and combat)
        # Using is_3d=True for FMOD native 3D spatialization (binaural)
        self._drone_channels = [
            {
                'ambient': FMODChannelWrapper(self._fmod, 'drones', 'drone_0_ambient', is_3d=True),
                'combat': FMODChannelWrapper(self._fmod, 'drones', 'drone_0_combat', is_3d=True)
            },
            {
                'ambient': FMODChannelWrapper(self._fmod, 'drones', 'drone_1_ambient', is_3d=True),
                'combat': FMODChannelWrapper(self._fmod, 'drones', 'drone_1_combat', is_3d=True)
            }
        ]

    @property
    def fmod(self) -> MechAudio:
        """Access to underlying FMOD system."""
        return self._fmod

    def get_channel(self, name: str) -> FMODChannelWrapper:
        """Get a named channel wrapper.

        Args:
            name: Channel name (missiles, blaster, etc.)

        Returns:
            FMODChannelWrapper for the channel
        """
        return self._channels.get(name)

    def get_drone_channels(self, drone_id: int) -> dict:
        """Get drone channel wrappers.

        Args:
            drone_id: Drone ID (0 or 1)

        Returns:
            Dict with 'ambient' and 'combat' channels
        """
        if 0 <= drone_id < len(self._drone_channels):
            return self._drone_channels[drone_id]
        return None

    def set_master_volume(self, volume: float):
        """Set master volume.

        Args:
            volume: Volume from 0.0 to 1.0
        """
        self.master_volume = max(0.0, min(1.0, volume))
        self._fmod.set_master_volume(self.master_volume)

    def adjust_volume(self, delta: float) -> float:
        """Adjust master volume by delta.

        Args:
            delta: Amount to add/subtract

        Returns:
            New master volume
        """
        self.set_master_volume(self.master_volume + delta)
        return self.master_volume

    def load_sound(self, path: str, name: str, loop: bool = False, stream: bool = False, mono: bool = False):
        """Load a sound file.

        Args:
            path: File path
            name: Sound name for reference
            loop: Whether the sound should loop
            stream: If True, stream from disk (OPTIMIZATION for large files)
            mono: If True, force stereo to mono for proper 3D positioning

        Returns:
            The loaded sound object
        """
        return self._fmod.load_sound(path, name, loop=loop, stream=stream, mono=mono)

    def load_sound_compressed(self, path: str, name: str, loop: bool = False, mono: bool = False):
        """Load a sound as compressed sample (less memory, more CPU).

        Args:
            path: File path
            name: Sound name for reference
            loop: Whether the sound should loop
            mono: If True, force stereo to mono for proper 3D positioning

        Returns:
            The loaded sound object
        """
        return self._fmod.load_sound_compressed(path, name, loop=loop, mono=mono)

    def load_sound_3d(self, path: str, name: str, loop: bool = False,
                      min_distance: float = 2.0, max_distance: float = 60.0, is_3d: bool = True):
        """Load a sound with FMOD 3D spatialization enabled.

        Args:
            path: File path
            name: Sound name for reference
            loop: Whether the sound should loop
            min_distance: Distance where sound is at full volume
            max_distance: Distance where sound attenuates to minimum
            is_3d: If True, enable 3D mode (default). Set False to load as 2D.

        Returns:
            The loaded sound object
        """
        if is_3d:
            return self._fmod.load_sound_3d(path, name, loop=loop,
                                            min_distance=min_distance, max_distance=max_distance)
        else:
            return self._fmod.load_sound(path, name, loop=loop)

    def get_sound(self, name: str):
        """Get a loaded sound by name.

        Args:
            name: Sound name

        Returns:
            Sound object or None
        """
        return self._fmod.get_sound(name)

    def play_sound(self, name: str, group: str, loop_count: int = 0):
        """Play a sound by name.

        Args:
            name: Sound name
            group: Channel group name
            loop_count: Number of loops (-1 for infinite)

        Returns:
            The channel playing the sound
        """
        return self._fmod.play_sound(name, group, loop_count=loop_count)

    def play_sound_object(self, sound, group: str, loop_count: int = 0,
                          position_3d: tuple = None, velocity: tuple = None):
        """Play a sound object directly.

        Args:
            sound: Sound object
            group: Channel group name
            loop_count: Number of loops (-1 for infinite)
            position_3d: Optional (x, y, z) position for 3D spatialization
            velocity: Optional (vx, vy, vz) velocity for Doppler effect

        Returns:
            The channel playing the sound
        """
        return self._fmod.play_sound_object(
            sound, group, loop_count=loop_count,
            position_3d=position_3d, velocity=velocity
        )

    def set_channel(self, name: str, channel):
        """Track a channel by name.

        Args:
            name: Channel name for tracking
            channel: The channel object
        """
        self._fmod.set_channel(name, channel)

    def stop_channel(self, name: str):
        """Stop a tracked channel.

        Args:
            name: Channel name
        """
        self._fmod.stop_channel(name)

    def check_channel_ended(self, name: str) -> bool:
        """Check if a channel has finished playing.

        Args:
            name: Channel name

        Returns:
            True if channel has ended
        """
        return self._fmod.check_channel_ended(name)

    def stop_all(self):
        """Stop all playing sounds."""
        # Stop all registered channels by name
        channels_to_stop = [
            'startup', 'ambience', 'chaingun', 'missiles', 'shield',
            'weapon_equip', 'fabrication', 'rotation',
            'thruster_activate', 'thruster_pitch', 'player_damage',
            'blaster', 'emp'
        ]
        for name in channels_to_stop:
            self._fmod.stop_channel(name)

        # Stop drone channels
        for dc in self._drone_channels:
            if dc['ambient']._channel:
                try:
                    dc['ambient']._channel.stop()
                except Exception:
                    pass
            if dc['combat']._channel:
                try:
                    dc['combat']._channel.stop()
                except Exception:
                    pass

    def start_ducking(self, groups_to_duck: list = None, duck_volume: float = 0.5, speed: float = 5.0):
        """Start audio ducking for TTS clarity.

        Args:
            groups_to_duck: List of group names to duck (default: all)
            duck_volume: Target volume during ducking
            speed: Ducking speed
        """
        self._fmod.start_ducking(groups_to_duck=groups_to_duck, duck_volume=duck_volume, speed=speed)

    def stop_ducking(self, speed: float = 3.0):
        """Stop audio ducking and restore volumes.

        Args:
            speed: Restore speed
        """
        self._fmod.stop_ducking(speed=speed)

    def is_ducking(self) -> bool:
        """Check if audio ducking is active."""
        return self._fmod.is_ducking()

    def set_hull_damage_effect(self, hull_percent: float):
        """Apply audio effects based on hull damage.

        Args:
            hull_percent: Current hull percentage
        """
        self._fmod.set_hull_damage_effect(hull_percent)

    def set_reverb(self, wet_level_db: float, decay_ms: float, enabled: bool = True):
        """Set reverb parameters.

        Args:
            wet_level_db: Wet level in dB
            decay_ms: Decay time in milliseconds
            enabled: Whether reverb is enabled
        """
        self._fmod.set_reverb(wet_level_db=wet_level_db, decay_ms=decay_ms, enabled=enabled)

    def calculate_spatial_audio(self, source_x, source_y, source_altitude,
                                 listener_x, listener_y, listener_altitude,
                                 listener_facing, max_distance=50.0, min_distance=2.0):
        """Calculate spatial audio positioning.

        Returns:
            Tuple of (pan, volume, distance, relative_angle, altitude_diff)
        """
        return self._fmod.calculate_spatial_audio(
            source_x=source_x,
            source_y=source_y,
            source_altitude=source_altitude,
            listener_x=listener_x,
            listener_y=listener_y,
            listener_altitude=listener_altitude,
            listener_facing=listener_facing,
            max_distance=max_distance,
            min_distance=min_distance
        )

    # === FMOD 3D Audio Methods ===

    def init_3d_audio(self, doppler_scale=0.0, distance_factor=1.0, rolloff_scale=1.0):
        """Initialize 3D audio settings.

        Args:
            doppler_scale: Doppler effect intensity (0.0 = disabled)
            distance_factor: Distance scale (1.0 = meters)
            rolloff_scale: How quickly sound attenuates with distance
        """
        self._fmod.set_3d_settings(doppler_scale, distance_factor, rolloff_scale)

    def update_3d_listener(self, x, y, altitude, facing_angle):
        """Update the 3D listener position and orientation.

        Call this every frame to keep the listener in sync with player position.

        Args:
            x: Player X position (meters, East)
            y: Player Y position (meters, North)
            altitude: Player altitude (feet)
            facing_angle: Player facing angle (degrees, 0=North, 90=East)
        """
        import math

        # Convert facing angle to forward vector
        # Game: 0=North (+Y), 90=East (+X)
        angle_rad = math.radians(facing_angle)
        forward_x = math.sin(angle_rad)  # East component
        forward_y = math.cos(angle_rad)  # North component
        forward_z = 0  # No vertical tilt

        # Up vector is always straight up
        up_x, up_y, up_z = 0, 0, 1

        # Convert altitude from feet to meters for 3D audio
        altitude_meters = altitude / 3.28

        position = (x, y, altitude_meters)
        forward = (forward_x, forward_y, forward_z)
        up = (up_x, up_y, up_z)

        self._fmod.set_3d_listener_attributes(position, forward, up)

    def set_sound_3d_distance(self, sound, min_distance=2.0, max_distance=50.0):
        """Set the min/max distance for 3D sound attenuation.

        Args:
            sound: Sound object
            min_distance: Distance where sound is at full volume
            max_distance: Distance where sound is at minimum volume
        """
        self._fmod.set_sound_3d_min_max_distance(sound, min_distance, max_distance)

    def apply_directional_filter(self, channel, relative_angle, altitude_diff, distance,
                                   apply_air_absorption=True, apply_occlusion=True,
                                   channel_id=None, dt=0.016):
        """Apply directional audio filter to a channel.

        Creates perception of front/behind and above/below through frequency filtering:
        - Behind: Muffled (lowpass) due to head shadowing - ENHANCED
        - Above: Brighter (less lowpass)
        - Below: Duller (more lowpass)
        - SMOOTH TRANSITIONS: Interpolates changes to prevent jarring audio

        Args:
            channel: FMODChannelWrapper or raw channel
            relative_angle: Angle from forward direction (-180 to 180, 0=front)
            altitude_diff: Altitude difference in meters (positive=above)
            distance: Distance in meters
            apply_air_absorption: If True, apply distance-based air absorption
            apply_occlusion: If True, apply occlusion simulation
            channel_id: Optional unique ID for smooth transition tracking
            dt: Delta time in seconds for interpolation
        """
        self._fmod.apply_directional_filter(
            channel, relative_angle, altitude_diff, distance,
            apply_air_absorption=apply_air_absorption,
            apply_occlusion=apply_occlusion,
            channel_id=channel_id,
            dt=dt
        )

    def calculate_directional_params(self, source_x, source_y, source_altitude,
                                     listener_x, listener_y, listener_altitude,
                                     listener_facing):
        """Calculate directional audio parameters for filtering.

        Args:
            source_x, source_y: Source position
            source_altitude: Source altitude in feet
            listener_x, listener_y: Listener position
            listener_altitude: Listener altitude in feet
            listener_facing: Listener facing angle (degrees, 0=North)

        Returns:
            Tuple of (relative_angle, altitude_diff_meters, distance_meters)
        """
        return self._fmod.calculate_directional_params(
            source_x, source_y, source_altitude,
            listener_x, listener_y, listener_altitude,
            listener_facing
        )

    def update(self):
        """Update audio system (call each frame)."""
        self._fmod.update()

    def update_ducking(self, dt: float):
        """Update ducking system.

        Args:
            dt: Delta time in seconds
        """
        self._fmod.update_ducking(dt)

    def cleanup(self):
        """Clean up audio resources."""
        if self._initialized:
            self.stop_all()
            self._fmod.cleanup()
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if audio is initialized."""
        return self._initialized

    # === HRTF Spatialization ===

    def init_hrtf(self, dll_path: str = None) -> bool:
        """Initialize HRTF spatialization (optional enhancement).

        Attempts to load Steam Audio for true binaural HRTF.
        Falls back to FMOD's native 3D audio if unavailable.

        Args:
            dll_path: Optional path to phonon_fmod.dll

        Returns:
            True if HRTF (or fallback) is enabled
        """
        try:
            from steam_audio import HRTFManager
            self._hrtf = HRTFManager(self)
            if self._hrtf.initialize(dll_path):
                return True
        except ImportError as e:
            print(f"HRTF: steam_audio module not found - {e}")
        except Exception as e:
            print(f"HRTF: Initialization failed - {e}")

        self._hrtf = None
        return False

    @property
    def hrtf(self):
        """Get the HRTF manager (or None if not initialized)."""
        return getattr(self, '_hrtf', None)

    def update_hrtf_listener(self, x: float, y: float, z: float, facing_angle: float):
        """Update HRTF listener position.

        Args:
            x: Player X position (game coords)
            y: Player Y position (game coords)
            z: Player altitude (game coords)
            facing_angle: Facing angle in degrees
        """
        if self.hrtf and self.hrtf.is_enabled:
            self.hrtf.update_listener(x, y, z, facing_angle)
