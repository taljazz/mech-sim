"""
Helper utilities for MechSimulator.

Contains direction calculations, angle normalization, and other
utility functions used across multiple modules.
"""

import math


def normalize_angle(angle: float) -> float:
    """Normalize an angle to 0-360 range.

    Args:
        angle: Angle in degrees

    Returns:
        Angle normalized to 0-360 range
    """
    return angle % 360


def get_cardinal_direction(angle: float) -> str:
    """Get cardinal direction name from angle.

    Args:
        angle: Facing angle in degrees (0=North, 90=East, 180=South, 270=West)

    Returns:
        Cardinal direction string (N, NE, E, SE, S, SW, W, NW)
    """
    angle = normalize_angle(angle)

    if 337.5 <= angle or angle < 22.5:
        return "North"
    elif 22.5 <= angle < 67.5:
        return "Northeast"
    elif 67.5 <= angle < 112.5:
        return "East"
    elif 112.5 <= angle < 157.5:
        return "Southeast"
    elif 157.5 <= angle < 202.5:
        return "South"
    elif 202.5 <= angle < 247.5:
        return "Southwest"
    elif 247.5 <= angle < 292.5:
        return "West"
    elif 292.5 <= angle < 337.5:
        return "Northwest"

    return "North"  # Fallback


def get_direction_description(relative_angle: float, distance: float) -> str:
    """Convert relative angle to TTS-friendly direction with distance.

    Args:
        relative_angle: Angle relative to player facing (-180 to 180)
        distance: Distance in meters

    Returns:
        Human-readable description like "close, ahead left"
    """
    # Distance description
    if distance < 10:
        dist_desc = "close"
    elif distance < 25:
        dist_desc = "medium range"
    else:
        dist_desc = "far"

    # Direction description
    abs_angle = abs(relative_angle)
    if abs_angle <= 22:
        direction = "ahead"
    elif abs_angle <= 67:
        direction = "ahead right" if relative_angle > 0 else "ahead left"
    elif abs_angle <= 112:
        direction = "right" if relative_angle > 0 else "left"
    elif abs_angle <= 157:
        direction = "behind right" if relative_angle > 0 else "behind left"
    else:
        direction = "behind"

    return f"{dist_desc}, {direction}"


def angle_to_vector(angle_degrees: float) -> tuple:
    """Convert angle to unit vector.

    Args:
        angle_degrees: Angle in degrees (0=North, 90=East)

    Returns:
        Tuple (x, y) unit vector
    """
    rad = math.radians(angle_degrees)
    return (math.sin(rad), math.cos(rad))


def vector_to_angle(x: float, y: float) -> float:
    """Convert vector to angle.

    Args:
        x: X component
        y: Y component

    Returns:
        Angle in degrees (0=North, 90=East)
    """
    return math.degrees(math.atan2(x, y)) % 360


def distance_2d(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate 2D distance between two points.

    Args:
        x1, y1: First point
        x2, y2: Second point

    Returns:
        Distance in same units as input
    """
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to a range.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))
