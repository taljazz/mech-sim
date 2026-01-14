"""Pre-game Configuration Menu for MechSimulator.

Provides an accessible audio-first menu for configuring game settings
before starting gameplay. Uses TTS for all feedback.
"""

import pygame
from typing import List, Callable, Optional


class MenuItem:
    """A single menu item with selectable values."""

    def __init__(self, label: str, values: List, default_index: int = 0,
                 format_func: Optional[Callable] = None):
        """Create a menu item.

        Args:
            label: Display label for the item
            values: List of possible values
            default_index: Starting value index
            format_func: Optional function to format values for display
        """
        self.label = label
        self.values = values
        self.current_index = default_index
        self.format_func = format_func or str

    @property
    def current_value(self):
        """Get the currently selected value."""
        return self.values[self.current_index]

    def next_value(self):
        """Move to the next value (wraps around)."""
        self.current_index = (self.current_index + 1) % len(self.values)
        return self.current_value

    def prev_value(self):
        """Move to the previous value (wraps around)."""
        self.current_index = (self.current_index - 1) % len(self.values)
        return self.current_value

    def get_display_text(self) -> str:
        """Get the full display text for this item."""
        return f"{self.label}: {self.format_func(self.current_value)}"

    def get_value_text(self) -> str:
        """Get just the value portion for announcement."""
        return self.format_func(self.current_value)


class ConfigMenu:
    """Pre-game configuration menu with TTS support.

    Navigation:
    - UP/DOWN: Move between menu items
    - LEFT/RIGHT: Change selected item's value
    - ENTER: Confirm and start game (when on Start Game item)
    """

    def __init__(self, tts_manager):
        """Create the configuration menu.

        Args:
            tts_manager: TTSManager instance for audio feedback
        """
        self.tts = tts_manager
        self.items: List[MenuItem] = []
        self.selected_index = 0
        self.confirmed = False
        self._announced = False
        self._setup_default_items()

    def _setup_default_items(self):
        """Set up the default menu items."""
        # Drone count: 1-6 (default 2, which is index 1)
        self.items.append(MenuItem(
            label="Maximum Drones",
            values=[1, 2, 3, 4, 5, 6],
            default_index=1,  # Default to 2 drones
            format_func=lambda x: f"{x} drone{'s' if x != 1 else ''}"
        ))

        # Start Game option (action item)
        self.items.append(MenuItem(
            label="Start Game",
            values=["Press Enter to begin"],
            default_index=0
        ))

    def get_drone_count(self) -> int:
        """Get the selected drone count."""
        return self.items[0].current_value

    def handle_input(self, key: int) -> bool:
        """Handle keyboard input.

        Args:
            key: pygame key constant

        Returns:
            True if menu should close (game should start)
        """
        if key == pygame.K_UP:
            self._move_selection(-1)
        elif key == pygame.K_DOWN:
            self._move_selection(1)
        elif key == pygame.K_LEFT:
            self._change_value(-1)
        elif key == pygame.K_RIGHT:
            self._change_value(1)
        elif key == pygame.K_RETURN:
            return self._confirm_selection()

        return False

    def _move_selection(self, direction: int):
        """Move menu selection up or down."""
        old_index = self.selected_index
        self.selected_index = (self.selected_index + direction) % len(self.items)

        if self.selected_index != old_index:
            self._announce_current_item()

    def _change_value(self, direction: int):
        """Change the value of the current menu item."""
        item = self.items[self.selected_index]

        # Skip for action items (like Start Game) that only have one "value"
        if len(item.values) <= 1:
            return

        if direction > 0:
            item.next_value()
        else:
            item.prev_value()

        self._announce_current_value()

    def _confirm_selection(self) -> bool:
        """Handle enter key press.

        Returns:
            True if game should start
        """
        # If on Start Game item, confirm and close menu
        if self.selected_index == len(self.items) - 1:
            self.confirmed = True
            drone_count = self.get_drone_count()
            self.tts.speak(f"Starting with {drone_count} drones maximum")
            return True

        # Otherwise treat enter as cycling the value
        item = self.items[self.selected_index]
        if len(item.values) > 1:
            item.next_value()
            self._announce_current_value()

        return False

    def _announce_current_item(self):
        """Announce the currently selected menu item."""
        item = self.items[self.selected_index]
        self.tts.speak(item.get_display_text())

    def _announce_current_value(self):
        """Announce just the current value of the selected item."""
        item = self.items[self.selected_index]
        self.tts.speak(item.get_value_text())

    def announce_menu(self):
        """Announce the full menu introduction.

        Call this when the menu first appears.
        """
        if self._announced:
            return

        self._announced = True
        self.tts.speak(
            "Configuration menu. "
            "Use up and down arrows to navigate. "
            "Left and right arrows to change values. "
            "Enter to start."
        )

        # Brief pause then announce first item
        self._announce_current_item()

    def get_config(self) -> dict:
        """Get all configuration values as a dictionary.

        Returns:
            Dict with configuration keys and values
        """
        return {
            'drone_count': self.get_drone_count()
        }

    def reset(self):
        """Reset menu to default state."""
        self.selected_index = 0
        self.confirmed = False
        self._announced = False
        # Reset items to defaults
        self.items[0].current_index = 1  # Default 2 drones

    def print_status(self):
        """Print current menu status to console."""
        print("\n=== CONFIGURATION MENU ===")
        for i, item in enumerate(self.items):
            marker = ">" if i == self.selected_index else " "
            print(f"{marker} {item.get_display_text()}")
        print("==========================")
        print("UP/DOWN: Navigate | LEFT/RIGHT: Change | ENTER: Select")
