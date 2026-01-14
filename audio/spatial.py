"""
Spatial audio calculations for MechSimulator.

Handles 3D audio positioning, stereo panning, and volume attenuation
based on distance and relative angles.
"""

import math


class SpatialAudio:
    """Handles spatial audio calculations for 3D positioning."""

    def __init__(self, max_distance: float = 50.0, min_distance: float = 2.0):
        """Initialize spatial audio calculator.

        Args:
            max_distance: Maximum audible distance in meters
            min_distance: Distance at which sound is at full volume
        """
        self.max_distance = max_distance
        self.min_distance = min_distance

    def calculate_pan_and_volume(
        self,
        source_x: float,
        source_y: float,
        listener_x: float,
        listener_y: float,
        listener_facing: float,
        source_altitude: float = 0.0,
        listener_altitude: float = 0.0
    ) -> tuple:
        """Calculate stereo pan and volume for a sound source.

        Args:
            source_x: Source X position
            source_y: Source Y position
            listener_x: Listener X position
            listener_y: Listener Y position
            listener_facing: Listener facing angle in degrees (0=North)
            source_altitude: Source altitude in feet
            listener_altitude: Listener altitude in feet

        Returns:
            Tuple of (pan, volume, distance, relative_angle, altitude_diff)
            - pan: -1.0 (full left) to 1.0 (full right)
            - volume: 0.0 to 1.0
            - distance: 2D distance in meters
            - relative_angle: Angle relative to facing (-180 to 180)
            - altitude_diff: Altitude difference (source - listener)
        """
        # Calculate 2D distance
        dx = source_x - listener_x
        dy = source_y - listener_y
        distance = math.sqrt(dx * dx + dy * dy)

        # Calculate altitude difference
        altitude_diff = source_altitude - listener_altitude

        # Calculate angle to source (0=North, 90=East)
        angle_to_source = math.degrees(math.atan2(dx, dy)) % 360

        # Calculate relative angle (-180 to 180)
        relative_angle = (angle_to_source - listener_facing + 180) % 360 - 180

        # Calculate stereo pan from relative angle
        # -90° = full left, +90° = full right
        pan = math.sin(math.radians(relative_angle))
        pan = max(-1.0, min(1.0, pan))

        # Calculate volume based on distance (inverse square with min/max)
        if distance <= self.min_distance:
            volume = 1.0
        elif distance >= self.max_distance:
            volume = 0.0
        else:
            # Inverse square falloff
            normalized_dist = (distance - self.min_distance) / (self.max_distance - self.min_distance)
            volume = 1.0 - (normalized_dist * normalized_dist)
            volume = max(0.0, min(1.0, volume))

        # Altitude affects volume slightly (sounds above/below are slightly muffled)
        if abs(altitude_diff) > 20:
            altitude_factor = max(0.7, 1.0 - abs(altitude_diff) / 200)
            volume *= altitude_factor

        return pan, volume, distance, relative_angle, altitude_diff

    def apply_stereo_pan(self, channel, pan: float, volume: float, base_volume: float, master_volume: float):
        """Apply stereo panning to a channel.

        Args:
            channel: FMODChannelWrapper or similar with set_volume(left, right)
            pan: Pan value from -1.0 (left) to 1.0 (right)
            volume: Distance-based volume (0.0 to 1.0)
            base_volume: Base volume for this sound category
            master_volume: Master volume setting
        """
        final_volume = base_volume * master_volume * volume

        # Calculate left/right volumes from pan
        # pan = -1: left = 1, right = 0
        # pan = 0: left = 1, right = 1
        # pan = +1: left = 0, right = 1
        left_vol = final_volume * min(1.0, 1.0 - pan)
        right_vol = final_volume * min(1.0, 1.0 + pan)

        channel.set_volume(left_vol, right_vol)

    def get_direction_quadrant(self, relative_angle: float) -> str:
        """Get the quadrant description for a relative angle.

        Args:
            relative_angle: Angle relative to facing (-180 to 180)

        Returns:
            Direction string: "front", "right", "left", "behind"
        """
        abs_angle = abs(relative_angle)

        if abs_angle <= 45:
            return "front"
        elif abs_angle <= 135:
            return "right" if relative_angle > 0 else "left"
        else:
            return "behind"
