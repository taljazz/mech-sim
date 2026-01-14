# Mech-Sim

An audio-only mech combat simulator designed for blind and low-vision players. Experience piloting a mechanized battle suit through sound alone, featuring realistic HRTF binaural audio, immersive 3D soundscapes, and full screen reader integration.

## About

Mech-Sim puts you in the cockpit of a combat mech with nothing but your ears to guide you. Every system, enemy, and environment is conveyed through carefully designed spatial audio - from the directional hum of approaching drones to the mechanical whir of your own suit's systems.

This project aims to prove that compelling, realistic game experiences don't require visuals. Built from the ground up with accessibility as a core feature, not an afterthought.

## Features

### Audio Systems
- **HRTF Binaural Positioning**: Steam Audio integration for true 3D sound localization
- **Directional Filtering**: Head-shadow simulation for front/behind audio distinction
- **Distance Attenuation**: Realistic sound falloff with air absorption modeling
- **Doppler Effects**: Moving sound sources shift in pitch realistically

### Gameplay
- **Tank Controls**: Intuitive WASD movement with Q/E rotation
- **Flight System**: 50-stage variable thrust with realistic physics
- **Weapon Systems**: Chaingun, barrage missiles, hand blaster, EMP, and energy shield
- **Combat AI**: Intelligent drone enemies with distinct audio signatures and behaviors
- **Resource Management**: Collect debris, fabricate ammunition

### Accessibility
- **Screen Reader Support**: Full TTS via cytolk (NVDA, JAWS, Narrator)
- **Echolocation Mode**: Continuous proximity audio feedback
- **Radar System**: Spatialized contact pings with distance-based pitch
- **Status Keys**: Instant audio readout of ammo, hull, altitude, contacts

## Requirements

