"""
Camouflage System for MechSimulator.

Handles stealth plates, energy management, and reveal mechanics.
"""

from state.constants import (
    CAMO_ENERGY_MAX, CAMO_DRAIN_RATE, CAMO_REGEN_RATE,
    CAMO_REVEAL_DURATION, CAMO_REVEAL_EXTEND_MS, CAMO_REVEAL_FOOTSTEP,
    CAMO_CONFUSION_ENABLED, CAMO_CONFUSION_DURATION, CAMO_CONFUSION_LOSE_LOCK_RANGE,
    CAMO_PROXIMITY_WARNING_ENABLED, CAMO_PROXIMITY_WARNING_RANGE, CAMO_PROXIMITY_WARNING_INTERVAL
)


class CamouflageSystem:
    """Manages camouflage/stealth mechanics."""

    def __init__(self, audio_manager, sound_loader, tts, game_state):
        """Initialize the camouflage system.

        Args:
            audio_manager: AudioManager instance
            sound_loader: SoundLoader instance
            tts: TTSManager instance
            game_state: GameState instance
        """
        self.audio = audio_manager
        self.sounds = sound_loader
        self.tts = tts
        self.state = game_state
        self._last_proximity_warning = 0  # For proximity warning cooldown

    def toggle(self, current_time: int):
        """Toggle camouflage on/off.

        Args:
            current_time: Current game time in milliseconds
        """
        # Can't use camo if shield is active
        if self.state.shield_active:
            self.tts.speak("Cannot activate camo while shield is active")
            print("Camo: Shield must be deactivated first")
            return

        if not self.state.camo_active:
            self._activate(current_time)
        else:
            self._deactivate()

    def _activate(self, current_time: int):
        """Activate camouflage."""
        if self.state.camo_energy <= 5:
            self.tts.speak("Camo energy depleted")
            print("Camo: Insufficient energy")
            return

        self.state.camo_active = True
        self.state.camo_revealed = False
        self.state.camo_ambush_ready = True  # First attack gets ambush bonus
        self.tts.speak("Camo engaged")
        print("Camo: Activated - Detection range reduced, ambush ready")

        # Play activation sound
        sound = self.sounds.get_drone_sound('interfaces')
        if sound:
            channel = self.audio.get_channel('player_damage')
            channel.set_volume(0.6 * self.audio.master_volume)
            channel.play(sound)

    def _deactivate(self):
        """Deactivate camouflage."""
        self.state.camo_active = False
        self.state.camo_revealed = False
        self.tts.speak("Camo disengaged")
        print("Camo: Deactivated")

        # Play deactivation sound
        sound = self.sounds.get_drone_sound('interfaces')
        if sound:
            channel = self.audio.get_channel('player_damage')
            channel.set_volume(0.5 * self.audio.master_volume)
            channel.play(sound)

    def reveal(self, current_time: int, reveal_duration: int = None, drone_manager=None):
        """Temporarily reveal the player (from movement/firing while camo'd).

        Implements partial camo recovery - subsequent actions extend reveal
        time instead of resetting to full duration.

        Args:
            current_time: Current game time in milliseconds
            reveal_duration: Custom reveal duration (uses default if None)
            drone_manager: Optional DroneManager to trigger drone confusion
        """
        if not self.state.camo_active:
            return

        duration = reveal_duration if reveal_duration is not None else CAMO_REVEAL_DURATION

        if not self.state.camo_revealed:
            # First reveal - full duration and trigger drone confusion
            self.state.camo_revealed = True
            self.state.camo_revealed_end = current_time + duration
            print("Camo: Temporarily revealed!")

            # Trigger drone confusion when camo is first broken
            if CAMO_CONFUSION_ENABLED and drone_manager:
                self._confuse_drones(drone_manager, current_time)
        else:
            # Already revealed - extend the reveal time instead of reset
            # This makes consecutive actions less punishing
            new_end = self.state.camo_revealed_end + CAMO_REVEAL_EXTEND_MS
            # Cap at current time + full duration to prevent infinite stacking
            max_end = current_time + duration
            self.state.camo_revealed_end = min(new_end, max_end)

    def _confuse_drones(self, drone_manager, current_time: int):
        """Cause drones to briefly lose lock when camo is broken.

        Drones beyond confusion range lose their lock on the player,
        giving a brief window to escape or reposition.

        Args:
            drone_manager: DroneManager instance
            current_time: Current game time
        """
        for drone in drone_manager.drones:
            if drone['state'] in ('detecting', 'engaging', 'winding_up'):
                if drone['distance'] > CAMO_CONFUSION_LOSE_LOCK_RANGE:
                    # Drone loses lock - enters brief confusion
                    drone['confused_until'] = current_time + CAMO_CONFUSION_DURATION
                    drone['state'] = 'searching'
                    drone['state_start'] = current_time
                    print(f"Drone {drone['id']} confused by camo break")

    def update(self, current_time: int, dt: float, drone_manager=None):
        """Update camouflage energy and reveal status.

        Args:
            current_time: Current game time in milliseconds
            dt: Delta time in seconds
            drone_manager: Optional DroneManager to force drones to lose track
        """
        # Energy drain while active
        if self.state.camo_active:
            self.state.camo_energy = max(0, self.state.camo_energy - CAMO_DRAIN_RATE * dt)
            if self.state.camo_energy <= 0:
                self.state.camo_active = False
                self.state.camo_revealed = False
                self.tts.speak("Camo depleted")
                print("Camo: Energy depleted - deactivated")

        # Energy regeneration when inactive
        if not self.state.camo_active and self.state.camo_energy < CAMO_ENERGY_MAX:
            self.state.camo_energy = min(
                CAMO_ENERGY_MAX,
                self.state.camo_energy + CAMO_REGEN_RATE * dt
            )

        # Check reveal timer expiration
        if self.state.camo_revealed and current_time >= self.state.camo_revealed_end:
            self.state.camo_revealed = False
            self.state.camo_ambush_ready = True  # Ambush bonus refreshed on stealth restore
            print("Camo: Stealth restored, ambush ready")

        # Proximity warning - alert player when drone approaches detection range
        if (CAMO_PROXIMITY_WARNING_ENABLED and
            self.state.camo_active and
            not self.state.camo_revealed and
            drone_manager):
            self._check_proximity_warning(drone_manager, current_time)

    def _check_proximity_warning(self, drone_manager, current_time: int):
        """Check if any drone is approaching and play warning ping.

        Provides audio feedback when drones get close while camo is active,
        giving the player awareness of nearby threats without breaking stealth.

        Args:
            drone_manager: DroneManager instance
            current_time: Current game time in milliseconds
        """
        # Check cooldown
        if current_time - self._last_proximity_warning < CAMO_PROXIMITY_WARNING_INTERVAL:
            return

        # Find closest active drone
        closest_distance = float('inf')
        closest_drone = None

        for drone in drone_manager.drones:
            if drone['state'] in ('spawning', 'destroyed'):
                continue
            if drone['distance'] < closest_distance:
                closest_distance = drone['distance']
                closest_drone = drone

        # Play warning if drone within proximity range
        if closest_drone and closest_distance <= CAMO_PROXIMITY_WARNING_RANGE:
            self._last_proximity_warning = current_time

            # Play warning ping (use beacon sound for familiarity)
            sound = self.sounds.get_drone_sound('beacons')
            if sound:
                channel = self.audio.get_channel('player_damage')
                # Volume based on proximity (louder = closer)
                proximity_factor = 1.0 - (closest_distance / CAMO_PROXIMITY_WARNING_RANGE)
                volume = 0.3 + (0.4 * proximity_factor)  # 0.3 to 0.7
                channel.set_volume(volume * self.audio.master_volume)
                channel.play(sound)
                print(f"Camo: Proximity warning - drone at {closest_distance:.1f}m")

    def force_drones_to_lose_track(self, drone_manager, current_time: int, lose_range: float = 15.0):
        """Force engaging drones to lose track when camo activates.

        Args:
            drone_manager: DroneManager instance
            current_time: Current game time
            lose_range: Distance beyond which drones lose track
        """
        for drone in drone_manager.drones:
            if drone['state'] in ('detecting', 'engaging') and drone['distance'] > lose_range:
                drone['state'] = 'searching'
                drone['state_start'] = current_time
                print(f"Drone {drone['id']} lost track due to camo")

    @property
    def is_active(self) -> bool:
        """Check if camo is active."""
        return self.state.camo_active

    @property
    def is_effective(self) -> bool:
        """Check if camo is effectively hiding the player."""
        return self.state.camo_active and not self.state.camo_revealed

    @property
    def energy(self) -> float:
        """Get current camo energy."""
        return self.state.camo_energy

    @property
    def energy_percent(self) -> float:
        """Get camo energy as percentage."""
        return (self.state.camo_energy / CAMO_ENERGY_MAX) * 100
