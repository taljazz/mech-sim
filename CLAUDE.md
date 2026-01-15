# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MechSimulator is a Python-based audio game that simulates operating a mech suit. The game is entirely audio-driven with minimal visual interface, using FMOD (via pyfmodex) for audio and cytolk for text-to-speech feedback. Players control movement (WASD), rotation (Q/E), weapons (1-4 + CTRL), shield (Z), and flight (Page Up/Down) while hearing footsteps, weapon sounds, drone combat, and ambient audio.

## Running the Application

### Quick Start (Windows)
Double-click `run_mech.bat` to launch the simulator.

### Manual Execution

**Standard Python:**
```bash
python mech.py
```

**Using Conda Environment (mech):**
```bash
# Direct path method (most reliable)
~/.conda/envs/mech/python.exe mech.py

# Or on Windows Command Prompt
%USERPROFILE%\.conda\envs\mech\python.exe mech.py

# Or using conda run
conda run -n mech python mech.py
```

For detailed conda environment management, see `docs/conda.md`.

## Dependencies

The application requires:
- **pygame**: Event handling and display surface
- **pyfmodex**: FMOD Python bindings for audio
- **cytolk**: TTS (text-to-speech) via screen reader integration

Install dependencies:
```bash
pip install pygame pyfmodex cytolk
```

FMOD DLLs (`fmod.dll`, `fmodL.dll`) must be in the project root directory.

## Project Architecture

### Modular OOP Design

The codebase uses a modular object-oriented architecture with clear separation of concerns:

```
MechSimulator/
├── mech.py              # Entry point (imports and runs main)
├── main.py              # Game class with main loop, system initialization
├── fmod_audio.py        # Low-level FMOD wrapper (MechAudio, FMODChannelWrapper)
│
├── audio/               # Audio management layer
│   ├── __init__.py
│   ├── manager.py       # AudioManager - high-level audio control
│   ├── loader.py        # SoundLoader - loads all game sounds by category
│   └── spatial.py       # SpatialAudio - 3D positioning calculations
│
├── systems/             # Core game systems
│   ├── __init__.py
│   ├── movement.py      # MovementSystem - footsteps, rotation, position
│   ├── thrusters.py     # ThrusterSystem - flight, altitude, energy
│   ├── weapons.py       # WeaponSystem - all 5 weapons + fabrication
│   ├── shield.py        # ShieldSystem - shield activation/energy
│   └── camouflage.py    # CamouflageSystem - stealth mechanics
│
├── combat/              # Combat systems
│   ├── __init__.py
│   ├── drone.py         # Drone class - individual drone entity
│   ├── drone_manager.py # DroneManager - spawning, AI, audio positioning
│   ├── damage.py        # DamageSystem - hull, malfunctions, damage effects
│   └── radar.py         # RadarSystem - scanning and contact announcements
│
├── state/               # Game state management
│   ├── __init__.py
│   ├── constants.py     # All game constants and configuration values
│   └── game_state.py    # GameState class - centralized mutable state
│
├── ui/                  # User interface
│   ├── __init__.py
│   └── tts.py           # TTSManager - cytolk wrapper with throttling
│
├── utils/               # Utility functions
│   ├── __init__.py
│   └── helpers.py       # Direction calculations, angle utilities
│
├── sounds/              # Audio assets (see Sound Directory Structure)
├── docs/                # Documentation (conda.md, fmod.md, etc.)
└── Misc/                # Development files, original code, scripts
```

### Core Classes

**Game (`main.py`)**
- Initializes all systems with dependency injection
- Runs the 60 FPS main game loop
- Handles pygame events and delegates to systems
- Manages startup sequence and game over state

**GameState (`state/game_state.py`)**
- Centralized container for all mutable game state
- Player position, health, ammo, weapon states
- Provides `reset()` for game restart
- Helper properties: `is_in_flight`, `is_grounded`, `is_camo_effective`

**AudioManager (`audio/manager.py`)**
- Wraps `fmod_audio.MechAudio` with higher-level interface
- Manages named channel wrappers for weapons, drones, etc.
- Handles volume control, ducking, and DSP effects

**SoundLoader (`audio/loader.py`)**
- Loads all sounds organized by category
- Provides accessors: `get_footstep()`, `get_thruster_sound()`, `get_drone_sound()`
- Categories: footsteps, ambience, combat, fabrication, thrusters, drones
- **Optimizations**: Lazy-loads drone sounds, uses compressed samples for thrusters

