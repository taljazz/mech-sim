"""
FMOD Audio Module for MechSimulator

This module provides an abstraction layer over pyfmodex (FMOD Python bindings)
for use in the MechSimulator game. It replaces pygame.mixer functionality.

Usage:
    from fmod_audio import MechAudio

    audio = MechAudio()
    audio.init(max_channels=64)
    audio.load_sound('sounds/Combat/ChaingunStart.wav', 'chaingun_start')
    channel = audio.play_sound('chaingun_start', 'weapons')
    audio.set_channel('chaingun', channel)

    # In main loop:
    audio.update()

    # Cleanup:
    audio.cleanup()
"""

import os
import pyfmodex
from pyfmodex.flags import MODE
from pyfmodex.enums import DSP_TYPE

# Import audio logger (lazy import to avoid circular dependency)
_audio_logger = None
_audio_log = None

def _get_logger():
    """Get the audio logger instance (lazy initialization)."""
    global _audio_logger
    if _audio_logger is None:
        try:
            from audio.logging import AudioLogger
            _audio_logger = AudioLogger.get_instance()
        except ImportError:
            # Fallback if logging module not available
            class DummyLogger:
                def log(self, *args, **kwargs): pass
                def error(self, *args, **kwargs): pass
                def warning(self, *args, **kwargs): pass
                def info(self, *args, **kwargs): pass
                def debug(self, *args, **kwargs): pass
            _audio_logger = DummyLogger()
    return _audio_logger

def _get_audio_log():
    """Get the new audio logging system (lazy initialization)."""
    global _audio_log
    if _audio_log is None:
        try:
            from audio.audio_logger import audio_log
            _audio_log = audio_log
        except ImportError:
            # Fallback if logging module not available
            class DummyAudioLog:
                def spatial(self, *args, **kwargs): pass
                def occlusion(self, *args, **kwargs): pass
                def reverb(self, *args, **kwargs): pass
                def ducking(self, *args, **kwargs): pass
                def rolloff(self, *args, **kwargs): pass
                def compressor(self, *args, **kwargs): pass
                def general(self, *args, **kwargs): pass
                def hrtf(self, *args, **kwargs): pass
            _audio_log = DummyAudioLog()
    return _audio_log