### System
- Windows 10/11 (required for screen reader integration)
- Python 3.10 or higher
- A screen reader (NVDA recommended - free at [nvaccess.org](https://www.nvaccess.org/))
- Headphones (required for spatial audio)

### Python Dependencies

```bash
pip install pygame pyfmodex cytolk cryptography
```

### FMOD Runtime (Required)

Download FMOD Engine from [fmod.com/download](https://www.fmod.com/download):
1. Download "FMOD Engine" for Windows
2. Extract and locate the DLLs in `api/core/lib/x64/`
3. Copy to project root:
   - `fmod.dll` (required)
   - `fmodL.dll` (optional, logging version)

### Steam Audio (Optional, Recommended)

For enhanced binaural HRTF audio:
1. Download from [Steam Audio Releases](https://github.com/ValveSoftware/steam-audio/releases)
2. Copy to project root:
   - `phonon.dll`
   - `phonon_fmod.dll`

Without Steam Audio, the game falls back to FMOD's built-in 3D audio (still good, but less precise HRTF).

## Audio Assets

**Audio assets are not included in this repository** as they are proprietary/licensed content.

To run the game, you need either:
- A `game.sounds` encrypted pack file in the project root, OR
- Raw audio files in a `sounds/` directory structure

The game automatically detects and uses whichever is available. Without audio assets, the game will not function.

## Installation

```bash
# Clone the repository
git clone https://github.com/taljazz/mech-sim.git
cd mech-sim

# Install dependencies
pip install pygame pyfmodex cytolk cryptography

# Download and place FMOD DLLs (see requirements above)

# Obtain audio assets (not included)

# Run the game
python mech.py
```

## Controls

### Movement
| Key | Action |
|-----|--------|
| W | Move forward |
| S | Move backward |
| A | Strafe left |
| D | Strafe right |
| Q | Rotate left |
| E | Rotate right |
| Page Up | Increase thrust |
| Page Down | Decrease thrust |

### Combat
| Key | Action |
|-----|--------|
| 1 | Select Chaingun |
| 2 | Select Barrage Missiles |
| 3 | Select Hand Blaster |
| 4 | Select EMP |
| Ctrl | Fire weapon |
| Z (hold) | Activate shield |

### Systems
| Key | Action |
|-----|--------|
| R | Radar scan (2s cooldown) |
| X | Toggle echolocation |
| C | Toggle camouflage |
| F | Fabricate ammunition |

### Status Reports
| Key | Action |
|-----|--------|
| T | Ammo and debris count |
| Y | Thrust, altitude, shield, camo status |
| U | Hull integrity |
| I | Active contact count |

### Other
| Key | Action |
|-----|--------|
| + | Increase volume |
| - | Decrease volume |
| Esc | Quit game |

## How to Play

1. **Start**: The mech powers up automatically. Wait for "Mech online" announcement.
2. **Configure**: Select maximum drone count (1-4) and press Enter.
3. **Listen**: Use headphones. Drones will spawn and patrol around you.
4. **Detect**: Press R for radar or X for continuous echolocation.
5. **Engage**: Rotate toward threats (Q/E), select weapon (1-4), fire (Ctrl).
6. **Survive**: Monitor hull (U key), fabricate ammo (F key), use shield (Z) and camo (C).

### Combat Tips
- **Chaingun**: High rate of fire, good for close-medium range
- **Missiles**: Lock-on system, devastating damage, limited ammo
- **Blaster**: Single powerful shots, good accuracy
- **EMP**: Disables nearby drones temporarily, very limited uses
- **Shield**: Blocks 80% damage while held, drains energy

## Project Structure

```
mech-sim/
├── mech.py              # Entry point
├── main.py              # Game loop and system orchestration
├── fmod_audio.py        # Low-level FMOD audio wrapper
├── asset_crypto.py      # Encrypted asset pack support
│
├── audio/               # Audio management layer
│   ├── manager.py       # High-level audio control
│   ├── loader.py        # Sound loading from pack or files
│   ├── spatial.py       # 3D positioning calculations
│   └── drone_pool.py    # Pooled drone audio channels
│
├── systems/             # Core game systems
│   ├── movement.py      # Walking and rotation
│   ├── thrusters.py     # Flight and altitude
│   ├── weapons.py       # All weapon implementations
│   ├── shield.py        # Energy shield
│   └── camouflage.py    # Stealth system
│
├── combat/              # Combat subsystems
│   ├── drone.py         # Drone entity class
│   ├── drone_manager.py # AI, spawning, audio positioning
│   ├── damage.py        # Hull damage and malfunctions
│   └── radar.py         # Scanning and echolocation
│
├── state/               # State management
│   ├── constants.py     # All configuration values
│   └── game_state.py    # Centralized game state
│
└── ui/                  # User interface
    ├── tts.py           # Text-to-speech manager
    └── menu.py          # Configuration menu
```

## Technical Details

### Audio Pipeline
1. **Loading**: Sounds loaded from encrypted pack or raw files into FMOD
2. **Spatialization**: Steam Audio HRTF or FMOD 3D positioning
3. **Filtering**: Directional lowpass (head shadow), air absorption, occlusion
4. **Mixing**: Channel groups for weapons, drones, ambient, UI
5. **Output**: Binaural stereo to headphones

### Drone AI States
- **Patrol**: Circling at distance, ambient engine sound
- **Alerted**: Detected player, beacon ping, closing distance
- **Engaging**: Attack run, supersonic approach sound
- **Attacking**: Weapon fire, positioned relative to player
- **Retreating**: Breaking off, repositioning

## Contributing

Contributions are welcome! Areas that could use help:
- Additional accessibility features
- New weapon types or enemy variants
- Audio design improvements
- Documentation and tutorials

## License

Source code is provided under the MIT License. Audio assets are not included and are proprietary.

## Acknowledgments

- **FMOD** by Firelight Technologies - Audio engine
- **Steam Audio** by Valve Corporation - HRTF spatialization
- **cytolk** - Screen reader integration
- **pygame** - Input handling and window management

---

*"In the darkness of the cockpit, your ears are your eyes."*
