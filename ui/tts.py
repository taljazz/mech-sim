"""
Text-to-Speech Manager for MechSimulator.

Provides a wrapper around cytolk for screen reader integration,
with throttling support to prevent announcement spam.
"""

from cytolk import tolk


class TTSManager:
    """Manages text-to-speech announcements via cytolk/screen reader."""

    def __init__(self):
        self._initialized = False
        self._last_announcements = {}  # key -> timestamp for throttling

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

    def speak(self, text: str, interrupt: bool = True):
        """Speak text through the screen reader.

        Args:
            text: The text to speak
            interrupt: If True, interrupts any current speech
        """
        if self._initialized:
            tolk.speak(text, interrupt=interrupt)

    def speak_throttled(self, key: str, text: str, cooldown_ms: int, current_time: int) -> bool:
        """Speak text with throttling to prevent spam.

        Args:
            key: Unique key for this announcement type
            text: The text to speak
            cooldown_ms: Minimum time between announcements in milliseconds
            current_time: Current game time in milliseconds

        Returns:
            True if the text was spoken, False if throttled
        """
        last_time = self._last_announcements.get(key, 0)

        if current_time - last_time >= cooldown_ms:
            self.speak(text)
            self._last_announcements[key] = current_time
            return True

        return False

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
