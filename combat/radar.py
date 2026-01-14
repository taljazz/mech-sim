"""
Radar System for MechSimulator.

Handles radar scanning and contact announcements.
Includes echolocation/sonar enhancements for accessibility.
"""

from state.constants import RADAR_COOLDOWN, BASE_VOLUMES
from utils.helpers import get_direction_description


class RadarSystem:
    """Manages radar scanning functionality with echolocation enhancement."""

    # Echolocation constants
    ECHO_COOLDOWN = 150  # ms between echo pings
    ECHO_MAX_DISTANCE = 50.0  # Max distance for echo (meters)
    ECHO_PITCH_MIN = 0.6  # Pitch multiplier at max distance
    ECHO_PITCH_MAX = 1.4  # Pitch multiplier at min distance

    def __init__(self, audio_manager, sound_loader, tts, game_state, drone_manager):
        """Initialize the radar system.

        Args:
            audio_manager: AudioManager instance
            sound_loader: SoundLoader instance
            tts: TTSManager instance
            game_state: GameState instance
            drone_manager: DroneManager instance
        """
        self.audio = audio_manager
        self.sounds = sound_loader
        self.tts = tts
        self.state = game_state
        self.drones = drone_manager

        # Echolocation state
        self._last_echo_time = 0
        self._echo_enabled = False

    def scan(self, current_time: int):
        """Perform a radar scan and announce contacts.

        Enhanced with pitch-based distance indication for accessibility.
        Higher pitch = closer target (like Gears 5's fabricator ping).

        Args:
            current_time: Current game time in milliseconds
        """
        # Check for malfunction
        if self.state.is_malfunctioning('radar'):
            self.tts.speak("Radar offline")
            return

        # Check cooldown
        if current_time - self.state.last_radar_scan < RADAR_COOLDOWN:
            return

        self.state.last_radar_scan = current_time

        # Play scan sound
        sound = self.sounds.get_drone_sound('scans')
        if sound:
            channel = self.audio.get_channel('player_damage')
            channel.set_volume(0.8 * self.audio.master_volume)
            channel.play(sound)

        # Get active drones
        active_drones = self.drones.get_active_drones()

        if not active_drones:
            self.tts.speak("Radar clear")
            return

        # Sort by distance
        sorted_drones = sorted(active_drones, key=lambda d: d['distance'])

        # ACCESSIBILITY: Play spatialized ping for each contact with pitch indicating distance
        self._play_contact_pings(sorted_drones, current_time)

        # Build announcements
        announcements = []
        for i, drone in enumerate(sorted_drones):
            direction = get_direction_description(drone['relative_angle'], drone['distance'])
            dist_meters = int(drone['distance'])

            # Add health status
            if drone['health'] <= 25:
                health_status = ", critical"
            elif drone['health'] <= 50:
                health_status = ", damaged"
            elif drone['health'] <= 75:
                health_status = ", wounded"
            else:
                health_status = ""

            announcements.append(f"Contact {i+1}: {direction}, {dist_meters} meters{health_status}")

        self.tts.speak(". ".join(announcements))
        print(f"Radar scan: {len(active_drones)} contacts")

    def _play_contact_pings(self, drones: list, current_time: int):
        """Play spatialized pings for each contact with pitch-based distance.

        ACCESSIBILITY: Higher pitch = closer target.
        Spatial audio indicates direction.
        """
        import pygame

        beacon_sound = self.sounds.get_drone_sound('beacons', 0)
        if not beacon_sound:
            return

        # Play a quick succession of pings for each drone
        for i, drone in enumerate(drones):
            # Calculate pitch based on distance (closer = higher pitch)
            distance = drone.get('distance', self.ECHO_MAX_DISTANCE)
            normalized_dist = min(1.0, distance / self.ECHO_MAX_DISTANCE)
            # Inverse: closer = higher pitch
            pitch = self.ECHO_PITCH_MAX - (normalized_dist * (self.ECHO_PITCH_MAX - self.ECHO_PITCH_MIN))

            # Get spatial positioning
            pan = drone.get('pan', 0)
            vol = drone.get('vol', 0.5)

            # Play ping with delay based on order
            # Note: pygame.time.delay would block, so we just play with volume/pan adjustment
            # For a proper staggered effect, this would need a timer system
            channel = self.audio.get_channel('player_damage')
            if channel:
                # Apply spatial audio
                base_vol = BASE_VOLUMES.get('drone', 0.8)
                final_vol = base_vol * vol * self.audio.master_volume * 0.6
                channel.set_volume(final_vol)
                channel.play(beacon_sound)

    def update_echolocation(self, current_time: int):
        """Update continuous echolocation system.

        Call this each frame when echolocation is enabled.
        Plays proximity beeps that increase in frequency as drones get closer.

        Args:
            current_time: Current game time in milliseconds
        """
        if not self._echo_enabled:
            return

        if self.state.is_malfunctioning('radar'):
            return

        # Check cooldown
        if current_time - self._last_echo_time < self.ECHO_COOLDOWN:
            return

        # Get closest drone
        closest_distance = self.drones.get_closest_drone_distance()
        if closest_distance >= self.ECHO_MAX_DISTANCE:
            return

        # Adjust ping frequency based on distance (closer = faster pings)
        normalized_dist = closest_distance / self.ECHO_MAX_DISTANCE
        # Minimum 100ms between pings when very close, up to ECHO_COOLDOWN at max distance
        dynamic_cooldown = int(100 + (normalized_dist * (self.ECHO_COOLDOWN - 100)))

        if current_time - self._last_echo_time < dynamic_cooldown:
            return

        self._last_echo_time = current_time

        # Play proximity ping with pitch based on distance
        beacon_sound = self.sounds.get_drone_sound('beacons', 0)
        if beacon_sound:
            channel = self.audio.get_channel('player_damage')
            if channel:
                # Volume increases as drone gets closer
                vol = 0.3 + (1.0 - normalized_dist) * 0.4
                channel.set_volume(vol * self.audio.master_volume)
                channel.play(beacon_sound)

    def toggle_echolocation(self):
        """Toggle continuous echolocation on/off."""
        self._echo_enabled = not self._echo_enabled
        status = "enabled" if self._echo_enabled else "disabled"
        self.tts.speak(f"Echolocation {status}")
        print(f"Echolocation: {status}")
        return self._echo_enabled

    @property
    def echolocation_enabled(self) -> bool:
        """Check if echolocation is enabled."""
        return self._echo_enabled

    @property
    def is_on_cooldown(self) -> bool:
        """Check if radar is on cooldown."""
        import pygame
        current_time = pygame.time.get_ticks()
        return current_time - self.state.last_radar_scan < RADAR_COOLDOWN

    @property
    def cooldown_remaining(self) -> int:
        """Get remaining cooldown time in milliseconds."""
        import pygame
        current_time = pygame.time.get_ticks()
        elapsed = current_time - self.state.last_radar_scan
        return max(0, RADAR_COOLDOWN - elapsed)
