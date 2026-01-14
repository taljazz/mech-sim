"""
Drone entity for MechSimulator.

Represents an individual enemy combat drone.
"""

import math
import random

from state.constants import (
    DRONE_BASE_SPEED, DRONE_CLIMB_RATE, DRONE_WEAPONS,
    DRONE_DETECT_RANGE, DRONE_LOSE_TRACK_RANGE, DRONE_REACQUIRE_RANGE,
    DRONE_ATTACK_RANGE, DRONE_CAMO_DETECT_RANGE, DRONE_CAMO_LOSE_TRACK_RANGE,
    DRONE_CAMO_REACQUIRE_RANGE, DRONE_SPAWN_STATE_DURATION,
    DRONE_DETECT_STATE_DURATION, DRONE_ATTACK_STATE_DURATION,
    DRONE_COOLDOWN_MIN, DRONE_COOLDOWN_MAX, DRONE_SEARCH_TIMEOUT,
    ALTITUDE_MAX, DRONE_ENGAGE_SPEED_MULT, DRONE_EVASION_SPEED, DRONE_EVASION_ANGLE
)


class Drone:
    """Represents an enemy combat drone."""

    def __init__(self, drone_id: int, x: float, y: float, spawn_distance: float):
        """Initialize a drone.

        Args:
            drone_id: Unique drone ID (0 or 1)
            x: Spawn X position
            y: Spawn Y position
            spawn_distance: Initial distance from player
        """
        self.id = drone_id
        self.x = x
        self.y = y
        self.altitude = random.uniform(30, 80)  # 30-80 ft altitude

        self.health = 100.0
        self.state = 'spawning'
        self.state_start = 0

        self.speed = DRONE_BASE_SPEED + random.uniform(-1, 1)
        self.climb_rate = DRONE_CLIMB_RATE
        self.attack_cooldown = 0

        # Tracking data
        self.distance = spawn_distance
        self.relative_angle = 0.0
        self.altitude_diff = 0.0
        self.last_known_x = x
        self.last_known_y = y
        self.patrol_target = (x, y)

        # Evasion state
        self.evasion_direction = random.choice([-1, 1])  # Left or right
        self.evasion_timer = 0
        self.flank_angle_offset = 0  # Angle offset for flanking maneuvers

        # Audio tracking
        self.last_sound_update = 0

    def to_dict(self) -> dict:
        """Convert drone to dictionary (for compatibility with existing code).

        Returns:
            Dictionary representation of drone state
        """
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'altitude': self.altitude,
            'health': self.health,
            'state': self.state,
            'state_start': self.state_start,
            'speed': self.speed,
            'climb_rate': self.climb_rate,
            'attack_cooldown': self.attack_cooldown,
            'distance': self.distance,
            'relative_angle': self.relative_angle,
            'altitude_diff': self.altitude_diff,
            'last_known_x': self.last_known_x,
            'last_known_y': self.last_known_y,
            'patrol_target': self.patrol_target,
            'last_sound_update': self.last_sound_update,
            'evasion_direction': self.evasion_direction,
            'evasion_timer': self.evasion_timer,
            'flank_angle_offset': self.flank_angle_offset
        }

    @staticmethod
    def from_dict(data: dict) -> 'Drone':
        """Create drone from dictionary.

        Args:
            data: Dictionary with drone data

        Returns:
            Drone instance
        """
        drone = Drone(data['id'], data['x'], data['y'], data.get('distance', 50))
        drone.altitude = data.get('altitude', 50)
        drone.health = data.get('health', 100)
        drone.state = data.get('state', 'spawning')
        drone.state_start = data.get('state_start', 0)
        drone.speed = data.get('speed', DRONE_BASE_SPEED)
        drone.climb_rate = data.get('climb_rate', DRONE_CLIMB_RATE)
        drone.attack_cooldown = data.get('attack_cooldown', 0)
        drone.relative_angle = data.get('relative_angle', 0)
        drone.altitude_diff = data.get('altitude_diff', 0)
        drone.last_known_x = data.get('last_known_x', drone.x)
        drone.last_known_y = data.get('last_known_y', drone.y)
        drone.patrol_target = data.get('patrol_target', (drone.x, drone.y))
        drone.last_sound_update = data.get('last_sound_update', 0)
        drone.evasion_direction = data.get('evasion_direction', random.choice([-1, 1]))
        drone.evasion_timer = data.get('evasion_timer', 0)
        drone.flank_angle_offset = data.get('flank_angle_offset', 0)
        return drone

    def move_toward(self, target_x: float, target_y: float, dt: float) -> bool:
        """Move drone toward a target position.

        Args:
            target_x: Target X position
            target_y: Target Y position
            dt: Delta time in seconds

        Returns:
            True if reached target
        """
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.5:
            return True

        move_dist = self.speed * dt
        if move_dist > dist:
            move_dist = dist

        self.x += (dx / dist) * move_dist
        self.y += (dy / dist) * move_dist
        return False

    def move_with_evasion(self, target_x: float, target_y: float, player_facing: float,
                          dt: float) -> None:
        """Move toward target while evading if player is aiming at drone.

        Args:
            target_x: Target X position (player)
            target_y: Target Y position (player)
            player_facing: Player's facing angle in degrees
            dt: Delta time in seconds
        """
        # Check if player is aiming at this drone
        being_aimed_at = abs(self.relative_angle) < DRONE_EVASION_ANGLE

        if being_aimed_at:
            # Perform evasive maneuver - strafe perpendicular to player
            # Calculate perpendicular direction
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 0.5:
                # Perpendicular vector (rotated 90 degrees)
                perp_x = -dy / dist
                perp_y = dx / dist

                # Evasion movement
                evasion_dist = DRONE_EVASION_SPEED * dt * self.evasion_direction
                self.x += perp_x * evasion_dist
                self.y += perp_y * evasion_dist

                # Update evasion timer and occasionally change direction
                self.evasion_timer += dt
                if self.evasion_timer > 0.5:  # Change direction every 0.5 seconds
                    self.evasion_timer = 0
                    self.evasion_direction *= -1

                # Still move toward player but slower
                toward_dist = self.speed * DRONE_ENGAGE_SPEED_MULT * 0.5 * dt
                self.x += (dx / dist) * toward_dist
                self.y += (dy / dist) * toward_dist
        else:
            # Not being aimed at - aggressive pursuit
            self.move_toward(target_x, target_y, dt)

    def move_flanking(self, player_x: float, player_y: float, other_drone_angle: float,
                      dt: float) -> None:
        """Move to flank position relative to another drone.

        Args:
            player_x: Player X position
            player_y: Player Y position
            other_drone_angle: Angle of the other drone relative to player (degrees)
            dt: Delta time in seconds
        """
        # Calculate opposite angle for flanking (180 degrees offset)
        flank_angle = (other_drone_angle + 180) % 360

        # Target position at optimal attack range but on opposite side
        flank_distance = 20  # Optimal flanking distance
        angle_rad = math.radians(flank_angle)

        target_x = player_x + flank_distance * math.sin(angle_rad)
        target_y = player_y + flank_distance * math.cos(angle_rad)

        # Move toward flanking position with increased speed
        old_speed = self.speed
        self.speed *= DRONE_ENGAGE_SPEED_MULT
        self.move_toward(target_x, target_y, dt)
        self.speed = old_speed

    def adjust_altitude(self, target_altitude: float, dt: float):
        """Adjust drone altitude toward target.

        Args:
            target_altitude: Target altitude in feet
            dt: Delta time in seconds
        """
        alt_diff = target_altitude - self.altitude
        if abs(alt_diff) > 5:
            if alt_diff > 0:
                self.altitude = min(ALTITUDE_MAX, self.altitude + self.climb_rate * dt)
            else:
                self.altitude = max(0, self.altitude - self.climb_rate * dt)

    def take_damage(self, amount: float) -> bool:
        """Apply damage to drone.

        Args:
            amount: Damage amount

        Returns:
            True if drone is destroyed
        """
        self.health -= amount
        return self.health <= 0

    def select_weapon(self) -> str:
        """Select best weapon based on current distance.

        Returns:
            Weapon type string or None if out of range
        """
        if self.distance <= 15:
            return 'pulse_cannon'
        elif self.distance <= 25:
            return 'plasma_launcher'
        elif self.distance <= 40:
            return 'rail_gun'
        return None

    def get_detection_ranges(self, camo_effective: bool) -> tuple:
        """Get detection ranges based on camo state.

        Args:
            camo_effective: Whether player camo is effective

        Returns:
            Tuple of (detect_range, lose_track_range, reacquire_range)
        """
        if camo_effective:
            return DRONE_CAMO_DETECT_RANGE, DRONE_CAMO_LOSE_TRACK_RANGE, DRONE_CAMO_REACQUIRE_RANGE
        return DRONE_DETECT_RANGE, DRONE_LOSE_TRACK_RANGE, DRONE_REACQUIRE_RANGE

    def update_state(self, player_x: float, player_y: float, player_altitude: float,
                     camo_effective: bool, current_time: int, dt: float,
                     on_detect=None, on_engage=None, on_lost=None, on_reacquire=None,
                     on_attack=None) -> str:
        """Update drone state machine.

        Args:
            player_x: Player X position
            player_y: Player Y position
            player_altitude: Player altitude
            camo_effective: Whether player camo is effective
            current_time: Current game time in milliseconds
            dt: Delta time in seconds
            on_detect: Callback when drone detects player
            on_engage: Callback when drone engages player
            on_lost: Callback when drone loses player
            on_reacquire: Callback when drone reacquires player
            on_attack: Callback when drone attacks player

        Returns:
            Current state name
        """
        detect_range, lose_track_range, reacquire_range = self.get_detection_ranges(camo_effective)

        if self.state == 'spawning':
            if current_time - self.state_start >= DRONE_SPAWN_STATE_DURATION:
                self.state = 'patrol'
                self.patrol_target = self._generate_patrol_point(player_x, player_y)
                self.state_start = current_time

        elif self.state == 'patrol':
            reached = self.move_toward(*self.patrol_target, dt)
            if reached:
                self.patrol_target = self._generate_patrol_point(player_x, player_y)

            if self.distance <= detect_range:
                self.state = 'detecting'
                self.state_start = current_time
                self.last_known_x = player_x
                self.last_known_y = player_y
                if on_detect:
                    on_detect(self)

        elif self.state == 'detecting':
            self.last_known_x = player_x
            self.last_known_y = player_y
            if current_time - self.state_start >= DRONE_DETECT_STATE_DURATION:
                self.state = 'engaging'
                self.state_start = current_time
                if on_engage:
                    on_engage(self)

        elif self.state == 'engaging':
            # Aggressive pursuit with evasion when being aimed at
            old_speed = self.speed
            self.speed *= DRONE_ENGAGE_SPEED_MULT  # Faster pursuit
            self.move_with_evasion(player_x, player_y, 0, dt)  # 0 for player_facing (relative_angle handles this)
            self.speed = old_speed

            # Adjust altitude to match player
            self.adjust_altitude(player_altitude, dt)

            self.last_known_x = player_x
            self.last_known_y = player_y

            if self.distance > lose_track_range:
                self.state = 'searching'
                self.state_start = current_time
                if on_lost:
                    on_lost(self)
            elif self.distance <= DRONE_ATTACK_RANGE:
                self.state = 'attacking'
                self.state_start = current_time
                if on_attack:
                    on_attack(self)

        elif self.state == 'searching':
            reached = self.move_toward(self.last_known_x, self.last_known_y, dt)

            if self.distance <= reacquire_range:
                self.state = 'detecting'
                self.state_start = current_time
                self.last_known_x = player_x
                self.last_known_y = player_y
                if on_reacquire:
                    on_reacquire(self)
            elif reached or (current_time - self.state_start >= DRONE_SEARCH_TIMEOUT):
                self.state = 'patrol'
                self.patrol_target = self._generate_patrol_point(player_x, player_y)
                self.state_start = current_time

        elif self.state == 'attacking':
            if current_time - self.state_start >= DRONE_ATTACK_STATE_DURATION:
                self.state = 'cooldown'
                self.state_start = current_time

        elif self.state == 'cooldown':
            cooldown_duration = random.randint(DRONE_COOLDOWN_MIN, DRONE_COOLDOWN_MAX)
            if current_time - self.state_start >= cooldown_duration:
                if self.distance <= lose_track_range:
                    self.state = 'engaging'
                    self.last_known_x = player_x
                    self.last_known_y = player_y
                else:
                    self.state = 'searching'
                self.state_start = current_time

        return self.state

    def _generate_patrol_point(self, player_x: float, player_y: float) -> tuple:
        """Generate a new patrol waypoint around player.

        Args:
            player_x: Player X position
            player_y: Player Y position

        Returns:
            Tuple of (x, y) coordinates
        """
        patrol_distance = random.uniform(25, 35)
        patrol_angle = random.uniform(0, 360)
        angle_rad = math.radians(patrol_angle)
        return (
            player_x + patrol_distance * math.sin(angle_rad),
            player_y + patrol_distance * math.cos(angle_rad)
        )

    @property
    def is_destroyed(self) -> bool:
        """Check if drone is destroyed."""
        return self.state == 'destroyed' or self.health <= 0

    @property
    def is_active(self) -> bool:
        """Check if drone is active (not destroyed)."""
        return self.state != 'destroyed' and self.health > 0
