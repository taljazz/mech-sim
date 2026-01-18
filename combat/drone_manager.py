"""
Drone Manager for MechSimulator.

Handles drone spawning, updates, audio, and combat.
"""

import math
import random

from state.constants import (
    DRONE_SPAWN_INTERVAL,
    DRONE_SPAWN_DISTANCE_MIN, DRONE_SPAWN_DISTANCE_MAX,
    DRONE_WEAPONS, BASE_VOLUMES, AIM_ASSIST_COOLDOWN,
    TARGET_LOCK_ANGLE, TARGET_LOCK_COOLDOWN,
    DRONE_ATTACK_WINDUP_MS, DRONE_ATTACK_WINDUP_ENABLED,
    # AI Personalities
    DRONE_PERSONALITIES, DRONE_PERSONALITY_WEIGHTS, PERSONALITY_WEAPON_PREFS,
    # Evasion
    EVASION_INTERVAL_MIN, EVASION_INTERVAL_MAX, EVASION_ANGLE_VARIANCE,
    # State transitions
    HESITATION_CHANCE, FALSE_START_CHANCE, COOLDOWN_REASSESS_CHANCE, COOLDOWN_PEEK_INTERVAL,
    # State durations
    DRONE_SPAWN_DURATION_MIN, DRONE_SPAWN_DURATION_MAX,
    DRONE_DETECT_DURATION_MIN, DRONE_DETECT_DURATION_MAX,
    DRONE_ATTACK_DURATION_MIN, DRONE_ATTACK_DURATION_MAX,
    # Search patterns
    SEARCH_SPIRAL_EXPANSION, SEARCH_ZIGZAG_WIDTH, SEARCH_WANDER_DISTANCE,
    DRONE_SEARCH_TIMEOUT_MIN, DRONE_SEARCH_TIMEOUT_MAX,
    SEARCH_EXPAND_ENABLED, SEARCH_EXPAND_INTERVAL, SEARCH_EXPAND_MULTIPLIER, SEARCH_EXPAND_MAX_MULT,
    # Flanking
    FLANK_SEPARATION_MIN, FLANK_SEPARATION_MAX, FLANK_CIRCLE_SPEED,
    FLANK_DISTANCE_MIN, FLANK_DISTANCE_MAX,
    ALTITUDE_FLANK_ENABLED, ALTITUDE_FLANK_OFFSET_MIN, ALTITUDE_FLANK_OFFSET_MAX,
    # Coordination
    CROSSFIRE_WINDOW,
    COORDINATED_ASSAULT_ENABLED, COORDINATED_ASSAULT_RANGE, COORDINATED_ASSAULT_SYNC_WINDOW,
    COORDINATED_ASSAULT_CONVERGE_ANGLE,
    # Movement constants (moved from function-level imports)
    DRONE_ENGAGE_SPEED_MULT, DRONE_EVASION_SPEED, DRONE_EVASION_ANGLE,
    # Attack adaptation
    ATTACK_FRUSTRATION_THRESHOLD, ATTACK_BREAK_OFF_CHANCE, ATTACK_MIN_SHOTS_BEFORE_ADAPT,
    ATTACK_ADAPTATION_ENABLED, ATTACK_WEAPON_SWITCH_THRESHOLD, ATTACK_RANGE_ADJUST_THRESHOLD,
    # Sound reactions
    SOUND_REACTION_RANGE, SOUND_REACTION_DODGE_CHANCE, SOUND_REACTION_COOLDOWN,
    SOUND_DETECTION_ENABLED, SOUND_DETECTION_RANGE, SOUND_DETECTION_CHANCE,
    # Wounded state
    WOUNDED_HEALTH_THRESHOLD, WOUNDED_EVASION_MULT, WOUNDED_AGGRESSION_MULT,
    WOUNDED_SPEED_MULT, WOUNDED_ERRATIC_INTERVAL,
    # Suppression state
    SUPPRESSION_ENABLED, SUPPRESSION_DAMAGE_THRESHOLD, SUPPRESSION_TIME_WINDOW,
    SUPPRESSION_DURATION_MIN, SUPPRESSION_DURATION_MAX, SUPPRESSION_COOLDOWN,
    # Distress beacon
    DISTRESS_BEACON_ENABLED, DISTRESS_DAMAGE_THRESHOLD, DISTRESS_HEALTH_THRESHOLD,
    DISTRESS_BEACON_DURATION, DISTRESS_ALERT_RANGE, DISTRESS_RESPONSE_SPEED_MULT,
    # Evasion feinting
    FEINT_ENABLED, FEINT_CHANCE, FEINT_DOUBLE_BACK_DELAY,
    # Camo system
    CAMO_SOUND_DETECTION_RANGE_MULT, CAMO_PROXIMITY_WARNING_ENABLED,
    CAMO_PROXIMITY_WARNING_RANGE, CAMO_PROXIMITY_WARNING_INTERVAL,
    CAMO_AMBUSH_ENABLED, CAMO_AMBUSH_DAMAGE_MULT,
    CAMO_CONFUSION_ENABLED, CAMO_CONFUSION_DURATION, CAMO_CONFUSION_LOSE_LOCK_RANGE
)
from audio.spatial import SpatialAudio

# Audio logging (lazy import)
_audio_log = None

def _get_audio_log():
    """Get the audio logging system."""
    global _audio_log
    if _audio_log is None:
        try:
            from audio.audio_logger import audio_log
            _audio_log = audio_log
        except ImportError:
            class DummyLog:
                def spatial(self, *a, **k): pass
                def drone_state(self, *a, **k): pass
                def drone_audio(self, *a, **k): pass
                def attack_warning(self, *a, **k): pass
                def hit_confirm(self, *a, **k): pass
            _audio_log = DummyLog()
    return _audio_log


