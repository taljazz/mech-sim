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
CAMO_REVEAL_DURATION = 3000  # Milliseconds (default, used by movement)
CAMO_DETECT_RANGE = 5     # Meters (drones must be this close to detect)

# Weapon-specific reveal durations (milliseconds)
CAMO_REVEAL_CHAINGUN = 3000   # Loud sustained fire
CAMO_REVEAL_BLASTER = 2000    # Single shots, less loud
CAMO_REVEAL_MISSILES = 5000   # Very loud launch signature
CAMO_REVEAL_EMP = 4000        # Powerful tech signature
CAMO_REVEAL_FOOTSTEP = 1500   # Footsteps reveal for shorter time

# Partial camo recovery (extend reveal instead of resetting)
CAMO_REVEAL_EXTEND_MS = 500   # Add this much time per action instead of full reset

# Camo footstep attenuation
CAMO_FOOTSTEP_VOLUME_MULT = 0.5  # 50% volume while camo active

# Camo sound detection reduction
CAMO_SOUND_DETECTION_RANGE_MULT = 0.5  # Sound detection range halved while camo active

# Camo proximity warning
CAMO_PROXIMITY_WARNING_ENABLED = True
CAMO_PROXIMITY_WARNING_RANGE = 8   # meters - warn when drone within this range
CAMO_PROXIMITY_WARNING_INTERVAL = 1500  # ms between warning pings

# Camo ambush bonus
CAMO_AMBUSH_ENABLED = True
CAMO_AMBUSH_DAMAGE_MULT = 1.5  # 50% extra damage on first attack from camo

# Drone confusion on camo reveal
CAMO_CONFUSION_ENABLED = True
CAMO_CONFUSION_DURATION = 800  # ms - drones confused when camo breaks
CAMO_CONFUSION_LOSE_LOCK_RANGE = 20  # meters - drones beyond this lose lock on reveal

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
DRONE_CHANNELS_PER_DRONE = 7  # ambient, combat, weapon, debris, takeoff, passby, supersonic
DRONE_CROSSFADE_OUT_MS = 100  # Fade out time for sound transitions
DRONE_CROSSFADE_IN_MS = 50    # Fade in time for sound transitions
DRONE_SPAWN_INTERVAL = 10000  # Milliseconds
DRONE_SPAWN_DISTANCE_MIN = 15  # Can spawn close for immediate threat
DRONE_SPAWN_DISTANCE_MAX = 80  # Or far away, giving time to prepare
DRONE_BASE_SPEED = 5.0
DRONE_CLIMB_RATE = 15.0  # Feet per second
DRONE_ENGAGE_SPEED_MULT = 1.3  # Speed multiplier when engaging (reduced for better audio sync)
DRONE_EVASION_SPEED = 5.0  # Lateral evasion speed when being aimed at (reduced for smoother audio)
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
# State duration ranges (randomized per state entry)
DRONE_SPAWN_DURATION_MIN = 1500
DRONE_SPAWN_DURATION_MAX = 2500
DRONE_DETECT_DURATION_MIN = 800
DRONE_DETECT_DURATION_MAX = 1500
DRONE_ATTACK_DURATION_MIN = 150
DRONE_ATTACK_DURATION_MAX = 300
# Dynamic cooldown between bursts (spread out for realism)
DRONE_COOLDOWN_MIN = 800   # Minimum time between bursts
DRONE_COOLDOWN_MAX = 2000  # Maximum time between bursts
DRONE_SEARCH_TIMEOUT = 8000  # Legacy (use MIN/MAX instead)
DRONE_SEARCH_TIMEOUT_MIN = 6000
DRONE_SEARCH_TIMEOUT_MAX = 10000

# Legacy fixed durations (for reference, replaced by ranges above)
DRONE_SPAWN_STATE_DURATION = 2000
DRONE_DETECT_STATE_DURATION = 1000
DRONE_ATTACK_STATE_DURATION = 200

