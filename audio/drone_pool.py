"""Drone Audio Pool for MechSimulator.

Manages pooled audio channels for drone entities with:
- 4 channels per drone (ambient, combat, weapon, debris)
- Crossfade support for smooth sound transitions
- Proper lifecycle management
"""

from typing import Dict, Optional, List
from fmod_audio import FMODChannelWrapper
from audio.logging import audio_log


class DroneAudioPool:
    """Pool-based audio channel management for drones.

    Provides 7 channels per drone for better sound separation:
    - ambient: General ambient/idle sounds
    - combat: Combat engagement sounds (beacons, scans, detection)
    - weapon: Weapon fire sounds (pulse, plasma, rail)
    - debris: Destruction sounds (explosion, debris)
    - takeoff: Drone spawn/launch sounds (plays independently)
    - passby: Patrol movement sounds (plays independently)
    - supersonic: Engaging/aggressive movement sounds (plays independently)
    """

    CHANNEL_TYPES = ['ambient', 'combat', 'weapon', 'debris', 'takeoff', 'passby', 'supersonic']

    def __init__(self, fmod_audio, max_drones: int = 6):
        """Initialize drone audio pool.

        Args:
            fmod_audio: MechAudio instance (low-level FMOD wrapper)
            max_drones: Maximum number of drones to support
        """
        self.fmod = fmod_audio
        self.max_drones = max_drones
        self._channels: Dict[int, Dict[str, FMODChannelWrapper]] = {}
        self._active_drones: set = set()
        self._initialized = False

        audio_log('INFO', f"DroneAudioPool created", {'max_drones': max_drones})

    def initialize(self, hrtf_manager=None):
        """Create channel wrappers for all potential drones.

        Call this after audio system is initialized but before
        any drones spawn.

        Args:
            hrtf_manager: Optional HRTFManager for Steam Audio spatialization
        """
        if self._initialized:
            return

        self._hrtf_manager = hrtf_manager
        hrtf_enabled = hrtf_manager and hrtf_manager.is_enabled

        audio_log('INFO', f"Initializing drone audio pool", {
            'max_drones': self.max_drones,
            'channels_per_drone': len(self.CHANNEL_TYPES),
            'hrtf_enabled': hrtf_enabled
        })

        for drone_id in range(self.max_drones):
            self._channels[drone_id] = {}
            for channel_type in self.CHANNEL_TYPES:
                name = f'drone_{drone_id}_{channel_type}'
                wrapper = FMODChannelWrapper(
                    self.fmod,
                    'drones',  # Channel group
                    name,
                    is_3d=True  # All drone channels use 3D positioning
                )

                # Enable HRTF if available
                if hrtf_enabled:
                    wrapper.enable_hrtf(hrtf_manager, name)

                self._channels[drone_id][channel_type] = wrapper
                audio_log('DEBUG', f"Created channel", {
                    'drone_id': drone_id,
                    'channel_type': channel_type,
                    'name': name,
                    'hrtf': hrtf_enabled
                })

        self._initialized = True
        total_channels = self.max_drones * len(self.CHANNEL_TYPES)
        audio_log('INFO', f"Drone audio pool initialized", {
            'total_channels': total_channels,
            'hrtf': hrtf_enabled
        })
        print(f"Drone audio pool: {self.max_drones} drones, {total_channels} channels")

    def get_channels(self, drone_id: int) -> Optional[Dict[str, FMODChannelWrapper]]:
        """Get all channels for a drone.

        Args:
            drone_id: The drone's ID

        Returns:
            Dict with channel wrappers keyed by type, or None if invalid ID
        """
        if not self._initialized:
            self.initialize()
        return self._channels.get(drone_id)

    def get_channel(self, drone_id: int, channel_type: str) -> Optional[FMODChannelWrapper]:
        """Get a specific channel for a drone.

        Args:
            drone_id: The drone's ID
            channel_type: One of 'ambient', 'combat', 'weapon', 'debris'

        Returns:
            FMODChannelWrapper or None if not found
        """
        channels = self.get_channels(drone_id)
        if channels:
            return channels.get(channel_type)
        return None

    def activate_drone(self, drone_id: int):
        """Mark a drone as active (spawned).

        Args:
            drone_id: The drone's ID
        """
        if drone_id >= self.max_drones:
            audio_log('WARNING', f"Drone ID exceeds pool size", {
                'drone_id': drone_id,
                'max_drones': self.max_drones
            })
            return

        if drone_id not in self._active_drones:
            self._active_drones.add(drone_id)
            audio_log('DEBUG', f"Drone activated in audio pool", {'drone_id': drone_id})

    def deactivate_drone(self, drone_id: int):
        """Mark a drone as inactive and stop all its sounds.

        Args:
            drone_id: The drone's ID
        """
        if drone_id in self._active_drones:
            self._active_drones.discard(drone_id)
            self.stop_all_channels(drone_id)
            audio_log('DEBUG', f"Drone deactivated in audio pool", {'drone_id': drone_id})

    def stop_all_channels(self, drone_id: int):
        """Stop all audio channels for a drone.

        Args:
            drone_id: The drone's ID
        """
        channels = self.get_channels(drone_id)
        if not channels:
            return

        for channel_type, channel in channels.items():
            if channel.get_busy() or channel.is_fading():
                channel.stop()
                audio_log('DEBUG', f"Stopped channel", {
                    'drone_id': drone_id,
                    'channel_type': channel_type
                })

    def stop_channel(self, drone_id: int, channel_type: str):
        """Stop a specific channel for a drone.

        Args:
            drone_id: The drone's ID
            channel_type: The channel type to stop
        """
        channel = self.get_channel(drone_id, channel_type)
        if channel and (channel.get_busy() or channel.is_fading()):
            channel.stop()
            audio_log('DEBUG', f"Stopped specific channel", {
                'drone_id': drone_id,
                'channel_type': channel_type
            })

    def update_fades(self, dt: float):
        """Update all active drone channel crossfades.

        Call this each frame.

        Args:
            dt: Delta time in seconds
        """
        for drone_id in self._active_drones:
            channels = self._channels.get(drone_id)
            if channels:
                for channel in channels.values():
                    if channel.is_fading():
                        channel.update_fade(dt)

    def is_drone_silent(self, drone_id: int) -> bool:
        """Check if all channels for a drone are silent.

        Use this for cleanup checks - only remove drone when all
        sounds have finished playing.

        Args:
            drone_id: The drone's ID

        Returns:
            True if all channels are silent (not playing and not fading)
        """
        channels = self.get_channels(drone_id)
        if not channels:
            return True

        for channel in channels.values():
            if channel.get_busy() or channel.is_fading():
                return False
        return True

    def is_channel_busy(self, drone_id: int, channel_type: str) -> bool:
        """Check if a specific drone channel is busy.

        Args:
            drone_id: The drone's ID
            channel_type: The channel type to check

        Returns:
            True if channel is playing or fading
        """
        channel = self.get_channel(drone_id, channel_type)
        if not channel:
            return False
        return channel.get_busy() or channel.is_fading()

    @property
    def active_count(self) -> int:
        """Get the number of currently active drones."""
        return len(self._active_drones)

    @property
    def active_drone_ids(self) -> List[int]:
        """Get list of active drone IDs."""
        return list(self._active_drones)

    def get_pool_status(self) -> dict:
        """Get status information about the pool.

        Returns:
            Dict with pool status information
        """
        busy_channels = 0
        fading_channels = 0

        for drone_id, channels in self._channels.items():
            for channel in channels.values():
                if channel.is_fading():
                    fading_channels += 1
                elif channel.get_busy():
                    busy_channels += 1

        return {
            'max_drones': self.max_drones,
            'active_drones': self.active_count,
            'total_channels': self.max_drones * len(self.CHANNEL_TYPES),
            'busy_channels': busy_channels,
            'fading_channels': fading_channels,
            'initialized': self._initialized
        }

    def cleanup(self):
        """Stop all sounds and clean up the pool."""
        audio_log('INFO', "Cleaning up drone audio pool")

        for drone_id in list(self._active_drones):
            self.deactivate_drone(drone_id)

        self._channels.clear()
        self._active_drones.clear()
        self._initialized = False
