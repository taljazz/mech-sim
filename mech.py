#!/usr/bin/env python3
"""
MechSimulator - An audio-driven mech combat game.

This is the entry point for the game. Run this file to start the simulator.
The original monolithic code has been refactored into modular components:

- audio/     - Audio management (FMOD wrapper, sound loading, spatial audio)
- systems/   - Core game systems (movement, thrusters, weapons, shield, camo)
- combat/    - Combat systems (drones, damage, radar)
- state/     - Game state and constants
- ui/        - User interface (TTS)
- utils/     - Utility functions

Usage:
    python mech.py

Or via the batch file:
    run_mech.bat
"""

from main import main

if __name__ == '__main__':
    main()
