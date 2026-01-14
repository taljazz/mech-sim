"""
Game constants and configuration for MechSimulator.

All tunable parameters and constant values are centralized here
for easy modification and balancing.
"""

# =============================================================================
# DISPLAY
# =============================================================================
WINDOW_SIZE = (1, 1)  # Minimal window (audio-focused game)
WINDOW_TITLE = "Mech Simulator"
FPS = 60

# =============================================================================
# MOVEMENT
# =============================================================================
STEP_INTERVAL = 600  # Milliseconds between footsteps
PLAYER_SPEED = 3.0   # Base movement speed in meters/second
ROTATION_SPEED = 90  # Degrees per second

# Footstep sound indices (into loaded footstep_sounds array)
LEFT_FOOT_INDICES = [0, 2, 3]
RIGHT_FOOT_INDICES = [1]

# =============================================================================
# WEAPONS
# =============================================================================
WEAPON_CHAINGUN = 1
WEAPON_MISSILES = 2
WEAPON_BLASTER = 3
WEAPON_SHIELD = 4
WEAPON_EMP = 5

WEAPON_NAMES = {
    WEAPON_CHAINGUN: "Chaingun",
    WEAPON_MISSILES: "Barrage Missiles",
    WEAPON_BLASTER: "Hand Blaster",
    WEAPON_EMP: "EMP Burst"
}

# Shield is equipment, not a weapon - WEAPON_SHIELD constant used for energy tracking

# Chaingun variants
CHAINGUN_STANDARD = 0
CHAINGUN_MINIGUN = 1

CHAINGUN_VARIANT_NAMES = {
    CHAINGUN_STANDARD: "Chaingun",
    CHAINGUN_MINIGUN: "Small Minigun"
}

# Ammo settings
AMMO_INITIAL = {
    WEAPON_CHAINGUN: 250,
    WEAPON_MISSILES: 18,      # Start with 3 full barrages (6 per barrage)
    WEAPON_BLASTER: 50,
    WEAPON_SHIELD: 100,
    WEAPON_EMP: 3
}

AMMO_MAX = {
    WEAPON_CHAINGUN: 500,
    WEAPON_MISSILES: 36,      # 6 full barrages max
    WEAPON_BLASTER: 100,
    WEAPON_SHIELD: 100,
    WEAPON_EMP: 5
}

# Fabrication ammo gains
AMMO_FABRICATION_GAINS = {
    WEAPON_CHAINGUN: 100,
    WEAPON_MISSILES: 6,       # One full barrage per fabrication
    WEAPON_BLASTER: 20,
    WEAPON_SHIELD: 50,
    WEAPON_EMP: 1
}

# Low ammo warning thresholds
LOW_AMMO_THRESHOLDS = {
    WEAPON_CHAINGUN: 50,
    WEAPON_MISSILES: 6,       # Warn when less than 1 barrage left
    WEAPON_BLASTER: 10,
    WEAPON_SHIELD: 20,
    WEAPON_EMP: 1
}

# Weapon-specific settings
CHAINGUN_CONSUMPTION_RATE = 10  # Rounds per second
CHAINGUN_HIT_CHANCE = 0.15      # Per frame while spinning
CHAINGUN_DAMAGE = 5
CHAINGUN_RANGE = 30
CHAINGUN_ARC = 45  # Degrees

# Missile system - optimized lock-on (MOST POWERFUL WEAPON)
MISSILE_LOCK_MIN = 300          # Minimum lock time (point-blank) - faster lock
MISSILE_LOCK_MAX = 1000         # Maximum lock time (max range) - reduced from 1500
MISSILE_LOCK_DURATION = 1000    # Legacy/fallback
MISSILE_WARM_DURATION = 15000   # Missiles stay "warm" for 15 seconds after use
MISSILE_BEEP_START_INTERVAL = 300   # Initial beep interval (ms) - faster beeps
MISSILE_BEEP_END_INTERVAL = 80      # Final beep interval when locked (ms)
MISSILE_DAMAGE = 50             # Doubled from 25 - devastating per missile
MISSILE_RANGE = 70              # Extended range from 50
MISSILE_COUNT = 6               # 6 missiles per barrage (up from 4) = 300 max damage!

