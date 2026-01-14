"""
Camouflage System for MechSimulator.

Handles stealth plates, energy management, and reveal mechanics.
"""

from state.constants import (
    CAMO_ENERGY_MAX, CAMO_DRAIN_RATE, CAMO_REGEN_RATE,
    CAMO_REVEAL_DURATION
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
        self.tts.speak("Camo engaged")
        print("Camo: Activated - Detection range reduced")

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

    def reveal(self, current_time: int):
        """Temporarily reveal the player (from movement/firing while camo'd).

        Args:
            current_time: Current game time in milliseconds
        """
        if self.state.camo_active and not self.state.camo_revealed:
            self.state.camo_revealed = True
            self.state.camo_revealed_end = current_time + CAMO_REVEAL_DURATION
            print("Camo: Temporarily revealed!")

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
            print("Camo: Stealth restored")

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