class DroneManager:
    """Manages all drone entities and their behavior."""

    # Panning update threshold (radians) - only update if angle changed significantly
    PAN_UPDATE_THRESHOLD = 0.05  # ~3 degrees

    # Pan smoothing factor (0-1): higher = smoother but slower response
    # 0.75 means 75% old value + 25% new value per frame (smooth transitions)
    PAN_SMOOTHING_FACTOR = 0.75

    # Audio fade durations (milliseconds) - increased for smoother transitions
    TAKEOFF_FADE_IN_MS = 300      # Fade in for drone spawn/takeoff sounds
    PASSBY_FADE_IN_MS = 500       # Fade in for patrol passby sounds (longer for smooth entry)
    SUPERSONIC_FADE_IN_MS = 350   # Fade in for engaging supersonic sounds (smoother transition)
    AMBIENT_CROSSFADE_MS = 400    # Crossfade between ambient sounds (reduced audio dropouts)

    # Cached personality selection data (avoid recreating lists each spawn)
    _PERSONALITY_TYPES = list(DRONE_PERSONALITY_WEIGHTS.keys())
    _PERSONALITY_WEIGHTS = list(DRONE_PERSONALITY_WEIGHTS.values())

    def __init__(self, audio_manager, sound_loader, tts, game_state):
        """Initialize the drone manager.

        Args:
            audio_manager: AudioManager instance
            sound_loader: SoundLoader instance
            tts: TTSManager instance
            game_state: GameState instance
        """
        self.audio = audio_manager
        self.sounds = sound_loader
        self.tts = tts
        self.state = game_state

        self.drones = []
        self.spawn_timer = 0
        self.spatial = SpatialAudio()

        # Drone audio pool (set via set_drone_pool after config menu)
        self._drone_pool = None

        # Cached active drones list (updated once per frame)
        self._cached_active_drones = []
        self._active_drones_dirty = True

        # OPTIMIZATION: Cached player position (updated once per frame)
        self._player_x = 0.0
        self._player_y = 0.0
        self._player_altitude = 0.0
        self._player_facing = 0.0

    def set_drone_pool(self, pool):
        """Set the drone audio pool (called after config menu).

        Args:
            pool: DroneAudioPool instance
        """
        self._drone_pool = pool

    @property
    def max_drones(self) -> int:
        """Get the maximum number of drones (from config or pool)."""
        if self._drone_pool:
            return self._drone_pool.max_drones
        return self.state.config_drone_count

    def _get_drone_channels(self, drone_id: int):
        """Get drone channels from pool or fallback to audio manager.

        Args:
            drone_id: Drone ID

        Returns:
            Dict with channel wrappers
        """
        if self._drone_pool:
            return self._drone_pool.get_channels(drone_id)
        return self.audio.get_drone_channels(drone_id)

    def _update_drone_fades(self, dt: float):
        """Update fade states for all active drone audio channels.

        Must be called each frame to process fade in/out transitions.

        Args:
            dt: Delta time in seconds
        """
        for drone in self.drones:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                # Update fade for all drone channels
                for channel_name in ['ambient', 'combat', 'takeoff', 'passby', 'supersonic']:
                    if channel_name in dc and hasattr(dc[channel_name], 'update_fade'):
                        dc[channel_name].update_fade(dt)

    def update(self, current_time: int, dt: float, damage_system, camo_system) -> list:
        """Update all drones.

        Args:
            current_time: Current game time in milliseconds
            dt: Delta time in seconds
            damage_system: DamageSystem for applying damage
            camo_system: CamouflageSystem for camo state

        Returns:
            List of events that occurred (for external handling)
        """
        if not self.sounds.has_drone_sounds:
            return []

        events = []

        # OPTIMIZATION: Cache player position once at frame start
        self._player_x = self.state.player_x
        self._player_y = self.state.player_y
        self._player_altitude = self.state.player_altitude
        self._player_facing = self.state.facing_angle

        # Mark active drones cache as dirty at start of frame
        self._active_drones_dirty = True

        # Update fade states for all drone audio channels
        self._update_drone_fades(dt)

        # Spawn check - use cached active count
        if current_time - self.spawn_timer >= DRONE_SPAWN_INTERVAL:
            self.spawn_timer = current_time
            if len(self._get_active_drones_cached()) < self.max_drones:
                drone = self._spawn_drone(current_time)
                if drone:
                    events.append(('spawn', drone))

        # Update each drone
        drones_to_remove = []
        for drone in self.drones:
            if drone['state'] == 'destroyed':
                # Check if all destruction sounds have finished
                # Use pool's is_drone_silent if available, else fallback
                if self._drone_pool:
                    if self._drone_pool.is_drone_silent(drone['id']):
                        drones_to_remove.append(drone)
                else:
                    dc = self._get_drone_channels(drone['id'])
                    if dc and not dc['combat'].get_busy() and not dc['ambient'].get_busy():
                        drones_to_remove.append(drone)
                continue

            # Update position calculations for spatial audio (pass dt for velocity)
            self._update_spatial_audio(drone, dt)

            # Update state machine
            camo_effective = camo_system.is_effective if camo_system else False
            self._update_drone_state(drone, camo_effective, current_time, dt, damage_system)

            # Update ambient audio
            self._update_ambient_audio(drone, current_time)

        # Remove destroyed drones
        for drone in drones_to_remove:
            # Deactivate in pool if available
            if self._drone_pool:
                self._drone_pool.deactivate_drone(drone['id'])
            else:
                dc = self._get_drone_channels(drone['id'])
                if dc:
                    dc['ambient'].stop()
                    dc['combat'].stop()
            self.drones.remove(drone)
            print(f"Drone {drone['id']} removed from game")

        # Aiming assist
        self._update_aim_assist(current_time)

        return events

    def _spawn_drone(self, current_time: int) -> dict:
        """Spawn a new drone.

        Args:
            current_time: Current game time

        Returns:
            Drone dictionary or None
        """
        if len(self.drones) >= self.max_drones:
            return None

        spawn_angle = random.uniform(0, 360)
        spawn_distance = random.uniform(DRONE_SPAWN_DISTANCE_MIN, DRONE_SPAWN_DISTANCE_MAX)

        angle_rad = math.radians(spawn_angle)
        spawn_x = self._player_x + spawn_distance * math.sin(angle_rad)
        spawn_y = self._player_y + spawn_distance * math.cos(angle_rad)

        # Select personality using weighted random choice (cached lists)
        personality_type = random.choices(
            self._PERSONALITY_TYPES, weights=self._PERSONALITY_WEIGHTS, k=1
        )[0]
        personality = DRONE_PERSONALITIES[personality_type]

        # Base speed with personality multiplier
        base_speed = 5.0 + random.uniform(-1, 1)

        # Per-drone evasion interval (randomized, modified by personality evasion_skill)
        base_evasion_interval = random.uniform(EVASION_INTERVAL_MIN, EVASION_INTERVAL_MAX)
        evasion_interval = base_evasion_interval / personality['evasion_skill']  # Better evasion = faster dodging

        drone = {
            'id': len(self.drones),
            'state': 'spawning',
            'x': spawn_x,
            'y': spawn_y,
            'altitude': random.uniform(30, 80),
            'health': 100.0,
            'distance': spawn_distance,
            'altitude_diff': 0.0,
            'relative_angle': 0.0,
            'speed': base_speed * personality['speed_mult'],
            'base_speed': base_speed,  # Store unmodified for reference
            'climb_rate': 15.0,
            'attack_cooldown': 0,
            'state_start': current_time,
            'last_sound_update': 0,
            'patrol_target': (spawn_x, spawn_y),
            'last_known_x': spawn_x,
            'last_known_y': spawn_y,
            # Velocity tracking for Doppler effect
            'prev_x': spawn_x,
            'prev_y': spawn_y,
            'prev_altitude': random.uniform(30, 80),
            'velocity': (0.0, 0.0, 0.0),  # (vx, vy, vz) in meters/second
            # Personality system
            'personality': personality_type,
            'personality_data': personality,
            'accuracy_mult': personality['accuracy_mult'],
            'aggression': personality['aggression'],
            'evasion_skill': personality['evasion_skill'],
            'hesitation_chance': personality.get('hesitation_chance', HESITATION_CHANCE),
            'evasion_interval': evasion_interval,
            'evasion_timer': 0.0,
            'evasion_direction': 1,  # 1 or -1, toggled during evasion
            # Attack tracking for adaptation
            'shots_fired': 0,
            'hits_landed': 0,
            'attack_frustrated': False,
            # Coordination
            'tactic_role': None,  # 'primary', 'support', 'flanker'
            # Sound reaction
            'last_sound_reaction': 0,
            # State transition flags
            'hesitating': False,
            'false_start': False,
            # Search pattern
            'search_pattern': None,
            'search_waypoints': [],
            'search_waypoint_index': 0,
            # OPTIMIZATION: Pre-computed channel IDs to avoid per-frame string allocation
            '_channel_ids': {
                'ambient': f"drone_{len(self.drones)}_ambient",
                'combat': f"drone_{len(self.drones)}_combat",
                'takeoff': f"drone_{len(self.drones)}_takeoff",
                'passby': f"drone_{len(self.drones)}_passby",
                'supersonic': f"drone_{len(self.drones)}_supersonic",
                'explosion': f"drone_{len(self.drones)}_explosion",
                'debris': f"drone_{len(self.drones)}_debris"
            },
            # === NEW BEHAVIOR FIELDS ===
            # Wounded state
            'is_wounded': False,
            'wounded_erratic_timer': 0.0,
            # Suppression state
            'is_suppressed': False,
            'suppression_end_time': 0,
            'suppression_cooldown_end': 0,
            'recent_damage': 0,
            'damage_window_start': 0,
            # Distress beacon
            'distress_active': False,
            'distress_start_time': 0,
            # Coordinated assault
            'in_coordinated_assault': False,
            'assault_partner_id': None,
            'assault_converge_angle': 0,
            # Altitude flanking
            'target_flank_altitude': None,
            # Evasion feinting
            'feint_pending': False,
            'feint_timer': 0.0,
            # Attack adaptation
            'weapon_history': [],  # Track weapon effectiveness
            'preferred_range': None,  # Learned optimal range
            # Search expansion
            'search_expand_count': 0,
            'last_search_expand': 0
        }

        self.drones.append(drone)

        # Activate in pool if available
        if self._drone_pool:
            self._drone_pool.activate_drone(drone['id'])

        # Calculate initial spatial audio for the new drone
        self._update_spatial_audio(drone)

        # Play spawn sound using dedicated takeoff channel (won't cut off other sounds)
        dc = self._get_drone_channels(drone['id'])
        if dc:
            sound = self.sounds.get_drone_sound('takeoffs')
            if sound:
                pos = self._get_drone_3d_position(drone)
                dc['takeoff'].play_with_fade_in(
                    sound,
                    fade_in_ms=self.TAKEOFF_FADE_IN_MS,
                    position_3d=pos
                )
                self._set_3d_position(dc['takeoff'], drone, 'takeoff')  # Apply directional filter
                drone['takeoff_playing'] = True

        # Announce with personality for flavor
        personality_names = {
            'rookie': 'Rookie drone',
            'veteran': 'Veteran drone',
            'ace': 'Ace drone',
            'berserker': 'Berserker drone'
        }
        announcement = personality_names.get(personality_type, 'Hostile') + ' detected'
        self.tts.speak(announcement)
        print(f"Drone {drone['id']} ({personality_type}) spawned at ({spawn_x:.1f}, {spawn_y:.1f})")
        return drone

    def _update_spatial_audio(self, drone: dict, dt: float = 0.016):
        """Update spatial audio positioning for a drone.

        OPTIMIZATION: Calculates pan/vol ONCE and caches in drone dict.
        All other methods should use drone['pan'] and drone['vol'] directly.
        Also calculates velocity for Doppler effect.

        Args:
            drone: Drone dictionary
            dt: Delta time in seconds (for velocity calculation)
        """
        pan, vol, distance, rel_angle, alt_diff = self.audio.calculate_spatial_audio(
            source_x=drone['x'],
            source_y=drone['y'],
            source_altitude=drone['altitude'],
            listener_x=self._player_x,
            listener_y=self._player_y,
            listener_altitude=self._player_altitude,
            listener_facing=self._player_facing
        )

        # Apply pan smoothing to prevent jittery spatial audio during fast movement
        # Use exponential moving average: smoothed = old * factor + new * (1 - factor)
        if 'pan' in drone:
            old_pan = drone['pan']
            smoothed_pan = old_pan * self.PAN_SMOOTHING_FACTOR + pan * (1 - self.PAN_SMOOTHING_FACTOR)
        else:
            smoothed_pan = pan  # First frame, no smoothing needed

        # Cache ALL spatial values including smoothed pan/vol for reuse this frame
        drone['pan'] = smoothed_pan
        drone['raw_pan'] = pan  # Store raw value for debugging
        drone['vol'] = vol
        drone['distance'] = distance
        drone['relative_angle'] = rel_angle
        drone['altitude_diff'] = alt_diff
        drone['dt'] = dt  # Store dt for use in other methods

        # Calculate velocity for Doppler effect (meters per second)
        if dt > 0.001:  # Avoid division by zero
            prev_x = drone['prev_x']
            prev_y = drone['prev_y']
            prev_alt = drone['prev_altitude']

            # Calculate velocity components
            vx = (drone['x'] - prev_x) / dt
            vy = (drone['y'] - prev_y) / dt
            vz = (drone['altitude'] - prev_alt) / dt / 3.28  # Convert ft to m

            drone['velocity'] = (vx, vy, vz)

            # Store current position for next frame
            drone['prev_x'] = drone['x']
            drone['prev_y'] = drone['y']
            drone['prev_altitude'] = drone['altitude']

        # === LOGGING ===
        alog = _get_audio_log()
        alog.spatial(
            source=f"Drone {drone['id']}",
            pan=pan,
            volume=vol,
            distance=distance,
            angle=rel_angle,
            altitude_diff=alt_diff / 3.28 if alt_diff else 0  # Convert to meters for display
        )

    def _get_cached_spatial(self, drone: dict) -> tuple:
        """Get cached spatial audio pan and volume for a drone.

        OPTIMIZATION: Returns cached values from _update_spatial_audio().
        Falls back to calculation only if cache is missing.
        """
        if 'pan' in drone and 'vol' in drone:
            return drone['pan'], drone['vol']
        # Fallback (should rarely happen)
        self._update_spatial_audio(drone)
        return drone['pan'], drone['vol']

    def _apply_pan(self, channel, pan: float, vol: float):
        """Apply stereo panning to a channel (legacy 2D method)."""
        base_vol = BASE_VOLUMES.get('drone', 0.8)
        self.spatial.apply_stereo_pan(channel, pan, vol, base_vol, self.audio.master_volume)

    def _apply_dynamic_pitch(self, channel, drone: dict, distance: float):
        """Apply dynamic pitch variation based on distance and drone speed.

        Creates more immersive audio by:
        - Higher pitch when close (more urgent/aggressive feel)
        - Lower pitch when far (atmospheric, distant feel)
        - Additional pitch boost when drone is moving fast (charging)

        Args:
            channel: FMODChannelWrapper to adjust
            drone: Drone dictionary with position and velocity data
            distance: Distance to drone in meters
        """
        if not channel or not hasattr(channel, 'set_pitch'):
            return

        try:
            from state.constants import (
                AUDIO_DISTANCE_CLOSE, AUDIO_DISTANCE_MEDIUM, AUDIO_DISTANCE_FAR,
                AUDIO_PITCH_CLOSE, AUDIO_PITCH_MEDIUM, AUDIO_PITCH_FAR,
                AUDIO_SPEED_THRESHOLD, AUDIO_SPEED_PITCH_BOOST
            )
        except ImportError:
            # Use defaults if constants not defined
            AUDIO_DISTANCE_CLOSE = 20.0
            AUDIO_DISTANCE_MEDIUM = 40.0
            AUDIO_DISTANCE_FAR = 60.0
            AUDIO_PITCH_CLOSE = 1.05
            AUDIO_PITCH_MEDIUM = 1.0
            AUDIO_PITCH_FAR = 0.95
            AUDIO_SPEED_THRESHOLD = 5.0
            AUDIO_SPEED_PITCH_BOOST = 0.1

        # Calculate distance-based pitch
        if distance <= AUDIO_DISTANCE_CLOSE:
            # Close: interpolate between close and medium pitch
            factor = distance / AUDIO_DISTANCE_CLOSE
            base_pitch = AUDIO_PITCH_CLOSE + factor * (AUDIO_PITCH_MEDIUM - AUDIO_PITCH_CLOSE)
        elif distance <= AUDIO_DISTANCE_MEDIUM:
            # Medium: interpolate between medium and far pitch
            factor = (distance - AUDIO_DISTANCE_CLOSE) / (AUDIO_DISTANCE_MEDIUM - AUDIO_DISTANCE_CLOSE)
            base_pitch = AUDIO_PITCH_MEDIUM + factor * (AUDIO_PITCH_FAR - AUDIO_PITCH_MEDIUM)
        else:
            # Far: use far pitch, slightly lower for very distant
            if distance >= AUDIO_DISTANCE_FAR:
                base_pitch = AUDIO_PITCH_FAR * 0.98  # Extra low for very far
            else:
                factor = (distance - AUDIO_DISTANCE_MEDIUM) / (AUDIO_DISTANCE_FAR - AUDIO_DISTANCE_MEDIUM)
                base_pitch = AUDIO_PITCH_FAR + factor * (AUDIO_PITCH_FAR * 0.98 - AUDIO_PITCH_FAR)

        # Add speed-based pitch boost
        velocity = drone['velocity']
        speed = (velocity[0]**2 + velocity[1]**2 + velocity[2]**2) ** 0.5

        pitch_boost = 0.0
        if speed > AUDIO_SPEED_THRESHOLD:
            # Drone is moving fast - add urgency via pitch boost
            speed_factor = min(1.0, (speed - AUDIO_SPEED_THRESHOLD) / AUDIO_SPEED_THRESHOLD)
            pitch_boost = speed_factor * AUDIO_SPEED_PITCH_BOOST
            base_pitch += pitch_boost

        # Apply the calculated pitch
        channel.set_pitch(base_pitch)

        # === LOGGING ===
        alog = _get_audio_log()
        alog.pitch(
            source=f"Drone {drone['id']}",
            distance=distance,
            base_pitch=base_pitch,
            speed=speed,
            speed_boost=pitch_boost
        )

    def _get_drone_3d_position(self, drone: dict):
        """Get 3D position tuple for a drone (for passing to play()).

        Returns:
            Tuple of (x, y, altitude_meters) in game coordinates
        """
        altitude_meters = drone['altitude'] / 3.28
        return (drone['x'], drone['y'], altitude_meters)

    def _set_3d_position(self, channel, drone: dict, channel_type: str = 'ambient', dt: float = 0.016):
        """Set 3D position and directional filters for a channel based on drone location.

        Uses FMOD's native 3D spatialization plus directional filtering for
        front/behind and above/below perception. Also sets velocity for Doppler effect.
        Includes smooth occlusion transitions to prevent jarring audio changes.
        Also updates distance-based reverb for spatial depth perception.

        OPTIMIZATION: Uses cached spatial values from _update_spatial_audio() instead
        of recalculating. Values are already computed and stored in drone dict.

        Args:
            channel: FMODChannelWrapper to position
            drone: Drone dictionary with position data (including cached spatial values)
            channel_type: Type of channel ('ambient', 'combat') for unique ID
            dt: Delta time in seconds for smooth interpolation
        """
        if channel and hasattr(channel, 'set_3d_position'):
            # Convert altitude from feet to meters for audio positioning
            altitude_meters = drone['altitude'] / 3.28

            # Get velocity for Doppler effect
            velocity = drone['velocity']

            # Set 3D position with velocity for Doppler
            channel.set_3d_position(drone['x'], drone['y'], altitude_meters, velocity=velocity)

            # OPTIMIZATION: Use cached spatial values from _update_spatial_audio()
            # instead of recalculating with calculate_directional_params()
            relative_angle = drone['relative_angle']
            altitude_diff = drone['altitude_diff']
            distance = drone['distance']

            # OPTIMIZATION: Use pre-computed channel ID to avoid per-frame string allocation
            channel_id = drone['_channel_ids'].get(channel_type, f"drone_{drone['id']}_{channel_type}")

            # Apply directional filter with dt for smooth interpolation
            self.audio.apply_directional_filter(
                channel, relative_angle, altitude_diff, distance,
                apply_air_absorption=True, apply_occlusion=True,
                channel_id=channel_id,
                dt=dt
            )

            # Update distance-based reverb for spatial depth perception
            # Only update for ambient channels to avoid duplicate calls
            # Pass player altitude for environmental depth (more reverb when flying high)
            if channel_type == 'ambient':
                self.audio.fmod.update_distance_reverb(
                    distance,
                    enabled=True,
                    player_altitude=self.state.player_altitude
                )

            # === DYNAMIC AUDIO VARIATION ===
            # Apply pitch variation based on distance and speed for more immersive audio
            self._apply_dynamic_pitch(channel, drone, distance)

    def _update_drone_state(self, drone: dict, camo_effective: bool,
                            current_time: int, dt: float, damage_system):
        """Update drone state machine."""
        from state.constants import (
            DRONE_DETECT_RANGE, DRONE_LOSE_TRACK_RANGE, DRONE_REACQUIRE_RANGE,
            DRONE_ATTACK_RANGE, DRONE_CAMO_DETECT_RANGE, DRONE_CAMO_LOSE_TRACK_RANGE,
            DRONE_CAMO_REACQUIRE_RANGE, ALTITUDE_MAX
        )

        detect_range = DRONE_CAMO_DETECT_RANGE if camo_effective else DRONE_DETECT_RANGE
        lose_track_range = DRONE_CAMO_LOSE_TRACK_RANGE if camo_effective else DRONE_LOSE_TRACK_RANGE
        reacquire_range = DRONE_CAMO_REACQUIRE_RANGE if camo_effective else DRONE_REACQUIRE_RANGE

        # === WOUNDED STATE CHECK ===
        # Update wounded status based on health
        health_percent = (drone['health'] / 100.0) * 100
        if health_percent <= WOUNDED_HEALTH_THRESHOLD and not drone['is_wounded']:
            drone['is_wounded'] = True
            # Modify behavior when wounded
            drone['evasion_skill'] *= WOUNDED_EVASION_MULT
            drone['aggression'] *= WOUNDED_AGGRESSION_MULT
            self.tts.speak("Drone wounded")

        # === SUPPRESSION STATE CHECK ===
        if SUPPRESSION_ENABLED and drone['is_suppressed']:
            if current_time >= drone['suppression_end_time']:
                drone['is_suppressed'] = False
                drone['suppression_cooldown_end'] = current_time + SUPPRESSION_COOLDOWN
            else:
                # Can't attack while suppressed - just evade
                if drone['state'] in ('engaging', 'winding_up', 'attacking'):
                    self._move_engaging(drone, dt)
                    return  # Skip normal state processing

        # === DISTRESS BEACON UPDATE ===
        if drone['distress_active']:
            if current_time - drone['distress_start_time'] >= DISTRESS_BEACON_DURATION:
                drone['distress_active'] = False

        state = drone['state']

        if state == 'spawning':
            # Get or calculate spawn duration (randomized per spawn)
            if 'state_duration' not in drone:
                drone['state_duration'] = random.randint(DRONE_SPAWN_DURATION_MIN, DRONE_SPAWN_DURATION_MAX)
            if current_time - drone['state_start'] >= drone['state_duration']:
                drone['state'] = 'patrol'
                drone['patrol_target'] = self._generate_patrol_point()
                drone['state_start'] = current_time
                drone.pop('state_duration', None)  # Clear for next state

        elif state == 'patrol':
            reached = self._move_drone_toward(drone, drone['patrol_target'], dt)
            if reached:
                drone['patrol_target'] = self._generate_patrol_point()

            if drone['distance'] <= detect_range:
                drone['state'] = 'detecting'
                drone['state_start'] = current_time
                drone['last_known_x'] = self._player_x
                drone['last_known_y'] = self._player_y
                self._play_detection_sound(drone)

        elif state == 'detecting':
            drone['last_known_x'] = self._player_x
            drone['last_known_y'] = self._player_y
            # Get or calculate detect duration (randomized)
            if 'state_duration' not in drone:
                drone['state_duration'] = random.randint(DRONE_DETECT_DURATION_MIN, DRONE_DETECT_DURATION_MAX)
                # Check for hesitation (personality-based delay)
                if random.random() < drone['hesitation_chance']:
                    drone['hesitating'] = True
                    drone['state_duration'] += random.randint(300, 600)  # Additional hesitation delay
            if current_time - drone['state_start'] >= drone['state_duration']:
                # Check for false start (brief return to patrol)
                if random.random() < FALSE_START_CHANCE and not drone.get('had_false_start', False):
                    drone['state'] = 'patrol'
                    drone['patrol_target'] = self._generate_patrol_point()
                    drone['state_start'] = current_time
                    drone['had_false_start'] = True  # Only one false start per detection
                    drone.pop('state_duration', None)
                    drone['hesitating'] = False
                else:
                    drone['state'] = 'engaging'
                    drone['state_start'] = current_time
                    drone.pop('state_duration', None)
                    drone['hesitating'] = False
                    drone['had_false_start'] = False  # Reset for next time
                    self.tts.speak("Drone engaging")

        elif state == 'engaging':
            # Coordinate tactics with other drones
            self._coordinate_tactics(drone, current_time)

            # Aggressive pursuit with evasion and flanking
            self._move_engaging(drone, dt)

            # Adjust altitude
            self._adjust_altitude(drone, self._player_altitude, dt)

            drone['last_known_x'] = self._player_x
            drone['last_known_y'] = self._player_y

            if drone['distance'] > lose_track_range:
                drone['state'] = 'searching'
                drone['state_start'] = current_time
                self.tts.speak("Drone lost contact")
                self._play_scan_sound(drone)
            elif drone['distance'] <= DRONE_ATTACK_RANGE:
                # Check if coordinated tactics require holding fire
                hold_until = drone.get('hold_fire_until', 0)
                if current_time < hold_until:
                    return  # Wait for coordinated timing

                # Transition to wind-up state for pre-attack warning
                if DRONE_ATTACK_WINDUP_ENABLED:
                    drone['state'] = 'winding_up'
                    drone['state_start'] = current_time
                    self._play_attack_windup(drone)
                else:
                    drone['state'] = 'attacking'
                    drone['state_start'] = current_time
                    self._execute_attack(drone, damage_system, current_time)

        elif state == 'winding_up':
            # Pre-attack warning state - randomized duration for unpredictability
            if 'state_duration' not in drone:
                drone['state_duration'] = random.randint(DRONE_ATTACK_DURATION_MIN, DRONE_ATTACK_DURATION_MAX)
            if current_time - drone['state_start'] >= drone['state_duration']:
                drone['state'] = 'attacking'
                drone['state_start'] = current_time
                drone.pop('state_duration', None)
                # Log state change
                alog = _get_audio_log()
                alog.drone_state(drone['id'], 'attacking', drone['distance'], old_state='winding_up')
                self._execute_attack(drone, damage_system, current_time)
            # Drone still tracks player during wind-up
            drone['last_known_x'] = self._player_x
            drone['last_known_y'] = self._player_y

        elif state == 'searching':
            # Initialize search pattern if not set
            if not drone.get('search_pattern'):
                patterns = ['spiral', 'zigzag', 'wander']
                drone['search_pattern'] = random.choice(patterns)
                drone['search_waypoints'] = self._generate_search_waypoints(
                    drone,
                    drone.get('last_known_x', self._player_x),
                    drone.get('last_known_y', self._player_y)
                )
                drone['search_waypoint_index'] = 0
                drone['search_expand_count'] = 0
                drone['last_search_expand'] = current_time

            # === EXPANDING SEARCH RADIUS ===
            if SEARCH_EXPAND_ENABLED:
                if current_time - drone['last_search_expand'] >= SEARCH_EXPAND_INTERVAL:
                    drone['last_search_expand'] = current_time
                    current_mult = 1.0 + (drone['search_expand_count'] * (SEARCH_EXPAND_MULTIPLIER - 1.0))
                    if current_mult < SEARCH_EXPAND_MAX_MULT:
                        drone['search_expand_count'] += 1
                        # Regenerate waypoints with expanded radius
                        drone['search_waypoints'] = self._generate_search_waypoints(
                            drone,
                            drone.get('last_known_x', self._player_x),
                            drone.get('last_known_y', self._player_y),
                            expand_mult=1.0 + (drone['search_expand_count'] * (SEARCH_EXPAND_MULTIPLIER - 1.0))
                        )
                        drone['search_waypoint_index'] = 0

            # Get current waypoint
            waypoints = drone.get('search_waypoints', [])
            wp_index = drone.get('search_waypoint_index', 0)

            if waypoints and wp_index < len(waypoints):
                target = waypoints[wp_index]
                reached = self._move_drone_toward(drone, target, dt)
                if reached:
                    drone['search_waypoint_index'] = wp_index + 1
            else:
                # Fallback to last known position if no waypoints left
                target = (drone.get('last_known_x', self._player_x),
                          drone.get('last_known_y', self._player_y))
                reached = self._move_drone_toward(drone, target, dt)

            # Get or calculate search timeout (randomized)
            if 'state_duration' not in drone:
                drone['state_duration'] = random.randint(DRONE_SEARCH_TIMEOUT_MIN, DRONE_SEARCH_TIMEOUT_MAX)

            if drone['distance'] <= reacquire_range:
                drone['state'] = 'detecting'
                drone['state_start'] = current_time
                drone['last_known_x'] = self._player_x
                drone['last_known_y'] = self._player_y
                drone.pop('state_duration', None)
                # Clear search pattern data
                drone['search_pattern'] = None
                drone['search_waypoints'] = []
                self.tts.speak("Drone reacquired")
                self._play_detection_sound(drone)
            elif reached or (current_time - drone['state_start'] >= drone['state_duration']):
                drone['state'] = 'patrol'
                drone['patrol_target'] = self._generate_patrol_point()
                drone['state_start'] = current_time
                drone.pop('state_duration', None)
                # Clear search pattern data
                drone['search_pattern'] = None
                drone['search_waypoints'] = []

        elif state == 'attacking':
            from state.constants import DRONE_ATTACK_STATE_DURATION, DRONE_COOLDOWN_MIN, DRONE_COOLDOWN_MAX
            # Fire shots continuously during attack state
            self._update_attack_firing(drone, damage_system, current_time)
            if current_time - drone['state_start'] >= DRONE_ATTACK_STATE_DURATION:
                drone['state'] = 'cooldown'
                drone['state_start'] = current_time
                # Set randomized cooldown duration for this burst
                drone['cooldown_duration'] = random.randint(DRONE_COOLDOWN_MIN, DRONE_COOLDOWN_MAX)
                # Store player position for reassessment tracking
                drone['last_attack_x'] = self._player_x
                drone['last_attack_y'] = self._player_y
                # Clear attack state
                drone['shots_fired'] = 0
                drone['last_shot_time'] = 0

        elif state == 'cooldown':
            cooldown_duration = drone.get('cooldown_duration', 300)

            # Periodic reassessment during cooldown
            last_peek = drone.get('last_peek_time', drone['state_start'])
            if current_time - last_peek >= COOLDOWN_PEEK_INTERVAL:
                drone['last_peek_time'] = current_time

                # Check if should reassess (personality affects chance)
                reassess_chance = COOLDOWN_REASSESS_CHANCE * (1 + drone['aggression'])
                if random.random() < reassess_chance:
                    # Track player movement since attack started
                    last_attack_x = drone.get('last_attack_x', drone['last_known_x'])
                    last_attack_y = drone.get('last_attack_y', drone['last_known_y'])
                    player_moved = math.hypot(
                        self._player_x - last_attack_x,
                        self._player_y - last_attack_y
                    )

                    # Panic response - player got very close
                    if drone['distance'] < 10:
                        drone['cooldown_duration'] = min(cooldown_duration, 200)  # Shorten cooldown
                        drone['state'] = 'engaging'
                        drone['state_start'] = current_time
                        return  # Exit early

                    # Player moved significantly - re-engage immediately
                    elif player_moved > 10:
                        drone['state'] = 'engaging'
                        drone['last_known_x'] = self._player_x
                        drone['last_known_y'] = self._player_y
                        drone['state_start'] = current_time
                        return  # Exit early

                    # Player very far - extend cooldown and consider disengaging
                    elif drone['distance'] > 40:
                        drone['cooldown_duration'] = cooldown_duration + 500  # Extend cooldown

            if current_time - drone['state_start'] >= cooldown_duration:
                if drone['distance'] <= lose_track_range:
                    drone['state'] = 'engaging'
                    drone['last_known_x'] = self._player_x
                    drone['last_known_y'] = self._player_y
                else:
                    drone['state'] = 'searching'
                drone['state_start'] = current_time
                drone.pop('last_peek_time', None)  # Clear peek tracking

    def _move_engaging(self, drone: dict, dt: float):
        """Move drone during engaging state with evasion and flanking.

        Implements:
        - Evasive maneuvers when player is aiming at drone
        - Flanking behavior when multiple drones are active
        - Aggressive pursuit speed
        """
        player_x = self._player_x
        player_y = self._player_y

        # Check if player is aiming at this drone
        being_aimed_at = abs(drone['relative_angle']) < DRONE_EVASION_ANGLE

        # Get other engaging drones for flanking coordination
        other_engaging = [d for d in self.drones
                         if d['id'] != drone['id'] and d['state'] == 'engaging']

        dx = player_x - drone['x']
        dy = player_y - drone['y']
        dist = math.hypot(dx, dy)

        if dist < 0.5:
            return

        if being_aimed_at and dist > 5:
            # Evasive maneuver - strafe at varied angle from perpendicular
            # Base perpendicular direction
            base_perp_x = -dy / dist
            base_perp_y = dx / dist

            # Add angle variance for unpredictable movement
            # Use stored variance or generate new one on direction change
            if 'evasion_angle_offset' not in drone:
                drone['evasion_angle_offset'] = random.uniform(-EVASION_ANGLE_VARIANCE, EVASION_ANGLE_VARIANCE)

            # Apply angle offset to perpendicular direction
            offset_rad = math.radians(drone['evasion_angle_offset'])
            cos_off, sin_off = math.cos(offset_rad), math.sin(offset_rad)
            perp_x = base_perp_x * cos_off - base_perp_y * sin_off
            perp_y = base_perp_x * sin_off + base_perp_y * cos_off

            # Evasion movement - skill affects speed
            evasion_speed = DRONE_EVASION_SPEED * drone['evasion_skill']
            evasion_dist = evasion_speed * dt * drone['evasion_direction']
            drone['x'] += perp_x * evasion_dist
            drone['y'] += perp_y * evasion_dist

            # Update evasion timer using per-drone interval (varies by personality)
            drone['evasion_timer'] += dt

            # === EVASION FEINTING ===
            # Check for feint (fake direction change before real one)
            if FEINT_ENABLED and not drone['feint_pending']:
                if drone['evasion_timer'] > drone['evasion_interval'] * 0.8:
                    # Near direction change - chance to feint
                    if random.random() < FEINT_CHANCE:
                        drone['feint_pending'] = True
                        drone['feint_timer'] = 0.0
                        # Fake out - reverse direction early
                        drone['evasion_direction'] *= -1

            # Handle feint double-back
            if drone['feint_pending']:
                drone['feint_timer'] += dt
                if drone['feint_timer'] >= FEINT_DOUBLE_BACK_DELAY:
                    # Double-back - reverse again (back to original direction)
                    drone['evasion_direction'] *= -1
                    drone['feint_pending'] = False
                    drone['evasion_timer'] = 0
                    drone['evasion_angle_offset'] = random.uniform(-EVASION_ANGLE_VARIANCE, EVASION_ANGLE_VARIANCE)

            elif drone['evasion_timer'] > drone['evasion_interval']:
                drone['evasion_timer'] = 0
                drone['evasion_direction'] *= -1
                # New random angle offset each direction change
                drone['evasion_angle_offset'] = random.uniform(-EVASION_ANGLE_VARIANCE, EVASION_ANGLE_VARIANCE)

            # Still approach player but slower
            toward_dist = drone['speed'] * DRONE_ENGAGE_SPEED_MULT * 0.5 * dt
            drone['x'] += (dx / dist) * toward_dist
            drone['y'] += (dy / dist) * toward_dist

        elif other_engaging:
            # Tactical flanking - maintain 90-120° separation from other drone
            other = other_engaging[0]
            other_angle = math.atan2(other['x'] - player_x, other['y'] - player_y)
            my_angle = math.atan2(drone['x'] - player_x, drone['y'] - player_y)

            # Current angular separation (in degrees)
            separation = math.degrees(my_angle - other_angle) % 360
            if separation > 180:
                separation = 360 - separation

            # Target separation (randomized within range, stored per drone)
            if 'target_separation' not in drone:
                drone['target_separation'] = random.uniform(FLANK_SEPARATION_MIN, FLANK_SEPARATION_MAX)

            # Gradual circling - move around player if not at target separation
            if separation < FLANK_SEPARATION_MIN - 10:
                # Too close to other drone, circle away (only set once)
                if 'circle_direction' not in drone:
                    drone['circle_direction'] = 1 if random.random() > 0.5 else -1
            elif separation > FLANK_SEPARATION_MAX + 10:
                # Too far from other drone, circle toward (only toggle once)
                if not drone.get('_circling_toward', False):
                    drone['circle_direction'] = -drone.get('circle_direction', 1)
                    drone['_circling_toward'] = True
            else:
                # Reset flags when in good range
                drone['_circling_toward'] = False

            # Apply gradual circling motion
            circle_speed_rad = math.radians(FLANK_CIRCLE_SPEED) * dt
            circle_dir = drone.get('circle_direction', 1)
            new_angle = my_angle + circle_speed_rad * circle_dir

            # Flank distance - store per drone to prevent jitter
            if 'flank_distance' not in drone:
                drone['flank_distance'] = random.uniform(FLANK_DISTANCE_MIN, FLANK_DISTANCE_MAX)
            flank_distance = drone['flank_distance']

            # === ALTITUDE-BASED FLANKING ===
            # Set altitude offset for tactical advantage (one high, one low)
            if ALTITUDE_FLANK_ENABLED:
                if drone['target_flank_altitude'] is None:
                    # Determine altitude offset based on drone ID (alternates high/low)
                    offset = random.uniform(ALTITUDE_FLANK_OFFSET_MIN, ALTITUDE_FLANK_OFFSET_MAX)
                    if drone['id'] % 2 == 0:
                        drone['target_flank_altitude'] = self._player_altitude + offset
                    else:
                        drone['target_flank_altitude'] = self._player_altitude - offset

            # Calculate new position on the circle
            target_x = player_x + flank_distance * math.sin(new_angle)
            target_y = player_y + flank_distance * math.cos(new_angle)

            # Move toward calculated flank position
            old_speed = drone['speed']
            drone['speed'] *= DRONE_ENGAGE_SPEED_MULT
            self._move_drone_toward(drone, (target_x, target_y), dt)
            drone['speed'] = old_speed
        else:
            # Direct aggressive pursuit
            old_speed = drone['speed']
            drone['speed'] *= DRONE_ENGAGE_SPEED_MULT
            self._move_drone_toward(drone, (player_x, player_y), dt)
            drone['speed'] = old_speed

    def _move_drone_toward(self, drone: dict, target: tuple, dt: float) -> bool:
        """Move drone toward target position."""
        tx, ty = target
        dx = tx - drone['x']
        dy = ty - drone['y']
        dist = math.hypot(dx, dy)

        if dist < 0.5:
            return True

        move_dist = drone['speed'] * dt
        if move_dist > dist:
            move_dist = dist

        drone['x'] += (dx / dist) * move_dist
        drone['y'] += (dy / dist) * move_dist
        return False

    def _adjust_altitude(self, drone: dict, target_alt: float, dt: float):
        """Adjust drone altitude.

        Uses target_flank_altitude for flanking drones if set.
        """
        from state.constants import ALTITUDE_MAX

        # Use flanking altitude if set, otherwise use passed target
        if ALTITUDE_FLANK_ENABLED and drone['target_flank_altitude'] is not None:
            target_alt = drone['target_flank_altitude']

        # Calculate difference to target
        alt_diff = drone['altitude'] - target_alt
        climb_rate = drone['climb_rate']

        # Wounded drones have erratic altitude
        if drone['is_wounded']:
            # Add random altitude jitter
            if random.random() < WOUNDED_ERRATIC_INTERVAL:
                alt_diff += random.uniform(-10, 10)

        if alt_diff > 5:
            drone['altitude'] = max(0, drone['altitude'] - climb_rate * dt)
        elif alt_diff < -5:
            drone['altitude'] = min(ALTITUDE_MAX, drone['altitude'] + climb_rate * dt)

    def _generate_patrol_point(self) -> tuple:
        """Generate a patrol waypoint around player."""
        patrol_distance = random.uniform(25, 35)
        patrol_angle = random.uniform(0, 360)
        angle_rad = math.radians(patrol_angle)
        return (
            self._player_x + patrol_distance * math.sin(angle_rad),
            self._player_y + patrol_distance * math.cos(angle_rad)
        )

    def _generate_search_waypoints(self, drone: dict, last_x: float, last_y: float,
                                     expand_mult: float = 1.0) -> list:
        """Generate waypoints for search pattern.

        Args:
            drone: Drone dictionary (contains search_pattern)
            last_x: Last known player X position
            last_y: Last known player Y position
            expand_mult: Multiplier for search radius (for expanding search)

        Returns:
            List of (x, y) waypoints
        """
        pattern = drone.get('search_pattern', 'wander')
        waypoints = []

        # Apply expansion multiplier to search distances
        spiral_exp = SEARCH_SPIRAL_EXPANSION * expand_mult
        zigzag_width = SEARCH_ZIGZAG_WIDTH * expand_mult
        wander_dist = SEARCH_WANDER_DISTANCE * expand_mult

        if pattern == 'spiral':
            # Spiral outward from last known position
            for i in range(5):
                angle = i * 72  # 72 degrees per step (5 steps = full circle)
                radius = (i + 1) * spiral_exp
                rad = math.radians(angle)
                waypoints.append((
                    last_x + radius * math.sin(rad),
                    last_y + radius * math.cos(rad)
                ))

        elif pattern == 'zigzag':
            # Zigzag perpendicular to approach vector
            # Approach direction from drone to last known pos
            dx = last_x - drone['x']
            dy = last_y - drone['y']
            dist = math.hypot(dx, dy) or 1

            # Perpendicular vector
            perp_x = -dy / dist
            perp_y = dx / dist

            # Forward vector
            fwd_x = dx / dist
            fwd_y = dy / dist

            # Generate zigzag pattern
            for i in range(4):
                side = 1 if i % 2 == 0 else -1
                forward_dist = (i + 1) * 5 * expand_mult  # 5m forward per step, scaled
                lateral_dist = side * zigzag_width
                waypoints.append((
                    drone['x'] + fwd_x * forward_dist + perp_x * lateral_dist,
                    drone['y'] + fwd_y * forward_dist + perp_y * lateral_dist
                ))

        else:  # wander
            # Random waypoints around last known position
            for _ in range(4):
                angle = random.uniform(0, 360)
                dist = random.uniform(wander_dist * 0.5, wander_dist)
                rad = math.radians(angle)
                waypoints.append((
                    last_x + dist * math.sin(rad),
                    last_y + dist * math.cos(rad)
                ))

        # Always end at last known position
        waypoints.append((last_x, last_y))
        return waypoints

    def react_to_player_fire(self, current_time: int, weapon_type: str = None):
        """Make drones react when player fires a weapon.

        Called from WeaponSystem when player fires.
        Drones within range have a chance to dodge or advance.
        Patrol drones can detect player via sound at extended range.

        Args:
            current_time: Current game time in ms
            weapon_type: Type of weapon fired (for varied reactions)
        """
        player_facing_rad = math.radians(self._player_facing)
        player_x = self._player_x
        player_y = self._player_y

        for drone in self.drones:
            if drone['state'] in ('spawning', 'destroyed'):
                continue

            # === SOUND-BASED DETECTION FOR PATROL DRONES ===
            if SOUND_DETECTION_ENABLED and drone['state'] in ('patrol', 'searching'):
                # Camo reduces sound detection range by 50%
                camo_effective = self.state.camo_active and not self.state.camo_revealed
                sound_range = SOUND_DETECTION_RANGE
                if camo_effective:
                    sound_range = SOUND_DETECTION_RANGE * CAMO_SOUND_DETECTION_RANGE_MULT

                if drone['distance'] <= sound_range:
                    if random.random() < SOUND_DETECTION_CHANCE:
                        # Sound gave away player position!
                        drone['state'] = 'detecting'
                        drone['state_start'] = current_time
                        drone['last_known_x'] = player_x
                        drone['last_known_y'] = player_y
                        self._play_detection_sound(drone)
                        self.tts.speak("Drone heard weapon")
                        continue

            # Only react if within hearing range
            if drone['distance'] > SOUND_REACTION_RANGE:
                continue

            # Check cooldown on reactions
            last_reaction = drone.get('last_sound_reaction', 0)
            if current_time - last_reaction < SOUND_REACTION_COOLDOWN:
                continue

            # Personality affects reaction
            personality = drone.get('personality', 'veteran')
            aggression = drone.get('aggression', 0.5)

            # === WEAPON-TYPE SPECIFIC REACTIONS ===
            dodge_chance = SOUND_REACTION_DODGE_CHANCE * (1 - aggression)
            if weapon_type == 'missiles':
                dodge_chance = min(0.9, dodge_chance * 1.5)  # More likely to dodge missiles
            elif weapon_type == 'emp':
                dodge_chance = min(0.8, dodge_chance * 1.3)  # EMP is scary

            # Determine reaction type
            if random.random() < dodge_chance:
                # Dodge - move perpendicular to player's facing
                perp_x = -math.cos(player_facing_rad)
                perp_y = math.sin(player_facing_rad)

                # Random direction left or right
                dodge_dir = random.choice([-1, 1])
                dodge_distance = 3.0  # Meters to dodge

                # Missiles cause bigger dodge
                if weapon_type == 'missiles':
                    dodge_distance = 5.0

                drone['x'] += perp_x * dodge_distance * dodge_dir
                drone['y'] += perp_y * dodge_distance * dodge_dir
                drone['last_sound_reaction'] = current_time

                # Rookies might flee entirely
                if personality == 'rookie' and random.random() < 0.3:
                    # Run away
                    dx = drone['x'] - player_x
                    dy = drone['y'] - player_y
                    dist = math.hypot(dx, dy) or 1
                    drone['x'] += (dx / dist) * 5  # Move 5m away
                    drone['y'] += (dy / dist) * 5
            else:
                # Advance aggressively (more likely for aggressive personalities)
                if random.random() < aggression:
                    # Move toward player
                    dx = player_x - drone['x']
                    dy = player_y - drone['y']
                    dist = math.hypot(dx, dy) or 1
                    advance_distance = 2.0

                    drone['x'] += (dx / dist) * advance_distance
                    drone['y'] += (dy / dist) * advance_distance
                    drone['last_sound_reaction'] = current_time

                    # Berserkers get extra aggressive
                    if personality == 'berserker':
                        drone['x'] += (dx / dist) * advance_distance  # Double advance

    def _coordinate_tactics(self, drone: dict, current_time: int):
        """Assign tactical roles and coordinate multi-drone behavior.

        Implements:
        - Crossfire: Both drones attack within 500ms of each other
        - Suppression: One drone attacks while other repositions
        - Pincer: Approach from opposite angles

        Args:
            drone: The drone to coordinate
            current_time: Current game time in ms
        """
        # Throttle coordination checks to every 200ms (not every frame)
        last_coord = drone.get('_last_coordination', 0)
        if current_time - last_coord < 200:
            return
        drone['_last_coordination'] = current_time

        # Get other engaging/attacking drones
        other_combat_drones = [d for d in self.drones
                               if d['id'] != drone['id']
                               and d['state'] in ('engaging', 'attacking', 'winding_up')]

        if not other_combat_drones:
            # Solo drone - acts as primary
            drone['tactic_role'] = 'primary'
            return

        other = other_combat_drones[0]

        # If other drone is attacking, coordinate timing
        if other['state'] in ('attacking', 'winding_up'):
            other_attack_start = other.get('state_start', 0)
            time_since_other = current_time - other_attack_start

            # Crossfire - try to attack within CROSSFIRE_WINDOW
            if time_since_other < CROSSFIRE_WINDOW:
                drone['tactic_role'] = 'crossfire'
                # Ready to attack - coordinated timing
            else:
                # Other drone has been attacking a while - be support
                drone['tactic_role'] = 'support'
                # Suppression role - reposition instead of immediate attack
                if random.random() < 0.4:  # 40% chance to hold fire and reposition
                    drone['hold_fire_until'] = current_time + 500  # Wait 500ms
        else:
            # Both engaging - assign complementary roles based on aggression
            my_aggression = drone['aggression']
            other_aggression = other['aggression']

            if my_aggression > other_aggression:
                drone['tactic_role'] = 'primary'
                other['tactic_role'] = 'flanker'
            else:
                drone['tactic_role'] = 'flanker'
                other['tactic_role'] = 'primary'

            # === COORDINATED ASSAULT ===
            # Check if both drones in range for synchronized attack
            if COORDINATED_ASSAULT_ENABLED:
                if (drone['distance'] <= COORDINATED_ASSAULT_RANGE and
                    other['distance'] <= COORDINATED_ASSAULT_RANGE):
                    # Both in range - initiate coordinated assault
                    if not drone['in_coordinated_assault']:
                        drone['in_coordinated_assault'] = True
                        drone['assault_partner_id'] = other['id']
                        # Set converge angles (attack from different directions)
                        drone['assault_converge_angle'] = COORDINATED_ASSAULT_CONVERGE_ANGLE
                        other['assault_converge_angle'] = -COORDINATED_ASSAULT_CONVERGE_ANGLE
                        # Sync attack timing
                        drone['hold_fire_until'] = current_time + COORDINATED_ASSAULT_SYNC_WINDOW
                        other['hold_fire_until'] = current_time + COORDINATED_ASSAULT_SYNC_WINDOW

                        # === COORDINATION AUDIO ===
                        # Play transmission sound to indicate drones coordinating
                        self._play_coordination_audio(drone)

    def _play_coordination_audio(self, drone: dict):
        """Play transmission sound when drones coordinate tactics."""
        sound = self.sounds.get_drone_sound('transmissions')
        if sound:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                pos = self._get_drone_3d_position(drone)
                dc['combat'].play(sound, position_3d=pos)
                self._set_3d_position(dc['combat'], drone, 'combat')

    def _play_detection_sound(self, drone: dict):
        """Play drone detection beacon sound with 3D positioning."""
        sound = self.sounds.get_drone_sound('beacons')
        if sound:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                pos = self._get_drone_3d_position(drone)
                dc['combat'].play(sound, position_3d=pos)
                self._set_3d_position(dc['combat'], drone, 'combat')  # Apply directional filter

    def _play_scan_sound(self, drone: dict):
        """Play drone scanning sound with 3D positioning."""
        sound = self.sounds.get_drone_sound('scans')
        if sound:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                pos = self._get_drone_3d_position(drone)
                dc['combat'].play(sound, position_3d=pos)
                self._set_3d_position(dc['combat'], drone, 'combat')  # Apply directional filter

    def _play_attack_windup(self, drone: dict):
        """Play pre-attack warning sound with 3D positioning.

        This gives players a ~200ms audio cue before the attack starts,
        allowing reaction time for shield activation or evasion.

        WEAPON-SPECIFIC SOUNDS:
        - Pulse cannon: Fast beeps (close range threat)
        - Plasma launcher: Rising warble (medium range)
        - Rail gun: Charging hum (long range, most dangerous)
        """
        # === LOGGING ===
        alog = _get_audio_log()
        alog.attack_warning(
            drone_id=drone['id'],
            windup_ms=DRONE_ATTACK_WINDUP_MS,
            distance=drone['distance']
        )
        alog.drone_state(drone['id'], 'winding_up', drone['distance'], old_state='engaging')

        # Pre-select weapon for this attack (stored for execution phase)
        weapon_type = self._select_weapon(drone)
        drone['attack_weapon'] = weapon_type

        # === WEAPON-SPECIFIC WIND-UP SOUNDS ===
        # Try to use weapon-specific sounds, fall back to beacons
        dc = self._get_drone_channels(drone['id'])
        if not dc:
            return

        pos = self._get_drone_3d_position(drone)

        # Try weapon-specific sound first (weapon types are direct categories)
        weapon_sound = self.sounds.get_drone_sound(weapon_type)
        if weapon_sound:
            dc['combat'].play(weapon_sound, position_3d=pos, velocity=drone['velocity'])
            self._set_3d_position(dc['combat'], drone, 'combat')
            alog.drone_audio(drone['id'], f'windup_{weapon_type}', 'play')
        else:
            # Fall back to beacon sounds with pitch variation by weapon
            sound = self.sounds.get_drone_sound('beacons')
            if sound:
                dc['combat'].play(sound, position_3d=pos, velocity=drone['velocity'])
                self._set_3d_position(dc['combat'], drone, 'combat')
                alog.drone_audio(drone['id'], 'windup_beacon', 'play')

    def _update_ambient_audio(self, drone: dict, current_time: int):
        """Update drone ambient/movement audio with 3D positioning.

        Sound volume is controlled by FMOD 3D distance attenuation.
        Sounds loop continuously while drone is active.
        """
        # Allow ambient audio during all active drone states
        # (not during spawning, destroyed, or searching when drone lost player)
        if drone['state'] not in ('patrol', 'detecting', 'engaging', 'attacking', 'cooldown'):
            return

        dc = self._get_drone_channels(drone['id'])
        if not dc:
            return

        # Determine which sound type is needed based on drone behavior
        # Supersonic for aggressive states (engaging, attacking), passby for patrol
        need_supersonic = (drone['state'] in ('engaging', 'attacking'))

        # Get drone position for 3D audio
        pos = self._get_drone_3d_position(drone)

        # Get dt from drone (stored during spatial audio update)
        dt = drone['dt']

        # Update takeoff channel position if still playing
        if dc['takeoff'].get_busy():
            self._set_3d_position(dc['takeoff'], drone, 'takeoff', dt=dt)

        # Handle passby channel (patrol sounds) - separate channel, won't cut off others
        if not need_supersonic:
            # Need passby sound - stop supersonic if playing, start/continue passby
            if dc['supersonic'].get_busy():
                dc['supersonic'].fade_out(self.AMBIENT_CROSSFADE_MS)

            if not dc['passby'].get_busy():
                # Start new passby sound
                sound = self.sounds.get_drone_sound('passbys')
                if sound:
                    dc['passby'].play_with_fade_in(
                        sound,
                        fade_in_ms=self.PASSBY_FADE_IN_MS,
                        loops=0,
                        mono_downmix=True,
                        position_3d=pos
                    )
            # Update 3D position
            self._set_3d_position(dc['passby'], drone, 'passby', dt=dt)
        else:
            # Need supersonic sound - stop passby if playing, start/continue supersonic
            if dc['passby'].get_busy():
                dc['passby'].fade_out(self.AMBIENT_CROSSFADE_MS)

            if not dc['supersonic'].get_busy():
                # Start new supersonic sound
                sound = self.sounds.get_drone_sound('supersonics')
                if sound:
                    dc['supersonic'].play_with_fade_in(
                        sound,
                        fade_in_ms=self.SUPERSONIC_FADE_IN_MS,
                        loops=0,
                        mono_downmix=True,
                        position_3d=pos
                    )
            # Update 3D position
            self._set_3d_position(dc['supersonic'], drone, 'supersonic', dt=dt)

    def _execute_attack(self, drone: dict, damage_system, current_time: int):
        """Initialize drone attack on player - sets up rapid fire state."""
        if self.state.game_over:
            return

        weapon_type = self._select_weapon(drone)
        if weapon_type is None:
            return

        weapon = DRONE_WEAPONS.get(weapon_type, DRONE_WEAPONS['pulse_cannon'])

        # Randomized shot count within weapon's range
        shots_min = weapon.get('shots_min', 4)
        shots_max = weapon.get('shots_max', 6)
        num_shots = random.randint(shots_min, shots_max)

        # Initialize attack state for rapid fire
        drone['attack_weapon'] = weapon_type
        drone['shots_to_fire'] = num_shots
        drone['shots_fired'] = 0
        drone['last_shot_time'] = 0
        drone['hits_this_burst'] = 0

        # Store interval range for staggered timing (each shot gets random interval)
        drone['interval_min'] = weapon.get('interval_min', 80)
        drone['interval_max'] = weapon.get('interval_max', 120)
        drone['next_shot_interval'] = random.randint(drone['interval_min'], drone['interval_max'])

        # Calculate hit chance once for this burst (personality affects accuracy)
        accuracy_mult = drone['accuracy_mult']
        distance_factor = drone['distance'] / weapon['range']
        hit_chance = (weapon['accuracy'] * accuracy_mult) - (distance_factor * 0.2)
        altitude_diff = abs(drone['altitude_diff'])
        if altitude_diff > 20:
            altitude_penalty = min(0.3, altitude_diff / 150)
            hit_chance -= altitude_penalty
        drone['hit_chance'] = max(0.2, hit_chance)
        # Track hits for adaptation
        drone['hits_this_burst'] = 0

    def _update_attack_firing(self, drone: dict, damage_system, current_time: int):
        """Fire individual shots with sounds during attack state - staggered timing."""
        if self.state.game_over:
            return

        shots_to_fire = drone.get('shots_to_fire', 0)
        shots_fired = drone.get('shots_fired', 0)
        last_shot_time = drone.get('last_shot_time', 0)
        next_interval = drone.get('next_shot_interval', 80)

        # Check if we have more shots to fire and enough time has passed
        if shots_fired < shots_to_fire:
            if current_time - last_shot_time >= next_interval:
                # Fire a shot
                weapon_type = drone.get('attack_weapon', 'pulse_cannon')
                weapon = DRONE_WEAPONS.get(weapon_type, DRONE_WEAPONS['pulse_cannon'])

                # Play weapon sound with 3D positioning at drone's exact location
                dc = self._get_drone_channels(drone['id'])
                weapon_sound = self.sounds.get_drone_sound(weapon_type)
                if weapon_sound and dc:
                    pos = self._get_drone_3d_position(drone)
                    velocity = drone['velocity']
                    # Play with position and velocity for proper 3D + Doppler
                    dc['combat'].play(weapon_sound, position_3d=pos, velocity=velocity)
                    # Apply directional filters (lowpass for behind, etc.)
                    self._set_3d_position(dc['combat'], drone, 'combat')

                # Check if this shot hits
                hit_chance = drone.get('hit_chance', 0.5)
                if random.random() < hit_chance:
                    damage_system.apply_damage(weapon['damage'], current_time)
                    drone['hits_this_burst'] += 1

                    # Play hit sound
                    hit_sound = self.sounds.get_drone_sound('projectile_hit')
                    if hit_sound:
                        channel = self.audio.get_channel('player_damage')
                        channel.set_volume(BASE_VOLUMES.get('drone', 0.8) * self.audio.master_volume)
                        channel.play(hit_sound)

                drone['shots_fired'] = shots_fired + 1
                drone['last_shot_time'] = current_time

                # Generate new random interval for next shot (staggered timing)
                interval_min = drone.get('interval_min', 80)
                interval_max = drone.get('interval_max', 120)
                drone['next_shot_interval'] = random.randint(interval_min, interval_max)

                # Attack adaptation - check if drone should break off early
                new_shots_fired = drone['shots_fired']
                if new_shots_fired >= ATTACK_MIN_SHOTS_BEFORE_ADAPT:
                    hits = drone.get('hits_this_burst', 0)
                    hit_rate = hits / new_shots_fired if new_shots_fired > 0 else 0

                    # If hit rate is too low, drone gets frustrated
                    if hit_rate < ATTACK_FRUSTRATION_THRESHOLD:
                        drone['attack_frustrated'] = True
                        # Chance to break off attack early
                        if random.random() < ATTACK_BREAK_OFF_CHANCE:
                            # Force end of burst - return to cooldown early
                            drone['shots_to_fire'] = new_shots_fired  # Stop firing more
                            self._log_attack_results(drone, weapon_type)
                            return

                # Log the burst results after all shots fired
                if drone['shots_fired'] >= shots_to_fire:
                    self._log_attack_results(drone, weapon_type)

    def _log_attack_results(self, drone: dict, weapon_type: str):
        """Log attack results after burst completes and apply attack adaptation."""
        if self.state.game_over:
            return

        weapon = DRONE_WEAPONS.get(weapon_type, DRONE_WEAPONS['pulse_cannon'])
        shots_fired = drone.get('shots_fired', 0)
        hits = drone.get('hits_this_burst', 0)
        total_damage = hits * weapon['damage']
        distance_at_attack = drone['distance']

        if hits > 0:
            print(f"Drone {drone['id']} ({weapon['name']}) {hits}/{shots_fired} hits for {total_damage} damage")
        else:
            print(f"Drone {drone['id']} ({weapon['name']}) missed")

        # === CONTEXT-AWARE ATTACK ADAPTATION ===
        if ATTACK_ADAPTATION_ENABLED:
            hit_rate = hits / shots_fired if shots_fired > 0 else 0

            # Track weapon effectiveness
            if 'weapon_history' not in drone:
                drone['weapon_history'] = []

            drone['weapon_history'].append({
                'weapon': weapon_type,
                'hit_rate': hit_rate,
                'distance': distance_at_attack,
                'hits': hits,
                'shots': shots_fired
            })

            # Keep only last 5 attacks for learning
            if len(drone['weapon_history']) > 5:
                drone['weapon_history'] = drone['weapon_history'][-5:]

            # Learn optimal range from successful attacks
            successful_attacks = [a for a in drone['weapon_history'] if a['hit_rate'] >= 0.3]
            if successful_attacks:
                avg_good_range = sum(a['distance'] for a in successful_attacks) / len(successful_attacks)
                drone['preferred_range'] = avg_good_range

            # If hit rate is very low, consider switching weapons next time
            if hit_rate < ATTACK_WEAPON_SWITCH_THRESHOLD:
                # Mark that this weapon didn't work well at this range
                drone['_avoid_weapon'] = weapon_type
                drone['_avoid_distance'] = distance_at_attack

            # If hit rate is good, reinforce this weapon/range combo
            if hit_rate >= 0.4:
                drone['_effective_weapon'] = weapon_type
                drone['_effective_distance'] = distance_at_attack

        # Reset burst tracking
        drone['hits_this_burst'] = 0

    def _select_weapon(self, drone: dict) -> str:
        """Select weapon based on distance AND personality.

        Different personalities prefer different weapons and ranges.
        Also considers attack adaptation (learned optimal range).
        """
        distance = drone['distance']
        personality = drone['personality']

        # Check if attack adaptation has set a preferred range
        if ATTACK_ADAPTATION_ENABLED and drone.get('preferred_range'):
            pref_range = drone['preferred_range']
            # Adjust distance preference slightly toward learned optimal
            distance = distance * 0.7 + pref_range * 0.3

        # Get personality-specific weapon preferences
        prefs = PERSONALITY_WEAPON_PREFS.get(personality, PERSONALITY_WEAPON_PREFS['veteran'])

        # Find weapons valid for current distance
        valid_weapons = []
        for weapon, (min_range, max_range) in prefs.items():
            if min_range <= distance <= max_range:
                valid_weapons.append(weapon)

        if valid_weapons:
            # Wounded drones prefer faster weapons (panic)
            if drone['is_wounded'] and 'pulse_cannon' in valid_weapons:
                return 'pulse_cannon'

            # Personality-based selection from valid weapons
            if personality == 'berserker':
                # Prefer high damage weapons
                if 'rail_gun' in valid_weapons:
                    return 'rail_gun' if random.random() < 0.6 else random.choice(valid_weapons)
                if 'plasma_launcher' in valid_weapons:
                    return 'plasma_launcher' if random.random() < 0.7 else random.choice(valid_weapons)
            elif personality == 'ace':
                # Optimal selection based on exact range
                if distance <= 12 and 'pulse_cannon' in valid_weapons:
                    return 'pulse_cannon'
                elif distance <= 30 and 'plasma_launcher' in valid_weapons:
                    return 'plasma_launcher'
                elif 'rail_gun' in valid_weapons:
                    return 'rail_gun'
            elif personality == 'rookie':
                # Prefer close-range, safer weapons
                if 'pulse_cannon' in valid_weapons:
                    return 'pulse_cannon' if random.random() < 0.7 else random.choice(valid_weapons)

            return random.choice(valid_weapons)

        # Fallback: use old logic if no valid weapons found
        if distance <= 15:
            return random.choice(['pulse_cannon', 'pulse_cannon', 'plasma_launcher'])
        elif distance <= 25:
            return random.choice(['pulse_cannon', 'plasma_launcher', 'plasma_launcher'])
        elif distance <= 35:
            return random.choice(['plasma_launcher', 'plasma_launcher', 'rail_gun'])
        elif distance <= 45:
            return random.choice(['rail_gun', 'rail_gun', 'plasma_launcher'])

        return None

    def _update_aim_assist(self, current_time: int):
        """Update aiming assist beep with two tiers: direct lock and approximate facing."""
        # Use cached active drones list
        active_drones = self._get_active_drones_cached()
        if not active_drones:
            return

        for drone in active_drones:
            if drone['distance'] > 40:
                continue

            # Check for direct target lock (very tight angle)
            if abs(drone['relative_angle']) <= TARGET_LOCK_ANGLE:
                if current_time - self.state.last_target_lock_beep >= TARGET_LOCK_COOLDOWN:
                    channel = self.audio.get_channel('player_damage')
                    channel.set_volume(0.5 * self.audio.master_volume)
                    channel.play('target_lock')
                    self.state.last_target_lock_beep = current_time
                    self.state.last_aim_assist_beep = current_time  # Also reset aim assist
                break

            # Check for approximate facing (wider angle)
            elif abs(drone['relative_angle']) <= 45:
                if current_time - self.state.last_aim_assist_beep >= AIM_ASSIST_COOLDOWN:
                    sound = self.sounds.get_drone_sound('beacons', 0)
                    if sound:
                        channel = self.audio.get_channel('player_damage')
                        channel.set_volume(0.3 * self.audio.master_volume)
                        channel.play(sound)
                    self.state.last_aim_assist_beep = current_time
                break

    def damage_drone(self, drone: dict, damage: float) -> bool:
        """Apply damage to a drone with hit confirmation audio feedback.

        Hit confirmation varies based on damage dealt and remaining health:
        - Light hit: Standard interface beep
        - Heavy hit (25+ damage): Higher-pitched confirmation
        - Critical hit (50+ damage): More urgent sound
        - Kill: Distinct destruction confirmation

        Args:
            drone: Drone dict
            damage: Damage amount

        Returns:
            True if drone was destroyed
        """
        old_health = drone['health']
        drone['health'] -= damage

        # Determine hit confirmation tier based on damage and remaining health
        health_percent = max(0, drone['health'] / 100.0)
        is_kill = drone['health'] <= 0

        # Get hit confirmation constants
        try:
            from state.constants import HIT_CONFIRM_DAMAGE_THRESHOLDS, HIT_CONFIRM_KILL_SOUND
        except ImportError:
            HIT_CONFIRM_DAMAGE_THRESHOLDS = [25, 50, 75]
            HIT_CONFIRM_KILL_SOUND = True

        # Select sound and volume based on hit tier
        channel = self.audio.get_channel('player_damage')
        alog = _get_audio_log()

        if is_kill and HIT_CONFIRM_KILL_SOUND:
            # Kill confirmation - use explosion/interface combination
            # Play the destruction sound first for dramatic effect
            alog.hit_confirm(drone['id'], damage, 0, 0.8, is_kill=True)
            self._destroy_drone(drone)
            # Additional kill confirmation sound
            sound = self.sounds.get_drone_sound('interfaces')
            if sound:
                channel.set_volume(0.8 * self.audio.master_volume)
                channel.play(sound)
            return True
        elif damage >= HIT_CONFIRM_DAMAGE_THRESHOLDS[2]:
            # Massive hit (75+ damage) - loudest confirmation
            vol = 0.9
            alog.hit_confirm(drone['id'], damage, drone['health'], vol)
            sound = self.sounds.get_drone_sound('interfaces')
            if sound:
                channel.set_volume(vol * self.audio.master_volume)
                channel.play(sound)
        elif damage >= HIT_CONFIRM_DAMAGE_THRESHOLDS[1]:
            # Critical hit (50+ damage) - loud confirmation
            vol = 0.75
            alog.hit_confirm(drone['id'], damage, drone['health'], vol)
            sound = self.sounds.get_drone_sound('interfaces')
            if sound:
                channel.set_volume(vol * self.audio.master_volume)
                channel.play(sound)
        elif damage >= HIT_CONFIRM_DAMAGE_THRESHOLDS[0]:
            # Heavy hit (25+ damage) - moderate confirmation
            vol = 0.6
            alog.hit_confirm(drone['id'], damage, drone['health'], vol)
            sound = self.sounds.get_drone_sound('interfaces')
            if sound:
                channel.set_volume(vol * self.audio.master_volume)
                channel.play(sound)
        else:
            # Light hit - standard feedback
            vol = 0.4
            alog.hit_confirm(drone['id'], damage, drone['health'], vol)
            sound = self.sounds.get_drone_sound('interfaces')
            if sound:
                channel.set_volume(vol * self.audio.master_volume)
                channel.play(sound)

        # Announce critical damage thresholds
        if drone['health'] > 0:
            if old_health > 50 and drone['health'] <= 50:
                # Drone half health
                pass  # Could add TTS: "Hostile damaged"
            elif old_health > 25 and drone['health'] <= 25:
                self.tts.speak("Hostile critical", duck_audio=False)

            # === DISTRESS BEACON SYSTEM ===
            if DISTRESS_BEACON_ENABLED:
                # Trigger distress on high damage hit or low health
                health_percent = (drone['health'] / 100.0) * 100
                if (damage >= DISTRESS_DAMAGE_THRESHOLD or
                    health_percent <= DISTRESS_HEALTH_THRESHOLD):
                    if not drone['distress_active']:
                        drone['distress_active'] = True
                        drone['distress_start_time'] = self._get_current_time()
                        self._activate_distress_beacon(drone)

            # === SUPPRESSION TRIGGER ===
            if SUPPRESSION_ENABLED:
                current_time = self._get_current_time()
                # Track recent damage for suppression calculation
                if current_time - drone['damage_window_start'] > SUPPRESSION_TIME_WINDOW:
                    # Reset damage window
                    drone['damage_window_start'] = current_time
                    drone['recent_damage'] = 0

                drone['recent_damage'] += damage

                # Check if suppressed (enough damage in time window)
                if (drone['recent_damage'] >= SUPPRESSION_DAMAGE_THRESHOLD and
                    not drone['is_suppressed'] and
                    current_time >= drone['suppression_cooldown_end']):
                    drone['is_suppressed'] = True
                    suppression_duration = random.randint(SUPPRESSION_DURATION_MIN, SUPPRESSION_DURATION_MAX)
                    drone['suppression_end_time'] = current_time + suppression_duration
                    self.tts.speak("Drone suppressed")

        return False

    def _get_current_time(self) -> int:
        """Get current time in milliseconds (for internal use)."""
        import pygame
        return pygame.time.get_ticks()

    def _activate_distress_beacon(self, drone: dict):
        """Activate distress beacon - alert nearby drones."""
        # Play distress sound from the damaged drone
        sound = self.sounds.get_drone_sound('beacons')
        if sound:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                pos = self._get_drone_3d_position(drone)
                dc['combat'].play(sound, position_3d=pos)

        # Alert nearby patrol/searching drones
        for other in self.drones:
            if other['id'] == drone['id']:
                continue
            if other['state'] not in ('patrol', 'searching'):
                continue
            if other['distance'] > DISTRESS_ALERT_RANGE:
                continue

            # Drone responds to distress call
            other['state'] = 'detecting'
            other['state_start'] = self._get_current_time()
            other['last_known_x'] = drone['x']
            other['last_known_y'] = drone['y']
            # Speed boost when responding to distress
            other['speed'] *= DISTRESS_RESPONSE_SPEED_MULT

    def _destroy_drone(self, drone: dict):
        """Handle drone destruction with 3D audio positioning."""
        drone['state'] = 'destroyed'

        dc = self._get_drone_channels(drone['id'])
        pos = self._get_drone_3d_position(drone)

        # Stop ambient sounds immediately
        if dc and 'ambient' in dc:
            dc['ambient'].stop()

        # Play explosion - use 'debris' channel if available (4-channel pool)
        # else fall back to 'combat' channel (2-channel legacy)
        explosion = self.sounds.get_drone_sound('explosions')
        if explosion and dc:
            explosion_channel = dc.get('debris', dc.get('combat'))
            if explosion_channel:
                explosion_channel.play(explosion, position_3d=pos)
                self._set_3d_position(explosion_channel, drone, 'explosion')

        # Play debris sound - use 'weapon' channel if available (4-channel pool)
        # else fall back to 'ambient' channel (2-channel legacy)
        debris = self.sounds.get_drone_sound('debris')
        if debris and dc:
            debris_channel = dc.get('weapon', dc.get('ambient'))
            if debris_channel:
                debris_channel.play(debris, position_3d=pos)
                self._set_3d_position(debris_channel, drone, 'debris')

        self.tts.speak("Hostile destroyed")
        print(f"Drone {drone['id']} destroyed!")

    def _get_active_drones_cached(self) -> list:
        """Get cached list of active (non-destroyed) drones.

        OPTIMIZATION: Only rebuilds the list once per frame when dirty flag is set.
        """
        if self._active_drones_dirty:
            self._cached_active_drones = [d for d in self.drones if d['state'] != 'destroyed']
            self._active_drones_dirty = False
        return self._cached_active_drones

    def get_active_drones(self) -> list:
        """Get list of active (non-destroyed) drones.

        Returns cached list if available (within same frame).
        """
        return self._get_active_drones_cached()

    def get_closest_drone_distance(self) -> float:
        """Get distance to closest active drone."""
        active = self._get_active_drones_cached()
        if not active:
            return 999
        return min(d['distance'] for d in active)

    def get_drones_in_range(self, range_m: float, arc: float = None) -> list:
        """Get drones within range and optional arc.

        Args:
            range_m: Range in meters
            arc: Optional arc in degrees (±arc from facing)

        Returns:
            List of drones within range/arc
        """
        result = []
        for drone in self._get_active_drones_cached():
            if drone['distance'] <= range_m:
                if arc is None or abs(drone['relative_angle']) <= arc:
                    result.append(drone)
        return result

    def clear_all(self):
        """Clear all drones and stop their sounds."""
        # Use pool if available, else fallback to audio manager
        if self._drone_pool:
            for drone in self.drones:
                self._drone_pool.deactivate_drone(drone['id'])
        else:
            for dc_idx in range(self.max_drones):
                dc = self.audio.get_drone_channels(dc_idx)
                if dc:
                    dc['ambient'].stop()
                    dc['combat'].stop()
        self.drones.clear()