# =============================================================================
# DRONE AI PERSONALITIES
# =============================================================================
DRONE_PERSONALITIES = {
    'rookie': {
        'speed_mult': 0.8,
        'accuracy_mult': 0.7,
        'aggression': 0.3,
        'evasion_skill': 0.6,
        'hesitation_chance': 0.25,  # More likely to hesitate
    },
    'veteran': {
        'speed_mult': 1.0,
        'accuracy_mult': 1.0,
        'aggression': 0.5,
        'evasion_skill': 1.0,
        'hesitation_chance': 0.10,
    },
    'ace': {
        'speed_mult': 1.2,
        'accuracy_mult': 1.2,
        'aggression': 0.7,
        'evasion_skill': 1.3,
        'hesitation_chance': 0.05,  # Rarely hesitates
    },
    'berserker': {
        'speed_mult': 1.3,
        'accuracy_mult': 0.8,
        'aggression': 0.9,
        'evasion_skill': 0.5,  # Reckless, doesn't evade well
        'hesitation_chance': 0.0,  # Never hesitates
    }
}

# Personality spawn weights (higher = more common)
DRONE_PERSONALITY_WEIGHTS = {
    'rookie': 30,
    'veteran': 45,
    'ace': 15,
    'berserker': 10
}

# Personality-based weapon preferences (distance ranges for each weapon)
PERSONALITY_WEAPON_PREFS = {
    'rookie': {
        # Rookies prefer close range (safer, less skill needed)
        'pulse_cannon': (0, 18),    # Strongly prefers close combat
        'plasma_launcher': (15, 28),
        'rail_gun': (25, 40),       # Rarely uses long range
    },
    'veteran': {
        # Balanced usage
        'pulse_cannon': (0, 15),
        'plasma_launcher': (12, 32),
        'rail_gun': (28, 45),
    },
    'ace': {
        # Optimal weapon selection for range
        'pulse_cannon': (0, 12),    # Only close range
        'plasma_launcher': (10, 30),
        'rail_gun': (25, 50),       # Prefers precision long range
    },
    'berserker': {
        # Aggressive, prefers high damage
        'pulse_cannon': (0, 10),    # Quick bursts
        'plasma_launcher': (8, 35), # High DPS preferred
        'rail_gun': (30, 50),       # Max damage at range
    }
}

# =============================================================================
# DRONE EVASION SETTINGS
# =============================================================================
EVASION_INTERVAL_MIN = 0.3   # Seconds before direction change (was fixed 0.5)
EVASION_INTERVAL_MAX = 0.7
EVASION_ANGLE_VARIANCE = 30  # Degrees - evasion not purely perpendicular

# =============================================================================
# DRONE STATE TRANSITIONS (Probabilistic)
# =============================================================================
HESITATION_CHANCE = 0.15      # Base chance to hesitate before engaging
FALSE_START_CHANCE = 0.10     # Chance to abort detection and return to patrol
COOLDOWN_REASSESS_CHANCE = 0.15  # Chance to extend cooldown
COOLDOWN_PEEK_INTERVAL = 300  # ms - how often to check player during cooldown

# =============================================================================
# DRONE SEARCH PATTERNS
# =============================================================================
SEARCH_PATTERN_TYPES = ['spiral', 'zigzag', 'wander']
SEARCH_SPIRAL_EXPANSION = 5   # Meters per revolution
SEARCH_ZIGZAG_WIDTH = 10      # Meters side-to-side
SEARCH_WANDER_DISTANCE = 8    # Meters per waypoint

# Expanding search radius over time
SEARCH_EXPAND_ENABLED = True
SEARCH_EXPAND_INTERVAL = 2000     # ms - expand search every 2 seconds
SEARCH_EXPAND_MULTIPLIER = 1.3    # Expand radius by 30% each interval
SEARCH_EXPAND_MAX_MULT = 3.0      # Maximum expansion multiplier

# =============================================================================
# DRONE COORDINATION / FLANKING
# =============================================================================
FLANK_SEPARATION_MIN = 90     # Degrees between drones
FLANK_SEPARATION_MAX = 120
FLANK_CIRCLE_SPEED = 20       # Degrees per second when circling
FLANK_DISTANCE_MIN = 15       # Meters
FLANK_DISTANCE_MAX = 25
CROSSFIRE_WINDOW = 500        # ms - attacks within this window count as coordinated

# =============================================================================
# DRONE ATTACK ADAPTATION
# =============================================================================
ATTACK_FRUSTRATION_THRESHOLD = 0.2  # Hit rate below this = frustrated
ATTACK_BREAK_OFF_CHANCE = 0.5       # Chance to break off when frustrated
ATTACK_MIN_SHOTS_BEFORE_ADAPT = 4   # Minimum shots before considering break-off