BLASTER_COOLDOWN = 200  # Milliseconds
BLASTER_DAMAGE = 18
BLASTER_RANGE = 40
BLASTER_ARC = 20  # Degrees

SHIELD_DRAIN_RATE = 2    # Energy per second
SHIELD_REGEN_RATE = 1    # Energy per second
SHIELD_ABSORPTION = 0.8  # 80% damage absorbed

EMP_COOLDOWN = 5000  # Milliseconds
EMP_DAMAGE = 30
EMP_RANGE = 35

# =============================================================================
# THRUSTER SYSTEM
# =============================================================================
NUM_PITCH_STAGES = 50
THRUST_RATE = 0.4         # Change per second
THRUSTER_ENERGY_MAX = 100.0
ENERGY_REGEN_RATE = 5.0   # Per second when idle
BOOST_THRESHOLD = 0.6     # 60% thrust for boost

# Flight physics
ALTITUDE_MAX = 200.0      # Maximum altitude in feet
GRAVITY = 32.0            # Feet per second squared
MAX_LIFT = 64.0           # Maximum lift at 100% thrust
TERMINAL_VELOCITY = -60.0 # Maximum fall speed (negative = down)

# =============================================================================
# CAMOUFLAGE SYSTEM
# =============================================================================
CAMO_ENERGY_MAX = 100.0
CAMO_DRAIN_RATE = 5.0     # Energy per second
CAMO_REGEN_RATE = 10.0    # Energy per second when inactive
CAMO_REVEAL_DURATION = 3000  # Milliseconds
CAMO_DETECT_RANGE = 5     # Meters (drones must be this close to detect)

# =============================================================================
# RESOURCES
# =============================================================================
DEBRIS_MAX = 20
DEBRIS_COLLECTION_CHANCE = 0.15  # Per footstep
DEBRIS_ANNOUNCEMENT_COOLDOWN = 2000  # Milliseconds
FABRICATION_DURATION = 3000  # Milliseconds
FABRICATION_COST = 5  # Debris per fabrication

# =============================================================================
# COMBAT / HULL
# =============================================================================
HULL_MAX = 100.0
HULL_REGEN_RATE = 2.0     # HP per second when safe
HULL_REGEN_SAFE_DISTANCE = 30  # Meters from drones

MALFUNCTION_DURATION = 3000  # Milliseconds
MALFUNCTION_CHANCE = 0.15    # On hull damage

MALFUNCTION_TYPES = ['movement', 'weapons', 'radar', 'thrusters']

# =============================================================================
# DRONE SYSTEM
# =============================================================================
# Note: MAX_DRONES can be overridden at runtime via config menu
MAX_DRONES = 2
MIN_DRONES = 1
MAX_DRONES_CONFIGURABLE = 6  # Maximum selectable in config menu
DEFAULT_DRONE_COUNT = 2  # Default selection in config menu

# Drone audio pool settings
DRONE_CHANNELS_PER_DRONE = 4  # ambient, combat, weapon, debris
DRONE_CROSSFADE_OUT_MS = 100  # Fade out time for sound transitions
DRONE_CROSSFADE_IN_MS = 50    # Fade in time for sound transitions
DRONE_SPAWN_INTERVAL = 10000  # Milliseconds
DRONE_SPAWN_DISTANCE_MIN = 30
DRONE_SPAWN_DISTANCE_MAX = 50
DRONE_BASE_SPEED = 5.0
DRONE_CLIMB_RATE = 15.0  # Feet per second
DRONE_ENGAGE_SPEED_MULT = 2.0  # Speed multiplier when engaging (increased from 1.5)
DRONE_EVASION_SPEED = 8.0  # Lateral evasion speed when being aimed at
DRONE_EVASION_ANGLE = 30  # Player must be within this angle to trigger evasion

# Drone detection ranges
DRONE_DETECT_RANGE = 25
DRONE_LOSE_TRACK_RANGE = 50
DRONE_REACQUIRE_RANGE = 35
DRONE_ATTACK_RANGE = 40

# Drone detection ranges (with camo)
DRONE_CAMO_DETECT_RANGE = 5
DRONE_CAMO_LOSE_TRACK_RANGE = 15
DRONE_CAMO_REACQUIRE_RANGE = 10