### System Classes

Each system follows a consistent pattern:
```python
class SystemName:
    def __init__(self, audio_manager, sound_loader, tts, game_state, ...):
        # Store dependencies

    def update(self, keys, current_time, dt, ...):
        # Per-frame update logic

    def check_transitions(self):
        # Sound state machine transitions (optional)
```

**MovementSystem** - Handles WASD movement, Q/E rotation, footsteps, debris collection
**ThrusterSystem** - Page Up/Down thrust, altitude physics, energy management
**WeaponSystem** - All 5 weapons, state machines, fabrication
**ShieldSystem** - Shield activation, energy drain/regen, damage absorption
**CamouflageSystem** - Camo toggle, reveal mechanics, energy management
**DroneManager** - Drone spawning, AI state machine, spatial audio
**DamageSystem** - Hull damage, malfunctions, DSP effects, game over
**RadarSystem** - R key scanning, contact announcements, echolocation system

### Sound Directory Structure
```
sounds/
├── Movement/           # footsteps_001-004.wav, Rotation*.wav
├── Ambience/          # Background loops (randomly selected)
├── Combat/            # Chaingun, missiles, blaster, shield, EMP, damage
├── Flight/            # ThrusterPitch_001-050.wav (50 pitch stages)
├── Fabrication/       # Debris and ammo fabrication sounds
├── Suit Power-Up and Activation/  # Startup sequence, thruster sounds
├── Misc/              # Weapon extend/ready sounds
├── Drones/            # Combat drone enemy sounds
│   ├── Ambience/      # Drone idle/patrol sounds
│   ├── Beacons/       # Detection alert pings
│   ├── Scans/         # Radar scan feedback
│   ├── PassBys/       # Drone movement sounds (patrol)
│   ├── SuperSonics/   # Fast approach sounds (engaging)
│   ├── Takeoffs/      # Drone spawn sounds
│   ├── Hits/          # Player impact sounds
│   ├── Debris/        # Drone destruction debris
│   ├── Weapons/       # Drone weapon fire (pulse, plasma, rail)
│   ├── Explosions/    # Drone destruction explosions
│   ├── Malfunctions/  # System malfunction sounds
│   └── Interfaces/    # UI feedback sounds
├── Environmental/     # (not yet integrated)
├── System Alerts/     # (not yet integrated)
└── Advanced Suit Features/  # (not yet integrated)
```

## Development Patterns

### Adding New Systems
1. Create a new class in the appropriate directory (`systems/`, `combat/`, etc.)
2. Accept dependencies via constructor (audio, sounds, tts, state)
3. Implement `update(keys, current_time, dt)` for per-frame logic
4. Add `check_transitions()` if the system has sound state machines
5. Instantiate in `Game.__init__()` with proper dependency order
6. Call update/transition methods in `Game.run()` loop

### Adding New Sounds
1. Place .wav files in appropriate `sounds/` subdirectory
2. Add loading logic in `SoundLoader` (`audio/loader.py`)
3. Create accessor method (e.g., `get_new_sound()`)
4. Use via `self.sounds.get_new_sound()` in systems

### Adding New Constants
1. Add to `state/constants.py` with appropriate section
2. Import in the system that needs it
3. Use descriptive ALL_CAPS names with category prefix

### Modifying Game State
1. Add new state variables to `GameState.__init__()` and `reset()`
2. Access via `self.state.variable_name` in systems
3. For complex state, add helper properties/methods to GameState

### State Machine Pattern
Sound-based state machines use FMOD channel end detection:
```python
def check_transitions(self):
    if self.state.weapon_state == 'starting' and self.audio.check_channel_ended('weapon'):
        # Transition to next state
        self.state.weapon_state = 'active'
        self.audio.play_sound('weapon_loop', 'weapons', loop_count=-1)
```

## Controls

### Movement (Tank Controls)
- **W/S**: Move forward/backward in facing direction
- **A/D**: Strafe left/right relative to facing direction
- **Q/E**: Rotate left/right (90°/second)

### Weapons
- **1-4**: Switch weapons (1=Chaingun, 2=Missiles, 3=Blaster, 4=EMP)
- **CTRL**: Fire/activate current weapon

