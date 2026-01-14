"""
Shield System for MechSimulator.

Handles shield activation, energy management, and damage absorption.
"""

from state.constants import (
    WEAPON_SHIELD, SHIELD_DRAIN_RATE, SHIELD_REGEN_RATE,
    SHIELD_ABSORPTION, AMMO_MAX
)


class ShieldSystem:
    """Manages shield mechanics."""

    def __init__(self, audio_manager, tts, game_state):
        """Initialize the shield system.

        Args:
            audio_manager: AudioManager instance
            tts: TTSManager instance
            game_state: GameState instance
        """
        self.audio = audio_manager
        self.tts = tts
        self.state = game_state
        self._shield_channel = audio_manager.get_channel('shield')

    def activate(self):
        """Attempt to activate the shield."""
        if self.state.shield_state != 'idle':
            return False

        if self.state.ammo[WEAPON_SHIELD] <= 0:
            self.tts.speak("Shield energy depleted")
            return False

        self._shield_channel.play('shield_startstop')
        self.state.shield_state = 'activating'
        self.state.shield_active = True
        self.tts.speak("Shield activating")
        print("Shield: Activating")
        return True

    def deactivate(self):
        """Deactivate the shield."""
        if self.state.shield_state not in ('activating', 'active'):
            return False

        self.audio.stop_channel('shield')
        self._shield_channel.play('shield_startstop')
        self.state.shield_state = 'deactivating'
        self.state.shield_active = False
        self.tts.speak("Shield down")
        print("Shield: Deactivating")
        return True

    def update(self, dt: float):
        """Update shield energy consumption and regeneration.

        Args:
            dt: Delta time in seconds
        """
        # Consume energy while active
        if self.state.shield_state in ('activating', 'active'):
            self.state.ammo[WEAPON_SHIELD] = max(
                0,
                self.state.ammo[WEAPON_SHIELD] - SHIELD_DRAIN_RATE * dt
            )

            if self.state.ammo[WEAPON_SHIELD] <= 0:
                self._deplete()

        # Regenerate when not active (shield is now equipment, always regens when inactive)
        if self.state.shield_state in ('idle', 'deactivating'):
            self.state.ammo[WEAPON_SHIELD] = min(
                AMMO_MAX[WEAPON_SHIELD],
                self.state.ammo[WEAPON_SHIELD] + SHIELD_REGEN_RATE * dt
            )

    def _deplete(self):
        """Handle shield depletion."""
        self.audio.stop_channel('shield')
        self._shield_channel.play('shield_startstop')
        self.state.shield_state = 'deactivating'
        self.state.shield_active = False
        self.tts.speak("Shield depleted")
        print("Shield: Energy depleted!")

    def absorb_damage(self, damage: float) -> float:
        """Absorb damage through shield.

        Args:
            damage: Incoming damage amount

        Returns:
            Damage remaining after shield absorption
        """
        if not self.state.shield_active or self.state.ammo[WEAPON_SHIELD] <= 0:
            return damage

        # Shield absorbs SHIELD_ABSORPTION (80%) of damage
        absorbed = min(self.state.ammo[WEAPON_SHIELD], damage * SHIELD_ABSORPTION)
        self.state.ammo[WEAPON_SHIELD] -= absorbed
        remaining_damage = damage - absorbed

        if self.state.ammo[WEAPON_SHIELD] <= 0:
            self._collapse()

        return remaining_damage

    def _collapse(self):
        """Handle shield collapse from damage."""
        self.audio.stop_channel('shield')
        self._shield_channel.play('shield_startstop')
        self.state.shield_state = 'deactivating'
        self.state.shield_active = False
        self.tts.speak("Shield collapsed")
        print("Shield: Collapsed!")

    def check_transitions(self):
        """Check for shield sound state transitions."""
        if self.state.shield_state == 'activating' and self.audio.check_channel_ended('shield'):
            channel = self.audio.play_sound('shield_loop', 'weapons', loop_count=-1)
            self.audio.set_channel('shield', channel)
            self.state.shield_state = 'active'
            print("Shield: Active")
        elif self.state.shield_state == 'deactivating' and self.audio.check_channel_ended('shield'):
            self.state.shield_state = 'idle'
            print("Shield: Idle")

    @property
    def is_active(self) -> bool:
        """Check if shield is currently active."""
        return self.state.shield_active

    @property
    def energy(self) -> float:
        """Get current shield energy."""
        return self.state.ammo[WEAPON_SHIELD]

    @property
    def energy_percent(self) -> float:
        """Get shield energy as percentage."""
        return (self.state.ammo[WEAPON_SHIELD] / AMMO_MAX[WEAPON_SHIELD]) * 100
