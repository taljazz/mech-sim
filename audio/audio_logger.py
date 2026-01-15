"""
Audio Logging System for MechSimulator.

Provides detailed logging of audio events to help understand and debug
the spatial audio, HRTF, occlusion, and other audio processing systems.

Usage:
    from audio.audio_logger import audio_log, set_audio_logging

    # Enable/disable logging
    set_audio_logging(True)

    # Log events
    audio_log.spatial("Drone 0", pan=0.5, volume=0.8, distance=25.3)
    audio_log.occlusion("Drone 0", angle=135, cutoff=3500, rear_factor=0.6)
    audio_log.ducking("TTS", duck_volume=0.4, speed=8.0)

Toggle logging with 'L' key in-game (if implemented in main.py).
"""

import time
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class LogCategory(Enum):
    """Categories for audio logging."""
    SPATIAL = "SPATIAL"      # 3D positioning, pan, volume
    OCCLUSION = "OCCLUSION"  # Directional filtering, head shadow
    REVERB = "REVERB"        # Distance-based reverb
    PITCH = "PITCH"          # Dynamic pitch variation
    DUCKING = "DUCKING"      # Audio ducking for TTS/combat
    ROLLOFF = "ROLLOFF"      # Distance attenuation
    HRTF = "HRTF"            # Steam Audio HRTF
    COMPRESSOR = "COMPRESSOR"  # Dynamic range compression
    DRONE = "DRONE"          # Drone-specific audio events
    ATTACK = "ATTACK"        # Attack warnings and hit confirms
    GENERAL = "GENERAL"      # General audio events


@dataclass
class AudioLogConfig:
    """Configuration for audio logging."""
    enabled: bool = False
    log_to_console: bool = True
    log_to_file: bool = False
    log_file_path: str = "audio_debug.log"

    # Category filters (True = log this category)
    categories: dict = None

    # Throttling (avoid spam)
    throttle_ms: int = 100  # Minimum time between same-source logs

    # Detail level (0=minimal, 1=normal, 2=verbose)
    detail_level: int = 1

    def __post_init__(self):
        if self.categories is None:
            self.categories = {cat: True for cat in LogCategory}