### Equipment
- **Z** (hold): Activate shield (release to deactivate)

### Thrusters
- **Spacebar**: Toggle thrusters on/off
- **Page Up** (hold): Increase thrust level
- **Page Down** (hold): Decrease thrust level

### Other
- **F**: Fabricate ammo (costs 5 debris, takes 3 seconds)
- **C**: Toggle camouflage
- **R**: Radar scan (2-second cooldown)
- **X**: Toggle echolocation (continuous proximity audio feedback)
- **T/Y/U/I**: Status keys (ammo/thrust/hull/contacts)
- **+/-**: Volume control (5% increments)
- **ESC**: Quit application

## Game Systems Reference

### Resource Management
- **Debris**: 15% collection chance per footstep, max 20 pieces
- **Fabrication**: 5 debris → weapon-specific ammo (3 seconds)

### Ammo Pools
| Weapon | Initial | Max | Fabrication Gain |
|--------|---------|-----|------------------|
| Chaingun | 250 | 500 | +100 |
| Missiles | 18 | 36 | +6 (one barrage) |
| Blaster | 50 | 100 | +20 |
| EMP | 3 | 5 | +1 |

### Shield (Equipment)
Shield is equipment activated with Z key (not a weapon):
- **Energy**: 100 max, drains at 2/sec while active
- **Regeneration**: 1/sec when inactive (always regenerates)
- **Absorption**: Blocks 80% of incoming damage
- **Status**: Shown with Y key (thrust/equipment status)

### Thruster System
- **50 pitch stages** for smooth audio transitions
- **Energy**: 100 max, drains based on thrust level, regenerates when idle
- **Boost**: Engaged at 60% thrust (forward flight speed multiplier)
- **Flight physics**: Lift vs gravity, terminal velocity, hard landing damage

### Drone Combat
- **Max drones**: 2 simultaneous
- **Spawn interval**: 10 seconds
- **Detection range**: 25m (5m with camo)
- **Weapons**: Pulse Cannon (close), Plasma Launcher (mid), Rail Gun (long)
- **Hull regeneration**: 2 HP/sec when no drones within 30m

### Missile System (Most Powerful Weapon)

Barrage missiles are the mech's heavy hitter - 6 missiles at 50 damage each = **300 max damage per barrage**, capable of destroying multiple drones in a single volley.

**State Machine**:
```
Cold:  ready → initializing → locking → locked → launching → ready
Warm:  ready → locking → locked → launching → ready (skips init)
```

**Stats Comparison**:
| Stat | Value | Notes |
|------|-------|-------|
| Damage | 50 per missile | Highest single-hit damage |
| Missiles/Barrage | 6 | 300 total damage potential |
| Range | 70m | Longest range weapon |
| Lock Time | 300-1000ms | Distance-based |
| Warm Duration | 15 seconds | Skip init phase |

**Features**:
| Feature | Description |
|---------|-------------|
| Warm Missiles | Skip init if fired within 15 seconds |
| Distance-Based Lock | 300ms point-blank, 1000ms at max range (70m) |
| Accelerating Beeps | Lock feedback: 300ms → 80ms interval |
| Target Announcements | TTS reports count + closest distance |
| Multi-Target | Damages all drones in firing arc |

**Lock Time Formula**:
```python
lock_time = LOCK_MIN + (LOCK_MAX - LOCK_MIN) * (distance / max_range)
# Example: 35m target = 300 + (1000-300) * 0.5 = 650ms
```

**Constants** (state/constants.py):
- `MISSILE_LOCK_MIN = 300` - Point-blank lock time (ms)
- `MISSILE_LOCK_MAX = 1000` - Max range lock time (ms)
- `MISSILE_WARM_DURATION = 15000` - Warm window (15 sec)
- `MISSILE_RANGE = 70` - Maximum targeting range (meters)
- `MISSILE_COUNT = 6` - Missiles per barrage
- `MISSILE_DAMAGE = 50` - Damage per missile

### Malfunctions
15% chance on hull damage, 3-second duration:
- **Movement**: 50% speed
- **Weapons**: Cannot fire
- **Radar**: Scan disabled
- **Thrusters**: Thrust disabled

## File References

### Core Files
- Entry point: `mech.py`
- Main game loop: `main.py`
- FMOD wrapper: `fmod_audio.py`
- Batch launcher: `run_mech.bat`