# Context-aware attack adaptation
ATTACK_ADAPTATION_ENABLED = True
ATTACK_WEAPON_SWITCH_THRESHOLD = 0.15  # Switch weapon if hit rate below this
ATTACK_RANGE_ADJUST_THRESHOLD = 0.25   # Adjust attack range preference if struggling

# =============================================================================
# DRONE WOUNDED STATE
# =============================================================================
WOUNDED_HEALTH_THRESHOLD = 25       # Health % to enter wounded state
WOUNDED_EVASION_MULT = 1.5          # Evasion skill multiplier when wounded
WOUNDED_AGGRESSION_MULT = 0.4       # Aggression reduction when wounded
WOUNDED_SPEED_MULT = 0.7            # Speed reduction when wounded (erratic)
WOUNDED_ERRATIC_INTERVAL = 0.2      # Seconds between erratic movements

# =============================================================================
# DRONE SUPPRESSION STATE
# =============================================================================
SUPPRESSION_ENABLED = True
SUPPRESSION_DAMAGE_THRESHOLD = 15   # Damage in time window to trigger suppression
SUPPRESSION_TIME_WINDOW = 1000      # ms - window to accumulate damage
SUPPRESSION_DURATION_MIN = 500      # ms - minimum suppression duration
SUPPRESSION_DURATION_MAX = 1200     # ms - maximum suppression duration
SUPPRESSION_COOLDOWN = 3000         # ms - can't be suppressed again for this long

# =============================================================================
# DRONE DISTRESS BEACON
# =============================================================================
DISTRESS_BEACON_ENABLED = True
DISTRESS_DAMAGE_THRESHOLD = 40      # Single hit damage to trigger distress
DISTRESS_HEALTH_THRESHOLD = 30      # Health % to trigger distress
DISTRESS_BEACON_DURATION = 3000     # ms - how long beacon is active
DISTRESS_ALERT_RANGE = 60           # meters - drones within this react to distress
DISTRESS_RESPONSE_SPEED_MULT = 1.3  # Speed multiplier for responding drones

# =============================================================================
# DRONE COORDINATED ASSAULT
# =============================================================================
COORDINATED_ASSAULT_ENABLED = True
COORDINATED_ASSAULT_RANGE = 30      # meters - drones must be within this to coordinate
COORDINATED_ASSAULT_SYNC_WINDOW = 300  # ms - attack timing synchronization
COORDINATED_ASSAULT_CONVERGE_ANGLE = 45  # degrees - angle to converge from

# =============================================================================
# ALTITUDE-BASED FLANKING
# =============================================================================
ALTITUDE_FLANK_ENABLED = True
ALTITUDE_FLANK_OFFSET_MIN = 15      # feet - minimum altitude difference
ALTITUDE_FLANK_OFFSET_MAX = 30      # feet - maximum altitude difference

# =============================================================================
# EVASION FEINTING
# =============================================================================
FEINT_ENABLED = True
FEINT_CHANCE = 0.20                 # 20% chance to feint
FEINT_DOUBLE_BACK_DELAY = 0.15      # seconds - delay before double-back

# =============================================================================
# DRONE SOUND REACTIONS
# =============================================================================
SOUND_REACTION_RANGE = 50     # Meters - drones within this react to player fire
SOUND_REACTION_DODGE_CHANCE = 0.7   # Chance to dodge vs advance
SOUND_REACTION_COOLDOWN = 1000      # ms - minimum time between reactions

# Sound-based detection (patrol drones can hear weapon fire)
SOUND_DETECTION_ENABLED = True
SOUND_DETECTION_RANGE = 100   # Meters - patrol drones can detect player at this range
SOUND_DETECTION_CHANCE = 0.7  # Chance to detect on weapon fire

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

# =============================================================================
# ENHANCED AUDIO SETTINGS (Research-based improvements)
# =============================================================================

# Logarithmic rolloff settings (more natural than linear)
# Uses inverse square law: volume halves per doubling of distance
ROLLOFF_MODE = 'logarithmic'  # 'linear' or 'logarithmic'
ROLLOFF_REFERENCE_DISTANCE = 1.0  # Distance where sound is at full volume

# Smooth occlusion transitions (prevents jarring filter changes)
# Higher values = faster transitions (20.0 = ~50ms to reach target)
OCCLUSION_INTERPOLATION_SPEED = 20.0  # How fast filters transition (per second)
OCCLUSION_MIN_CHANGE_THRESHOLD = 0.02  # Minimum change to trigger update

