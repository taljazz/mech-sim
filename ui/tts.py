"""
Text-to-Speech Manager for MechSimulator.

Provides a wrapper around cytolk for screen reader integration,
with throttling support to prevent announcement spam.
Now includes audio ducking support for clearer TTS during gameplay.
"""

from cytolk import tolk


class TTSManager:
    """Manages text-to-speech announcements via cytolk/screen reader."""

    def __init__(self, audio_manager=None):
        """Initialize the TTS manager.

        Args:
            audio_manager: Optional AudioManager for audio ducking support.
                          Can be set later via set_audio_manager().
        """
        self._initialized = False
        self._last_announcements = {}  # key -> timestamp for throttling
        self._audio_manager = audio_manager
        self._ducking_enabled = True  # Enable audio ducking during TTS

        # Get ducking settings from constants or use defaults
        try:
            from state.constants import TTS_DUCK_VOLUME, TTS_DUCK_SPEED
            self._duck_volume = TTS_DUCK_VOLUME
            self._duck_speed = TTS_DUCK_SPEED
        except ImportError:
            self._duck_volume = 0.4
            self._duck_speed = 8.0

    def set_audio_manager(self, audio_manager):
        """Set the audio manager for ducking support.

        Args:
            audio_manager: AudioManager instance
        """
        self._audio_manager = audio_manager

    def set_ducking_enabled(self, enabled: bool):
        """Enable or disable audio ducking during TTS.

        Args:
            enabled: If True, other audio will duck when TTS speaks
        """
        self._ducking_enabled = enabled

    def init(self):
        """Initialize the TTS system."""
        if not self._initialized:
            tolk.load()
            self._initialized = True

    def cleanup(self):
        """Clean up TTS resources."""
        if self._initialized:
            tolk.unload()
            self._initialized = False

    def _start_ducking(self, text: str = ""):
        """Start audio ducking for clearer TTS."""
        if self._ducking_enabled and self._audio_manager:
            try:
                # Create a short reason from the text
                reason = f"TTS: {text[:20]}..." if len(text) > 20 else f"TTS: {text}"
                # Duck all game audio except UI sounds
                self._audio_manager.start_ducking(
                    groups_to_duck=['ambience', 'weapons', 'movement', 'thrusters', 'drones'],
                    duck_volume=self._duck_volume,
                    speed=self._duck_speed,
                    reason=reason
                )
            except Exception:
                pass  # Audio manager may not support ducking

    def _stop_ducking(self):
        """Restore normal audio levels after TTS."""
        if self._ducking_enabled and self._audio_manager:
            try:
                self._audio_manager.stop_ducking(speed=self._duck_speed * 0.6, reason="TTS_complete")
            except Exception:
                pass

    def speak(self, text: str, interrupt: bool = True, duck_audio: bool = True):
        """Speak text through the screen reader.

        Args:
            text: The text to speak
            interrupt: If True, interrupts any current speech
            duck_audio: If True, duck other audio for clarity (default True)
        """
        if self._initialized:
            if duck_audio:
                self._start_ducking(text)
            tolk.speak(text, interrupt=interrupt)
            # Note: We can't easily detect when TTS finishes,
            # so ducking will be restored on next update cycle
            # or by calling stop_ducking() manually

    def speak_throttled(self, key: str, text: str, cooldown_ms: int, current_time: int,
                         duck_audio: bool = True) -> bool:
        """Speak text with throttling to prevent spam.

        Args:
            key: Unique key for this announcement type
            text: The text to speak
            cooldown_ms: Minimum time between announcements in milliseconds
            current_time: Current game time in milliseconds
            duck_audio: If True, duck other audio for clarity

        Returns:
            True if the text was spoken, False if throttled
        """
        last_time = self._last_announcements.get(key, 0)

        if current_time - last_time >= cooldown_ms:
            self.speak(text, duck_audio=duck_audio)
            self._last_announcements[key] = current_time
            return True

        return False

    def update_ducking(self, dt: float):
        """Update ducking state (call each frame).

        This helps manage the ducking lifecycle since we can't detect
        when TTS finishes speaking.

        Args:
            dt: Delta time in seconds
        """
        # The actual ducking update is handled by AudioManager
        # This method is here for consistency and future expansion
        pass

    def clear_throttle(self, key: str = None):
        """Clear throttle state for a key or all keys.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            self._last_announcements.clear()
        elif key in self._last_announcements:
            del self._last_announcements[key]

    @property
    def is_initialized(self) -> bool:
        """Check if TTS is initialized."""
        return self._initialized