### Documentation
- `docs/conda.md` - Conda environment management
- `docs/fmod.md` - FMOD audio system documentation
- `docs/reaper.md` - Reaper DAW usage for sound creation
- `docs/extras.md` - Additional feature documentation

### Development Files (Misc/)
- `mech_original.py` - Original monolithic codebase (2,267 lines)
- `CreateThrusterSounds.lua` - Reaper script for thruster sound generation
- `test_fmod*.py` - FMOD testing scripts

## Performance Optimizations

The codebase includes several optimizations for better performance:

### Audio System Optimizations

**Lazy Loading**
- **Drone sounds**: Loaded on first drone spawn instead of startup (saves ~50-100 MB initially)
- **DSP effects**: Reverb, lowpass, distortion created on first use (saves ~1-2 MB)

**Memory-Efficient Loading**
- **Thruster sounds**: Use `CREATECOMPRESSEDSAMPLE` mode (reduces ~9 MB to ~2-3 MB)
- **Streaming support**: `load_sound(stream=True)` for large files

**Audio Ducking Optimization**
- Pre-cached channel group references avoid dictionary lookups during volume transitions

### Game Loop Optimizations

**DroneManager (`combat/drone_manager.py`)**
- **Cached spatial audio**: Pan/vol calculated once per frame, stored in drone dict
- **Cached active drones list**: Rebuilt once per frame with dirty flag pattern
- **Aim assist reordering**: Cooldown check before list filtering
- **Panning threshold**: Only updates audio if angle changed >3 degrees (~0.05 radians)

**Main Loop (`main.py`)**
- Uses actual elapsed time (`clock.tick()`) for consistent physics across frame rates

### FMOD Audio Methods

```python
# Standard loading (full decompression to memory)
audio.load_sound(path, name, loop=False)

# Streaming (decodes in realtime, low memory, one instance)
audio.load_sound(path, name, stream=True)

# Compressed sample (keeps compressed in memory, multiple instances)
audio.load_sound_compressed(path, name, loop=False)
```

### Mono Downmix for 3D Audio

Sounds with baked-in stereo panning (like flyby effects) interfere with 3D spatial positioning. The mono downmix is applied at playback time via `FMODChannelWrapper.play(sound, mono_downmix=True)`:

```python
# In drone_manager.py _update_ambient_audio():
dc['ambient'].play(sound, mono_downmix=True)
```

**How it works**: Uses FMOD's channel mix matrix to combine stereo L+R inputs to a centered mono signal, then applies pan control on top:
- Mix matrix combines: `Output = 0.5 * Input L + 0.5 * Input R`
- Pan is then applied via matrix gains: `left_gain/right_gain` based on drone position

**Sounds using mono downmix**:
- **PassBys** - Drone patrol movement sounds (stereo with baked-in L/R sweeps)
- **SuperSonics** - Drone engaging/approach sounds
- **SonicBooms** - Drone boost/dive sounds

## Accessibility Features

### Echolocation System

Toggle with **X** key. Provides continuous audio feedback about nearby drones:

- **Proximity pings**: Beep frequency increases as drones get closer
- **Dynamic timing**: 100ms between pings when very close, up to 150ms at max range
- **Volume scaling**: Louder pings for closer targets
- TTS announces "Echolocation enabled/disabled"

### Radar Scan Enhancements

The **R** key radar scan now includes:

- **Spatialized contact pings**: Each drone gets an audio ping with spatial positioning
- **Distance-based pitch**: Higher pitch = closer target (inspired by Gears 5)
- **Health status**: Announces drone damage level (wounded, damaged, critical)

### Audio Accessibility Design

Based on accessibility best practices for blind/low-vision players:

- **Spatial audio**: All drones use 3D stereo positioning
- **Distinct sounds**: Different audio cues for drone states (patrol, engaging, attacking)
- **TTS announcements**: All important game events announced via screen reader
- **Status keys**: T/Y/U/I provide on-demand information

## Platform Considerations

- **Windows required**: cytolk requires Windows with screen reader (NVDA, JAWS, etc.)
- **FMOD DLLs**: `fmod.dll` and `fmodL.dll` must be in project root
- **Audio format**: All sounds must be .wav format
- **Display**: Minimal 1x1 pixel window (pygame requirement)
