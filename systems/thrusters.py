"""
Thruster System for MechSimulator.

Handles flight, altitude, thrust control, and vertical physics.
"""

from state.constants import (
    NUM_PITCH_STAGES, THRUST_RATE, THRUSTER_ENERGY_MAX,
    ENERGY_REGEN_RATE, BOOST_THRESHOLD,
    ALTITUDE_MAX, GRAVITY, MAX_LIFT, TERMINAL_VELOCITY,
    HARD_LANDING_THRESHOLD, HARD_LANDING_DAMAGE_FACTOR
)


class ThrusterSystem:
    """Manages thruster and flight mechanics."""

    def __init__(self, audio_manager, sound_loader, tts, game_state):
        """Initialize the thruster system.

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

    def update(self, keys, dt: float, current_time: int, reveal_callback=None) -> dict:
        """Update thruster system.

        Args:
            keys: Pygame key state
            dt: Delta time in seconds
            current_time: Current game time in milliseconds
            reveal_callback: Optional callback to reveal camo'd player

        Returns:
            Dict with any landing information
        """
        import pygame

        result = {'landed': False, 'landing_damage': 0}

        page_up = keys[pygame.K_PAGEUP]
        page_down = keys[pygame.K_PAGEDOWN]
        w_pressed = keys[pygame.K_w]

        # Check for thruster malfunction
        if self.state.is_malfunctioning('thrusters'):
            if self.state.thruster_state == 'active':
                self._force_shutdown()
        else:
            # Determine flight mode
            was_forward_flight = self.state.forward_flight_mode
            self.state.forward_flight_mode = w_pressed and self.state.thruster_state == 'active'

            # Announce flight mode changes
            if self.state.thruster_state == 'active':
                if self.state.forward_flight_mode and not was_forward_flight:
                    self.tts.speak("Forward thrust")
                    print("Flight: Forward thrust engaged")
                elif not self.state.forward_flight_mode and was_forward_flight:
                    self.tts.speak("Hovering")
                    print("Flight: Hovering")

            # Determine thrust direction
            thrust_direction = 0
            if page_up and not page_down:
                thrust_direction = 1
            elif page_down and not page_up:
                thrust_direction = -1

            # Handle thruster activation
            if thrust_direction == 1 and self.state.thruster_state == 'idle' and self.state.thruster_energy > 0:
                self._activate_thrusters(w_pressed)

            # Update thrust level
            if self.state.thruster_state == 'active' and self.state.thruster_energy > 0:
                self._update_thrust(thrust_direction, dt, current_time, reveal_callback)

        # Energy regeneration
        self._update_energy_regen(dt)

        # Freefall physics
        self._update_freefall(dt)

        # Landing detection
        landing_result = self._check_landing()
        if landing_result['landed']:
            result = landing_result

        return result

    def _activate_thrusters(self, w_pressed: bool):
        """Activate thrusters."""
        self.state.thruster_state = 'active'
        self.state.forward_flight_mode = w_pressed
        self.state.thrust_level = 0.02  # Start at 2%

        # Play activation sound
        channel = self.audio.play_sound('thruster_activate', 'thrusters')
        self.audio.set_channel('thruster_activate', channel)

        # Start thruster pitch sound
        thruster_sounds = self.sounds.sounds.get('thrusters', [])
        if thruster_sounds:
            pitch_idx = int(self.state.thrust_level * (NUM_PITCH_STAGES - 1))
            pitch_idx = max(0, min(pitch_idx, len(thruster_sounds) - 1))
            sound = thruster_sounds[pitch_idx]
            channel = self.audio.play_sound_object(sound, 'thrusters', loop_count=-1)
            self.audio.set_channel('thruster_pitch', channel)
            self.state.current_pitch_index = pitch_idx

        self.tts.speak("Thrusters activating")
        print("Thrusters: Active")

    def _force_shutdown(self):
        """Force shutdown thrusters (malfunction)."""
        self.audio.stop_channel('thruster_pitch')
        self.state.thruster_state = 'idle'
        self.state.current_pitch_index = -1
        self.state.thrust_level = 0.0
        self.state.forward_flight_mode = False
        self.state.boost_active = False

    def _update_thrust(self, thrust_direction: int, dt: float, current_time: int, reveal_callback):
        """Update thrust level and related systems."""
        old_thrust = self.state.thrust_level

        if thrust_direction == 1:
            self.state.thrust_level = min(1.0, self.state.thrust_level + THRUST_RATE * dt)
        elif thrust_direction == -1:
            self.state.thrust_level = max(0.0, self.state.thrust_level - THRUST_RATE * dt)

        # Thrusters above 10% reveal camo'd player
        if self.state.thrust_level > 0.10 and reveal_callback:
            reveal_callback(current_time)

        # Check for thrust cutoff
        if self.state.thrust_level <= 0:
            self._deactivate_thrusters(depleted=False)
            return

        # Update pitch sound
        self._update_pitch_sound()

        # Announce thrust milestones
        self._announce_thrust_milestones()

        # Boost status
        self._update_boost_status()

        # Flight physics
        self._update_flight_physics(dt)

        # Energy consumption
        self._update_energy_consumption(dt)

    def _deactivate_thrusters(self, depleted: bool = False):
        """Deactivate thrusters."""
        self.audio.stop_channel('thruster_pitch')
        self.state.thruster_state = 'idle'
        self.state.current_pitch_index = -1
        self.state.thrust_level = 0.0
        self.state.forward_flight_mode = False
        self.state.boost_active = False

        if self.state.player_altitude > 0:
            self.state.vertical_state = 'falling'
            # Track if this fall is due to depletion (for crash landing)
            self.state.thrusters_depleted = depleted
            if depleted:
                channel = self.audio.play_sound('thruster_depleted', 'thrusters')
                self.audio.set_channel('thruster_activate', channel)
                self.tts.speak("Thruster energy depleted, falling!")
                print("Thrusters: Energy depleted - FALLING!")
            else:
                self.tts.speak("Thrusters off, falling")
                print("Thrusters: Off - FALLING!")
        else:
            self.state.vertical_state = 'grounded'
            if depleted:
                channel = self.audio.play_sound('thruster_depleted', 'thrusters')
                self.audio.set_channel('thruster_activate', channel)
                self.tts.speak("Thruster energy depleted")
                print("Thrusters: Energy depleted (Grounded)")
            else:
                self.tts.speak("Thrusters idle")
                print("Thrusters: Idle (Grounded)")

    def _update_pitch_sound(self):
        """Update thruster pitch sound based on thrust level."""
        thruster_sounds = self.sounds.sounds.get('thrusters', [])
        if not thruster_sounds:
            return

        new_pitch_index = int(self.state.thrust_level * (NUM_PITCH_STAGES - 1))
        new_pitch_index = max(0, min(new_pitch_index, len(thruster_sounds) - 1))

        if new_pitch_index != self.state.current_pitch_index:
            self.audio.stop_channel('thruster_pitch')
            sound = thruster_sounds[new_pitch_index]
            channel = self.audio.play_sound_object(sound, 'thrusters', loop_count=-1)
            self.audio.set_channel('thruster_pitch', channel)
            self.state.current_pitch_index = new_pitch_index

    def _announce_thrust_milestones(self):
        """Announce thrust milestones (25%, 50%, 75%, 100%)."""
        thrust_percent = int(self.state.thrust_level * 100)
        milestone = (thrust_percent // 25) * 25

        if milestone > self.state.last_thrust_milestone and milestone > 0:
            self.tts.speak(f"{milestone} percent thrust")
            self.state.last_thrust_milestone = milestone
            print(f"Thrust: {milestone}%")
        elif milestone < self.state.last_thrust_milestone:
            self.state.last_thrust_milestone = milestone

    def _update_boost_status(self):
        """Update boost engaged/disengaged status."""
        if self.state.forward_flight_mode and self.state.thrust_level >= BOOST_THRESHOLD and not self.state.boost_active:
            self.state.boost_active = True
            self.tts.speak("Boost engaged")
            print("BOOST ENGAGED")
        elif (self.state.thrust_level < BOOST_THRESHOLD or not self.state.forward_flight_mode) and self.state.boost_active:
            self.state.boost_active = False
            self.tts.speak("Boost disengaged")
            print("Boost disengaged")

    def _update_flight_physics(self, dt: float):
        """Update vertical physics during powered flight."""
        lift = self.state.thrust_level * MAX_LIFT
        net_acceleration = lift - GRAVITY

        self.state.vertical_velocity += net_acceleration * dt

        if self.state.vertical_velocity < TERMINAL_VELOCITY:
            self.state.vertical_velocity = TERMINAL_VELOCITY

        old_altitude = self.state.player_altitude
        self.state.player_altitude += self.state.vertical_velocity * dt

        # Clamp altitude
        if self.state.player_altitude >= ALTITUDE_MAX:
            self.state.player_altitude = ALTITUDE_MAX
            self.state.vertical_velocity = min(0, self.state.vertical_velocity)
        elif self.state.player_altitude <= 0:
            # Detect powered landing (was airborne, now grounded)
            if old_altitude > 0 and self.state.vertical_state in ('descending', 'hovering', 'ascending'):
                self.state.powered_landing_pending = True
            self.state.player_altitude = 0
            self.state.vertical_velocity = max(0, self.state.vertical_velocity)

        # Update vertical state
        old_vertical = self.state.vertical_state
        if self.state.player_altitude > 0:
            if self.state.vertical_velocity > 2:
                self.state.vertical_state = 'ascending'
            elif self.state.vertical_velocity < -2:
                self.state.vertical_state = 'descending'
            else:
                self.state.vertical_state = 'hovering'

            if self.state.vertical_state != old_vertical:
                if self.state.vertical_state == 'ascending':
                    self.tts.speak("Ascending")
                    print("Vertical: Ascending")
                elif self.state.vertical_state == 'descending':
                    self.tts.speak("Descending")
                    print("Vertical: Descending")
                elif self.state.vertical_state == 'hovering':
                    self.tts.speak("Altitude stable")
                    print("Vertical: Hovering (stable)")

    def _update_energy_consumption(self, dt: float):
        """Update energy drain during thrust."""
        energy_drain = self.state.thrust_level * 3.0 * dt
        self.state.thruster_energy = max(0, self.state.thruster_energy - energy_drain)

        if self.state.thruster_energy <= 0:
            self._deactivate_thrusters(depleted=True)

    def _update_energy_regen(self, dt: float):
        """Regenerate energy when idle or low thrust."""
        if self.state.thruster_state == 'idle' or self.state.thrust_level < 0.1:
            if self.state.thruster_energy < THRUSTER_ENERGY_MAX:
                self.state.thruster_energy = min(
                    THRUSTER_ENERGY_MAX,
                    self.state.thruster_energy + ENERGY_REGEN_RATE * dt
                )

    def _update_freefall(self, dt: float):
        """Update physics during freefall (thrusters off but airborne)."""
        if self.state.thruster_state == 'idle' and self.state.player_altitude > 0:
            self.state.vertical_velocity -= GRAVITY * dt

            if self.state.vertical_velocity < TERMINAL_VELOCITY:
                self.state.vertical_velocity = TERMINAL_VELOCITY

            self.state.player_altitude += self.state.vertical_velocity * dt

            if self.state.vertical_state != 'falling':
                self.state.vertical_state = 'falling'

            # Altitude warnings
            if self.state.player_altitude <= 50 and self.state.player_altitude > 45:
                self.tts.speak("50 feet")
            elif self.state.player_altitude <= 20 and self.state.player_altitude > 15:
                self.tts.speak("20 feet, brace for impact")

    def _check_landing(self) -> dict:
        """Check for landing and calculate damage.

        Handles both freefall landings and powered landings.

        Returns:
            Dict with:
            - 'landed': bool - whether landing occurred
            - 'landing_type': str - 'soft', 'hard', or 'crash'
            - 'landing_damage': int - damage from hard/crash landing
        """
        result = {'landed': False, 'landing_type': None, 'landing_damage': 0}

        # Check for freefall landing (thrusters off)
        freefall_landing = (
            self.state.player_altitude <= 0 and
            self.state.vertical_velocity < -1 and
            self.state.vertical_state in ('falling', 'descending')
        )

        # Check for powered landing (thrusters on, landed during flight)
        powered_landing = self.state.powered_landing_pending

        if freefall_landing or powered_landing:
            self.state.player_altitude = 0
            landing_speed = abs(self.state.vertical_velocity)
            self.state.vertical_velocity = 0
            self.state.vertical_state = 'grounded'
            self.state.powered_landing_pending = False

            result['landed'] = True

            # Determine landing type
            if self.state.thrusters_depleted:
                # Crash: thrusters ran out of energy during descent
                result['landing_type'] = 'crash'
                damage = int(landing_speed * HARD_LANDING_DAMAGE_FACTOR)
                result['landing_damage'] = damage
                self.tts.speak(f"Crash landing, {damage} damage")
                print(f"CRASH LANDING! -{damage} hull (Speed: {landing_speed:.1f} ft/s)")
            elif self.state.thrust_level < 0.10:
                # Hard landing: thrust below 10%
                result['landing_type'] = 'hard'
                if landing_speed > HARD_LANDING_THRESHOLD:
                    damage = int((landing_speed - HARD_LANDING_THRESHOLD) * HARD_LANDING_DAMAGE_FACTOR)
                    result['landing_damage'] = damage
                    self.tts.speak(f"Hard landing, {damage} damage")
                    print(f"HARD LANDING! -{damage} hull (Speed: {landing_speed:.1f} ft/s)")
                else:
                    self.tts.speak("Hard landing")
                    print(f"Hard landing (Speed: {landing_speed:.1f} ft/s)")
            else:
                # Soft landing: thrust >= 10%
                result['landing_type'] = 'soft'
                self.tts.speak("Landed")
                print(f"Soft landing (Speed: {landing_speed:.1f} ft/s)")

            # Clear depleted flag after landing
            self.state.thrusters_depleted = False

        return result