class AudioLogger:
    """Centralized audio logging system."""

    def __init__(self):
        self.config = AudioLogConfig()
        self._last_log_times = {}  # source_id -> last log time
        self._log_file = None
        self._start_time = time.time()

    def enable(self, enabled: bool = True):
        """Enable or disable audio logging."""
        self.config.enabled = enabled
        if enabled:
            print("\n" + "=" * 60)
            print("AUDIO LOGGING ENABLED")
            print("=" * 60)
            self._print_legend()
        else:
            print("\nAudio logging disabled")

    def set_detail_level(self, level: int):
        """Set detail level (0=minimal, 1=normal, 2=verbose)."""
        self.config.detail_level = max(0, min(2, level))
        print(f"Audio log detail level: {self.config.detail_level}")

    def set_category(self, category: LogCategory, enabled: bool):
        """Enable/disable a specific category."""
        self.config.categories[category] = enabled

    def _print_legend(self):
        """Print a legend explaining the log output."""
        print("""
LEGEND:
  [SPATIAL]    - 3D positioning (pan L/R, volume, distance)
  [OCCLUSION]  - Directional filtering (front/back, head shadow)
  [REVERB]     - Distance-based reverb (wet level, decay)
  [PITCH]      - Dynamic pitch variation (distance/speed-based)
  [DUCKING]    - Volume ducking (TTS, combat events)
  [ROLLOFF]    - Distance attenuation (logarithmic/linear)
  [HRTF]       - Steam Audio binaural processing
  [COMPRESSOR] - Dynamic range compression
  [DRONE]      - Drone audio state changes
  [ATTACK]     - Attack warnings, hit confirmations

VALUES:
  pan:      -1.0 (full left) to +1.0 (full right)
  vol:      0.0 (silent) to 1.0 (full volume)
  dist:     Distance in meters
  angle:    -180 to +180 (0=front, 180=behind)
  cutoff:   Lowpass filter frequency (Hz)
  rear_f:   Rear attenuation factor (0=front, 1=behind)
  pitch:    Playback pitch (1.0=normal, >1=higher, <1=lower)

Press 'L' to toggle logging on/off
""" + "=" * 60 + "\n")

    def _should_log(self, category: LogCategory, source_id: str = None) -> bool:
        """Check if we should log this event."""
        if not self.config.enabled:
            return False
        if not self.config.categories.get(category, True):
            return False

        # Throttle repeated logs from same source
        if source_id and self.config.throttle_ms > 0:
            now = time.time() * 1000
            last_time = self._last_log_times.get(source_id, 0)
            if now - last_time < self.config.throttle_ms:
                return False
            self._last_log_times[source_id] = now

        return True

    def _format_time(self) -> str:
        """Format elapsed time."""
        elapsed = time.time() - self._start_time
        return f"{elapsed:8.2f}s"

    def _log(self, category: LogCategory, message: str, source_id: str = None):
        """Internal logging method."""
        if not self._should_log(category, source_id):
            return

        timestamp = self._format_time()
        cat_str = f"[{category.value:10}]"
        full_message = f"{timestamp} {cat_str} {message}"

        if self.config.log_to_console:
            print(full_message)

        if self.config.log_to_file and self._log_file:
            self._log_file.write(full_message + "\n")
            self._log_file.flush()

    # === Convenience Methods ===

    def spatial(self, source: str, pan: float, volume: float, distance: float,
                angle: float = None, altitude_diff: float = None):
        """Log spatial audio positioning."""
        pan_indicator = self._pan_indicator(pan)
        msg = f"{source:15} | pan:{pan:+5.2f} {pan_indicator} | vol:{volume:4.2f} | dist:{distance:5.1f}m"
        if angle is not None and self.config.detail_level >= 1:
            direction = self._angle_to_direction(angle)
            msg += f" | angle:{angle:+6.1f} ({direction})"
        if altitude_diff is not None and self.config.detail_level >= 2:
            msg += f" | alt_diff:{altitude_diff:+5.1f}m"
        self._log(LogCategory.SPATIAL, msg, f"spatial_{source}")

    def occlusion(self, source: str, angle: float, lowpass_gain: float,
                  rear_factor: float = None, volume_mult: float = None,
                  is_interpolating: bool = False):
        """Log occlusion/directional filtering."""
        cutoff_hz = int(lowpass_gain * 22000)
        direction = self._angle_to_direction(angle)
        msg = f"{source:15} | angle:{angle:+6.1f} ({direction:6}) | cutoff:{cutoff_hz:5}Hz"
        if rear_factor is not None and self.config.detail_level >= 1:
            msg += f" | rear_f:{rear_factor:4.2f}"
        if volume_mult is not None and self.config.detail_level >= 1:
            msg += f" | vol_mult:{volume_mult:4.2f}"
        if is_interpolating:
            msg += " [INTERP]"
        self._log(LogCategory.OCCLUSION, msg, f"occ_{source}")

    def reverb(self, source: str, distance: float, wet_db: float, decay_ms: float):
        """Log distance-based reverb settings."""
        msg = f"{source:15} | dist:{distance:5.1f}m | wet:{wet_db:+5.1f}dB | decay:{decay_ms:5.0f}ms"
        self._log(LogCategory.REVERB, msg, f"reverb_{source}")

    def pitch(self, source: str, distance: float, base_pitch: float,
              speed: float = None, speed_boost: float = None):
        """Log dynamic pitch variation.

        Args:
            source: Sound source identifier
            distance: Distance to source in meters
            base_pitch: Final pitch value (1.0 = normal)
            speed: Speed of moving source (optional)
            speed_boost: Additional pitch from speed (optional)
        """
        msg = f"{source:15} | dist:{distance:5.1f}m | pitch:{base_pitch:5.3f}"
        if speed is not None and self.config.detail_level >= 1:
            msg += f" | speed:{speed:5.1f}"
        if speed_boost is not None and speed_boost > 0 and self.config.detail_level >= 1:
            msg += f" | speed_boost:+{speed_boost:.3f}"
        self._log(LogCategory.PITCH, msg, f"pitch_{source}")

    def ducking(self, reason: str, duck_volume: float, speed: float,
                is_starting: bool = True):
        """Log audio ducking events."""
        action = "START" if is_starting else "STOP"
        msg = f"{action:5} | reason: {reason:15} | target_vol:{duck_volume:4.2f} | speed:{speed:4.1f}"
        self._log(LogCategory.DUCKING, msg)

    def rolloff(self, source: str, distance: float, raw_volume: float,
                rolloff_type: str = "logarithmic"):
        """Log distance rolloff calculation."""
        if self.config.detail_level >= 2:
            msg = f"{source:15} | dist:{distance:5.1f}m | raw_vol:{raw_volume:4.2f} | type:{rolloff_type}"
            self._log(LogCategory.ROLLOFF, msg, f"rolloff_{source}")

    def hrtf(self, message: str, source: str = None):
        """Log HRTF/Steam Audio events."""
        if source:
            msg = f"{source:15} | {message}"
        else:
            msg = message
        self._log(LogCategory.HRTF, msg)

    def compressor(self, threshold_db: float, ratio: float, enabled: bool,
                   reason: str = ""):
        """Log compressor settings."""
        status = "ON" if enabled else "OFF"
        msg = f"{status:3} | threshold:{threshold_db:+5.1f}dB | ratio:{ratio:4.1f}:1"
        if reason:
            msg += f" | reason: {reason}"
        self._log(LogCategory.COMPRESSOR, msg)

    def drone_state(self, drone_id: int, state: str, distance: float,
                    old_state: str = None):
        """Log drone state changes."""
        if old_state:
            msg = f"Drone {drone_id} | {old_state:12} -> {state:12} | dist:{distance:5.1f}m"
        else:
            msg = f"Drone {drone_id} | state: {state:12} | dist:{distance:5.1f}m"
        self._log(LogCategory.DRONE, msg)

    def drone_audio(self, drone_id: int, sound_type: str, action: str = "play"):
        """Log drone audio playback."""
        if self.config.detail_level >= 1:
            msg = f"Drone {drone_id} | {action:6} | {sound_type}"
            self._log(LogCategory.DRONE, msg, f"drone_audio_{drone_id}")

    def attack_warning(self, drone_id: int, windup_ms: int, distance: float):
        """Log pre-attack warning."""
        msg = f"Drone {drone_id} | PRE-ATTACK WARNING | windup:{windup_ms}ms | dist:{distance:5.1f}m"
        self._log(LogCategory.ATTACK, msg)

    def hit_confirm(self, drone_id: int, damage: float, drone_health: float,
                    volume: float, is_kill: bool = False):
        """Log hit confirmation."""
        if is_kill:
            msg = f"Drone {drone_id} | KILL CONFIRMED | damage:{damage:5.1f} | vol:{volume:4.2f}"
        else:
            msg = f"Drone {drone_id} | HIT | damage:{damage:5.1f} | health:{drone_health:5.1f}% | vol:{volume:4.2f}"
        self._log(LogCategory.ATTACK, msg)

    def general(self, message: str):
        """Log general audio event."""
        self._log(LogCategory.GENERAL, message)

    # === Helper Methods ===

    def _pan_indicator(self, pan: float) -> str:
        """Create a visual pan indicator."""
        # Create a 9-character indicator: [   |   ]
        # Pan -1.0 = [#  |   ]
        # Pan  0.0 = [   |   ]
        # Pan +1.0 = [   |  #]
        width = 7
        center = width // 2
        pos = int((pan + 1) / 2 * (width - 1))
        indicator = [' '] * width
        indicator[center] = '|'
        indicator[pos] = '#'
        return '[' + ''.join(indicator) + ']'

    def _angle_to_direction(self, angle: float) -> str:
        """Convert angle to direction string."""
        abs_angle = abs(angle)
        if abs_angle <= 22.5:
            return "FRONT"
        elif abs_angle <= 67.5:
            return "F-RIGHT" if angle > 0 else "F-LEFT"
        elif abs_angle <= 112.5:
            return "RIGHT" if angle > 0 else "LEFT"
        elif abs_angle <= 157.5:
            return "B-RIGHT" if angle > 0 else "B-LEFT"
        else:
            return "BEHIND"


# Global logger instance
audio_log = AudioLogger()


def set_audio_logging(enabled: bool):
    """Enable or disable audio logging globally."""
    audio_log.enable(enabled)


def set_log_detail(level: int):
    """Set logging detail level (0=minimal, 1=normal, 2=verbose)."""
    audio_log.set_detail_level(level)
