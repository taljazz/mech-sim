"""
Movement System for MechSimulator.

Handles player movement, footsteps, and rotation.
"""

import math
import random

from state.constants import (
    STEP_INTERVAL, PLAYER_SPEED, ROTATION_SPEED,
    LEFT_FOOT_INDICES, RIGHT_FOOT_INDICES,
    DEBRIS_COLLECTION_CHANCE, DEBRIS_ANNOUNCEMENT_COOLDOWN
)
from utils.helpers import get_cardinal_direction, normalize_angle


class MovementSystem:
    """Manages player movement, footsteps, and rotation."""

    def __init__(self, audio_manager, sound_loader, tts, game_state):
        """Initialize the movement system.

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

    def update_rotation(self, keys, dt: float, current_time: int):
        """Update rotation based on Q/E keys.

        Args:
            keys: Pygame key state
            dt: Delta time in seconds
            current_time: Current game time in milliseconds
        """
        import pygame

        q_pressed = keys[pygame.K_q]
        e_pressed = keys[pygame.K_e]

        rotation_direction = 0
        if q_pressed and not e_pressed:
            rotation_direction = -1  # Rotate left
        elif e_pressed and not q_pressed:
            rotation_direction = 1   # Rotate right

        in_flight = self.state.is_in_flight

        if rotation_direction != 0:
            if not self.state.rotating:
                # Start rotating
                self.state.rotating = True
                if not in_flight:
                    channel = self.audio.play_sound('rotation_start', 'movement')
                    self.audio.set_channel('rotation', channel)
                    self.state.rotation_state = 'starting'
                else:
                    self.state.rotation_state = 'rotating'
                print(f"{'Yaw' if in_flight else 'Rotating'} {'left' if rotation_direction == -1 else 'right'}")

            # Update facing angle
            if self.state.rotation_state in ('starting', 'rotating'):
                delta_angle = rotation_direction * ROTATION_SPEED * dt
                self.state.facing_angle = normalize_angle(self.state.facing_angle + delta_angle)

                # Announce cardinal directions when crossing
                cardinal = get_cardinal_direction(self.state.facing_angle)
                if cardinal != self.state.last_cardinal_announced:
                    self.tts.speak(f"Facing {cardinal}")
                    self.state.last_cardinal_announced = cardinal
                    print(f"Facing: {cardinal} ({int(self.state.facing_angle)})")
        else:
            if self.state.rotating and self.state.rotation_state in ('starting', 'rotating'):
                # Stop rotating
                self.state.rotating = False
                if not in_flight:
                    self.audio.stop_channel('rotation')
                    channel = self.audio.play_sound('rotation_end', 'movement')
                    self.audio.set_channel('rotation', channel)
                    self.state.rotation_state = 'stopping'
                    print("Rotation stopping")
                else:
                    self.state.rotation_state = 'idle'

    def update_movement(self, keys, dt: float, current_time: int, reveal_callback=None):
        """Update movement based on WASD keys.

        Args:
            keys: Pygame key state
            dt: Delta time in seconds
            current_time: Current game time in milliseconds
            reveal_callback: Optional callback to reveal camo'd player

        Returns:
            True if player is walking
        """
        import pygame

        walking = False
        direction = ""

        if keys[pygame.K_w]:
            walking = True
            direction = "forward"
        elif keys[pygame.K_s]:
            walking = True
            direction = "backward"

        if keys[pygame.K_a]:
            walking = True
            if not direction:
                direction = "left strafe"
            else:
                direction += " and strafing left"
        elif keys[pygame.K_d]:
            walking = True
            if not direction:
                direction = "right strafe"
            else:
                direction += " and strafing right"

        in_flight = self.state.is_in_flight

        # TTS on movement start (only when grounded)
        if walking and not self.state.prev_walking and not in_flight:
            if "strafe" in direction:
                self.tts.speak(f"{direction}")
                self.state.start_with_left = ("left" in direction)
            else:
                self.tts.speak(f"Moving {direction}")
                self.state.start_with_left = random.choice([True, False])
            self.state.step_counter = 0

        self.state.prev_walking = walking

        # Update position
        if walking:
            move_speed = PLAYER_SPEED

            # Forward flight speed boost
            if in_flight and self.state.forward_flight_mode and self.state.thrust_level > 0:
                flight_speed_multiplier = 1.0 + (self.state.thrust_level * 3.0)
                move_speed = PLAYER_SPEED * flight_speed_multiplier

            if self.state.is_malfunctioning('movement'):
                move_speed *= 0.5

            facing_rad = math.radians(self.state.facing_angle)

            if keys[pygame.K_w]:
                self.state.player_x += math.sin(facing_rad) * move_speed * dt
                self.state.player_y += math.cos(facing_rad) * move_speed * dt
            elif keys[pygame.K_s]:
                self.state.player_x -= math.sin(facing_rad) * move_speed * dt
                self.state.player_y -= math.cos(facing_rad) * move_speed * dt

            if keys[pygame.K_a]:
                strafe_rad = facing_rad - math.pi / 2
                self.state.player_x += math.sin(strafe_rad) * move_speed * dt
                self.state.player_y += math.cos(strafe_rad) * move_speed * dt
            elif keys[pygame.K_d]:
                strafe_rad = facing_rad + math.pi / 2
                self.state.player_x += math.sin(strafe_rad) * move_speed * dt
                self.state.player_y += math.cos(strafe_rad) * move_speed * dt

        # Footsteps (only when grounded)
        if walking and not in_flight and (current_time - self.state.last_step_time > STEP_INTERVAL):
            self._play_footstep(current_time, reveal_callback)

        return walking

    def _play_footstep(self, current_time: int, reveal_callback=None):
        """Play a footstep sound and handle debris collection.

        Args:
            current_time: Current game time
            reveal_callback: Optional callback to reveal camo'd player
        """
        self.state.step_counter += 1
        is_left_foot = (self.state.step_counter % 2 == 1) == self.state.start_with_left

        sound = self.sounds.get_random_footstep(is_left_foot)
        if sound:
            self.audio.play_sound_object(sound, 'movement')
            print(f"STEP: {'left' if is_left_foot else 'right'}")

        self.state.last_step_time = current_time

        # Reveal camo'd player
        if reveal_callback:
            reveal_callback(current_time)

        # Debris collection
        if random.random() < DEBRIS_COLLECTION_CHANCE:
            if self.state.add_debris():
                self.audio.play_sound('debris_collect', 'ui')
                if self.tts.speak_throttled(
                    'debris',
                    f"Debris collected. {self.state.debris_count} pieces.",
                    DEBRIS_ANNOUNCEMENT_COOLDOWN,
                    current_time
                ):
                    pass
                print(f"Debris collected! Total: {self.state.debris_count}")
            else:
                self.audio.play_sound('debris_trash', 'ui')
                print("Debris inventory full!")

    def play_landing_footsteps(self):
        """Play both footsteps simultaneously for landing."""
        left_sound = self.sounds.get_random_footstep(True)
        right_sound = self.sounds.get_random_footstep(False)

        if left_sound:
            self.audio.play_sound_object(left_sound, 'movement')
        if right_sound:
            self.audio.play_sound_object(right_sound, 'movement')

    def check_rotation_transitions(self):
        """Check for rotation sound state transitions."""
        if self.state.rotation_state == 'starting' and self.audio.check_channel_ended('rotation'):
            channel = self.audio.play_sound('rotation_loop', 'movement', loop_count=-1)
            self.audio.set_channel('rotation', channel)
            self.state.rotation_state = 'rotating'
            print("Rotation: Looping")
        elif self.state.rotation_state == 'stopping' and self.audio.check_channel_ended('rotation'):
            self.state.rotation_state = 'idle'
            print("Rotation: Idle")
