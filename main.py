"""
Main game loop for MechSimulator.

Initializes all systems and runs the main game loop.
"""

import pygame
import sys

from state.constants import (
    WINDOW_SIZE, WINDOW_TITLE, FPS, VOLUME_STEP,
    WEAPON_CHAINGUN, WEAPON_MISSILES, WEAPON_BLASTER, WEAPON_EMP,
    WEAPON_NAMES, AMMO_MAX, WEAPON_SHIELD, MAX_DRONES
)
import state.constants as constants  # For runtime override
from state.game_state import GameState
from audio.manager import AudioManager
from audio.loader import SoundLoader
from audio.drone_pool import DroneAudioPool
from audio.logging import AudioLogger
from audio.audio_logger import audio_log, set_audio_logging, set_log_detail
from ui.tts import TTSManager
from ui.menu import ConfigMenu
from systems.movement import MovementSystem
from systems.thrusters import ThrusterSystem
from systems.shield import ShieldSystem
from systems.camouflage import CamouflageSystem
from systems.weapons import WeaponSystem
from combat.damage import DamageSystem
from combat.drone_manager import DroneManager
from combat.radar import RadarSystem


class Game:
    """Main game class that orchestrates all systems."""

    def __init__(self):
        """Initialize the game."""
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()

        # Initialize core systems
        self.tts = TTSManager()
        self.tts.init()

        self.audio = AudioManager()
        self.audio.init(max_channels=64)

        # Initialize FMOD 3D audio settings for binaural spatialization
        # doppler_scale=0.5 (enabled - subtle pitch shifting for approaching/departing)
        # distance_factor=1.0 (1 unit = 1 meter)
        # rolloff_scale=1.0 (normal distance attenuation)
        self.audio.init_3d_audio(doppler_scale=0.5, distance_factor=1.0, rolloff_scale=1.0)

        # Initialize HRTF spatialization (Steam Audio if available, fallback to FMOD 3D)
        if self.audio.init_hrtf():
            if self.audio.hrtf.is_using_hrtf:
                print("HRTF: Steam Audio binaural enabled")
            else:
                print("HRTF: Using FMOD 3D audio fallback")
        else:
            print("HRTF: Disabled")

        self.sounds = SoundLoader(self.audio)

        # Try to load from encrypted pack first, fall back to raw files
        self.sounds.init_pack('game.sounds')

        if not self.sounds.load_all():
            print("Failed to load essential sounds!")
            self.cleanup()
            sys.exit(1)

        # Initialize game state
        self.state = GameState()

        # Initialize game systems with dependencies
        self.shield = ShieldSystem(self.audio, self.tts, self.state)
        self.camo = CamouflageSystem(self.audio, self.sounds, self.tts, self.state)
        self.movement = MovementSystem(self.audio, self.sounds, self.tts, self.state)
        self.thrusters = ThrusterSystem(self.audio, self.sounds, self.tts, self.state)

        # Initialize combat systems
        self.drone_manager = DroneManager(self.audio, self.sounds, self.tts, self.state)
        self.damage = DamageSystem(self.audio, self.sounds, self.tts, self.state, self.shield)
        self.radar = RadarSystem(self.audio, self.sounds, self.tts, self.state, self.drone_manager)
        self.weapons = WeaponSystem(
            self.audio, self.sounds, self.tts, self.state,
            self.drone_manager, self.shield
        )

        # Game control
        self.running = True

        # Configuration menu (created when needed, after startup sequence)
        self.config_menu = None
        self.drone_pool = None  # Created after config is confirmed

        # Audio debug logging (toggle with F12)
        self.audio_logger = AudioLogger.get_instance()
        self.audio_logger.enable(False)  # Disabled by default

        # Spatial audio logging (toggle with L key)
        # Shows detailed info about: positioning, occlusion, reverb, ducking, etc.
        self._spatial_audio_logging = False

        # Thruster toggle flag (spacebar press detection)
        self._space_pressed = False

        # Start power-up sequence
        self._start_powerup_sequence()

        print("\n=== Initializing Mech Simulator ===")
        print("Starting power-up sequence...\n")

    def _start_powerup_sequence(self):
        """Start the mech power-up sequence."""
        self.state.startup_state = 'starting'
        channel = self.audio.play_sound('powerup_start', 'powerup')
        self.audio.set_channel('startup', channel)
        print("Mech powering up...")

    def run(self):
        """Run the main game loop."""
        while self.running:
            # OPTIMIZATION: Use actual elapsed time for consistent physics
            # clock.tick() returns milliseconds since last call
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0  # Convert to seconds

            current_time = pygame.time.get_ticks()

            # Handle events
            self._handle_events(current_time)

            # Check sound transitions
            self._check_sound_transitions()

            # Skip gameplay during startup
            if not self.state.mech_operational:
                continue

            # Handle game over state
            if self.state.game_over:
                self._handle_game_over()
                continue

            # Get key state
            keys = pygame.key.get_pressed()

            # Update all systems
            self._update_rotation(keys, dt, current_time)
            self._update_movement(keys, dt, current_time)
            self._update_thrusters(keys, dt, current_time)
            self._update_camo(current_time, dt)
            self._update_weapons(keys, current_time, dt)
            self._update_shield(keys, dt)
            self._update_drones(current_time, dt)
            self._update_environmental_audio()

            # Update 3D audio listener position based on player state
            self.audio.update_3d_listener(
                self.state.player_x,
                self.state.player_y,
                self.state.player_altitude,
                self.state.facing_angle
            )

            # Update HRTF listener (if Steam Audio enabled)
            self.audio.update_hrtf_listener(
                self.state.player_x,
                self.state.player_y,
                self.state.player_altitude / 3.28,  # Convert feet to meters
                self.state.facing_angle
            )

            # Update audio system
            self.audio.update()
            self.audio.update_ducking(dt)

        self.cleanup()

    def _handle_events(self, current_time: int):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

                # Config menu navigation (during startup)
                elif self.state.startup_state == 'config_menu' and self.config_menu:
                    if self.config_menu.handle_input(event.key):
                        self._start_game_with_config()
                    continue

                # Game over menu navigation
                elif self.state.game_over:
                    self._handle_game_over_input(event)

                # F12: Toggle audio debug logging
                elif event.key == pygame.K_F12:
                    self.audio_logger.toggle()

                # L: Toggle spatial audio logging (detailed positioning/occlusion/reverb)
                elif event.key == pygame.K_l:
                    self._spatial_audio_logging = not self._spatial_audio_logging
                    set_audio_logging(self._spatial_audio_logging)
                    if self._spatial_audio_logging:
                        self.tts.speak("Spatial audio logging enabled", duck_audio=False)
                    else:
                        self.tts.speak("Spatial audio logging disabled", duck_audio=False)

                # Shift+L: Cycle log detail level (0=minimal, 1=normal, 2=verbose)
                elif event.key == pygame.K_l and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    # This won't trigger due to order, but kept for documentation
                    pass

                # Volume control
                elif event.key == pygame.K_EQUALS:
                    self.audio.adjust_volume(VOLUME_STEP)
                    self.tts.speak(f"Volume at {int(self.audio.master_volume * 100)} percent")
                    print(f"Master volume: {self.audio.master_volume:.2f}")

                elif event.key == pygame.K_MINUS:
                    self.audio.adjust_volume(-VOLUME_STEP)
                    self.tts.speak(f"Volume at {int(self.audio.master_volume * 100)} percent")
                    print(f"Master volume: {self.audio.master_volume:.2f}")

                # Weapon switching (1-3 for weapons, 4 for EMP - shield is now Z key)
                elif event.key == pygame.K_1:
                    self.weapons.switch_weapon(WEAPON_CHAINGUN)
                elif event.key == pygame.K_2 and self.state.current_weapon != WEAPON_MISSILES:
                    self.weapons.switch_weapon(WEAPON_MISSILES)
                elif event.key == pygame.K_3 and self.state.current_weapon != WEAPON_BLASTER:
                    self.weapons.switch_weapon(WEAPON_BLASTER)
                elif event.key == pygame.K_4 and self.state.current_weapon != WEAPON_EMP:
                    self.weapons.switch_weapon(WEAPON_EMP)

                # Fabrication
                elif event.key == pygame.K_f and not self.state.fabricating:
                    self.weapons.start_fabrication(current_time)

                # Status keys
                elif event.key == pygame.K_t:
                    self._announce_ammo_status()
                elif event.key == pygame.K_y:
                    self._announce_thruster_status()
                elif event.key == pygame.K_u:
                    self._announce_hull_status()
                elif event.key == pygame.K_i:
                    self._announce_contact_count()

                # Spacebar: Toggle thrusters on/off
                elif event.key == pygame.K_SPACE:
                    self._space_pressed = True

                # Radar, camo, and echolocation
                elif event.key == pygame.K_r:
                    self.radar.scan(current_time)
                elif event.key == pygame.K_c:
                    self.camo.toggle(current_time)
                elif event.key == pygame.K_x:
                    self.radar.toggle_echolocation()

    def _handle_game_over_input(self, event):
        """Handle game over menu input."""
        if event.key == pygame.K_UP and self.state.game_over_selection > 0:
            self.state.game_over_selection = 0
            self.tts.speak("Play Again")
            print("Selected: Play Again")
        elif event.key == pygame.K_DOWN and self.state.game_over_selection < 1:
            self.state.game_over_selection = 1
            self.tts.speak("Quit")
            print("Selected: Quit")
        elif event.key == pygame.K_RETURN:
            if self.state.game_over_selection == 0:
                self._restart_game()
            else:
                self.running = False

    def _handle_game_over(self):
        """Handle game over state display."""
        if not self.state.game_over_announced:
            self.state.game_over_announced = True
            # Stop all sounds immediately
            self.audio.stop_all()
            menu_options = ["Play Again", "Quit"]
            self.tts.speak(f"{menu_options[self.state.game_over_selection]} selected. Use up and down arrows to change, Enter to confirm.")
            print("\n=== GAME OVER ===")
            print("Use UP/DOWN arrows to select, ENTER to confirm:")
            print(f"  {'>' if self.state.game_over_selection == 0 else ' '} Play Again")
            print(f"  {'>' if self.state.game_over_selection == 1 else ' '} Quit")

    def _restart_game(self):
        """Restart the game."""
        self.tts.speak("Restarting. Mech systems rebooting.")

        # Reset game state
        self.state.reset()

        # Clear drones
        self.drone_manager.clear_all()
        self.drone_manager.spawn_timer = pygame.time.get_ticks()

        # Reset audio effects
        self.audio.set_hull_damage_effect(100)
        self.audio.set_reverb(wet_level_db=-15, decay_ms=800, enabled=True)
        self.audio.stop_ducking(speed=10.0)

        # Restart ambience
        if self.sounds.has_ambience:
            channel = self.audio.play_sound('ambience', 'ambience', loop_count=-1)
            self.audio.set_channel('ambience', channel)

        self.state.mech_operational = True
        self.tts.speak("Mech online. Ready for combat.")

        print("\n=== GAME RESET ===")
        print("Mech systems restored. Ready for combat.\n")

    def _check_sound_transitions(self):
        """Check for sound state transitions."""
        # Skip if game over
        if self.state.game_over:
            return

        # Weapon transitions
        if self.state.mech_operational:
            self.weapons.check_transitions()
            self.movement.check_rotation_transitions()
            self.shield.check_transitions()

        # Startup sequence
        if self.state.startup_state == 'starting' and self.audio.check_channel_ended('startup'):
            channel = self.audio.play_sound('powerup_loop', 'powerup')
            self.audio.set_channel('startup', channel)
            self.state.startup_state = 'looping'
            print("Mech: Systems initializing...")

        elif self.state.startup_state == 'looping' and self.audio.check_channel_ended('startup'):
            channel = self.audio.play_sound('powerup_end', 'powerup')
            self.audio.set_channel('startup', channel)
            self.state.startup_state = 'ending'
            print("Mech: Startup completing...")

        elif self.state.startup_state == 'ending' and self.audio.check_channel_ended('startup'):
            # Transition to config menu instead of directly to gameplay
            self.state.startup_state = 'config_menu'
            self.config_menu = ConfigMenu(self.tts)
            self.config_menu.announce_menu()
            self.config_menu.print_status()

        # Config menu doesn't need transitions - handled by _start_game_with_config()

    def _start_game_with_config(self):
        """Start the game with configuration from the menu."""
        config = self.config_menu.get_config()
        drone_count = config['drone_count']

        # Store config in game state (persists across restarts)
        self.state.config_drone_count = drone_count

        # Override MAX_DRONES constant for this session
        constants.MAX_DRONES = drone_count

        # Initialize drone audio pool with configured count and HRTF support
        self.drone_pool = DroneAudioPool(self.audio.fmod, max_drones=drone_count)
        self.drone_pool.initialize(hrtf_manager=self.audio.hrtf)

        # Pass drone pool to DroneManager
        self.drone_manager.set_drone_pool(self.drone_pool)

        # Pre-load drone sounds NOW (during menu transition, prevents first-spawn stall)
        self.sounds._ensure_drone_sounds_loaded()

        # Complete startup
        self.state.startup_state = 'complete'
        self.state.mech_operational = True

        # Start ambience
        if self.sounds.has_ambience:
            channel = self.audio.play_sound('ambience', 'ambience', loop_count=-1)
            self.audio.set_channel('ambience', channel)

        # Announce game start with drone count
        hostile_word = "hostile" if drone_count == 1 else "hostiles"
        self.tts.speak(f"Mech online. {drone_count} {hostile_word} maximum.")

        print(f"\n=== MECH ONLINE (Max drones: {drone_count}) ===")
        print("WASD to move (tank controls). Q/E to rotate. Keys 1-4 to switch weapons. CTRL to fire.")
        print("Z=Shield (hold). SPACE=Thrusters toggle. PgUp/PgDn=Thrust. C=Camo. R=Radar. X=Echo. F=Fabricate.")
        print("T=Ammo. Y=Thrust. U=Hull. I=Contacts. +/- volume. F12=Debug. ESC quit.\n")

    def _update_rotation(self, keys, dt: float, current_time: int):
        """Update rotation system."""
        self.movement.update_rotation(keys, dt, current_time)

    def _update_movement(self, keys, dt: float, current_time: int):
        """Update movement system."""
        self.movement.update_movement(keys, dt, current_time, reveal_callback=self.camo.reveal)

    def _update_thrusters(self, keys, dt: float, current_time: int):
        """Update thruster system."""
        result = self.thrusters.update(
            keys, dt, current_time,
            space_pressed=self._space_pressed,
            reveal_callback=self.camo.reveal
        )
        self._space_pressed = False  # Reset after handling

        # Handle landing
        if result['landed']:
            # Play appropriate landing sound based on type
            landing_sounds = {
                'soft': 'soft_landing',
                'hard': 'hard_landing',
                'crash': 'crash_landing'
            }
            sound_name = landing_sounds.get(result['landing_type'], 'soft_landing')
            self.audio.play_sound(sound_name, 'movement')

            if result['landing_damage'] > 0:
                self.damage.apply_landing_damage(result['landing_damage'])

    def _update_camo(self, current_time: int, dt: float):
        """Update camouflage system."""
        self.camo.update(current_time, dt)

    def _update_weapons(self, keys, current_time: int, dt: float):
        """Update weapon system."""
        self.weapons.update(keys, current_time, dt, reveal_callback=self.camo.reveal)

    def _update_shield(self, keys, dt: float):
        """Update shield system with Z key input."""
        # Z key for shield activation (hold to activate, release to deactivate)
        shield_key = keys[pygame.K_z]
        shield_pressed = shield_key and not self.state.prev_shield_key
        shield_released = not shield_key and self.state.prev_shield_key

        if shield_pressed and self.state.shield_state == 'idle':
            self.shield.activate()
        elif shield_released and self.state.shield_state in ('activating', 'active'):
            self.shield.deactivate()

        self.state.prev_shield_key = shield_key

        # Update shield energy drain/regen
        self.shield.update(dt)

    def _update_drones(self, current_time: int, dt: float):
        """Update drone system."""
        if not self.sounds.has_drone_sounds:
            return

        self.drone_manager.update(current_time, dt, self.damage, self.camo)
        self.damage.update_malfunctions(current_time)

        # Update drone audio pool crossfades
        if self.drone_pool:
            self.drone_pool.update_fades(dt)

        # Update echolocation (accessibility feature)
        self.radar.update_echolocation(current_time)

        # Hull regeneration when safe
        closest_dist = self.drone_manager.get_closest_drone_distance()
        self.damage.update_hull_regen(dt, closest_dist)

    def _update_environmental_audio(self):
        """Update environmental audio based on altitude and movement speed."""
        # Update reverb based on altitude zone
        if self.state.player_altitude < 10:
            zone = 'ground'
        elif self.state.player_altitude < 50:
            zone = 'low'
        elif self.state.player_altitude < 100:
            zone = 'mid'
        else:
            zone = 'high'

        if zone != self.state.last_altitude_zone:
            self.state.last_altitude_zone = zone

            reverb_settings = {
                'ground': (-15, 800),
                'low': (-20, 500),
                'mid': (-30, 300),
                'high': (-40, 200)
            }
            wet, decay = reverb_settings[zone]
            self.audio.set_reverb(wet_level_db=wet, decay_ms=decay, enabled=True)

        # Update wind ambience volume based on speed/state
        self._update_wind_ambience()

    def _update_wind_ambience(self):
        """Update wind ambience volume based on vertical speed and flight state.

        Wind gets louder during:
        - Freefall: Dramatically louder based on falling speed (up to 2x base)
        - Powered descent: Moderately louder based on descent rate
        - Boost mode: Louder to simulate supersonic wind
        """
        from state.constants import BASE_VOLUMES, TERMINAL_VELOCITY

        base_volume = BASE_VOLUMES.get('ambience', 0.5)
        volume_multiplier = 1.0

        # Freefall - wind gets much louder based on falling speed
        if self.state.vertical_state == 'falling':
            # Scale from 1.0 to 2.0 based on how fast we're falling
            # Terminal velocity is around -60 ft/s
            fall_speed = abs(self.state.vertical_velocity)
            max_fall_speed = abs(TERMINAL_VELOCITY)
            fall_factor = min(1.0, fall_speed / max_fall_speed)
            volume_multiplier = 1.0 + fall_factor  # 1.0 to 2.0

        # Powered descent - moderate wind increase
        elif self.state.vertical_state == 'descending':
            descent_speed = abs(self.state.vertical_velocity)
            descent_factor = min(1.0, descent_speed / 30.0)  # Normalize to 30 ft/s
            volume_multiplier = 1.0 + (descent_factor * 0.5)  # 1.0 to 1.5

        # Boost mode - supersonic wind
        elif self.state.boost_active:
            volume_multiplier = 1.8  # Strong wind at full boost

        # High thrust at altitude - some wind
        elif self.state.thruster_state == 'active' and self.state.thrust_level > 0.6:
            thrust_factor = (self.state.thrust_level - 0.6) / 0.4  # 0 to 1
            volume_multiplier = 1.0 + (thrust_factor * 0.4)  # 1.0 to 1.4

        # Apply volume to ambience channel
        ambience_channel = self.audio.get_channel('ambience')
        if ambience_channel:
            final_volume = base_volume * volume_multiplier * self.audio.master_volume
            ambience_channel.set_volume(final_volume)

    def _announce_ammo_status(self):
        """Announce current ammo and debris status."""
        weapon = self.state.current_weapon
        if weapon == WEAPON_CHAINGUN:
            from state.constants import CHAINGUN_VARIANT_NAMES
            name = CHAINGUN_VARIANT_NAMES.get(self.state.chaingun_variant, "Chaingun")
        else:
            name = WEAPON_NAMES.get(weapon, "Unknown")

        ammo = int(self.state.ammo[weapon])
        max_ammo = AMMO_MAX[weapon]
        self.tts.speak(f"{name}: {ammo} of {max_ammo}. Debris: {self.state.debris_count}")
        print(f"Ammo - {name}: {ammo}/{max_ammo}, Debris: {self.state.debris_count}")

    def _announce_thruster_status(self):
        """Announce thruster, altitude, and equipment status."""
        thrust_pct = int(self.state.thrust_level * 100)
        energy_pct = int(self.state.thruster_energy)
        alt_ft = int(self.state.player_altitude)
        camo_status = "active" if self.state.camo_active else "inactive"
        camo_pct = int(self.state.camo_energy)
        shield_status = "active" if self.state.shield_active else "inactive"
        shield_pct = int(self.state.ammo[WEAPON_SHIELD])
        self.tts.speak(f"Altitude: {alt_ft} feet. Thrust: {thrust_pct} percent. Energy: {energy_pct}. Shield: {shield_status}, {shield_pct}. Camo: {camo_status}")
        print(f"Altitude: {alt_ft} ft | Thrust: {thrust_pct}%, Energy: {energy_pct}% | Shield: {shield_status}, {shield_pct}% | Camo: {camo_status}, {camo_pct}%")

    def _announce_hull_status(self):
        """Announce hull integrity."""
        hull_pct = int(self.state.player_hull)
        self.tts.speak(f"Hull integrity: {hull_pct} percent")
        print(f"Hull: {hull_pct}%")

    def _announce_contact_count(self):
        """Announce drone contact count."""
        count = len(self.drone_manager.get_active_drones())
        self.tts.speak(f"Contacts: {count}")
        print(f"Contacts: {count}")

    def cleanup(self):
        """Clean up all resources."""
        print("Mech powering down...")
        self.audio.stop_all()
        self.sounds.cleanup_pack()  # Close encrypted pack if open
        self.audio.cleanup()
        self.tts.cleanup()
        pygame.quit()
        print("Mech powered down.")


def main():
    """Entry point for the game."""
    game = Game()
    game.run()


if __name__ == '__main__':
    main()