# Enhanced front/back distinction
REAR_LOWPASS_CUTOFF = 18000  # Hz - gentle lowpass for rear (subtle high-freq roll-off)
REAR_LOWPASS_START_ANGLE = 90  # Degrees - where rear filtering starts
REAR_VOLUME_REDUCTION = 0.0  # No volume reduction - only use lowpass for distinction

# Pre-attack audio warning
DRONE_ATTACK_WINDUP_MS = 200  # Milliseconds of warning before attack
DRONE_ATTACK_WINDUP_ENABLED = True

# Audio ducking settings
TTS_DUCK_VOLUME = 0.4  # Volume during TTS (40%)
TTS_DUCK_SPEED = 8.0  # Fade speed for ducking
COMBAT_DUCK_VOLUME = 0.6  # Volume during combat events
COMBAT_DUCK_SPEED = 6.0

# Compressor DSP settings (prevents clipping during intense damage)
COMPRESSOR_THRESHOLD_DB = -12.0  # Start compressing at this level
COMPRESSOR_RATIO = 4.0  # Compression ratio (4:1)
COMPRESSOR_ATTACK_MS = 10.0  # Attack time
COMPRESSOR_RELEASE_MS = 100.0  # Release time

# Hit confirmation settings
HIT_CONFIRM_DAMAGE_THRESHOLDS = [25, 50, 75]  # Damage thresholds for sound variation
HIT_CONFIRM_KILL_SOUND = True  # Play distinct sound for kills

# Reverb distance scaling
REVERB_DISTANCE_START = 15.0  # Distance where reverb starts increasing
REVERB_DISTANCE_MAX = 60.0  # Distance where reverb is at maximum
REVERB_WET_MIN_DB = -30.0  # Minimum reverb wet level (close sounds)
REVERB_WET_MAX_DB = -10.0  # Maximum reverb wet level (distant sounds)
REVERB_DECAY_MIN_MS = 800  # Minimum decay time
REVERB_DECAY_MAX_MS = 2500  # Maximum decay time

# =============================================================================
# DYNAMIC AUDIO VARIATION
# =============================================================================
# Distance-based sound intensity (pitch and volume modulation)
AUDIO_DISTANCE_CLOSE = 20.0  # Distance threshold for "close" sounds
AUDIO_DISTANCE_MEDIUM = 40.0  # Distance threshold for "medium" sounds
AUDIO_DISTANCE_FAR = 60.0  # Distance threshold for "far" sounds

# Pitch variation based on distance (1.0 = normal, <1.0 = lower, >1.0 = higher)
AUDIO_PITCH_CLOSE = 1.05  # Slightly higher pitch when close (more urgent)
AUDIO_PITCH_MEDIUM = 1.0  # Normal pitch at medium distance
AUDIO_PITCH_FAR = 0.95  # Slightly lower pitch when far (atmospheric)

# Speed-based sound intensity (for moving drones)
AUDIO_SPEED_THRESHOLD = 5.0  # Speed above which drone sounds more aggressive
AUDIO_SPEED_PITCH_BOOST = 0.1  # Additional pitch when drone moving fast
AUDIO_SPEED_VOLUME_BOOST = 0.15  # Additional volume when drone moving fast

# =============================================================================
# ENVIRONMENTAL AUDIO DEPTH
# =============================================================================
# Altitude-based reverb (more reverb when flying high = open sky)
ALTITUDE_REVERB_GROUND = 0.0  # Altitude in feet considered "ground level"
ALTITUDE_REVERB_LOW = 50.0  # Low altitude threshold
ALTITUDE_REVERB_HIGH = 200.0  # High altitude threshold
ALTITUDE_REVERB_MULTIPLIER_GROUND = 0.7  # Reverb multiplier on ground (less reverb)
ALTITUDE_REVERB_MULTIPLIER_HIGH = 1.4  # Reverb multiplier at high altitude (more reverb)

# Altitude-based decay (longer decay at high altitude = open space)
ALTITUDE_DECAY_MULTIPLIER_GROUND = 0.8  # Shorter decay on ground
ALTITUDE_DECAY_MULTIPLIER_HIGH = 1.3  # Longer decay at high altitude

# Echo effect for very distant sounds
AUDIO_ECHO_DISTANCE_START = 50.0  # Distance where echo starts
AUDIO_ECHO_DELAY_MS = 80  # Echo delay in milliseconds
AUDIO_ECHO_FEEDBACK = 0.3  # Echo feedback amount (0-1)
