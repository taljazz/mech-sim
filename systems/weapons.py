"""
Weapon System for MechSimulator.

Handles all player weapons: Chaingun, Missiles, Blaster, Shield, EMP.
"""

import random

from state.constants import (
    WEAPON_CHAINGUN, WEAPON_MISSILES, WEAPON_BLASTER, WEAPON_EMP,
    WEAPON_NAMES, CHAINGUN_VARIANT_NAMES, CHAINGUN_STANDARD, CHAINGUN_MINIGUN,
    AMMO_MAX, AMMO_FABRICATION_GAINS, LOW_AMMO_THRESHOLDS,
    CHAINGUN_CONSUMPTION_RATE, CHAINGUN_HIT_CHANCE, CHAINGUN_DAMAGE,
    CHAINGUN_RANGE, CHAINGUN_ARC,
    MISSILE_LOCK_MIN, MISSILE_LOCK_MAX, MISSILE_WARM_DURATION,
    MISSILE_BEEP_START_INTERVAL, MISSILE_BEEP_END_INTERVAL,
    MISSILE_DAMAGE, MISSILE_RANGE, MISSILE_COUNT,
    BLASTER_COOLDOWN, BLASTER_DAMAGE, BLASTER_RANGE, BLASTER_ARC,
    EMP_COOLDOWN, EMP_DAMAGE, EMP_RANGE,
    FABRICATION_DURATION, FABRICATION_COST,
    # Camo reveal durations
    CAMO_REVEAL_CHAINGUN, CAMO_REVEAL_BLASTER, CAMO_REVEAL_MISSILES, CAMO_REVEAL_EMP,
    CAMO_AMBUSH_ENABLED, CAMO_AMBUSH_DAMAGE_MULT
)


