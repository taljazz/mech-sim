"""
Game State container for MechSimulator.

Holds all mutable game state in a centralized location for easy
reset and state management.
"""

from .constants import (
    HULL_MAX, AMMO_INITIAL, AMMO_MAX, DEBRIS_MAX,
    THRUSTER_ENERGY_MAX, CAMO_ENERGY_MAX, DEFAULT_DRONE_COUNT
)


class GameState:
    """Container for all mutable game state."""

    def __init__(self):
        """Initialize game state with default values."""
        # Configuration settings (persist across game restarts)
        self.config_drone_count = DEFAULT_DRONE_COUNT

        self.reset()

    def reset(self):
        """Reset all game state to initial values."""
        # Player position and orientation
        self.player_x = 0.0
        self.player_y = 0.0
        self.player_altitude = 0.0
        self.facing_angle = 0.0
        self.vertical_velocity = 0.0

        # Player health
        self.player_hull = HULL_MAX
        self.player_hull_max = HULL_MAX

        # Resources
        self.debris_count = 0
        self.ammo = dict(AMMO_INITIAL)  # Copy to avoid mutating constant

        # Thruster state
        self.thrust_level = 0.0
        self.thruster_energy = THRUSTER_ENERGY_MAX
        self.thruster_state = 'idle'
        self.current_pitch_index = -1
        self.boost_active = False
        self.forward_flight_mode = False
        self.vertical_state = 'grounded'
        self.thrusters_depleted = False  # Track if fall is due to energy depletion (for crash landing)
        self.powered_landing_pending = False  # Track powered landing (thrusters active when landing)
        self.last_thrust_milestone = 0

        # Camouflage state
        self.camo_active = False
        self.camo_revealed = False
        self.camo_revealed_end = 0
        self.camo_energy = CAMO_ENERGY_MAX

        # Shield state
        self.shield_active = False
        self.shield_state = 'idle'

        # Weapon state
        self.current_weapon = 1
        self.weapon_state = 'ready'
        self.chaingun_variant = 0
        self.chaingun_state = 'ready'
        self.missile_state = 'ready'
        self.missile_lock_start = 0
        self.missile_last_fire = 0          # For "warm" missile system
        self.missile_lock_required = 1500   # Calculated lock time based on distance
        self.missile_last_beep = 0          # For accelerating beep feedback
        self.missile_target_count = 0       # Targets in range during lock
        self.missile_closest_distance = 0   # Distance to closest target
        self.blaster_last_shot = 0
        self.blaster_state = 'ready'
        self.emp_state = 'ready'
        self.emp_cooldown_start = 0
        self.low_ammo_warned = {1: False, 2: False, 3: False, 4: False, 5: False}

        # Fabrication state
        self.fabricating = False
        self.fabrication_start_time = 0

        # Movement state
        self.step_counter = 0
        self.prev_walking = False
        self.start_with_left = True
        self.last_step_time = 0
        self.rotating = False
        self.rotation_state = 'idle'
        self.last_cardinal_announced = None

        # Malfunctions
        self.malfunction_active = {
            'movement': False,
            'weapons': False,
            'radar': False,
            'thrusters': False
        }
        self.malfunction_end_time = {
            'movement': 0,
            'weapons': 0,
            'radar': 0,
            'thrusters': 0
        }

        # Radar and aiming
        self.last_radar_scan = 0
        self.last_aim_assist_beep = 0
        self.last_target_lock_beep = 0

        # Debris announcement throttle
        self.last_debris_announcement = 0

        # Game flow
        self.game_over = False
        self.game_over_selection = 0
        self.game_over_announced = False
        self.mech_operational = False
        self.startup_state = 'starting'

        # Previous input state (for edge detection)
        self.prev_ctrl = False
        self.prev_shield_key = False

        # DSP tracking
        self.last_hull_for_dsp = HULL_MAX
        self.last_altitude_zone = 'ground'

    def is_malfunctioning(self, system: str) -> bool:
        """Check if a system is malfunctioning.

        Args:
            system: System name (movement, weapons, radar, thrusters)

        Returns:
            True if the system is currently malfunctioning
        """
        return self.malfunction_active.get(system, False)

    def clear_malfunction(self, system: str):
        """Clear a malfunction.

        Args:
            system: System name to clear
        """
        if system in self.malfunction_active:
            self.malfunction_active[system] = False
            self.malfunction_end_time[system] = 0

    def get_ammo(self, weapon: int) -> int:
        """Get current ammo for a weapon.

        Args:
            weapon: Weapon ID (1-5)

        Returns:
            Current ammo count
        """
        return int(self.ammo.get(weapon, 0))

    def use_ammo(self, weapon: int, amount: float) -> bool:
        """Use ammo from a weapon.

        Args:
            weapon: Weapon ID
            amount: Amount to use

        Returns:
            True if there was enough ammo
        """
        if weapon in self.ammo:
            if self.ammo[weapon] >= amount:
                self.ammo[weapon] = max(0, self.ammo[weapon] - amount)
                return True
        return False

    def add_ammo(self, weapon: int, amount: int):
        """Add ammo to a weapon (capped at max).

        Args:
            weapon: Weapon ID
            amount: Amount to add
        """
        if weapon in self.ammo:
            self.ammo[weapon] = min(AMMO_MAX[weapon], self.ammo[weapon] + amount)

    def add_debris(self, amount: int = 1) -> bool:
        """Add debris to inventory.

        Args:
            amount: Amount to add

        Returns:
            True if there was room
        """
        if self.debris_count < DEBRIS_MAX:
            self.debris_count = min(DEBRIS_MAX, self.debris_count + amount)
            return True
        return False

    def use_debris(self, amount: int) -> bool:
        """Use debris from inventory.

        Args:
            amount: Amount to use

        Returns:
            True if there was enough
        """
        if self.debris_count >= amount:
            self.debris_count -= amount
            return True
        return False

    @property
    def is_in_flight(self) -> bool:
        """Check if player is in flight (thrusters active)."""
        return self.thruster_state == 'active'

    @property
    def is_grounded(self) -> bool:
        """Check if player is on the ground."""
        return self.player_altitude <= 0 and self.vertical_state == 'grounded'

    @property
    def hull_percent(self) -> float:
        """Get hull as percentage."""
        return (self.player_hull / self.player_hull_max) * 100

    @property
    def is_camo_effective(self) -> bool:
        """Check if camo is actively hiding the player."""
        return self.camo_active and not self.camo_revealed
