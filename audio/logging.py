"""Audio debug logging for MechSimulator.

Provides toggleable logging for audio events to help diagnose issues.
Toggle with F12 during gameplay.
"""

import time
from typing import Optional, Dict, Any, List


class AudioLogger:
    """Singleton logger for audio system debugging."""

    LEVELS = {
        'ERROR': 0,    # Always important
        'WARNING': 1,  # Potential issues
        'INFO': 2,     # State changes
        'DEBUG': 3     # Detailed events
    }

    _instance = None

    @classmethod
    def get_instance(cls) -> 'AudioLogger':
        """Get the singleton AudioLogger instance."""
        if cls._instance is None:
            cls._instance = AudioLogger()
        return cls._instance

    def __init__(self, level: str = 'WARNING', enabled: bool = False):
        """Initialize the audio logger.

        Args:
            level: Minimum level to log ('ERROR', 'WARNING', 'INFO', 'DEBUG')
            enabled: Whether logging is enabled (toggle with F12)
        """
        self.level_threshold = self.LEVELS.get(level, 1)
        self.enabled = enabled
        self._log_buffer: List[Dict[str, Any]] = []
        self._max_buffer = 100
        self._start_time = time.time()

    def set_level(self, level: str):
        """Set the logging level threshold."""
        self.level_threshold = self.LEVELS.get(level, 1)

    def enable(self, enabled: bool = True):
        """Enable or disable logging output."""
        self.enabled = enabled
        if enabled:
            print("[AUDIO] Debug logging ENABLED (F12 to disable)")
        else:
            print("[AUDIO] Debug logging DISABLED")

    def toggle(self) -> bool:
        """Toggle logging on/off. Returns new state."""
        self.enable(not self.enabled)
        return self.enabled

    def log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an audio event.

        Args:
            level: Log level ('ERROR', 'WARNING', 'INFO', 'DEBUG')
            message: Log message
            context: Optional dict with additional context
        """
        level_val = self.LEVELS.get(level, 1)
        if level_val > self.level_threshold:
            return

        elapsed = time.time() - self._start_time

        entry = {
            'time': elapsed,
            'level': level,
            'message': message,
            'context': context
        }

        # Add to buffer (ring buffer behavior)
        self._log_buffer.append(entry)
        if len(self._log_buffer) > self._max_buffer:
            self._log_buffer.pop(0)

        # Print if enabled
        if self.enabled:
            ctx_str = ""
            if context:
                ctx_items = [f"{k}={v}" for k, v in context.items()]
                ctx_str = f" | {', '.join(ctx_items)}"
            print(f"[AUDIO:{level}] {elapsed:.3f}s {message}{ctx_str}")

    def error(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an error."""
        self.log('ERROR', message, context)

    def warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a warning."""
        self.log('WARNING', message, context)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an info message."""
        self.log('INFO', message, context)

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a debug message."""
        self.log('DEBUG', message, context)

    def get_recent_logs(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent log entries from buffer."""
        return self._log_buffer[-count:]

    def clear_buffer(self):
        """Clear the log buffer."""
        self._log_buffer.clear()


# Convenience function for quick logging
def audio_log(level: str, message: str, context: Optional[Dict[str, Any]] = None):
    """Log an audio event using the singleton logger."""
    AudioLogger.get_instance().log(level, message, context)
