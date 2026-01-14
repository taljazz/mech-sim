"""
Damage System for MechSimulator.

Handles hull damage, malfunctions, and damage effects.
"""

import random

from state.constants import (
    HULL_MAX, MALFUNCTION_DURATION, MALFUNCTION_CHANCE,
    MALFUNCTION_TYPES, HULL_REGEN_RATE, HULL_REGEN_SAFE_DISTANCE
)


class DamageSystem:
    """Manages player damage, hull integrity, and malfunctions."""

    def __init__(self, audio_manager, sound_loader, tts, game_state, shield_system):
        """Initialize the damage system.

        Args:
            audio_manager: AudioManager instance
            sound_loader: SoundLoader instance
            tts: TTSManager instance
            game_state: GameState instance
            shield_system: ShieldSystem instance for damage absorption
        """
        self.audio = audio_manager
        self.sounds = sound_loader
        self.tts = tts
        self.state = game_state
        self.shield = shield_system

    def apply_damage(self, damage: float, current_time: int) -> bool:
        """Apply damage to player, with shield absorption.

        Args:
            damage: Amount of damage to apply
            current_time: Current game time in milliseconds

        Returns:
            True if player is still alive, False if game over
        """
        if self.state.game_over:
            return False

        # Shield absorbs damage first
        remaining_damage = self.shield.absorb_damage(damage)

        if remaining_damage > 0:
            self._apply_hull_damage(remaining_damage, current_time)

        return not self.state.game_over

    def _apply_hull_damage(self, damage: float, current_time: int):
        """Apply damage directly to hull.

        Args:
            damage: Amount of damage to apply
            current_time: Current game time in milliseconds
        """
        self.state.player_hull -= damage

        # Update hull damage audio effects
        self._update_hull_effects()

        # Play mech damaged sound
        sound = self.sounds.get_damaged_sound()
        if sound:
            channel = self.audio.get_channel('player_damage')
            channel.set_volume(self.audio.master_volume)
            channel.play(sound)

        # Critical hit check (15% chance on hull damage)
        if random.random() < MALFUNCTION_CHANCE:
            self._trigger_malfunction(current_time)

        # Announce hull status
        if self.state.player_hull <= 25 and self.state.player_hull > 0:
            self.tts.speak("Hull critical")
            self.audio.start_ducking(duck_volume=0.4, speed=5.0)
        elif self.state.player_hull <= 50 and self.state.player_hull > 25:
            self.tts.speak("Hull damaged")
            self.audio.start_ducking(duck_volume=0.6, speed=4.0)

        # Check for game over
        if self.state.player_hull <= 0:
            self._game_over()

    def _update_hull_effects(self):
        """Update audio DSP effects based on hull damage."""
        if abs(self.state.player_hull - self.state.last_hull_for_dsp) >= 5 or \
           (self.state.player_hull <= 25 and self.state.last_hull_for_dsp > 25):
            self.audio.set_hull_damage_effect(self.state.player_hull)
            self.state.last_hull_for_dsp = self.state.player_hull

            if self.state.player_hull <= 25 and not self.audio.is_ducking():
                self.audio.start_ducking(duck_volume=0.5, speed=3.0)

    def _trigger_malfunction(self, current_time: int):
        """Trigger a random system malfunction.

        Args:
            current_time: Current game time in milliseconds
        """
        system = random.choice(MALFUNCTION_TYPES)

        if not self.state.malfunction_active[system]:
            self.state.malfunction_active[system] = True
            self.state.malfunction_end_time[system] = current_time + MALFUNCTION_DURATION

            # Play malfunction sound
            sound = self.sounds.get_drone_sound('malfunctions')
            if sound:
                channel = self.audio.get_channel('player_damage')
                channel.set_volume(0.8 * self.audio.master_volume)
                channel.play(sound)

            messages = {
                'movement': "Movement systems damaged",
                'weapons': "Weapons offline",
                'radar': "Radar malfunction",
                'thrusters': "Thruster damage"
            }
            self.tts.speak(messages[system])
            print(f"MALFUNCTION: {system}")

    def update_malfunctions(self, current_time: int):
        """Check and clear expired malfunctions.

        Args:
            current_time: Current game time in milliseconds
        """
        for system in self.state.malfunction_active:
            if self.state.malfunction_active[system] and \
               current_time >= self.state.malfunction_end_time[system]:
                self.state.malfunction_active[system] = False
                self.tts.speak(f"{system.capitalize()} restored")
                print(f"Malfunction cleared: {system}")

    def update_hull_regen(self, dt: float, closest_drone_distance: float):
        """Update hull regeneration when safe.

        Args:
            dt: Delta time in seconds
            closest_drone_distance: Distance to nearest drone (999 if none)
        """
        if closest_drone_distance > HULL_REGEN_SAFE_DISTANCE and \
           self.state.player_hull < HULL_MAX:
            old_hull = self.state.player_hull
            self.state.player_hull = min(HULL_MAX, self.state.player_hull + HULL_REGEN_RATE * dt)

            # Update DSP effects as hull regenerates
            if int(self.state.player_hull / 10) != int(old_hull / 10):
                self._update_hull_effects()
                if self.state.player_hull > 50 and self.audio.is_ducking():
                    self.audio.stop_ducking(speed=2.0)

    def _game_over(self):
        """Handle game over state."""
        self.state.player_hull = 0
        self.state.game_over = True
        self.state.game_over_selection = 0
        self.state.game_over_announced = False

        # Clear damage effects
        self.audio.set_hull_damage_effect(100)

        # Stop all sounds
        self.audio.stop_all()

        self.tts.speak("Hull breach. Mech destroyed.")
        print("GAME OVER - Hull destroyed")

    def apply_landing_damage(self, damage: int):
        """Apply landing damage.

        Args:
            damage: Amount of damage from hard landing
        """
        self.state.player_hull = max(0, self.state.player_hull - damage)
        if self.state.player_hull <= 0:
            self._game_over()

    @property
    def hull(self) -> float:
        """Get current hull value."""
        return self.state.player_hull

    @property
    def hull_percent(self) -> float:
        """Get hull as percentage."""
        return (self.state.player_hull / HULL_MAX) * 100

    @property
    def is_dead(self) -> bool:
        """Check if player is dead."""
        return self.state.player_hull <= 0