class WeaponSystem:
    """Manages all player weapons and fabrication."""

    def __init__(self, audio_manager, sound_loader, tts, game_state, drone_manager, shield_system, camo_system=None):
        """Initialize the weapon system.

        Args:
            audio_manager: AudioManager instance
            sound_loader: SoundLoader instance
            tts: TTSManager instance
            game_state: GameState instance
            drone_manager: DroneManager instance
            shield_system: ShieldSystem instance
            camo_system: CamouflageSystem instance (optional)
        """
        self.audio = audio_manager
        self.sounds = sound_loader
        self.tts = tts
        self.camo = camo_system
        self.state = game_state
        self.drones = drone_manager
        self.shield = shield_system

        self._missile_channel = audio_manager.get_channel('missiles')
        self._blaster_channel = audio_manager.get_channel('blaster')
        self._emp_channel = audio_manager.get_channel('emp')
        self._fab_channel = audio_manager.get_channel('fabrication')

    def _get_ambush_damage(self, base_damage: int) -> int:
        """Calculate damage with ambush bonus if applicable.

        If camo is active and ambush is ready, applies damage multiplier
        and consumes the ambush bonus.

        Args:
            base_damage: Base weapon damage

        Returns:
            Damage to deal (base or boosted)
        """
        if CAMO_AMBUSH_ENABLED and self.state.camo_ambush_ready and self.state.camo_active:
            # Consume ambush bonus
            self.state.camo_ambush_ready = False
            boosted_damage = int(base_damage * CAMO_AMBUSH_DAMAGE_MULT)
            self.tts.speak("Ambush!")
            print(f"Camo: Ambush bonus! {base_damage} -> {boosted_damage} damage")
            return boosted_damage
        return base_damage

    def switch_weapon(self, weapon_num: int):
        """Switch to a different weapon.

        Args:
            weapon_num: Weapon ID (1-5)
        """
        if weapon_num == self.state.current_weapon:
            # Cycle chaingun variant if already equipped
            if weapon_num == WEAPON_CHAINGUN:
                self.state.chaingun_variant = (self.state.chaingun_variant + 1) % 2
                variant_name = self._get_chaingun_name()
                self.tts.speak(variant_name)
                print(f"Chaingun variant: {variant_name}")
            return

        # Duck audio for clarity
        self.audio.start_ducking(groups_to_duck=['ambience', 'drones'], duck_volume=0.5, speed=8.0)

        # Stop current weapon
        self._stop_current_weapon()

        # Play extend sound for new weapon
        self.state.current_weapon = weapon_num
        self.state.weapon_state = 'equipping'

        extend_sounds = {
            WEAPON_CHAINGUN: 'chaingun_extend',
            WEAPON_MISSILES: 'weapon1_extend',
            WEAPON_BLASTER: 'weapon2_extend',
            WEAPON_EMP: 'weapon2_extend'
        }

        channel = self.audio.play_sound(extend_sounds[weapon_num], 'weapons')
        self.audio.set_channel('weapon_equip', channel)

        if weapon_num == WEAPON_CHAINGUN:
            self.state.chaingun_state = 'extending'

        weapon_name = self._get_weapon_name(weapon_num)
        self.tts.speak(weapon_name)
        print(f"Switching to: {weapon_name}")

    def _stop_current_weapon(self):
        """Stop any active weapon before switching."""
        if self.state.current_weapon == WEAPON_CHAINGUN:
            if self.state.chaingun_state in ('starting', 'spinning'):
                self.audio.stop_channel('chaingun')
                self.state.chaingun_state = 'idle'
        elif self.state.current_weapon == WEAPON_MISSILES:
            if self.state.missile_state in ('initializing', 'locking', 'locked', 'init_ending'):
                self.audio.stop_channel('missiles')
                self.state.missile_state = 'ready'

    def update(self, keys, current_time: int, dt: float, reveal_callback=None):
        """Update weapon systems.

        Args:
            keys: Pygame key state
            current_time: Current game time in milliseconds
            dt: Delta time in seconds
            reveal_callback: Callback for revealing camo'd player
        """
        import pygame

        ctrl = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
        ctrl_pressed = ctrl and not self.state.prev_ctrl
        ctrl_released = not ctrl and self.state.prev_ctrl

        # Only fire if weapon is ready
        if self.state.weapon_state == 'ready':
            if self.state.current_weapon == WEAPON_CHAINGUN:
                self._update_chaingun(ctrl, ctrl_pressed, ctrl_released, current_time, dt, reveal_callback)
            elif self.state.current_weapon == WEAPON_MISSILES:
                self._update_missiles(ctrl, ctrl_pressed, ctrl_released, current_time, reveal_callback)
            elif self.state.current_weapon == WEAPON_BLASTER:
                self._update_blaster(ctrl, current_time, reveal_callback)
            elif self.state.current_weapon == WEAPON_EMP:
                self._update_emp(ctrl_pressed, current_time, reveal_callback)

        self.state.prev_ctrl = ctrl

        # Low ammo warnings
        self._check_low_ammo()

        # Fabrication completion
        self._check_fabrication(current_time)

    def _update_chaingun(self, ctrl, ctrl_pressed, ctrl_released, current_time, dt, reveal_callback):
        """Update chaingun state."""
        gun_start, gun_loop, gun_tail = self._get_chaingun_sounds()
        gun_name = self._get_chaingun_name()

        if ctrl_pressed:
            if self.state.chaingun_state == 'ready' and self.state.ammo[WEAPON_CHAINGUN] > 0:
                channel = self.audio.play_sound(gun_start, 'weapons')
                self.audio.set_channel('chaingun', channel)
                self.state.chaingun_state = 'starting'
                self.tts.speak(f"{gun_name} spinning up")
                print(f"{gun_name}: Starting")
                # Use weapon-specific reveal duration
                if self.camo:
                    self.camo.reveal(current_time, CAMO_REVEAL_CHAINGUN, self.drones)
            elif self.state.ammo[WEAPON_CHAINGUN] <= 0:
                self.tts.speak(f"{gun_name} out of ammo")
                print(f"{gun_name}: No ammo!")

        elif ctrl_released:
            if self.state.chaingun_state in ('starting', 'spinning'):
                self.audio.stop_channel('chaingun')
                channel = self.audio.play_sound(gun_tail, 'weapons')
                self.audio.set_channel('chaingun', channel)
                self.state.chaingun_state = 'stopping'
                self.tts.speak(f"{gun_name} spinning down")
                print(f"{gun_name}: Tailing")

        # While spinning, consume ammo and damage drones
        if self.state.chaingun_state == 'spinning' and not self.state.is_malfunctioning('weapons'):
            ammo_consumed = CHAINGUN_CONSUMPTION_RATE * dt
            self.state.ammo[WEAPON_CHAINGUN] = max(0, self.state.ammo[WEAPON_CHAINGUN] - ammo_consumed)

            # Trigger drone sound reactions (throttled to every 500ms, not every frame)
            if current_time - getattr(self, '_last_chaingun_reaction', 0) >= 500:
                self._last_chaingun_reaction = current_time
                self.drones.react_to_player_fire(current_time)

            # Hit drones in arc
            if random.random() < CHAINGUN_HIT_CHANCE:
                targets = self.drones.get_drones_in_range(CHAINGUN_RANGE, CHAINGUN_ARC)
                if targets:
                    target = min(targets, key=lambda d: d['distance'])
                    damage = self._get_ambush_damage(CHAINGUN_DAMAGE)
                    self.drones.damage_drone(target, damage)
                    print(f"{gun_name}: Hit!")

            if self.state.ammo[WEAPON_CHAINGUN] <= 0:
                self.audio.stop_channel('chaingun')
                channel = self.audio.play_sound(gun_tail, 'weapons')
                self.audio.set_channel('chaingun', channel)
                self.state.chaingun_state = 'stopping'
                self.tts.speak(f"{gun_name} out of ammo")
                print(f"{gun_name}: Out of ammo!")

    def _update_missiles(self, ctrl, ctrl_pressed, ctrl_released, current_time, reveal_callback):
        """Update missile system state.

        Optimized state machine:
        - ready → initializing (or skip to locking if warm)
        - initializing → locking (when init sound ends)
        - locking → locked (distance-based timing with beep feedback)
        - locked → launching → ready
        """
        if ctrl_pressed and self.state.missile_state == 'ready':
            if self.state.ammo[WEAPON_MISSILES] < MISSILE_COUNT:
                self.tts.speak("Insufficient missiles")
                print("Missiles: Not enough ammo!")
                return

            # Check if missiles are "warm" (recently fired)
            is_warm = (current_time - self.state.missile_last_fire) < MISSILE_WARM_DURATION

            if is_warm:
                # Skip initialization, go straight to locking
                self._start_missile_lock(current_time)
                self.tts.speak("Missiles warm, locking")
                print("Missiles: Warm - skipping init, locking")
            else:
                # Cold start - need initialization
                self._missile_channel.play('missile_init_start')
                self.state.missile_state = 'initializing'
                self.tts.speak("Initializing missiles")
                print("Missiles: Initializing")

        elif ctrl and self.state.missile_state == 'locking':
            # Update lock progress with beeping feedback
            self._update_missile_lock(current_time)

        elif ctrl_released:
            if self.state.missile_state == 'locked' and not self.state.is_malfunctioning('weapons'):
                self._fire_missiles(current_time, reveal_callback)

            elif self.state.missile_state == 'locking':
                # Cancelled during lock
                self.audio.stop_channel('missiles')
                self._missile_channel.play('missile_init_end')
                self.state.missile_state = 'init_ending'
                self.tts.speak("Lock cancelled")
                print("Missiles: Lock cancelled")

            elif self.state.missile_state == 'initializing':
                # Cancelled during init
                self.audio.stop_channel('missiles')
                self._missile_channel.play('missile_init_end')
                self.state.missile_state = 'init_ending'
                print("Missiles: Init cancelled")

    def _start_missile_lock(self, current_time: int):
        """Start the missile lock-on sequence."""
        # Get targets and calculate distance-based lock time
        targets = self.drones.get_drones_in_range(MISSILE_RANGE)
        self.state.missile_target_count = len(targets)

        if targets:
            closest = min(targets, key=lambda d: d['distance'])
            self.state.missile_closest_distance = closest['distance']

            # Distance-based lock time: closer = faster
            distance_ratio = self.state.missile_closest_distance / MISSILE_RANGE
            self.state.missile_lock_required = int(
                MISSILE_LOCK_MIN + (MISSILE_LOCK_MAX - MISSILE_LOCK_MIN) * distance_ratio
            )
        else:
            self.state.missile_closest_distance = 0
            self.state.missile_lock_required = MISSILE_LOCK_MAX

        self.state.missile_lock_start = current_time
        self.state.missile_last_beep = current_time
        self.state.missile_state = 'locking'

        # Announce targets
        if self.state.missile_target_count > 0:
            dist_str = f"{int(self.state.missile_closest_distance)} meters"
            if self.state.missile_target_count == 1:
                self.tts.speak(f"Locking, 1 contact at {dist_str}")
            else:
                self.tts.speak(f"Locking, {self.state.missile_target_count} contacts, closest {dist_str}")
            print(f"Missiles: Locking - {self.state.missile_target_count} targets, closest at {int(self.state.missile_closest_distance)}m, lock time {self.state.missile_lock_required}ms")
        else:
            self.tts.speak("Locking, no contacts")
            print(f"Missiles: Locking - no targets, lock time {self.state.missile_lock_required}ms")

        # Play lock init loop
        self._missile_channel.play('missile_init_loop')

    def _update_missile_lock(self, current_time: int):
        """Update lock progress with accelerating beep feedback."""
        lock_time = current_time - self.state.missile_lock_start
        lock_progress = min(1.0, lock_time / self.state.missile_lock_required)

        # Calculate beep interval (accelerates as lock completes)
        beep_interval = int(
            MISSILE_BEEP_START_INTERVAL -
            (MISSILE_BEEP_START_INTERVAL - MISSILE_BEEP_END_INTERVAL) * lock_progress
        )

        # Play beep if interval elapsed
        if current_time - self.state.missile_last_beep >= beep_interval:
            # Use interface sound for beep
            beep_sound = self.sounds.get_drone_sound('interfaces')
            if beep_sound:
                self._blaster_channel.play(beep_sound)  # Use blaster channel for beep
            self.state.missile_last_beep = current_time

        # Check if lock complete
        if lock_time >= self.state.missile_lock_required:
            self.state.missile_state = 'locked'
            self.audio.stop_channel('missiles')
            self.tts.speak("Target locked")
            print("Missiles: Locked!")

    def _fire_missiles(self, current_time: int, reveal_callback):
        """Fire missiles at locked targets."""
        self.audio.stop_channel('missiles')
        self._missile_channel.play('missile_movement')
        import pygame
        pygame.time.wait(150)
        self._missile_channel.play('missile_launch')
        self.state.missile_state = 'launching'
        self.state.ammo[WEAPON_MISSILES] -= MISSILE_COUNT
        self.state.missile_last_fire = current_time  # Mark as warm
        self.tts.speak("Missiles away")
        print(f"Missiles: Launching! (Ammo: {self.state.ammo[WEAPON_MISSILES]})")

        # Trigger drone sound reactions to player firing
        self.drones.react_to_player_fire(current_time)

        # Use weapon-specific reveal duration (missiles are loud!)
        if self.camo:
            self.camo.reveal(current_time, CAMO_REVEAL_MISSILES, self.drones)

        # Hit drones in range
        targets = self.drones.get_drones_in_range(MISSILE_RANGE)
        targets = sorted(targets, key=lambda d: d['distance'])
        missiles_remaining = MISSILE_COUNT
        hits = 0
        # First missile gets ambush bonus
        first_hit = True
        for drone in targets:
            if missiles_remaining <= 0:
                break
            damage = self._get_ambush_damage(MISSILE_DAMAGE) if first_hit else MISSILE_DAMAGE
            first_hit = False
            self.drones.damage_drone(drone, damage)
            missiles_remaining -= 1
            hits += 1

        if hits > 0:
            self.tts.speak(f"{hits} hits")
            print(f"Missiles: {hits} hits!")

    def _update_blaster(self, ctrl, current_time, reveal_callback):
        """Update blaster state."""
        if ctrl and (current_time - self.state.blaster_last_shot > BLASTER_COOLDOWN):
            if not self.state.is_malfunctioning('weapons'):
                if self.state.ammo[WEAPON_BLASTER] > 0:
                    self._blaster_channel.play('hand_blaster')
                    self.state.blaster_last_shot = current_time
                    self.state.ammo[WEAPON_BLASTER] -= 1
                    print(f"Blaster: Fire! (Ammo: {self.state.ammo[WEAPON_BLASTER]})")

                    # Use weapon-specific reveal duration (blaster is quieter)
                    if self.camo:
                        self.camo.reveal(current_time, CAMO_REVEAL_BLASTER, self.drones)

                    # Trigger drone sound reactions to player firing
                    self.drones.react_to_player_fire(current_time)

                    # Hit closest drone in tight arc
                    targets = self.drones.get_drones_in_range(BLASTER_RANGE, BLASTER_ARC)
                    if targets:
                        target = min(targets, key=lambda d: d['distance'])
                        damage = self._get_ambush_damage(BLASTER_DAMAGE)
                        self.drones.damage_drone(target, damage)
                        self.tts.speak("Direct hit")
                    else:
                        self.tts.speak("Miss")
                elif not self.state.prev_ctrl:
                    self.tts.speak("Blaster out of ammo")
                    print("Blaster: No ammo!")

    def _update_emp(self, ctrl_pressed, current_time, reveal_callback):
        """Update EMP state."""
        if ctrl_pressed and self.state.emp_state == 'ready':
            if not self.state.is_malfunctioning('weapons'):
                if self.state.ammo[WEAPON_EMP] > 0:
                    self._emp_channel.play('emp_sound')
                    self.state.emp_state = 'cooldown'
                    self.state.emp_cooldown_start = current_time
                    self.state.ammo[WEAPON_EMP] -= 1
                    self.tts.speak("E M P fired")
                    print(f"EMP: Fired! (Charges: {self.state.ammo[WEAPON_EMP]})")

                    # Use weapon-specific reveal duration (EMP has strong tech signature)
                    if self.camo:
                        self.camo.reveal(current_time, CAMO_REVEAL_EMP, self.drones)

                    # Trigger drone sound reactions to player firing
                    self.drones.react_to_player_fire(current_time)

                    # Damage all drones in range
                    targets = self.drones.get_drones_in_range(EMP_RANGE)
                    first_hit = True
                    for drone in targets:
                        # First hit gets ambush bonus
                        damage = self._get_ambush_damage(EMP_DAMAGE) if first_hit else EMP_DAMAGE
                        first_hit = False
                        self.drones.damage_drone(drone, damage)
                    if targets:
                        self.tts.speak(f"{len(targets)} targets hit")
                        print(f"EMP: Hit {len(targets)} drone(s)!")
                else:
                    self.tts.speak("E M P out of charges")
                    print("EMP: No charges!")

        # Check cooldown
        if self.state.emp_state == 'cooldown':
            if current_time - self.state.emp_cooldown_start >= EMP_COOLDOWN:
                self.state.emp_state = 'ready'
                self.tts.speak("E M P ready")
                print("EMP: Ready")

    def _check_low_ammo(self):
        """Check and warn about low ammo."""
        if self.state.weapon_state != 'ready':
            return

        weapon = self.state.current_weapon
        threshold = LOW_AMMO_THRESHOLDS[weapon]

        if self.state.ammo[weapon] <= threshold and not self.state.low_ammo_warned[weapon]:
            weapon_name = self._get_weapon_name(weapon)
            self.tts.speak(f"{weapon_name} ammo low")
            self.state.low_ammo_warned[weapon] = True
            print(f"WARNING: {weapon_name} ammo low!")
        elif self.state.ammo[weapon] > threshold:
            self.state.low_ammo_warned[weapon] = False

    def start_fabrication(self, current_time: int) -> bool:
        """Start ammo fabrication.

        Args:
            current_time: Current game time

        Returns:
            True if fabrication started
        """
        if self.state.fabricating:
            return False

        if self.state.debris_count < FABRICATION_COST:
            self.tts.speak(f"Need {FABRICATION_COST} debris to fabricate")
            print(f"Not enough debris! Need {FABRICATION_COST}, have {self.state.debris_count}")
            return False

        self.state.fabricating = True
        self.state.fabrication_start_time = current_time
        self.state.debris_count -= FABRICATION_COST

        channel = self.audio.play_sound('ammo_fab_init', 'ui')
        self.audio.set_channel('fabrication', channel)
        import pygame
        pygame.time.wait(200)
        channel = self.audio.play_sound('ammo_fab_process', 'ui', loop_count=-1)
        self.audio.set_channel('fabrication', channel)

        self.tts.speak("Fabricating ammunition")
        print(f"Fabrication started! Debris remaining: {self.state.debris_count}")
        return True

    def _check_fabrication(self, current_time: int):
        """Check for fabrication completion."""
        if not self.state.fabricating:
            return

        if current_time - self.state.fabrication_start_time >= FABRICATION_DURATION:
            self.audio.stop_channel('fabrication')
            self._fab_channel.play('ammo_fab_complete')
            self.state.fabricating = False

            # Add ammo to current weapon
            weapon = self.state.current_weapon
            gain = AMMO_FABRICATION_GAINS[weapon]
            old_ammo = self.state.ammo[weapon]
            self.state.ammo[weapon] = min(AMMO_MAX[weapon], self.state.ammo[weapon] + gain)
            gained = self.state.ammo[weapon] - old_ammo

            weapon_name = self._get_weapon_name(weapon)
            self.tts.speak(f"{weapon_name} ammo replenished")
            print(f"Fabrication complete! {weapon_name}: +{gained} ({int(self.state.ammo[weapon])}/{AMMO_MAX[weapon]})")

    def check_transitions(self):
        """Check for weapon sound state transitions."""
        # Weapon equipping
        if self.state.weapon_state == 'equipping' and self.audio.check_channel_ended('weapon_equip'):
            ready_sounds = {
                WEAPON_CHAINGUN: 'chaingun_ready',
                WEAPON_MISSILES: 'weapon1_ready',
                WEAPON_BLASTER: 'weapon2_ready',
                WEAPON_EMP: 'weapon2_ready'
            }
            channel = self.audio.play_sound(ready_sounds[self.state.current_weapon], 'weapons')
            self.audio.set_channel('weapon_equip', channel)
            self.state.weapon_state = 'ready'
            self.audio.stop_ducking(speed=4.0)
            print(f"Weapon {self.state.current_weapon}: Ready")

        # Chaingun states
        if self.state.chaingun_state == 'extending' and self.audio.check_channel_ended('chaingun'):
            channel = self.audio.play_sound('chaingun_ready', 'weapons')
            self.audio.set_channel('chaingun', channel)
            self.state.chaingun_state = 'ready'
            print(f"{self._get_chaingun_name()}: Ready")
        elif self.state.chaingun_state == 'starting' and self.audio.check_channel_ended('chaingun'):
            _, gun_loop, _ = self._get_chaingun_sounds()
            channel = self.audio.play_sound(gun_loop, 'weapons', loop_count=-1)
            self.audio.set_channel('chaingun', channel)
            self.state.chaingun_state = 'spinning'
            print(f"{self._get_chaingun_name()}: Looping")
        elif self.state.chaingun_state == 'stopping' and self.audio.check_channel_ended('chaingun'):
            self.state.chaingun_state = 'ready'
            print(f"{self._get_chaingun_name()}: Ready")

        # Missile states
        if self.state.missile_state == 'initializing' and self.audio.check_channel_ended('missiles'):
            # Init complete, start locking
            import pygame
            self._start_missile_lock(pygame.time.get_ticks())
            print("Missiles: Init complete, locking")
        elif self.state.missile_state == 'init_ending' and self.audio.check_channel_ended('missiles'):
            self.state.missile_state = 'ready'
            print("Missiles: Ready")
        elif self.state.missile_state == 'launching' and self.audio.check_channel_ended('missiles'):
            self.state.missile_state = 'ready'
            print("Missiles: Ready")

    def _get_chaingun_sounds(self) -> tuple:
        """Get chaingun sound names based on variant."""
        if self.state.chaingun_variant == CHAINGUN_STANDARD:
            return 'chaingun_start', 'chaingun_loop', 'chaingun_tail'
        return 'small_minigun_start', 'small_minigun_loop', 'small_minigun_end'

    def _get_chaingun_name(self) -> str:
        """Get current chaingun variant name."""
        return CHAINGUN_VARIANT_NAMES.get(self.state.chaingun_variant, "Chaingun")

    def _get_weapon_name(self, weapon: int) -> str:
        """Get weapon name, with chaingun variant handling."""
        if weapon == WEAPON_CHAINGUN:
            return self._get_chaingun_name()
        return WEAPON_NAMES.get(weapon, "Unknown")