# Drone weapon stats (extended burst patterns 4-12 shots)
DRONE_WEAPONS = {
    'pulse_cannon': {
        'damage': 2,
        'range': 20,
        'accuracy': 0.80,
        'shots_min': 4,    # 4-10 shots per burst
        'shots_max': 10,
        'interval_min': 70,   # Moderate fire rate
        'interval_max': 120,
        'name': 'Pulse Cannon'
    },
    'plasma_launcher': {
        'damage': 4,
        'range': 30,
        'accuracy': 0.75,
        'shots_min': 6,    # 6-12 shots per burst (faster weapon, more shots)
        'shots_max': 12,
        'interval_min': 40,   # Fast fire rate
        'interval_max': 80,
        'name': 'Plasma Launcher'
    },
    'rail_gun': {
        'damage': 8,
        'range': 45,
        'accuracy': 0.70,
        'shots_min': 4,    # 4-8 shots
        'shots_max': 8,
        'interval_min': 100,  # Slower, heavy weapon
        'interval_max': 160,
        'name': 'Rail Gun'
    }
}

RADAR_COOLDOWN = 2000  # Milliseconds
AIM_ASSIST_COOLDOWN = 500  # Milliseconds
TARGET_LOCK_ANGLE = 5  # Degrees - direct lock when within this angle
TARGET_LOCK_COOLDOWN = 300  # Milliseconds - faster feedback for direct lock

# =============================================================================
# AUDIO VOLUMES
# =============================================================================
MASTER_VOLUME_DEFAULT = 1.0
VOLUME_STEP = 0.05

BASE_VOLUMES = {
    'ambience': 0.5,
    'chaingun': 0.8,
    'footstep': 1.0,
    'missiles': 0.9,
    'blaster': 0.7,
    'shield': 0.6,
    'emp': 0.8,
    'weapon_extend': 0.7,
    'fabrication': 0.6,
    'rotation': 0.5,
    'powerup': 0.8,
    'thruster': 0.7,
    'drone': 0.8
}

# =============================================================================
# STATE TIMINGS
# =============================================================================
DRONE_SPAWN_STATE_DURATION = 2000
DRONE_DETECT_STATE_DURATION = 1000  # Reduced from 1500 - faster target acquisition
DRONE_ATTACK_STATE_DURATION = 200   # Reduced from 500 - rapid fire
# Dynamic cooldown between bursts (spread out for realism)
DRONE_COOLDOWN_MIN = 800   # Minimum time between bursts
DRONE_COOLDOWN_MAX = 2000  # Maximum time between bursts
DRONE_SEARCH_TIMEOUT = 8000

# =============================================================================
# LANDING
# =============================================================================
HARD_LANDING_THRESHOLD = 30  # ft/s - damage above this
HARD_LANDING_DAMAGE_FACTOR = 0.5  # Damage per ft/s over threshold

# =============================================================================
# HRTF AUDIO SETTINGS
# =============================================================================
HRTF_ENABLED = True  # Set False to disable HRTF and use standard FMOD 3D
HRTF_DLL_PATH = None  # None = auto-detect phonon_fmod.dll in project root
HRTF_POSITION_THRESHOLD = 0.5  # Minimum movement (meters) before position update

# =============================================================================
# ENHANCED SPATIAL AUDIO FILTERS
# =============================================================================
# These settings control realistic audio filtering based on distance and position

# Air absorption - distant sounds lose high frequencies (like real physics)
AIR_ABSORPTION_START_DISTANCE = 10.0   # Start applying at 10 meters
AIR_ABSORPTION_MAX_DISTANCE = 60.0     # Full effect at 60 meters
AIR_ABSORPTION_MAX_CUTOFF = 400        # Maximum highpass cutoff (Hz) at max distance

# Occlusion - sounds blocked by obstacles (head shadow, altitude differences)
OCCLUSION_LOWPASS_CUTOFF = 2000        # Lowpass cutoff when fully occluded (Hz)
OCCLUSION_VOLUME_REDUCTION = 0.7       # Volume multiplier when fully occluded (0.7 = 30% quieter)

# Doppler effect - pitch shifting for moving sound sources
DOPPLER_SCALE = 0.5  # 0.0 = disabled, 1.0 = realistic, 0.5 = subtle
