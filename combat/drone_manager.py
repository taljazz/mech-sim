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
    TARGET_LOCK_ANGLE, TARGET_LOCK_COOLDOWN
)
from audio.spatial import SpatialAudio


class DroneManager:
    """Manages all drone entities and their behavior."""

    # Panning update threshold (radians) - only update if angle changed significantly
    PAN_UPDATE_THRESHOLD = 0.05  # ~3 degrees

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

        # Mark active drones cache as dirty at start of frame
        self._active_drones_dirty = True

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
        spawn_x = self.state.player_x + spawn_distance * math.sin(angle_rad)
        spawn_y = self.state.player_y + spawn_distance * math.cos(angle_rad)

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
            'speed': 5.0 + random.uniform(-1, 1),
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
            'velocity': (0.0, 0.0, 0.0)  # (vx, vy, vz) in meters/second
        }

        self.drones.append(drone)

        # Activate in pool if available
        if self._drone_pool:
            self._drone_pool.activate_drone(drone['id'])

        # Calculate initial spatial audio for the new drone
        self._update_spatial_audio(drone)

        # Play spawn sound using 3D positioning (position set before playing)
        dc = self._get_drone_channels(drone['id'])
        if dc:
            sound = self.sounds.get_drone_sound('takeoffs')
            if sound:
                pos = self._get_drone_3d_position(drone)
                dc['ambient'].play(sound, position_3d=pos)
                self._set_3d_position(dc['ambient'], drone)  # Apply directional filter

        self.tts.speak("Hostile detected")
        print(f"Drone {drone['id']} spawned at ({spawn_x:.1f}, {spawn_y:.1f})")
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
            source_altitude=drone.get('altitude', 50),
            listener_x=self.state.player_x,
            listener_y=self.state.player_y,
            listener_altitude=self.state.player_altitude,
            listener_facing=self.state.facing_angle
        )

        # Cache ALL spatial values including pan/vol for reuse this frame
        drone['pan'] = pan
        drone['vol'] = vol
        drone['distance'] = distance
        drone['relative_angle'] = rel_angle
        drone['altitude_diff'] = alt_diff

        # Calculate velocity for Doppler effect (meters per second)
        if dt > 0.001:  # Avoid division by zero
            prev_x = drone.get('prev_x', drone['x'])
            prev_y = drone.get('prev_y', drone['y'])
            prev_alt = drone.get('prev_altitude', drone.get('altitude', 50))

            # Calculate velocity components
            vx = (drone['x'] - prev_x) / dt
            vy = (drone['y'] - prev_y) / dt
            vz = (drone.get('altitude', 50) - prev_alt) / dt / 3.28  # Convert ft to m

            drone['velocity'] = (vx, vy, vz)

            # Store current position for next frame
            drone['prev_x'] = drone['x']
            drone['prev_y'] = drone['y']
            drone['prev_altitude'] = drone.get('altitude', 50)

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

    def _get_drone_3d_position(self, drone: dict):
        """Get 3D position tuple for a drone (for passing to play()).

        Returns:
            Tuple of (x, y, altitude_meters) in game coordinates
        """
        drone_altitude = drone.get('altitude', 50)
        altitude_meters = drone_altitude / 3.28
        return (drone['x'], drone['y'], altitude_meters)

    def _set_3d_position(self, channel, drone: dict):
        """Set 3D position and directional filters for a channel based on drone location.

        Uses FMOD's native 3D spatialization plus directional filtering for
        front/behind and above/below perception. Also sets velocity for Doppler effect.
        """
        if channel and hasattr(channel, 'set_3d_position'):
            # Convert altitude from feet to meters for audio positioning
            drone_altitude = drone.get('altitude', 50)
            altitude_meters = drone_altitude / 3.28

            # Get velocity for Doppler effect (default to zero if not calculated yet)
            velocity = drone.get('velocity', (0.0, 0.0, 0.0))

            # Set 3D position with velocity for Doppler
            channel.set_3d_position(drone['x'], drone['y'], altitude_meters, velocity=velocity)

            # Calculate and apply enhanced directional filter
            # (includes air absorption and occlusion simulation)
            relative_angle, altitude_diff, distance = self.audio.calculate_directional_params(
                drone['x'], drone['y'], drone_altitude,
                self.state.player_x, self.state.player_y, self.state.player_altitude,
                self.state.facing_angle
            )
            self.audio.apply_directional_filter(
                channel, relative_angle, altitude_diff, distance,
                apply_air_absorption=True, apply_occlusion=True
            )

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

        state = drone['state']

        if state == 'spawning':
            if current_time - drone['state_start'] >= 2000:
                drone['state'] = 'patrol'
                drone['patrol_target'] = self._generate_patrol_point()
                drone['state_start'] = current_time

        elif state == 'patrol':
            reached = self._move_drone_toward(drone, drone['patrol_target'], dt)
            if reached:
                drone['patrol_target'] = self._generate_patrol_point()

            if drone['distance'] <= detect_range:
                drone['state'] = 'detecting'
                drone['state_start'] = current_time
                drone['last_known_x'] = self.state.player_x
                drone['last_known_y'] = self.state.player_y
                self._play_detection_sound(drone)

        elif state == 'detecting':
            drone['last_known_x'] = self.state.player_x
            drone['last_known_y'] = self.state.player_y
            if current_time - drone['state_start'] >= 1500:
                drone['state'] = 'engaging'
                drone['state_start'] = current_time
                self.tts.speak("Drone engaging")

        elif state == 'engaging':
            # Aggressive pursuit with evasion and flanking
            self._move_engaging(drone, dt)

            # Adjust altitude
            self._adjust_altitude(drone, self.state.player_altitude, dt)

            drone['last_known_x'] = self.state.player_x
            drone['last_known_y'] = self.state.player_y

            if drone['distance'] > lose_track_range:
                drone['state'] = 'searching'
                drone['state_start'] = current_time
                self.tts.speak("Drone lost contact")
                self._play_scan_sound(drone)
            elif drone['distance'] <= DRONE_ATTACK_RANGE:
                drone['state'] = 'attacking'
                drone['state_start'] = current_time
                self._execute_attack(drone, damage_system, current_time)

        elif state == 'searching':
            target = (drone.get('last_known_x', self.state.player_x),
                      drone.get('last_known_y', self.state.player_y))
            reached = self._move_drone_toward(drone, target, dt)

            if drone['distance'] <= reacquire_range:
                drone['state'] = 'detecting'
                drone['state_start'] = current_time
                drone['last_known_x'] = self.state.player_x
                drone['last_known_y'] = self.state.player_y
                self.tts.speak("Drone reacquired")
                self._play_detection_sound(drone)
            elif reached or (current_time - drone['state_start'] >= 8000):
                drone['state'] = 'patrol'
                drone['patrol_target'] = self._generate_patrol_point()
                drone['state_start'] = current_time

        elif state == 'attacking':
            from state.constants import DRONE_ATTACK_STATE_DURATION, DRONE_COOLDOWN_MIN, DRONE_COOLDOWN_MAX
            # Fire shots continuously during attack state
            self._update_attack_firing(drone, damage_system, current_time)
            if current_time - drone['state_start'] >= DRONE_ATTACK_STATE_DURATION:
                drone['state'] = 'cooldown'
                drone['state_start'] = current_time
                # Set randomized cooldown duration for this burst
                drone['cooldown_duration'] = random.randint(DRONE_COOLDOWN_MIN, DRONE_COOLDOWN_MAX)
                # Clear attack state
                drone['shots_fired'] = 0
                drone['last_shot_time'] = 0

        elif state == 'cooldown':
            cooldown_duration = drone.get('cooldown_duration', 300)
            if current_time - drone['state_start'] >= cooldown_duration:
                if drone['distance'] <= lose_track_range:
                    drone['state'] = 'engaging'
                    drone['last_known_x'] = self.state.player_x
                    drone['last_known_y'] = self.state.player_y
                else:
                    drone['state'] = 'searching'
                drone['state_start'] = current_time

    def _move_engaging(self, drone: dict, dt: float):
        """Move drone during engaging state with evasion and flanking.

        Implements:
        - Evasive maneuvers when player is aiming at drone
        - Flanking behavior when multiple drones are active
        - Aggressive pursuit speed
        """
        from state.constants import (
            DRONE_ENGAGE_SPEED_MULT, DRONE_EVASION_SPEED, DRONE_EVASION_ANGLE
        )

        player_x = self.state.player_x
        player_y = self.state.player_y

        # Check if player is aiming at this drone
        being_aimed_at = abs(drone['relative_angle']) < DRONE_EVASION_ANGLE

        # Get other engaging drones for flanking coordination
        other_engaging = [d for d in self.drones
                         if d['id'] != drone['id'] and d['state'] == 'engaging']

        dx = player_x - drone['x']
        dy = player_y - drone['y']
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.5:
            return

        if being_aimed_at and dist > 5:
            # Evasive maneuver - strafe perpendicular to player
            perp_x = -dy / dist
            perp_y = dx / dist

            # Initialize evasion state if needed
            if 'evasion_direction' not in drone:
                drone['evasion_direction'] = random.choice([-1, 1])
                drone['evasion_timer'] = 0

            # Evasion movement
            evasion_dist = DRONE_EVASION_SPEED * dt * drone['evasion_direction']
            drone['x'] += perp_x * evasion_dist
            drone['y'] += perp_y * evasion_dist

            # Update evasion timer and occasionally change direction
            drone['evasion_timer'] = drone.get('evasion_timer', 0) + dt
            if drone['evasion_timer'] > 0.5:
                drone['evasion_timer'] = 0
                drone['evasion_direction'] *= -1

            # Still approach player but slower
            toward_dist = drone['speed'] * DRONE_ENGAGE_SPEED_MULT * 0.5 * dt
            drone['x'] += (dx / dist) * toward_dist
            drone['y'] += (dy / dist) * toward_dist

        elif other_engaging:
            # Flanking - position on opposite side from other drone
            other = other_engaging[0]
            other_angle = math.degrees(math.atan2(other['x'] - player_x, other['y'] - player_y))
            flank_angle = (other_angle + 180) % 360

            # Target position for flanking
            flank_distance = 20
            angle_rad = math.radians(flank_angle)
            target_x = player_x + flank_distance * math.sin(angle_rad)
            target_y = player_y + flank_distance * math.cos(angle_rad)

            # Move toward flank position with aggressive speed
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
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.5:
            return True

        move_dist = drone['speed'] * dt
        if move_dist > dist:
            move_dist = dist

        drone['x'] += (dx / dist) * move_dist
        drone['y'] += (dy / dist) * move_dist
        return False

    def _adjust_altitude(self, drone: dict, target_alt: float, dt: float):
        """Adjust drone altitude."""
        alt_diff = drone.get('altitude_diff', 0)
        climb_rate = drone.get('climb_rate', 15.0)
        if alt_diff > 5:
            drone['altitude'] = max(0, drone['altitude'] - climb_rate * dt)
        elif alt_diff < -5:
            from state.constants import ALTITUDE_MAX
            drone['altitude'] = min(ALTITUDE_MAX, drone['altitude'] + climb_rate * dt)

    def _generate_patrol_point(self) -> tuple:
        """Generate a patrol waypoint around player."""
        patrol_distance = random.uniform(25, 35)
        patrol_angle = random.uniform(0, 360)
        angle_rad = math.radians(patrol_angle)
        return (
            self.state.player_x + patrol_distance * math.sin(angle_rad),
            self.state.player_y + patrol_distance * math.cos(angle_rad)
        )

    def _play_detection_sound(self, drone: dict):
        """Play drone detection beacon sound with 3D positioning."""
        sound = self.sounds.get_drone_sound('beacons')
        if sound:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                pos = self._get_drone_3d_position(drone)
                dc['combat'].play(sound, position_3d=pos)
                self._set_3d_position(dc['combat'], drone)  # Apply directional filter

    def _play_scan_sound(self, drone: dict):
        """Play drone scanning sound with 3D positioning."""
        sound = self.sounds.get_drone_sound('scans')
        if sound:
            dc = self._get_drone_channels(drone['id'])
            if dc:
                pos = self._get_drone_3d_position(drone)
                dc['combat'].play(sound, position_3d=pos)
                self._set_3d_position(dc['combat'], drone)  # Apply directional filter

    def _update_ambient_audio(self, drone: dict, current_time: int):
        """Update drone ambient/movement audio with 3D positioning."""
        if drone['state'] not in ('patrol', 'engaging', 'cooldown'):
            return

        dc = self._get_drone_channels(drone['id'])
        if not dc:
            return

        if not dc['ambient'].get_busy():
            if drone['state'] == 'engaging':
                sound = self.sounds.get_drone_sound('supersonics')
            else:
                sound = self.sounds.get_drone_sound('passbys')

            if sound:
                # Play sound with 3D position set before playing (for proper distance attenuation)
                pos = self._get_drone_3d_position(drone)
                dc['ambient'].play(sound, position_3d=pos)
                self._set_3d_position(dc['ambient'], drone)  # Apply directional filter
        else:
            # Update 3D position continuously for moving drone
            self._set_3d_position(dc['ambient'], drone)

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

        # Calculate hit chance once for this burst
        distance_factor = drone['distance'] / weapon['range']
        hit_chance = weapon['accuracy'] - (distance_factor * 0.2)
        altitude_diff = abs(drone.get('altitude_diff', 0))
        if altitude_diff > 20:
            altitude_penalty = min(0.3, altitude_diff / 150)
            hit_chance -= altitude_penalty
        drone['hit_chance'] = max(0.2, hit_chance)

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

                # Play weapon sound with 3D positioning (position set before playing)
                dc = self._get_drone_channels(drone['id'])
                weapon_sound = self.sounds.get_drone_sound(weapon_type)
                if weapon_sound and dc:
                    pos = self._get_drone_3d_position(drone)
                    dc['combat'].play(weapon_sound, position_3d=pos)
                    self._set_3d_position(dc['combat'], drone)  # Apply directional filter

                # Check if this shot hits
                hit_chance = drone.get('hit_chance', 0.5)
                if random.random() < hit_chance:
                    damage_system.apply_damage(weapon['damage'], current_time)
                    drone['hits_this_burst'] = drone.get('hits_this_burst', 0) + 1

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

                # Log the burst results after all shots fired
                if drone['shots_fired'] >= shots_to_fire:
                    self._log_attack_results(drone, weapon_type)

    def _log_attack_results(self, drone: dict, weapon_type: str):
        """Log attack results after burst completes."""
        if self.state.game_over:
            return

        weapon = DRONE_WEAPONS.get(weapon_type, DRONE_WEAPONS['pulse_cannon'])
        shots_fired = drone.get('shots_fired', 0)
        hits = drone.get('hits_this_burst', 0)
        total_damage = hits * weapon['damage']

        if hits > 0:
            print(f"Drone {drone['id']} ({weapon['name']}) {hits}/{shots_fired} hits for {total_damage} damage")
        else:
            print(f"Drone {drone['id']} ({weapon['name']}) missed")

        # Reset burst tracking
        drone['hits_this_burst'] = 0

    def _select_weapon(self, drone: dict) -> str:
        """Select weapon based on distance with some randomization.

        Drones can use multiple weapon types at various ranges for variety.
        """
        distance = drone['distance']

        # Close range (0-15): Pulse cannon preferred, plasma possible
        if distance <= 15:
            return random.choice(['pulse_cannon', 'pulse_cannon', 'plasma_launcher'])

        # Medium range (15-25): Both pulse and plasma equally likely
        elif distance <= 25:
            return random.choice(['pulse_cannon', 'plasma_launcher', 'plasma_launcher'])

        # Medium-long range (25-35): Plasma preferred, rail gun possible
        elif distance <= 35:
            return random.choice(['plasma_launcher', 'plasma_launcher', 'rail_gun'])

        # Long range (35-45): Rail gun preferred, plasma possible
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
        """Apply damage to a drone.

        Args:
            drone: Drone dict
            damage: Damage amount

        Returns:
            True if drone was destroyed
        """
        drone['health'] -= damage

        # Play hit feedback
        sound = self.sounds.get_drone_sound('interfaces')
        if sound:
            channel = self.audio.get_channel('player_damage')
            channel.set_volume(0.5 * self.audio.master_volume)
            channel.play(sound)

        if drone['health'] <= 0:
            self._destroy_drone(drone)
            return True
        return False

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
                self._set_3d_position(explosion_channel, drone)

        # Play debris sound - use 'weapon' channel if available (4-channel pool)
        # else fall back to 'ambient' channel (2-channel legacy)
        debris = self.sounds.get_drone_sound('debris')
        if debris and dc:
            debris_channel = dc.get('weapon', dc.get('ambient'))
            if debris_channel:
                debris_channel.play(debris, position_3d=pos)
                self._set_3d_position(debris_channel, drone)

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