class MechAudio:
    """Audio system wrapper for FMOD/pyfmodex."""

    def __init__(self):
        self.system = None
        self.master_group = None
        self.channel_groups = {}
        self.sounds = {}
        self.channels = {}  # Named channel tracking
        self.master_volume = 1.0
        self._initialized = False

        # DSP effects
        self.dsp_effects = {}  # Named DSP effect tracking
        self._reverb_dsp = None
        self._lowpass_dsp = None
        self._distortion_dsp = None

        # Audio ducking system
        self._ducking_active = False
        self._ducking_target_volume = 1.0
        self._ducking_current_volume = 1.0
        self._ducking_speed = 5.0  # Volume change per second
        self._ducked_groups = []  # Groups currently being ducked
        self._ducked_group_refs = []  # OPTIMIZATION: Pre-cached group references for ducking

        # Lazy DSP creation flags
        self._dsp_initialized = False
        self._reverb_enabled_once = False
        self._lowpass_enabled_once = False
        self._distortion_enabled_once = False

        # Smooth occlusion transition state (per-channel tracking)
        # Maps channel_id -> {'lowpass_gain': float, 'volume_mult': float, 'last_update': time}
        self._occlusion_states = {}
        self._occlusion_interpolation_speed = 8.0  # Units per second

        # Distance-based reverb state
        self._distance_reverb_enabled = False
        self._current_reverb_wet = -30.0
        self._current_reverb_decay = 800

    def init(self, max_channels=64):
        """Initialize FMOD system with optimal settings for game audio.

        Args:
            max_channels: Maximum number of virtual channels (default 64)
        """
        if self._initialized:
            return

        # Ensure DLLs can be found from project directory
        dll_path = os.path.dirname(os.path.abspath(__file__))
        try:
            os.add_dll_directory(dll_path)
        except (AttributeError, OSError):
            pass  # add_dll_directory not available or failed

        self.system = pyfmodex.System()
        self.system.init(maxchannels=max_channels)
        self.master_group = self.system.master_channel_group

        # Create channel groups for volume categories
        self._create_channel_groups()

        # Initialize DSP effects
        self._init_dsp_effects()

        self._initialized = True
        print(f"FMOD initialized: version {hex(self.system.version)}")

    def _create_channel_groups(self):
        """Create all audio category groups with base volumes."""
        groups = [
            ('ambience', 0.5),
            ('weapons', 0.8),
            ('movement', 1.0),
            ('thrusters', 0.7),
            ('drones', 0.8),
            ('ui', 0.6),
            ('powerup', 0.6),
            ('damage', 0.9),  # New group for damage feedback sounds
        ]
        for name, base_vol in groups:
            group = self.system.create_channel_group(name)
            group.volume = base_vol
            self.channel_groups[name] = {
                'group': group,
                'base_volume': base_vol,
                'dsp_effects': []  # Track DSP effects attached to this group
            }

    def _init_dsp_effects(self):
        """LAZY INITIALIZATION: DSP effects are now created on first use.

        This method is kept for compatibility but does nothing.
        Actual DSP creation happens in _ensure_reverb_dsp, _ensure_lowpass_dsp, etc.
        """
        # OPTIMIZATION: DSP effects are created lazily on first use
        # This saves ~1-2 MB memory when effects are not used
        self._dsp_initialized = True
        print("DSP: Lazy initialization enabled (effects created on first use)")

    def _ensure_reverb_dsp(self):
        """Lazily create reverb DSP on first use."""
        if self._reverb_dsp is not None:
            return True
        try:
            self._reverb_dsp = self.system.create_dsp_by_type(DSP_TYPE.SFXREVERB)
            # Set reverb parameters for a medium-sized metallic space (mech cockpit)
            self._reverb_dsp.set_parameter_float(0, 1500)   # Decay time (ms)
            self._reverb_dsp.set_parameter_float(1, 20)     # Early delay (ms)
            self._reverb_dsp.set_parameter_float(2, 40)     # Late delay (ms)
            self._reverb_dsp.set_parameter_float(3, 100)    # HF reference (Hz)
            self._reverb_dsp.set_parameter_float(4, 50)     # HF decay ratio (%)
            self._reverb_dsp.set_parameter_float(5, -6)     # Diffusion (dB)
            self._reverb_dsp.set_parameter_float(6, -6)     # Density (dB)
            self._reverb_dsp.set_parameter_float(7, 5000)   # Low shelf frequency
            self._reverb_dsp.set_parameter_float(8, 0)      # Low shelf gain
            self._reverb_dsp.set_parameter_float(9, 10000)  # High cut
            self._reverb_dsp.set_parameter_float(10, 100)   # Early late mix
            self._reverb_dsp.set_parameter_float(11, -20)   # Wet level (dB)
            self._reverb_dsp.set_parameter_float(12, 0)     # Dry level (dB)
            self._reverb_dsp.bypass = True
            print("DSP: Reverb created (lazy)")
            return True
        except Exception as e:
            print(f"DSP reverb creation warning: {e}")
            return False

    def _ensure_lowpass_dsp(self):
        """Lazily create lowpass DSP on first use."""
        if self._lowpass_dsp is not None:
            return True
        try:
            self._lowpass_dsp = self.system.create_dsp_by_type(DSP_TYPE.LOWPASS)
            self._lowpass_dsp.set_parameter_float(0, 22000)  # Cutoff frequency (Hz)
            self._lowpass_dsp.set_parameter_float(1, 1.0)    # Resonance
            self._lowpass_dsp.bypass = True
            print("DSP: Lowpass filter created (lazy)")
            return True
        except Exception as e:
            print(f"DSP lowpass creation warning: {e}")
            return False

    def _ensure_distortion_dsp(self):
        """Lazily create distortion DSP on first use."""
        if self._distortion_dsp is not None:
            return True
        try:
            self._distortion_dsp = self.system.create_dsp_by_type(DSP_TYPE.DISTORTION)
            self._distortion_dsp.set_parameter_float(0, 0.0)  # Distortion level
            self._distortion_dsp.bypass = True
            print("DSP: Distortion created (lazy)")
            return True
        except Exception as e:
            print(f"DSP distortion creation warning: {e}")
            return False

    def _ensure_highpass_dsp(self):
        """Lazily create highpass DSP on first use (for air absorption)."""
        if not hasattr(self, '_highpass_dsp'):
            self._highpass_dsp = None
        if self._highpass_dsp is not None:
            return True
        try:
            self._highpass_dsp = self.system.create_dsp_by_type(DSP_TYPE.HIGHPASS)
            self._highpass_dsp.set_parameter_float(0, 10)  # Cutoff frequency (Hz)
            self._highpass_dsp.set_parameter_float(1, 1.0)  # Resonance
            self._highpass_dsp.bypass = True
            print("DSP: Highpass filter created (lazy)")
            return True
        except Exception as e:
            print(f"DSP highpass creation warning: {e}")
            return False

    def _ensure_compressor_dsp(self):
        """Lazily create compressor DSP on first use (prevents clipping during damage)."""
        if not hasattr(self, '_compressor_dsp'):
            self._compressor_dsp = None
        if self._compressor_dsp is not None:
            return True
        try:
            self._compressor_dsp = self.system.create_dsp_by_type(DSP_TYPE.COMPRESSOR)
            # Set compressor parameters for damage effects
            # Prevents clipping during intense combat
            self._compressor_dsp.set_parameter_float(0, -12.0)  # Threshold (dB)
            self._compressor_dsp.set_parameter_float(1, 4.0)    # Ratio (4:1)
            self._compressor_dsp.set_parameter_float(2, 10.0)   # Attack (ms)
            self._compressor_dsp.set_parameter_float(3, 100.0)  # Release (ms)
            self._compressor_dsp.set_parameter_float(4, 0.0)    # Makeup gain (dB)
            self._compressor_dsp.bypass = True
            print("DSP: Compressor created (lazy)")
            return True
        except Exception as e:
            print(f"DSP compressor creation warning: {e}")
            return False

    def set_compressor(self, threshold_db=-12.0, ratio=4.0, enabled=True, reason=""):
        """Enable/configure compressor to prevent clipping during intense audio.

        Args:
            threshold_db: Level at which compression starts (-60 to 0 dB)
            ratio: Compression ratio (1.0 to 50.0, e.g., 4.0 = 4:1)
            enabled: If True, enable compressor; if False, bypass it
            reason: Optional reason for enabling (for logging)

        Use during combat or damage effects to prevent audio clipping.
        """
        if not self._ensure_compressor_dsp():
            return

        try:
            threshold_db = max(-60, min(0, threshold_db))
            ratio = max(1.0, min(50.0, ratio))
            self._compressor_dsp.set_parameter_float(0, threshold_db)
            self._compressor_dsp.set_parameter_float(1, ratio)
            self._compressor_dsp.bypass = not enabled

            if enabled and self._compressor_dsp not in self.channel_groups.get('_master_dsp', []):
                self.add_dsp_to_master(self._compressor_dsp)
                if '_master_dsp' not in self.channel_groups:
                    self.channel_groups['_master_dsp'] = []
                self.channel_groups['_master_dsp'].append(self._compressor_dsp)

            # === LOGGING ===
            alog = _get_audio_log()
            alog.compressor(
                threshold_db=threshold_db,
                ratio=ratio,
                enabled=enabled,
                reason=reason
            )
        except Exception as e:
            print(f"Failed to set compressor: {e}")

    def create_dsp_effect(self, dsp_type, name):
        """Create a named DSP effect for later use.

        Args:
            dsp_type: FMOD DSP_TYPE enum value (e.g., DSP_TYPE.LOWPASS)
            name: Unique name to identify this DSP effect

        Returns:
            The DSP object, or None if creation failed
        """
        try:
            dsp = self.system.create_dsp_by_type(dsp_type)
            self.dsp_effects[name] = dsp
            return dsp
        except Exception as e:
            print(f"Failed to create DSP effect '{name}': {e}")
            return None

    def get_dsp_effect(self, name):
        """Get a named DSP effect.

        Args:
            name: The DSP effect name

        Returns:
            The DSP object, or None if not found
        """
        return self.dsp_effects.get(name)

    def add_dsp_to_group(self, group_name, dsp):
        """Add a DSP effect to a channel group.

        Args:
            group_name: Name of the channel group
            dsp: The DSP object to add

        Returns:
            True if successful, False otherwise
        """
        if group_name not in self.channel_groups:
            return False
        try:
            group = self.channel_groups[group_name]['group']
            group.add_dsp(0, dsp)  # Add at head of DSP chain
            self.channel_groups[group_name]['dsp_effects'].append(dsp)
            return True
        except Exception as e:
            print(f"Failed to add DSP to group '{group_name}': {e}")
            return False

    def remove_dsp_from_group(self, group_name, dsp):
        """Remove a DSP effect from a channel group.

        Args:
            group_name: Name of the channel group
            dsp: The DSP object to remove

        Returns:
            True if successful, False otherwise
        """
        if group_name not in self.channel_groups:
            return False
        try:
            group = self.channel_groups[group_name]['group']
            group.remove_dsp(dsp)
            if dsp in self.channel_groups[group_name]['dsp_effects']:
                self.channel_groups[group_name]['dsp_effects'].remove(dsp)
            return True
        except Exception as e:
            print(f"Failed to remove DSP from group '{group_name}': {e}")
            return False

    def add_dsp_to_master(self, dsp):
        """Add a DSP effect to the master channel group.

        Args:
            dsp: The DSP object to add

        Returns:
            True if successful, False otherwise
        """
        try:
            self.master_group.add_dsp(0, dsp)
            return True
        except Exception as e:
            print(f"Failed to add DSP to master: {e}")
            return False

    def set_lowpass_filter(self, cutoff_hz, enabled=True):
        """Set lowpass filter parameters on master output.

        Args:
            cutoff_hz: Cutoff frequency in Hz (200-22000)
            enabled: If True, enable the filter; if False, bypass it

        This creates a "muffled" effect useful for damage feedback or underwater.
        """
        # OPTIMIZATION: Lazy create DSP on first use
        if not self._ensure_lowpass_dsp():
            return

        try:
            # Clamp cutoff frequency
            cutoff_hz = max(200, min(22000, cutoff_hz))
            self._lowpass_dsp.set_parameter_float(0, cutoff_hz)
            self._lowpass_dsp.bypass = not enabled

            # Add to master if not already added
            if enabled and self._lowpass_dsp not in self.channel_groups.get('_master_dsp', []):
                self.add_dsp_to_master(self._lowpass_dsp)
                if '_master_dsp' not in self.channel_groups:
                    self.channel_groups['_master_dsp'] = []
                self.channel_groups['_master_dsp'].append(self._lowpass_dsp)
        except Exception as e:
            print(f"Failed to set lowpass filter: {e}")

    def set_reverb(self, wet_level_db=-10, decay_ms=1500, enabled=True):
        """Set reverb parameters on master output.

        Args:
            wet_level_db: Wet signal level in dB (-80 to 0)
            decay_ms: Reverb decay time in milliseconds (100-20000)
            enabled: If True, enable reverb; if False, bypass it

        Use for environmental audio effects (e.g., enclosed spaces, hangars).
        """
        # OPTIMIZATION: Lazy create DSP on first use
        if not self._ensure_reverb_dsp():
            return

        try:
            wet_level_db = max(-80, min(0, wet_level_db))
            decay_ms = max(100, min(20000, decay_ms))
            self._reverb_dsp.set_parameter_float(0, decay_ms)
            self._reverb_dsp.set_parameter_float(11, wet_level_db)
            self._reverb_dsp.bypass = not enabled

            if enabled and self._reverb_dsp not in self.channel_groups.get('_master_dsp', []):
                self.add_dsp_to_master(self._reverb_dsp)
                if '_master_dsp' not in self.channel_groups:
                    self.channel_groups['_master_dsp'] = []
                self.channel_groups['_master_dsp'].append(self._reverb_dsp)
        except Exception as e:
            print(f"Failed to set reverb: {e}")

    def set_distortion(self, level, enabled=True):
        """Set distortion level on master output.

        Args:
            level: Distortion level (0.0 = none, 1.0 = maximum)
            enabled: If True, enable distortion; if False, bypass it

        Use for hull damage feedback or system malfunction effects.
        """
        # OPTIMIZATION: Lazy create DSP on first use
        if not self._ensure_distortion_dsp():
            return

        try:
            level = max(0.0, min(1.0, level))
            self._distortion_dsp.set_parameter_float(0, level)
            self._distortion_dsp.bypass = not enabled

            if enabled and self._distortion_dsp not in self.channel_groups.get('_master_dsp', []):
                self.add_dsp_to_master(self._distortion_dsp)
                if '_master_dsp' not in self.channel_groups:
                    self.channel_groups['_master_dsp'] = []
                self.channel_groups['_master_dsp'].append(self._distortion_dsp)
        except Exception as e:
            print(f"Failed to set distortion: {e}")

    def update_distance_reverb(self, distance, enabled=True, player_altitude=0.0):
        """Update reverb based on distance and altitude for spatial depth perception.

        Distant sounds should have more reverb to simulate environmental acoustics.
        Higher altitude adds more reverb (open sky feeling).
        This creates a sense of space and distance beyond simple volume attenuation.

        Args:
            distance: Distance to the primary sound source in meters
            enabled: If True, apply distance-based reverb scaling
            player_altitude: Player altitude in feet (affects reverb intensity)
        """
        if not enabled:
            if self._distance_reverb_enabled:
                self.set_reverb(enabled=False)
                self._distance_reverb_enabled = False
            return

        try:
            from state.constants import (
                REVERB_DISTANCE_START, REVERB_DISTANCE_MAX,
                REVERB_WET_MIN_DB, REVERB_WET_MAX_DB,
                REVERB_DECAY_MIN_MS, REVERB_DECAY_MAX_MS,
                ALTITUDE_REVERB_GROUND, ALTITUDE_REVERB_LOW, ALTITUDE_REVERB_HIGH,
                ALTITUDE_REVERB_MULTIPLIER_GROUND, ALTITUDE_REVERB_MULTIPLIER_HIGH,
                ALTITUDE_DECAY_MULTIPLIER_GROUND, ALTITUDE_DECAY_MULTIPLIER_HIGH
            )
        except ImportError:
            REVERB_DISTANCE_START = 15.0
            REVERB_DISTANCE_MAX = 60.0
            REVERB_WET_MIN_DB = -30.0
            REVERB_WET_MAX_DB = -10.0
            REVERB_DECAY_MIN_MS = 800
            REVERB_DECAY_MAX_MS = 2500
            ALTITUDE_REVERB_GROUND = 0.0
            ALTITUDE_REVERB_LOW = 50.0
            ALTITUDE_REVERB_HIGH = 200.0
            ALTITUDE_REVERB_MULTIPLIER_GROUND = 0.7
            ALTITUDE_REVERB_MULTIPLIER_HIGH = 1.4
            ALTITUDE_DECAY_MULTIPLIER_GROUND = 0.8
            ALTITUDE_DECAY_MULTIPLIER_HIGH = 1.3

        # Calculate altitude-based multipliers
        if player_altitude <= ALTITUDE_REVERB_GROUND:
            altitude_wet_mult = ALTITUDE_REVERB_MULTIPLIER_GROUND
            altitude_decay_mult = ALTITUDE_DECAY_MULTIPLIER_GROUND
        elif player_altitude >= ALTITUDE_REVERB_HIGH:
            altitude_wet_mult = ALTITUDE_REVERB_MULTIPLIER_HIGH
            altitude_decay_mult = ALTITUDE_DECAY_MULTIPLIER_HIGH
        else:
            # Interpolate between ground and high altitude
            if player_altitude <= ALTITUDE_REVERB_LOW:
                # Ground to low altitude
                factor = player_altitude / ALTITUDE_REVERB_LOW
                altitude_wet_mult = ALTITUDE_REVERB_MULTIPLIER_GROUND + factor * (1.0 - ALTITUDE_REVERB_MULTIPLIER_GROUND)
                altitude_decay_mult = ALTITUDE_DECAY_MULTIPLIER_GROUND + factor * (1.0 - ALTITUDE_DECAY_MULTIPLIER_GROUND)
            else:
                # Low to high altitude
                factor = (player_altitude - ALTITUDE_REVERB_LOW) / (ALTITUDE_REVERB_HIGH - ALTITUDE_REVERB_LOW)
                altitude_wet_mult = 1.0 + factor * (ALTITUDE_REVERB_MULTIPLIER_HIGH - 1.0)
                altitude_decay_mult = 1.0 + factor * (ALTITUDE_DECAY_MULTIPLIER_HIGH - 1.0)

        if distance < REVERB_DISTANCE_START:
            # Close sounds - minimal reverb
            target_wet = REVERB_WET_MIN_DB
            target_decay = REVERB_DECAY_MIN_MS
        elif distance >= REVERB_DISTANCE_MAX:
            # Max distance - full reverb
            target_wet = REVERB_WET_MAX_DB
            target_decay = REVERB_DECAY_MAX_MS
        else:
            # Interpolate based on distance
            factor = (distance - REVERB_DISTANCE_START) / (REVERB_DISTANCE_MAX - REVERB_DISTANCE_START)
            # Use sqrt for perceptually linear scaling
            factor = factor ** 0.7
            target_wet = REVERB_WET_MIN_DB + factor * (REVERB_WET_MAX_DB - REVERB_WET_MIN_DB)
            target_decay = REVERB_DECAY_MIN_MS + factor * (REVERB_DECAY_MAX_MS - REVERB_DECAY_MIN_MS)

        # Apply altitude multipliers (shift wet level, scale decay)
        # For wet level: multiply the offset from min (more reverb at altitude)
        wet_offset = target_wet - REVERB_WET_MIN_DB
        target_wet = REVERB_WET_MIN_DB + wet_offset * altitude_wet_mult

        # For decay: directly scale the decay time
        target_decay = target_decay * altitude_decay_mult

        # Clamp values to reasonable ranges
        target_wet = max(-40.0, min(-5.0, target_wet))
        target_decay = max(400, min(4000, target_decay))

        # Smooth interpolation to prevent jarring changes
        if abs(target_wet - self._current_reverb_wet) > 1.0:
            if target_wet > self._current_reverb_wet:
                self._current_reverb_wet = min(target_wet, self._current_reverb_wet + 2.0)
            else:
                self._current_reverb_wet = max(target_wet, self._current_reverb_wet - 2.0)

            self._current_reverb_decay = target_decay
            self.set_reverb(
                wet_level_db=self._current_reverb_wet,
                decay_ms=self._current_reverb_decay,
                enabled=True
            )
            self._distance_reverb_enabled = True

            # === LOGGING ===
            alog = _get_audio_log()
            alog.reverb(
                source="distance_reverb",
                distance=distance,
                wet_db=self._current_reverb_wet,
                decay_ms=self._current_reverb_decay
            )

    def set_hull_damage_effect(self, hull_percent):
        """Apply audio effects based on hull damage level.

        Args:
            hull_percent: Current hull percentage (0-100)

        Effects applied:
        - Above 50%: No effects
        - 25-50%: Light lowpass + minor distortion + compressor
        - Below 25%: Heavy lowpass + significant distortion + compressor (critical state)
        """
        # Enable compressor during damage to prevent clipping
        if hull_percent <= 50:
            self.set_compressor(threshold_db=-12.0, ratio=4.0, enabled=True,
                               reason=f"hull_damage_{int(hull_percent)}%")
        else:
            self.set_compressor(enabled=False, reason="hull_healthy")

        if hull_percent > 50:
            # No damage effects
            self.set_lowpass_filter(22000, enabled=False)
            self.set_distortion(0.0, enabled=False)
        elif hull_percent > 25:
            # Moderate damage - light muffling and distortion
            lowpass_cutoff = 8000 + (hull_percent - 25) * 200  # 8000-13000 Hz
            distortion_level = 0.1 + (50 - hull_percent) * 0.008  # 0.1-0.3
            self.set_lowpass_filter(lowpass_cutoff, enabled=True)
            self.set_distortion(distortion_level, enabled=True)
        else:
            # Critical damage - heavy muffling and distortion
            lowpass_cutoff = 2000 + hull_percent * 240  # 2000-8000 Hz
            distortion_level = 0.3 + (25 - hull_percent) * 0.02  # 0.3-0.8
            self.set_lowpass_filter(lowpass_cutoff, enabled=True)
            self.set_distortion(distortion_level, enabled=True)

    # === Audio Ducking System ===

    def start_ducking(self, groups_to_duck=None, duck_volume=0.3, speed=5.0, reason="unknown"):
        """Start ducking (lowering volume) on specified groups.

        Args:
            groups_to_duck: List of group names to duck, or None for all except 'ui'
            duck_volume: Target volume multiplier for ducked groups (0.0-1.0)
            speed: How fast to transition (volume change per second)
            reason: Reason for ducking (for logging)

        Use for important audio events (TTS, critical alerts, weapon impacts).
        """
        if groups_to_duck is None:
            # Duck everything except UI and damage
            groups_to_duck = ['ambience', 'weapons', 'movement', 'thrusters', 'drones']

        self._ducked_groups = groups_to_duck
        self._ducking_target_volume = duck_volume
        self._ducking_speed = speed
        self._ducking_active = True

        # === LOGGING ===
        alog = _get_audio_log()
        alog.ducking(reason=reason, duck_volume=duck_volume, speed=speed, is_starting=True)

        # OPTIMIZATION: Pre-cache group references to avoid dict lookups each frame
        self._ducked_group_refs = []
        for group_name in groups_to_duck:
            if group_name in self.channel_groups:
                self._ducked_group_refs.append({
                    'name': group_name,
                    'group': self.channel_groups[group_name]['group'],
                    'base_volume': self.channel_groups[group_name]['base_volume']
                })

    def stop_ducking(self, speed=3.0, reason="restore"):
        """Stop ducking and restore normal volumes.

        Args:
            speed: How fast to restore volume (volume change per second)
            reason: Reason for stopping (for logging)
        """
        self._ducking_target_volume = 1.0
        self._ducking_speed = speed
        # _ducking_active stays true until volumes are restored

        # === LOGGING ===
        alog = _get_audio_log()
        alog.ducking(reason=reason, duck_volume=1.0, speed=speed, is_starting=False)

    def update_ducking(self, dt):
        """Update ducking volumes (call each frame).

        Args:
            dt: Delta time in seconds since last frame
        """
        if not self._ducking_active:
            return

        # Move current volume toward target
        if self._ducking_current_volume < self._ducking_target_volume:
            self._ducking_current_volume = min(
                self._ducking_target_volume,
                self._ducking_current_volume + self._ducking_speed * dt
            )
        elif self._ducking_current_volume > self._ducking_target_volume:
            self._ducking_current_volume = max(
                self._ducking_target_volume,
                self._ducking_current_volume - self._ducking_speed * dt
            )

        # OPTIMIZATION: Use pre-cached group references instead of dict lookups
        for ref in self._ducked_group_refs:
            ducked_vol = ref['base_volume'] * self._ducking_current_volume
            try:
                ref['group'].volume = ducked_vol
            except Exception:
                pass

        # Check if ducking is complete
        if abs(self._ducking_current_volume - self._ducking_target_volume) < 0.01:
            if self._ducking_target_volume >= 1.0:
                self._ducking_active = False
                self._ducked_groups = []
                self._ducked_group_refs = []  # Clear cached refs

    def is_ducking(self):
        """Check if audio ducking is currently active.

        Returns:
            True if ducking is active
        """
        return self._ducking_active

    # === FMOD 3D Audio System ===

    def set_3d_settings(self, doppler_scale=0.0, distance_factor=1.0, rolloff_scale=1.0):
        """Configure FMOD 3D audio settings.

        Args:
            doppler_scale: Doppler effect scale (0.0 = disabled, 1.0 = normal)
            distance_factor: Distance units per meter (1.0 = meters)
            rolloff_scale: Rolloff curve scale (affects how sound attenuates)
        """
        if not self.system:
            return
        try:
            # Set 3D settings via threed_settings property
            self.system.threed_settings.doppler_scale = doppler_scale
            self.system.threed_settings.distance_factor = distance_factor
            self.system.threed_settings.rolloff_scale = rolloff_scale
            print(f"3D Audio settings: doppler={doppler_scale}, distance={distance_factor}, rolloff={rolloff_scale}")
        except Exception as e:
            print(f"Failed to set 3D settings: {e}")

    def set_3d_listener_attributes(self, position, forward, up, velocity=None, listener_id=0):
        """Set the 3D listener position and orientation.

        This should be called every frame to update the listener based on player position.

        Args:
            position: Tuple/list of (x, y, z) position in world space
            forward: Tuple/list of (x, y, z) forward direction vector (normalized)
            up: Tuple/list of (x, y, z) up direction vector (normalized)
            velocity: Optional tuple/list of (x, y, z) velocity (for Doppler)
            listener_id: Listener index (default 0 for single listener)

        Note: FMOD uses a left-handed coordinate system with Y up.
              Our game uses: X = East, Y = North, Z = Up (altitude)
              We convert: FMOD X = game X, FMOD Y = game Z, FMOD Z = game Y
        """
        if not self.system:
            return

        try:
            # Get listener object
            listener = self.system.listener(listener_id)

            # Convert game coordinates to FMOD coordinates
            # Game: X=East, Y=North, Z=Up -> FMOD: X=East, Y=Up, Z=North
            pos = [position[0], position[2] if len(position) > 2 else 0, position[1]]
            fwd = [forward[0], forward[2] if len(forward) > 2 else 0, forward[1]]
            up_vec = [up[0], up[2] if len(up) > 2 else 1, up[1]]

            # Set listener position
            listener.position = pos

            # Set listener orientation (forward and up vectors)
            listener.set_orientation(fwd, up_vec)

            # Set velocity for Doppler effect
            if velocity:
                vel = [velocity[0], velocity[2] if len(velocity) > 2 else 0, velocity[1]]
                listener.velocity = vel
        except Exception as e:
            print(f"Failed to set 3D listener attributes: {e}")

    def set_channel_3d_attributes(self, channel, position, velocity=None):
        """Set 3D position for a channel.

        Args:
            channel: FMOD channel or FMODChannelWrapper
            position: Tuple/list of (x, y, z) game coordinates (x=East, y=North, z=altitude)
            velocity: Optional tuple/list of (x, y, z) velocity

        Note: Converts game coordinates to FMOD coordinates (Y up).
        """
        if channel is None:
            return

        try:
            # Get the raw channel
            raw_channel = channel._channel if hasattr(channel, '_channel') else channel
            if raw_channel is None:
                return

            # Convert game coordinates to FMOD coordinates
            # Game: X=East, Y=North, Z=Up -> FMOD: X=East, Y=Up, Z=North
            fmod_pos = [
                position[0],  # X = East
                position[2] if len(position) > 2 else 0,  # Y = Up (altitude)
                position[1]   # Z = North
            ]

            # Set 3D position using the position property
            raw_channel.position = fmod_pos

            if velocity:
                fmod_vel = [
                    velocity[0],
                    velocity[2] if len(velocity) > 2 else 0,
                    velocity[1]
                ]
                raw_channel.velocity = fmod_vel
        except Exception as e:
            # Channel may have ended or sound may not be 3D
            logger = _get_logger()
            logger.debug(f"3D position update failed (channel may have ended)", {
                'error': str(e)
            })

    def set_sound_3d_min_max_distance(self, sound, min_distance=2.0, max_distance=50.0):
        """Set the min/max distance for a 3D sound's attenuation.

        Args:
            sound: The FMOD Sound object
            min_distance: Distance at which sound is at full volume
            max_distance: Distance at which sound is silent (or minimal)
        """
        if sound is None:
            return
        try:
            sound.min_distance = min_distance
            sound.max_distance = max_distance
        except Exception as e:
            print(f"Failed to set 3D distance: {e}")

    # === Directional Audio Filters ===

    def _get_spatial_constants(self):
        """Get spatial audio filter constants from config or use defaults."""
        try:
            from state.constants import (
                AIR_ABSORPTION_START_DISTANCE,
                AIR_ABSORPTION_MAX_DISTANCE,
                AIR_ABSORPTION_MAX_CUTOFF,
                OCCLUSION_LOWPASS_CUTOFF,
                OCCLUSION_VOLUME_REDUCTION
            )
            return {
                'air_start': AIR_ABSORPTION_START_DISTANCE,
                'air_max': AIR_ABSORPTION_MAX_DISTANCE,
                'air_cutoff': AIR_ABSORPTION_MAX_CUTOFF,
                'occ_cutoff': OCCLUSION_LOWPASS_CUTOFF,
                'occ_vol': OCCLUSION_VOLUME_REDUCTION
            }
        except ImportError:
            return {
                'air_start': 10.0,
                'air_max': 60.0,
                'air_cutoff': 400,
                'occ_cutoff': 2000,
                'occ_vol': 0.7
            }

    def create_channel_lowpass_dsp(self):
        """Create a lowpass DSP for per-channel use.

        Returns:
            FMOD DSP object or None
        """
        try:
            from pyfmodex.enums import DSP_TYPE
            return self.system.create_dsp_by_type(DSP_TYPE.LOWPASS)
        except Exception as e:
            print(f"Failed to create lowpass DSP: {e}")
            return None

    def create_channel_highpass_dsp(self):
        """Create a highpass DSP for per-channel use.

        Returns:
            FMOD DSP object or None
        """
        try:
            from pyfmodex.enums import DSP_TYPE
            return self.system.create_dsp_by_type(DSP_TYPE.HIGHPASS)
        except Exception as e:
            print(f"Failed to create highpass DSP: {e}")
            return None

    def calculate_air_absorption(self, distance: float) -> float:
        """Calculate air absorption effect based on distance.

        Air absorbs high frequencies more than low frequencies over distance.
        This simulates that by returning a highpass cutoff frequency.

        Args:
            distance: Distance to sound source in meters

        Returns:
            Highpass cutoff frequency (Hz). 0 = no filtering, higher = more bass cut.
        """
        c = self._get_spatial_constants()

        if distance <= c['air_start']:
            return 0.0

        if distance >= c['air_max']:
            return c['air_cutoff']

        # Linear interpolation between start and max distance
        normalized = (distance - c['air_start']) / (c['air_max'] - c['air_start'])

        # Use sqrt for more gradual onset (perceptually more natural)
        return normalized ** 0.7 * c['air_cutoff']

    def calculate_occlusion(self, relative_angle: float, altitude_diff: float,
                            distance: float) -> tuple:
        """Calculate occlusion effect for simulating obstacles.

        Simulates sound being partially blocked by:
        - Being significantly behind the listener (head shadow)
        - Large altitude differences (ground/ceiling blocking)

        Args:
            relative_angle: Angle from player's forward (-180 to 180 degrees)
            altitude_diff: Altitude difference in meters (positive = above)
            distance: Distance to sound source in meters

        Returns:
            Tuple of (occlusion_factor, lowpass_cutoff, volume_mult)
            - occlusion_factor: 0.0 (no occlusion) to 1.0 (fully occluded)
            - lowpass_cutoff: Recommended lowpass cutoff (Hz)
            - volume_mult: Volume multiplier (0.0 to 1.0)
        """
        c = self._get_spatial_constants()
        occlusion = 0.0

        # Head shadow occlusion - DISABLED
        # Directional distinction is handled by panning only, not filtering/volume
        abs_angle = abs(relative_angle)
        # (Previously applied 60% occlusion for sounds behind - now disabled)

        # Altitude-based occlusion (simulates ground/obstacles between)
        # Large altitude differences suggest sound may be partially blocked
        if abs(altitude_diff) > 15:
            alt_factor = min(1.0, (abs(altitude_diff) - 15) / 50.0)
            alt_occlusion = alt_factor * 0.4  # Max 40% occlusion
            occlusion = max(occlusion, alt_occlusion)

        # Calculate resulting filter values
        if occlusion > 0.05:
            # Interpolate lowpass cutoff: 22000 Hz (clear) to configured cutoff (occluded)
            lowpass_cutoff = 22000 - (occlusion * (22000 - c['occ_cutoff']))
            # Volume reduction
            volume_mult = 1.0 - (occlusion * (1.0 - c['occ_vol']))
        else:
            lowpass_cutoff = 22000
            volume_mult = 1.0

        return occlusion, lowpass_cutoff, volume_mult

    def apply_directional_filter(self, channel, relative_angle, altitude_diff, distance,
                                  apply_air_absorption=True, apply_occlusion=True,
                                  channel_id=None, dt=0.016):
        """Apply directional audio filters based on sound source position.

        This creates realistic perception of front/behind and above/below positioning
        by applying multiple frequency filtering techniques:
        - Behind: Lowpass filter (muffled, like head shadowing) - ENHANCED
        - Above: Slight brightness boost (less lowpass)
        - Below: Slight dulling (more lowpass)
        - Distance: Air absorption (highpass, distant sounds lose bass)
        - Occlusion: Additional lowpass and volume reduction for blocked sounds
        - SMOOTH TRANSITIONS: Interpolates filter changes to prevent jarring audio

        Args:
            channel: FMOD channel or FMODChannelWrapper
            relative_angle: Angle from player's forward direction (-180 to 180 degrees)
                           0 = directly in front, 180/-180 = directly behind
            altitude_diff: Altitude difference in meters (positive = above player)
            distance: Distance to sound source in meters
            apply_air_absorption: If True, apply distance-based air absorption
            apply_occlusion: If True, apply occlusion simulation
            channel_id: Optional unique ID for smooth transition tracking
            dt: Delta time in seconds for interpolation (default 16ms)
        """
        if channel is None:
            return

        try:
            raw_channel = channel._channel if hasattr(channel, '_channel') else channel
            if raw_channel is None:
                return

            # Get enhanced audio constants
            try:
                from state.constants import (
                    REAR_LOWPASS_CUTOFF, REAR_LOWPASS_START_ANGLE,
                    REAR_VOLUME_REDUCTION, OCCLUSION_INTERPOLATION_SPEED
                )
                rear_cutoff = REAR_LOWPASS_CUTOFF
                rear_start_angle = REAR_LOWPASS_START_ANGLE
                rear_vol_reduction = REAR_VOLUME_REDUCTION
                interp_speed = OCCLUSION_INTERPOLATION_SPEED
            except ImportError:
                rear_cutoff = 2500
                rear_start_angle = 90
                rear_vol_reduction = 0.15
                interp_speed = 8.0

            # === ENHANCED Directional Lowpass (Head Shadow) ===
            abs_angle = abs(relative_angle)

            # Calculate lowpass cutoff based on direction
            # Front (0°): 22000 Hz (no filtering)
            # Side (90°): ~12000 Hz (slight filtering)
            # Behind (180°): rear_cutoff Hz (significant muffling - ENHANCED)
            if abs_angle <= rear_start_angle:
                rear_factor = 0
            else:
                # Smooth transition from side to behind
                rear_factor = (abs_angle - rear_start_angle) / (180.0 - rear_start_angle)
                # Apply squared curve for more gradual onset
                rear_factor = rear_factor ** 1.5

            # === ENHANCED Rear Volume Reduction ===
            # Sounds behind should also be slightly quieter (head shadow)
            rear_volume_mult = 1.0
            if abs_angle > rear_start_angle:
                rear_volume_mult = 1.0 - (rear_factor * rear_vol_reduction)

            # === Vertical Positioning ===
            vertical_factor = 0
            if abs(altitude_diff) > 5:
                if altitude_diff > 0:
                    # Sound is above - brightness boost (reduce lowpass effect)
                    # This simulates high frequencies traveling down better
                    vertical_factor = -min(1.0, altitude_diff / 30.0) * 0.35
                else:
                    # Sound is below - duller (increase lowpass effect)
                    # Simulates ground absorption
                    vertical_factor = min(1.0, abs(altitude_diff) / 30.0) * 0.35

            # === Occlusion Effect ===
            occlusion_factor = 0
            occlusion_volume = 1.0
            if apply_occlusion:
                occlusion_factor, occ_cutoff, occlusion_volume = self.calculate_occlusion(
                    relative_angle, altitude_diff, distance
                )
                # Add occlusion to the filtering
                if occlusion_factor > 0.05:
                    rear_factor = max(rear_factor, occlusion_factor * 0.8)

            # === Combine factors for final lowpass cutoff ===
            combined_factor = max(0, min(1.0, rear_factor + vertical_factor))
            # Use enhanced rear cutoff for behind sounds
            min_cutoff = rear_cutoff if abs_angle > rear_start_angle else 3000
            lowpass_cutoff = 22000 - (combined_factor * (22000 - min_cutoff))
            lowpass_cutoff = max(min_cutoff, min(22000, lowpass_cutoff))

            # Calculate target lowpass gain
            target_lowpass_gain = lowpass_cutoff / 22000.0

            # Calculate target volume multiplier
            target_volume_mult = rear_volume_mult * occlusion_volume

            # === SMOOTH TRANSITIONS ===
            # Interpolate filter changes to prevent jarring audio
            if channel_id is not None:
                # Get or create state for this channel
                if channel_id not in self._occlusion_states:
                    self._occlusion_states[channel_id] = {
                        'lowpass_gain': target_lowpass_gain,
                        'volume_mult': target_volume_mult
                    }
                state = self._occlusion_states[channel_id]

                # Interpolate toward target
                current_lowpass = state['lowpass_gain']
                current_volume = state['volume_mult']

                # Calculate interpolation step (ensure minimum dt for responsiveness)
                # At 60fps, dt should be ~0.016. If smaller, use minimum to prevent sluggish response.
                effective_dt = max(dt, 0.016)  # Minimum 16ms (60fps equivalent)
                interp_step = interp_speed * effective_dt * 0.7  # 0.7x for subtle, natural filtering

                # Smooth interpolation
                if abs(target_lowpass_gain - current_lowpass) > 0.01:
                    if target_lowpass_gain > current_lowpass:
                        state['lowpass_gain'] = min(target_lowpass_gain, current_lowpass + interp_step)
                    else:
                        state['lowpass_gain'] = max(target_lowpass_gain, current_lowpass - interp_step)
                else:
                    state['lowpass_gain'] = target_lowpass_gain

                if abs(target_volume_mult - current_volume) > 0.01:
                    if target_volume_mult > current_volume:
                        state['volume_mult'] = min(target_volume_mult, current_volume + interp_step)
                    else:
                        state['volume_mult'] = max(target_volume_mult, current_volume - interp_step)
                else:
                    state['volume_mult'] = target_volume_mult

                # Use interpolated values
                lowpass_gain = state['lowpass_gain']
                final_volume_mult = state['volume_mult']
            else:
                # No channel_id - use direct values (backwards compatibility)
                lowpass_gain = target_lowpass_gain
                final_volume_mult = target_volume_mult

            # Apply lowpass via low_pass_gain
            raw_channel.low_pass_gain = lowpass_gain

            # === Air Absorption (Distance-based) ===
            c = self._get_spatial_constants()
            if apply_air_absorption and distance > c['air_start']:
                air_absorption_hz = self.calculate_air_absorption(distance)
                if air_absorption_hz > 50:
                    # Simulate air absorption via additional lowpass and volume reduction
                    absorption_factor = air_absorption_hz / c['air_cutoff']
                    # Further reduce the lowpass gain slightly for distant sounds
                    lowpass_gain *= (1.0 - absorption_factor * 0.15)
                    raw_channel.low_pass_gain = max(0.1, lowpass_gain)

            # === Apply Volume Multiplier ===
            if final_volume_mult < 1.0:
                try:
                    current_vol = raw_channel.volume
                    raw_channel.volume = current_vol * final_volume_mult
                except Exception:
                    pass

            # === LOGGING ===
            alog = _get_audio_log()
            source_name = channel_id if channel_id else "unknown"
            is_interpolating = channel_id is not None and channel_id in self._occlusion_states
            alog.occlusion(
                source=source_name,
                angle=relative_angle,
                lowpass_gain=lowpass_gain,
                rear_factor=rear_factor,
                volume_mult=final_volume_mult,
                is_interpolating=is_interpolating
            )

        except Exception as e:
            logger = _get_logger()
            logger.debug(f"Directional filter failed (channel may have ended)", {
                'error': str(e)
            })

    def apply_enhanced_spatial_filters(self, channel, source_x, source_y, source_altitude,
                                        listener_x, listener_y, listener_altitude,
                                        listener_facing, velocity=None):
        """Apply complete enhanced spatial audio filtering to a channel.

        Convenience method that calculates all parameters and applies:
        - Directional filtering (front/behind/above/below)
        - Air absorption (distance-based)
        - Occlusion simulation
        - Doppler velocity (if provided)

        Args:
            channel: FMOD channel or FMODChannelWrapper
            source_x, source_y: Source position in world coordinates
            source_altitude: Source altitude in feet
            listener_x, listener_y: Listener position
            listener_altitude: Listener altitude in feet
            listener_facing: Listener facing angle in degrees
            velocity: Optional (vx, vy, vz) velocity tuple for Doppler
        """
        # Calculate directional parameters
        relative_angle, altitude_diff, distance = self.calculate_directional_params(
            source_x, source_y, source_altitude,
            listener_x, listener_y, listener_altitude,
            listener_facing
        )

        # Apply directional filter with all enhancements
        self.apply_directional_filter(
            channel, relative_angle, altitude_diff, distance,
            apply_air_absorption=True, apply_occlusion=True
        )

        # Set 3D position for Doppler effect
        if velocity is not None:
            self.set_channel_3d_attributes(
                channel,
                (source_x, source_altitude / 3.28, source_y),  # Convert alt to meters
                velocity
            )

    def calculate_directional_params(self, source_x, source_y, source_altitude,
                                     listener_x, listener_y, listener_altitude,
                                     listener_facing):
        """Calculate parameters needed for directional audio filtering.

        Args:
            source_x, source_y: Source position
            source_altitude: Source altitude in feet
            listener_x, listener_y: Listener position
            listener_altitude: Listener altitude in feet
            listener_facing: Listener facing angle in degrees (0=North)

        Returns:
            Tuple of (relative_angle, altitude_diff_meters, distance_meters)
        """
        import math

        dx = source_x - listener_x
        dy = source_y - listener_y

        # Calculate horizontal distance
        horizontal_dist = math.sqrt(dx * dx + dy * dy)

        # Calculate angle to source (0=North, 90=East)
        angle_to_source = math.degrees(math.atan2(dx, dy)) % 360

        # Calculate relative angle (0=front, 180=behind)
        relative_angle = (angle_to_source - listener_facing + 180) % 360 - 180

        # Calculate altitude difference in meters
        altitude_diff = (source_altitude - listener_altitude) / 3.28

        # Calculate 3D distance
        alt_diff_m = altitude_diff
        distance = math.sqrt(horizontal_dist * horizontal_dist + alt_diff_m * alt_diff_m)

        return relative_angle, altitude_diff, distance

    # === Enhanced Spatial Audio (Manual Fallback) ===

    def calculate_spatial_audio(self, source_x, source_y, source_altitude,
                                 listener_x, listener_y, listener_altitude,
                                 listener_facing, max_distance=50.0, min_distance=2.0):
        """Calculate stereo panning and volume for 3D audio positioning.

        Args:
            source_x, source_y: Source position in world coordinates (meters)
            source_altitude: Source altitude in feet
            listener_x, listener_y: Listener position in world coordinates (meters)
            listener_altitude: Listener altitude in feet
            listener_facing: Listener facing angle in degrees (0=North, 90=East)
            max_distance: Maximum audible distance (meters)
            min_distance: Distance at which volume is maximum (meters)

        Returns:
            tuple: (pan, volume, distance, relative_angle, altitude_diff)
                - pan: -1.0 (left) to 1.0 (right)
                - volume: 0.0 to 1.0
                - distance: 3D distance in meters
                - relative_angle: Angle from listener's facing (-180 to 180)
                - altitude_diff: Altitude difference in feet (positive = above)
        """
        import math

        # Calculate horizontal distance
        dx = source_x - listener_x
        dy = source_y - listener_y
        horizontal_distance = math.sqrt(dx * dx + dy * dy)

        # Calculate altitude difference (source - listener)
        altitude_diff = source_altitude - listener_altitude

        # Calculate 3D distance (convert altitude from feet to meters)
        dz = altitude_diff / 3.28  # feet to meters
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        # Calculate absolute angle from listener to source (0 = North/+Y)
        angle_to_source = math.degrees(math.atan2(dx, dy)) % 360

        # Calculate relative angle (how far left/right of listener's facing)
        relative_angle = (angle_to_source - listener_facing + 180) % 360 - 180

        # === Enhanced Stereo Panning ===
        # More realistic panning with vertical offset consideration
        if abs(relative_angle) <= 90:
            # Source is in front hemisphere
            pan = relative_angle / 90.0
        else:
            # Source is behind - wrap panning more dramatically
            if relative_angle > 0:
                pan = 1.0 - (relative_angle - 90) / 90.0 * 0.3
            else:
                pan = -1.0 - (relative_angle + 90) / 90.0 * 0.3

        # Reduce panning extremity for sources significantly above/below
        # (sounds from above/below should feel more centered)
        altitude_factor = 1.0 - min(0.5, abs(altitude_diff) / 100.0)
        pan *= altitude_factor

        # Clamp pan to valid range
        pan = max(-1.0, min(1.0, pan))

        # === Enhanced Volume Calculation ===
        # Use logarithmic falloff for more natural distance perception
        if distance <= min_distance:
            volume = 1.0
        elif distance >= max_distance:
            volume = 0.02  # Slight ambient presence at max distance
        else:
            # Logarithmic falloff for more natural sound
            normalized = (distance - min_distance) / (max_distance - min_distance)
            # Use sqrt for moderate falloff (between linear and inverse square)
            volume = 1.0 - (normalized ** 0.6)

        # Slight volume boost for sources above (sound travels down well)
        if altitude_diff > 20:
            volume *= 1.1
        # Slight volume reduction for sources below (muffled by ground)
        elif altitude_diff < -20:
            volume *= 0.9

        # Clamp volume
        volume = max(0.0, min(1.0, volume))

        return pan, volume, distance, relative_angle, altitude_diff

    def apply_spatial_to_channel(self, channel, pan, volume, base_volume=1.0):
        """Apply spatial audio parameters to an FMOD channel.

        Args:
            channel: The FMOD Channel object (or FMODChannelWrapper)
            pan: Pan position (-1.0 to 1.0)
            volume: Volume multiplier (0.0 to 1.0)
            base_volume: Base volume for this sound category
        """
        if channel is None:
            return

        final_volume = base_volume * volume * self.master_volume

        # Calculate left/right volumes for stereo panning
        left_vol = final_volume * min(1.0, 1.0 - pan)
        right_vol = final_volume * min(1.0, 1.0 + pan)

        try:
            if hasattr(channel, 'set_volume'):
                # FMODChannelWrapper
                channel.set_volume(left_vol, right_vol)
            else:
                # Raw FMOD channel
                channel.volume = final_volume
                channel.set_pan(pan)
        except Exception:
            pass

    def load_sound(self, path, name, loop=False, is_3d=False, stream=False, mono=False):
        """Load a sound file into memory or as a stream.

        Args:
            path: Path to the sound file
            name: Unique name to reference this sound
            loop: If True, sound will loop when played
            is_3d: If True, enable 3D positioning (default False for 2D)
            stream: If True, stream from disk instead of loading into memory
                   (OPTIMIZATION: Use for large files to reduce memory usage)
            mono: If True, mark sound for mono downmix at playback
                  (Use for sounds with baked-in stereo panning like passbys/supersonics)

        Returns:
            The loaded Sound object, or None if loading failed
        """
        # OPTIMIZATION: Use CREATESTREAM for large files to reduce memory usage
        if stream:
            mode = MODE.CREATESTREAM
        else:
            mode = MODE.CREATESAMPLE

        if not is_3d:
            mode |= MODE.TWOD
        else:
            mode |= MODE.THREED
        if loop:
            mode |= MODE.LOOP_NORMAL
        else:
            mode |= MODE.LOOP_OFF

        try:
            sound = self.system.create_sound(path, mode)
            self.sounds[name] = sound
            # Track sounds that need mono downmix at playback
            if mono:
                if not hasattr(self, '_mono_sounds'):
                    self._mono_sounds = set()
                self._mono_sounds.add(name)
            return sound
        except Exception as e:
            print(f"Failed to load sound '{name}' from {path}: {e}")
            return None

    def load_sound_compressed(self, path, name, loop=False, is_3d=False, mono=False):
        """Load a sound file as compressed sample (keeps compressed in memory).

        OPTIMIZATION: Uses less memory than full decompression but more CPU.
        Best for short sounds that play frequently.

        Args:
            path: Path to the sound file
            name: Unique name to reference this sound
            loop: If True, sound will loop when played
            is_3d: If True, enable 3D positioning
            mono: If True, mark sound for mono downmix at playback

        Returns:
            The loaded Sound object, or None if loading failed
        """
        mode = MODE.CREATECOMPRESSEDSAMPLE
        if not is_3d:
            mode |= MODE.TWOD
        else:
            mode |= MODE.THREED
        if loop:
            mode |= MODE.LOOP_NORMAL
        else:
            mode |= MODE.LOOP_OFF

        try:
            sound = self.system.create_sound(path, mode)
            self.sounds[name] = sound
            # Track sounds that need mono downmix at playback
            if mono:
                if not hasattr(self, '_mono_sounds'):
                    self._mono_sounds = set()
                self._mono_sounds.add(name)
            return sound
        except Exception as e:
            print(f"Failed to load compressed sound '{name}' from {path}: {e}")

    def load_sound_3d(self, path, name, loop=False, min_distance=2.0, max_distance=60.0,
                       use_logarithmic=True):
        """Load a sound file with 3D positioning enabled.

        This is a convenience method for loading sounds that will use
        FMOD's native 3D spatialization (binaural-like positioning).

        Args:
            path: Path to the sound file
            name: Unique name to reference this sound
            loop: If True, sound will loop when played
            min_distance: Distance at which sound is at full volume (meters)
            max_distance: Distance at which sound reaches minimum volume (meters)
            use_logarithmic: If True (default), use logarithmic/inverse-square rolloff
                            for more natural distance attenuation. If False, use linear.

        Returns:
            The loaded Sound object, or None if loading failed

        Note:
            Logarithmic rolloff follows the inverse square law where volume halves
            per doubling of distance - this is how sound behaves in the real world.
            Linear rolloff provides more predictable behavior but sounds less natural.
        """
        # Use logarithmic (inverse square) rolloff for natural sound falloff
        # This is more realistic than linear - sound halves per doubling of distance
        if use_logarithmic:
            # THREED_INVERSEROLLOFF uses inverse square law (1/distance^2)
            mode = MODE.CREATESAMPLE | MODE.THREED | MODE.THREED_INVERSEROLLOFF
        else:
            mode = MODE.CREATESAMPLE | MODE.THREED | MODE.THREED_LINEARROLLOFF

        if loop:
            mode |= MODE.LOOP_NORMAL
        else:
            mode |= MODE.LOOP_OFF

        try:
            sound = self.system.create_sound(path, mode)
            if sound:
                # Set 3D distance parameters
                # For logarithmic rolloff:
                # - min_distance: sound is at full volume
                # - max_distance: sound reaches minimum audible level
                sound.min_distance = min_distance
                sound.max_distance = max_distance
                self.sounds[name] = sound
            return sound
        except Exception as e:
            print(f"Failed to load 3D sound '{name}' from {path}: {e}")
            return None

    def load_sounds_from_dir(self, directory, name_prefix=None):
        """Load all WAV sounds from a directory.

        Args:
            directory: Path to the directory containing sound files
            name_prefix: Optional prefix for sound names (default: use filename)

        Returns:
            List of loaded Sound objects
        """
        sounds = []
        if not os.path.isdir(directory):
            print(f"Directory not found: {directory}")
            return sounds

        for f in sorted(os.listdir(directory)):
            if f.lower().endswith('.wav'):
                path = os.path.join(directory, f)
                name = os.path.splitext(f)[0]
                if name_prefix:
                    name = f"{name_prefix}_{name}"
                sound = self.load_sound(path, name)
                if sound:
                    sounds.append(sound)
        return sounds

    def get_sound(self, name):
        """Get a loaded sound by name.

        Args:
            name: The sound name used when loading

        Returns:
            The Sound object, or None if not found
        """
        return self.sounds.get(name)

    def play_sound(self, sound_name, group_name=None, loop_count=0, paused=False):
        """Play a loaded sound.

        Args:
            sound_name: Name of the loaded sound to play
            group_name: Optional channel group name for volume control
            loop_count: Number of loops (-1 for infinite, 0 for one-shot)
            paused: If True, start paused (call channel.paused = False to play)

        Returns:
            The Channel object for controlling playback, or None if failed
        """
        if sound_name not in self.sounds:
            print(f"Sound not found: {sound_name}")
            return None

        sound = self.sounds[sound_name]
        group = None
        if group_name and group_name in self.channel_groups:
            group = self.channel_groups[group_name]['group']

        try:
            channel = self.system.play_sound(sound, group, paused)
            if loop_count != 0:
                channel.loop_count = loop_count
            return channel
        except Exception as e:
            print(f"Failed to play sound '{sound_name}': {e}")
            return None

    def play_sound_object(self, sound, group_name=None, loop_count=0, paused=False,
                          position_3d=None, velocity=None):
        """Play a Sound object directly (useful for sound lists like thrusters).

        Args:
            sound: The Sound object to play
            group_name: Optional channel group name for volume control
            loop_count: Number of loops (-1 for infinite, 0 for one-shot)
            paused: If True, start paused
            position_3d: Optional (x, y, z) position for 3D spatialization
            velocity: Optional (vx, vy, vz) velocity for Doppler effect

        Returns:
            The Channel object for controlling playback, or None if failed
        """
        group = None
        if group_name and group_name in self.channel_groups:
            group = self.channel_groups[group_name]['group']

        try:
            # Start paused if we need to set 3D position before playing
            start_paused = paused or (position_3d is not None)
            channel = self.system.play_sound(sound, group, start_paused)
            if loop_count != 0:
                channel.loop_count = loop_count

            # Set 3D position if provided
            if position_3d is not None:
                self.set_channel_3d_attributes(channel, position_3d, velocity)
                # Unpause if we only paused for positioning
                if not paused:
                    channel.paused = False

            return channel
        except Exception as e:
            print(f"Failed to play sound object: {e}")
            return None

    def get_channel(self, name):
        """Get a tracked channel by name.

        Args:
            name: The channel name

        Returns:
            The Channel object, or None if not found/invalid
        """
        return self.channels.get(name)

    def set_channel(self, name, channel):
        """Store a channel reference by name.

        Args:
            name: Name to identify this channel
            channel: The Channel object to store
        """
        self.channels[name] = channel

    def stop_channel(self, name):
        """Stop a named channel.

        Args:
            name: The channel name to stop
        """
        if name in self.channels and self.channels[name]:
            try:
                self.channels[name].stop()
            except Exception:
                pass  # Channel may already be stopped/invalid
            self.channels[name] = None

    def check_channel_ended(self, name):
        """Check if a named channel has stopped playing.

        Args:
            name: The channel name to check

        Returns:
            True if channel is not playing (ended or never started)
        """
        channel = self.channels.get(name)
        if channel is None:
            return True
        try:
            return not channel.is_playing
        except Exception:
            return True  # Channel invalid, consider ended

    def is_channel_playing(self, name):
        """Check if a named channel is currently playing.

        Args:
            name: The channel name to check

        Returns:
            True if channel is actively playing
        """
        return not self.check_channel_ended(name)

    def set_channel_volume(self, name, volume):
        """Set volume for a named channel.

        Args:
            name: The channel name
            volume: Volume level (0.0 to 1.0, can exceed 1.0 for amplification)
        """
        channel = self.channels.get(name)
        if channel:
            try:
                channel.volume = volume
            except Exception:
                pass

    def set_channel_pan(self, name, pan):
        """Set stereo pan for a named channel.

        Args:
            name: The channel name
            pan: Pan position (-1.0 = left, 0.0 = center, 1.0 = right)
        """
        channel = self.channels.get(name)
        if channel:
            try:
                channel.set_pan(pan)
            except Exception:
                pass

    def apply_spatial_audio(self, name, pan, volume):
        """Apply both pan and volume for spatial positioning.

        Args:
            name: The channel name
            pan: Pan position (-1.0 to 1.0)
            volume: Volume level (0.0 to 1.0)
        """
        channel = self.channels.get(name)
        if channel:
            try:
                channel.set_pan(pan)
                channel.volume = volume
            except Exception:
                pass

    def set_master_volume(self, volume):
        """Set master volume affecting all sounds.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.master_volume = max(0.0, min(1.0, volume))
        if self.master_group:
            self.master_group.volume = self.master_volume

    def get_master_volume(self):
        """Get current master volume.

        Returns:
            Current master volume (0.0 to 1.0)
        """
        return self.master_volume

    def set_group_volume(self, group_name, volume):
        """Set volume for a channel group.

        Args:
            group_name: Name of the channel group
            volume: Volume level (0.0 to 1.0)
        """
        if group_name in self.channel_groups:
            try:
                self.channel_groups[group_name]['group'].volume = volume
            except Exception:
                pass

    def get_group_volume(self, group_name):
        """Get current volume for a channel group.

        Args:
            group_name: Name of the channel group

        Returns:
            Current volume, or 1.0 if group not found
        """
        if group_name in self.channel_groups:
            try:
                return self.channel_groups[group_name]['group'].volume
            except Exception:
                pass
        return 1.0

    def update(self):
        """Update FMOD system. Must be called every frame."""
        if self.system:
            try:
                self.system.update()
            except Exception:
                pass

    def cleanup(self):
        """Release all FMOD resources. Call before exiting."""
        if not self._initialized:
            return

        # Stop all tracked channels
        for name, channel in self.channels.items():
            if channel:
                try:
                    channel.stop()
                except Exception:
                    pass
        self.channels.clear()

        # Release DSP effects
        highpass_dsp = getattr(self, '_highpass_dsp', None)
        compressor_dsp = getattr(self, '_compressor_dsp', None)
        for dsp in [self._reverb_dsp, self._lowpass_dsp, self._distortion_dsp, highpass_dsp, compressor_dsp]:
            if dsp:
                try:
                    dsp.release()
                except Exception:
                    pass
        self._reverb_dsp = None
        self._lowpass_dsp = None
        self._distortion_dsp = None
        self._highpass_dsp = None
        self._compressor_dsp = None

        # Clear occlusion states
        self._occlusion_states.clear()

        for name, dsp in self.dsp_effects.items():
            try:
                dsp.release()
            except Exception:
                pass
        self.dsp_effects.clear()

        # Release all sounds
        for name, sound in self.sounds.items():
            try:
                sound.release()
            except Exception:
                pass
        self.sounds.clear()

        # Release channel groups
        for name, data in self.channel_groups.items():
            if name == '_master_dsp':
                continue  # Skip special tracking entry
            try:
                data['group'].release()
            except Exception:
                pass
        self.channel_groups.clear()

        # Close and release system
        if self.system:
            try:
                self.system.close()
                self.system.release()
            except Exception:
                pass
            self.system = None

        self._initialized = False
        print("FMOD audio system released")


# Convenience function for quick testing
def test_fmod():
    """Quick test to verify FMOD is working."""
    audio = MechAudio()
    audio.init()
    print("FMOD test successful!")
    audio.cleanup()
    return True


class FMODChannelWrapper:
    """Pygame-compatible channel wrapper for FMOD.

    This class provides a pygame.mixer.Channel-like interface while using
    FMOD under the hood. This allows gradual migration from pygame to FMOD.

    Supports both 2D stereo panning and FMOD's native 3D positioning.
    Enhanced with crossfade support for smooth sound transitions.
    """

    def __init__(self, audio_system, group_name=None, name=None, is_3d=False):
        """Create a channel wrapper.

        Args:
            audio_system: The MechAudio instance
            group_name: Optional channel group for volume control
            name: Optional name for this channel (for tracking)
            is_3d: If True, channel uses FMOD 3D positioning instead of manual pan
        """
        self.audio = audio_system
        self.group_name = group_name
        self.name = name
        self._channel = None
        self._volume = 1.0
        self._left_vol = 1.0
        self._right_vol = 1.0
        self._mono_downmix = False  # Track mono downmix state for combined matrix
        self._is_3d = is_3d  # Use FMOD 3D positioning
        self._position_3d = [0, 0, 0]  # 3D position (game coordinates)

        # Crossfade state
        self._fade_state = 'none'  # 'none', 'fading_out', 'fading_in'
        self._fade_volume = 1.0  # Current fade multiplier
        self._fade_target = 1.0  # Target fade volume
        self._fade_rate = 0.0  # Volume change per second
        self._pending_sound = None  # Sound waiting to play after fade out
        self._pending_params = {}  # Parameters for pending sound
        self._stop_after_fade = False  # Stop channel after fade out completes

    def play(self, sound, loops=0, mono_downmix=False, position_3d=None, velocity=None):
        """Play a sound on this channel.

        Args:
            sound: Either a Sound object or a sound name string
            loops: Number of loops (-1 for infinite, 0 for one-shot)
            mono_downmix: If True, downmix stereo to mono for proper 3D positioning
            position_3d: Optional (x, y, z) tuple for 3D sounds - sets position before playing
            velocity: Optional (vx, vy, vz) tuple for Doppler effect

        Returns:
            self for chaining
        """
        # Stop any currently playing sound
        self.stop()

        # For 3D sounds, start paused so we can set position first
        start_paused = (self._is_3d and position_3d is not None)

        # Determine if sound is a Sound object or name
        if isinstance(sound, str):
            self._channel = self.audio.play_sound(sound, self.group_name, loops, paused=start_paused)
        else:
            # It's a Sound object - play directly (paused if 3D with position)
            self._channel = self.audio.play_sound_object(sound, self.group_name, loops, paused=start_paused)

        # Store mono downmix state for combined matrix in _apply_volume
        self._mono_downmix = mono_downmix

        if self._channel:
            # For 3D sounds with position, set position (and velocity) before unpausing
            if position_3d is not None:
                self._position_3d = list(position_3d)
                self.audio.set_channel_3d_attributes(self._channel, position_3d, velocity)
                # Unpause after setting position
                if start_paused:
                    try:
                        self._channel.paused = False
                    except Exception:
                        pass

            # Apply stored volume/panning for non-3D sounds only
            # 3D sounds use FMOD's distance attenuation
            if not self._is_3d:
                self._apply_volume()

            # Note: Steam Audio FMOD plugin processes audio through FMOD's
            # native 3D system - per-channel DSP attachment is not needed.
            # The plugin automatically applies HRTF when 3D positions are set.

            # Register channel with audio system for state tracking
            if self.name:
                self.audio.set_channel(self.name, self._channel)

        return self

    def is_valid(self):
        """Check if channel is in a valid, usable state.

        Returns:
            True if channel can be safely used for operations
        """
        if self._channel is None:
            return False
        try:
            # Attempt a lightweight query to verify channel is valid
            _ = self._channel.is_playing
            return True
        except Exception:
            return False

    def play_crossfade(self, sound, fade_out_ms=100, fade_in_ms=50,
                       loops=0, mono_downmix=False, position_3d=None):
        """Play a sound with crossfade transition from current sound.

        If no sound is currently playing, plays immediately.
        Otherwise fades out current sound, then fades in new sound.

        Args:
            sound: Sound object or name to play
            fade_out_ms: Milliseconds to fade out current sound
            fade_in_ms: Milliseconds to fade in new sound
            loops: Number of loops (-1 for infinite)
            mono_downmix: If True, downmix stereo to mono
            position_3d: Optional 3D position tuple

        Returns:
            self for chaining
        """
        logger = _get_logger()

        # If not currently playing, just play directly
        if not self.get_busy():
            logger.debug(f"Crossfade: no current sound, playing directly", {'channel': self.name})
            return self.play(sound, loops, mono_downmix, position_3d)

        # Store pending sound parameters
        self._pending_sound = sound
        self._pending_params = {
            'loops': loops,
            'mono_downmix': mono_downmix,
            'position_3d': position_3d,
            'fade_in_ms': fade_in_ms
        }

        # Start fade out
        self._fade_state = 'fading_out'
        self._fade_volume = 1.0
        self._fade_target = 0.0
        # Convert ms to rate (volume per second)
        self._fade_rate = 1000.0 / max(1, fade_out_ms)

        logger.debug(f"Crossfade: starting fade out", {
            'channel': self.name,
            'fade_out_ms': fade_out_ms
        })

        return self

    def play_with_fade_in(self, sound, fade_in_ms=150, loops=0,
                          mono_downmix=False, position_3d=None):
        """Play a sound with a fade-in effect.

        Starts the sound at 0 volume and fades up to full volume.

        Args:
            sound: Sound object or name to play
            fade_in_ms: Milliseconds to fade in (default 150ms)
            loops: Number of loops (-1 for infinite)
            mono_downmix: If True, downmix stereo to mono
            position_3d: Optional 3D position tuple

        Returns:
            self for chaining
        """
        # Play the sound (this will stop any current sound)
        self.play(sound, loops, mono_downmix, position_3d)

        if self._channel:
            # Start fade in from 0
            self._fade_state = 'fading_in'
            self._fade_volume = 0.0
            self._fade_target = 1.0
            self._fade_rate = 1000.0 / max(1, fade_in_ms)
            self._apply_fade_volume()

        return self

    def fade_out(self, fade_out_ms=200, stop_when_done=True):
        """Fade out the current sound.

        Args:
            fade_out_ms: Milliseconds to fade out (default 200ms)
            stop_when_done: If True, stop the channel when fade completes

        Returns:
            self for chaining
        """
        if not self.get_busy():
            return self

        self._fade_state = 'fading_out'
        self._fade_volume = self._fade_volume if self._fade_volume < 1.0 else 1.0
        self._fade_target = 0.0
        self._fade_rate = 1000.0 / max(1, fade_out_ms)
        self._stop_after_fade = stop_when_done
        # Clear pending sound so fade_out just stops
        self._pending_sound = None
        self._pending_params = {}

        return self

    def update_fade(self, dt):
        """Update crossfade state. Must be called each frame when crossfading.

        Args:
            dt: Delta time in seconds since last frame
        """
        if self._fade_state == 'none':
            return

        logger = _get_logger()

        if self._fade_state == 'fading_out':
            # Decrease volume
            self._fade_volume = max(0.0, self._fade_volume - self._fade_rate * dt)
            self._apply_fade_volume()

            if self._fade_volume <= 0.0:
                # Fade out complete - stop current and start new
                logger.debug(f"Crossfade: fade out complete", {'channel': self.name})

                # Stop current sound
                if self._channel:
                    try:
                        self._channel.stop()
                    except Exception as e:
                        error_str = str(e).upper()
                        # INVALID HANDLE and CHANNEL STOLEN are expected - don't warn
                        if 'INVALID HANDLE' not in error_str and 'CHANNEL STOLEN' not in error_str:
                            logger.warning(f"Crossfade: error stopping channel", {
                                'channel': self.name,
                                'error': str(e)
                            })
                    self._channel = None

                # Play pending sound if we have one (crossfade case)
                if self._pending_sound is not None:
                    self.play(
                        self._pending_sound,
                        self._pending_params.get('loops', 0),
                        self._pending_params.get('mono_downmix', False),
                        self._pending_params.get('position_3d')
                    )

                    # Start fade in
                    fade_in_ms = self._pending_params.get('fade_in_ms', 50)
                    self._fade_state = 'fading_in'
                    self._fade_volume = 0.0
                    self._fade_target = 1.0
                    self._fade_rate = 1000.0 / max(1, fade_in_ms)
                    self._apply_fade_volume()

                    logger.debug(f"Crossfade: starting fade in", {
                        'channel': self.name,
                        'fade_in_ms': fade_in_ms
                    })
                else:
                    # Simple fade out (no pending sound)
                    self._fade_state = 'none'
                    self._fade_volume = 1.0  # Reset for next play

                # Clear pending and stop flag
                self._pending_sound = None
                self._pending_params = {}
                self._stop_after_fade = False

        elif self._fade_state == 'fading_in':
            # Increase volume
            self._fade_volume = min(1.0, self._fade_volume + self._fade_rate * dt)
            self._apply_fade_volume()

            if self._fade_volume >= 1.0:
                # Fade in complete
                self._fade_state = 'none'
                logger.debug(f"Crossfade: fade in complete", {'channel': self.name})

    def _apply_fade_volume(self):
        """Apply current fade volume multiplier to channel."""
        if self._channel is None:
            return
        try:
            # Apply fade multiplier on top of base volume
            effective_volume = self._volume * self._fade_volume
            self._channel.volume = effective_volume
        except Exception:
            pass

    def is_fading(self):
        """Check if channel is currently in a crossfade transition.

        Returns:
            True if crossfading
        """
        return self._fade_state != 'none'

    def stop(self):
        """Stop the channel and reset fade state."""
        logger = _get_logger()

        # Reset fade state
        self._fade_state = 'none'
        self._fade_volume = 1.0
        self._pending_sound = None
        self._pending_params = {}

        if self._channel:
            # Only attempt stop if channel is still valid
            if self.is_valid():
                try:
                    self._channel.stop()
                    logger.debug(f"Channel stopped", {'channel': self.name})
                except Exception as e:
                    error_str = str(e).upper()
                    # INVALID HANDLE and CHANNEL STOLEN are expected when sound finished
                    # or FMOD reused the channel - don't log warnings for these
                    if 'INVALID HANDLE' not in error_str and 'CHANNEL STOLEN' not in error_str:
                        logger.warning(f"Error stopping channel", {
                            'channel': self.name,
                            'error': str(e)
                        })
            self._channel = None
            # Clear registered channel
            if self.name:
                self.audio.channels[self.name] = None

    def get_busy(self):
        """Check if channel is playing.

        Returns:
            True if a sound is playing
        """
        if self._channel is None:
            return False
        try:
            return self._channel.is_playing
        except Exception as e:
            # Channel became invalid - log and clean up
            logger = _get_logger()
            logger.debug(f"Channel query failed (likely ended)", {
                'channel': self.name,
                'error': str(e)
            })
            self._channel = None
            return False

    def set_volume(self, left, right=None):
        """Set channel volume with optional stereo panning.

        Args:
            left: Left channel volume (0.0-1.0), or mono volume if right is None
            right: Right channel volume (0.0-1.0), or None for mono
        """
        if right is None:
            self._volume = left
            self._left_vol = left
            self._right_vol = left
        else:
            self._left_vol = left
            self._right_vol = right
            self._volume = (left + right) / 2

        self._apply_volume()

    def _apply_volume(self):
        """Apply volume and panning to the current channel.

        When _mono_downmix is True, uses a combined mix matrix that first
        downmixes stereo to mono, then applies panning. This is necessary
        because set_pan() would override a separate mix matrix.
        """
        if self._channel is None:
            return

        # Skip if channel is no longer valid (sound finished, channel stolen)
        if not self.is_valid():
            return

        try:
            # Calculate pan from left/right volumes
            if self._left_vol + self._right_vol > 0:
                pan = (self._right_vol - self._left_vol) / max(self._left_vol + self._right_vol, 0.001)
            else:
                pan = 0.0

            # Apply fade multiplier if fading
            effective_volume = self._volume * self._fade_volume
            self._channel.volume = effective_volume

            if self._mono_downmix:
                # Combined mono downmix + pan via mix matrix
                # First average L+R (0.5 each), then apply pan gains
                left_gain = min(1.0, 1.0 - pan)
                right_gain = min(1.0, 1.0 + pan)

                # Matrix: [outL_inL, outL_inR, outR_inL, outR_inR]
                # Output L = 0.5 * left_gain * (Input L + Input R)
                # Output R = 0.5 * right_gain * (Input L + Input R)
                mix_matrix = [
                    0.5 * left_gain,   # Output L from Input L
                    0.5 * left_gain,   # Output L from Input R
                    0.5 * right_gain,  # Output R from Input L
                    0.5 * right_gain,  # Output R from Input R
                ]
                self._channel.set_mix_matrix(mix_matrix, 2, 2)
            else:
                # Standard pan without mono downmix
                self._channel.set_pan(pan)
        except Exception as e:
            error_str = str(e).upper()
            # INVALID HANDLE and CHANNEL STOLEN are expected - don't warn
            if 'INVALID HANDLE' not in error_str and 'CHANNEL STOLEN' not in error_str:
                logger = _get_logger()
                logger.warning(f"Error applying volume/pan", {
                    'channel': self.name,
                    'error': str(e)
                })

    @property
    def is_playing(self):
        """Check if channel is playing (property version)."""
        return self.get_busy()

    def set_pitch(self, pitch):
        """Set the playback pitch for this channel.

        Args:
            pitch: Pitch multiplier (1.0 = normal, 2.0 = octave up, 0.5 = octave down)
                   Typical range: 0.5 to 2.0 for natural-sounding variation
        """
        if self._channel is None:
            return

        if not self.is_valid():
            return

        try:
            # Clamp pitch to reasonable range
            pitch = max(0.5, min(2.0, pitch))
            self._channel.pitch = pitch
        except Exception:
            pass  # Channel may be invalid

    def get_pitch(self):
        """Get the current playback pitch."""
        if self._channel is None:
            return 1.0

        try:
            return self._channel.pitch
        except Exception:
            return 1.0

    def set_3d_position(self, x, y, z=0, velocity=None):
        """Set 3D position for this channel (for 3D sounds).

        Args:
            x: X position (East in game coordinates)
            y: Y position (North in game coordinates)
            z: Z position/altitude (Up in game coordinates)
            velocity: Optional (vx, vy, vz) velocity tuple for Doppler

        Note: This only affects sounds loaded with 3D mode.
              The coordinate conversion to FMOD space is handled by MechAudio.
        """
        self._position_3d = [x, y, z]
        if self._channel is not None:
            self.audio.set_channel_3d_attributes(self._channel, (x, y, z), velocity)

    def get_3d_position(self):
        """Get the current 3D position."""
        return tuple(self._position_3d)

    # === HRTF Support ===

    def enable_hrtf(self, hrtf_manager, channel_id: str):
        """Enable HRTF spatialization for this channel.

        Args:
            hrtf_manager: HRTFManager instance
            channel_id: Unique identifier for this channel
        """
        self._hrtf_manager = hrtf_manager
        self._hrtf_channel_id = channel_id

        if hrtf_manager and hrtf_manager.is_enabled:
            hrtf_manager.enable_spatialization(self, channel_id)

    def update_hrtf_position(self, x: float, y: float, z: float = 0.0):
        """Update HRTF source position.

        Args:
            x: X position (game coords - East)
            y: Y position (game coords - North)
            z: Z position (game coords - Up/altitude)
        """
        if hasattr(self, '_hrtf_manager') and self._hrtf_manager:
            self._hrtf_manager.update_source_position(
                self._hrtf_channel_id, x, y, z
            )

    def has_hrtf(self) -> bool:
        """Check if HRTF is enabled for this channel."""
        return (
            hasattr(self, '_hrtf_manager') and
            self._hrtf_manager is not None and
            self._hrtf_manager.is_enabled
        )


if __name__ == "__main__":
    test_fmod()
