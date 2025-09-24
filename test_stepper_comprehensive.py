#!/usr/bin/env python3
"""
ESP32 Stepper Motor Comprehensive Test Suite

This script tests various combinations of:
- Speeds (different step delays)
- Directions (clockwise/counterclockwise)
- Microstep settings (1, 2, 4, 8, 16, 32, 64, 256)
- Movement modes (STEALTH, INTERPOLATED, CONTINUOUS)

Each test reports PASS/FAIL status and generates a detailed report.
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
from esp32link import ESP32StepperController

class StepperTestSuite:
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200):
        """Initialize the test suite."""
        self.controller = ESP32StepperController(port=port, baudrate=baudrate)
        self.test_results = []
        self.start_time = None
        
        # Test configurations - expanded for more comprehensive testing
        self.test_speeds = [100, 200, 500, 1000, 1500, 2000, 3000, 5000, 8000, 10000]  # Full range
        self.test_microsteps = [1, 2, 4, 8, 16, 32, 64, 256]
        self.test_movements = ["STEALTH", "INTERPOLATED", "CONTINUOUS"]
        self.test_directions = [50, 100, 200, 500, 1000, -50, -100, -200, -500, -1000]  # Various step counts
        
        # Extended test configurations
        self.endurance_test_steps = [100, 500, 1000, 2000]  # For endurance testing
        self.precision_test_steps = [1, 2, 5, 10, 20, 50]  # For precision testing
        self.speed_ramp_steps = [100, 200, 500]  # For speed ramping tests
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def log_test_result(self, test_name: str, passed: bool, details: str = "", 
                       duration: float = 0.0, error: str = ""):
        """Log a test result."""
        result = {
            'test_name': test_name,
            'passed': passed,
            'status': 'PASS' if passed else 'FAIL',
            'details': details,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'error': error
        }
        self.test_results.append(result)
        
        status_icon = "✅" if passed else "❌"
        self.logger.info(f"{status_icon} {test_name}: {result['status']} ({duration:.2f}s)")
        if details:
            self.logger.info(f"   Details: {details}")
        if error:
            self.logger.error(f"   Error: {error}")
    
    def test_basic_connection(self) -> bool:
        """Test basic connection and communication."""
        start_time = time.time()
        try:
            if not self.controller.connect():
                self.log_test_result("Basic Connection", False, 
                                   error="Failed to connect to ESP32",
                                   duration=time.time() - start_time)
                return False
            
            # Test status command
            status = self.controller.get_status()
            if not status:
                self.log_test_result("Basic Connection", False,
                                   error="Failed to get status",
                                   duration=time.time() - start_time)
                return False
            
            self.log_test_result("Basic Connection", True, 
                               f"Connected successfully. Initial status: {status}",
                               duration=time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test_result("Basic Connection", False, 
                               error=str(e),
                               duration=time.time() - start_time)
            return False
    
    def test_motor_enable_disable(self) -> bool:
        """Test motor enable and disable functionality."""
        start_time = time.time()
        try:
            # Test enable
            if not self.controller.enable_motor():
                self.log_test_result("Motor Enable/Disable", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            # Verify enabled status
            status = self.controller.get_status()
            if not status or not status.get('Enabled', False):
                self.log_test_result("Motor Enable/Disable", False,
                                   error="Motor not showing as enabled in status",
                                   duration=time.time() - start_time)
                return False
            
            # Test disable
            if not self.controller.disable_motor():
                self.log_test_result("Motor Enable/Disable", False,
                                   error="Failed to disable motor",
                                   duration=time.time() - start_time)
                return False
            
            # Verify disabled status
            status = self.controller.get_status()
            if not status or status.get('Enabled', True):
                self.log_test_result("Motor Enable/Disable", False,
                                   error="Motor not showing as disabled in status",
                                   duration=time.time() - start_time)
                return False
            
            self.log_test_result("Motor Enable/Disable", True,
                               "Enable and disable commands working correctly",
                               duration=time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test_result("Motor Enable/Disable", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
    
    def test_speed_settings(self) -> bool:
        """Test different speed settings."""
        start_time = time.time()
        passed_tests = 0
        total_tests = len(self.test_speeds)
        
        try:
            for speed in self.test_speeds:
                speed_start = time.time()
                
                if self.controller.set_speed(speed):
                    # Verify speed setting in status
                    status = self.controller.get_status()
                    if status and status.get('Speed') == speed:
                        passed_tests += 1
                        self.log_test_result(f"Speed Setting {speed}μs", True,
                                           f"Speed set and verified: {speed}μs",
                                           duration=time.time() - speed_start)
                    else:
                        self.log_test_result(f"Speed Setting {speed}μs", False,
                                           error=f"Speed not reflected in status. Expected: {speed}, Got: {status.get('Speed') if status else 'None'}",
                                           duration=time.time() - speed_start)
                else:
                    self.log_test_result(f"Speed Setting {speed}μs", False,
                                       error="Set speed command failed",
                                       duration=time.time() - speed_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Speed Settings", overall_passed,
                               f"Passed {passed_tests}/{total_tests} speed tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Speed Settings", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
    
    def test_microstep_settings(self) -> bool:
        """Test different microstep settings."""
        start_time = time.time()
        passed_tests = 0
        total_tests = len(self.test_microsteps)
        
        try:
            for microsteps in self.test_microsteps:
                microstep_start = time.time()
                
                if self.controller.set_microsteps(microsteps):
                    # Verify microstep setting in status
                    status = self.controller.get_status()
                    if status and status.get('Microsteps') == microsteps:
                        passed_tests += 1
                        self.log_test_result(f"Microstep Setting {microsteps}", True,
                                           f"Microsteps set and verified: {microsteps}",
                                           duration=time.time() - microstep_start)
                    else:
                        self.log_test_result(f"Microstep Setting {microsteps}", False,
                                           error=f"Microsteps not reflected in status. Expected: {microsteps}, Got: {status.get('Microsteps') if status else 'None'}",
                                           duration=time.time() - microstep_start)
                else:
                    self.log_test_result(f"Microstep Setting {microsteps}", False,
                                       error="Set microsteps command failed",
                                       duration=time.time() - microstep_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Microstep Settings", overall_passed,
                               f"Passed {passed_tests}/{total_tests} microstep tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Microstep Settings", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
    
    def test_movement_modes(self) -> bool:
        """Test different movement modes."""
        start_time = time.time()
        passed_tests = 0
        total_tests = len(self.test_movements)
        
        try:
            for movement in self.test_movements:
                movement_start = time.time()
                
                if self.controller.set_movement_type(movement):
                    # Verify movement type in status
                    status = self.controller.get_status()
                    if status and status.get('Movement') == movement:
                        passed_tests += 1
                        self.log_test_result(f"Movement Type {movement}", True,
                                           f"Movement type set and verified: {movement}",
                                           duration=time.time() - movement_start)
                    else:
                        self.log_test_result(f"Movement Type {movement}", False,
                                           error=f"Movement type not reflected in status. Expected: {movement}, Got: {status.get('Movement') if status else 'None'}",
                                           duration=time.time() - movement_start)
                else:
                    self.log_test_result(f"Movement Type {movement}", False,
                                       error="Set movement type command failed",
                                       duration=time.time() - movement_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Movement Types", overall_passed,
                               f"Passed {passed_tests}/{total_tests} movement type tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Movement Types", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
    
    def test_basic_movements(self) -> bool:
        """Test basic movement functionality in both directions."""
        start_time = time.time()
        passed_tests = 0
        total_tests = len(self.test_directions)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Basic Movements", False,
                                   error="Failed to enable motor for movement tests",
                                   duration=time.time() - start_time)
                return False
            
            # Home position first
            self.controller.home_position()
            time.sleep(0.5)
            
            for steps in self.test_directions:
                movement_start = time.time()
                direction = "clockwise" if steps > 0 else "counterclockwise"
                
                # Get initial position
                initial_status = self.controller.get_status()
                initial_position = initial_status.get('Position', 0) if initial_status else 0
                
                # Start movement
                if self.controller.move_steps(steps):
                    # Calculate timeout based on movement size (minimum 10s, add 1s per 100 steps)
                    timeout = max(10.0, 10.0 + abs(steps) / 100.0)
                    # Wait for movement to complete
                    if self.controller.wait_for_movement_complete(timeout=timeout):
                        # Check final position
                        final_status = self.controller.get_status()
                        if final_status:
                            final_position = final_status.get('Position', 0)
                            expected_position = initial_position + steps
                            
                            if final_position == expected_position:
                                passed_tests += 1
                                self.log_test_result(f"Movement {direction} ({steps} steps)", True,
                                                   f"Moved from {initial_position} to {final_position}",
                                                   duration=time.time() - movement_start)
                            else:
                                self.log_test_result(f"Movement {direction} ({steps} steps)", False,
                                                   error=f"Position mismatch. Expected: {expected_position}, Got: {final_position}",
                                                   duration=time.time() - movement_start)
                        else:
                            self.log_test_result(f"Movement {direction} ({steps} steps)", False,
                                               error="Could not get final status",
                                               duration=time.time() - movement_start)
                    else:
                        self.log_test_result(f"Movement {direction} ({steps} steps)", False,
                                           error="Movement did not complete within timeout",
                                           duration=time.time() - movement_start)
                else:
                    self.log_test_result(f"Movement {direction} ({steps} steps)", False,
                                       error="Move command failed",
                                       duration=time.time() - movement_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Basic Movements", overall_passed,
                               f"Passed {passed_tests}/{total_tests} movement tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Basic Movements", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def test_combined_configurations(self) -> bool:
        """Test combinations of different settings with actual movements."""
        start_time = time.time()
        passed_tests = 0
        
        # Test subset of combinations to keep test time reasonable
        test_configs = [
            {"speed": 1000, "microsteps": 16, "movement": "STEALTH"},
            {"speed": 500, "microsteps": 32, "movement": "INTERPOLATED"},
            {"speed": 2000, "microsteps": 8, "movement": "CONTINUOUS"},
            {"speed": 1000, "microsteps": 64, "movement": "STEALTH"},
        ]
        
        total_tests = len(test_configs)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Combined Configurations", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            self.controller.home_position()
            time.sleep(0.5)
            
            for i, config in enumerate(test_configs):
                config_start = time.time()
                config_name = f"Config {i+1}: {config['speed']}μs, {config['microsteps']} steps, {config['movement']}"
                
                # Apply configuration
                config_success = True
                config_success &= self.controller.set_speed(config['speed'])
                config_success &= self.controller.set_microsteps(config['microsteps'])
                config_success &= self.controller.set_movement_type(config['movement'])
                
                if not config_success:
                    self.log_test_result(config_name, False,
                                       error="Failed to apply configuration",
                                       duration=time.time() - config_start)
                    continue
                
                # Verify configuration
                status = self.controller.get_status()
                if not status:
                    self.log_test_result(config_name, False,
                                       error="Could not verify configuration",
                                       duration=time.time() - config_start)
                    continue
                
                # Test a small movement
                test_steps = 100
                initial_position = status.get('Position', 0)
                
                if self.controller.move_steps(test_steps):
                    if self.controller.wait_for_movement_complete(timeout=10.0):
                        final_status = self.controller.get_status()
                        if final_status:
                            final_position = final_status.get('Position', 0)
                            if final_position == initial_position + test_steps:
                                passed_tests += 1
                                self.log_test_result(config_name, True,
                                                   f"Configuration applied and movement successful",
                                                   duration=time.time() - config_start)
                            else:
                                self.log_test_result(config_name, False,
                                                   error=f"Position mismatch after movement",
                                                   duration=time.time() - config_start)
                        else:
                            self.log_test_result(config_name, False,
                                               error="Could not get final position",
                                               duration=time.time() - config_start)
                    else:
                        self.log_test_result(config_name, False,
                                           error="Movement timeout",
                                           duration=time.time() - config_start)
                else:
                    self.log_test_result(config_name, False,
                                       error="Movement command failed",
                                       duration=time.time() - config_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Combined Configurations", overall_passed,
                               f"Passed {passed_tests}/{total_tests} combined configuration tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Combined Configurations", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def test_precision_movements(self) -> bool:
        """Test precise small movements and position accuracy."""
        start_time = time.time()
        passed_tests = 0
        total_tests = len(self.precision_test_steps) * 2  # Test both directions
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Precision Movements", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            # Set precise configuration for precision testing
            self.controller.set_speed(500)  # Fast but controlled
            self.controller.set_microsteps(64)  # High precision
            self.controller.set_movement_type("INTERPOLATED")  # Smooth movement
            
            self.controller.home_position()
            time.sleep(0.5)
            
            for steps in self.precision_test_steps:
                # Test positive direction
                for direction_multiplier, direction_name in [(1, "positive"), (-1, "negative")]:
                    test_steps = steps * direction_multiplier
                    precision_start = time.time()
                    
                    initial_status = self.controller.get_status()
                    initial_position = initial_status.get('Position', 0) if initial_status else 0
                    
                    if self.controller.move_steps(test_steps):
                        if self.controller.wait_for_movement_complete(timeout=15.0):
                            final_status = self.controller.get_status()
                            if final_status:
                                final_position = final_status.get('Position', 0)
                                expected_position = initial_position + test_steps
                                
                                if final_position == expected_position:
                                    passed_tests += 1
                                    self.log_test_result(f"Precision {direction_name} {steps} steps", True,
                                                       f"Accurate movement: {initial_position} → {final_position}",
                                                       duration=time.time() - precision_start)
                                else:
                                    self.log_test_result(f"Precision {direction_name} {steps} steps", False,
                                                       error=f"Position error. Expected: {expected_position}, Got: {final_position}",
                                                       duration=time.time() - precision_start)
                            else:
                                self.log_test_result(f"Precision {direction_name} {steps} steps", False,
                                                   error="Could not get final status",
                                                   duration=time.time() - precision_start)
                        else:
                            self.log_test_result(f"Precision {direction_name} {steps} steps", False,
                                               error="Movement timeout",
                                               duration=time.time() - precision_start)
                    else:
                        self.log_test_result(f"Precision {direction_name} {steps} steps", False,
                                           error="Move command failed",
                                           duration=time.time() - precision_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Precision Movements", overall_passed,
                               f"Passed {passed_tests}/{total_tests} precision tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Precision Movements", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def test_speed_ramping(self) -> bool:
        """Test speed changes during operation and speed ramping."""
        start_time = time.time()
        passed_tests = 0
        
        speed_sequences = [
            [1000, 500, 2000, 1000],  # Fast to very fast to slow to medium
            [5000, 1000, 500, 3000],  # Slow to fast to very fast to medium-slow
            [100, 10000, 1000],       # Very fast to very slow to medium
        ]
        
        total_tests = len(speed_sequences) * len(self.speed_ramp_steps)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Speed Ramping", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            self.controller.set_microsteps(16)
            self.controller.set_movement_type("CONTINUOUS")
            self.controller.home_position()
            time.sleep(0.5)
            
            for seq_idx, speed_sequence in enumerate(speed_sequences):
                for step_count in self.speed_ramp_steps:
                    ramp_start = time.time()
                    test_name = f"Speed Ramp {seq_idx+1} ({step_count} steps)"
                    
                    sequence_success = True
                    positions = []
                    
                    for speed_idx, speed in enumerate(speed_sequence):
                        # Change speed
                        if not self.controller.set_speed(speed):
                            sequence_success = False
                            break
                        
                        # Verify speed change
                        status = self.controller.get_status()
                        if not status or status.get('Speed') != speed:
                            sequence_success = False
                            break
                        
                        # Make movement at this speed
                        initial_position = status.get('Position', 0)
                        if self.controller.move_steps(step_count):
                            if self.controller.wait_for_movement_complete(timeout=20.0):
                                final_status = self.controller.get_status()
                                if final_status:
                                    final_position = final_status.get('Position', 0)
                                    positions.append(final_position)
                                    
                                    if final_position != initial_position + step_count:
                                        sequence_success = False
                                        break
                                else:
                                    sequence_success = False
                                    break
                            else:
                                sequence_success = False
                                break
                        else:
                            sequence_success = False
                            break
                    
                    if sequence_success:
                        passed_tests += 1
                        self.log_test_result(test_name, True,
                                           f"Speed sequence completed. Speeds: {speed_sequence}, Final positions: {positions}",
                                           duration=time.time() - ramp_start)
                    else:
                        self.log_test_result(test_name, False,
                                           error="Speed ramp sequence failed",
                                           duration=time.time() - ramp_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Speed Ramping", overall_passed,
                               f"Passed {passed_tests}/{total_tests} speed ramp tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Speed Ramping", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def test_endurance_movements(self) -> bool:
        """Test extended movement sequences for endurance and reliability."""
        start_time = time.time()
        passed_tests = 0
        
        # Define endurance test scenarios
        endurance_configs = [
            {"microsteps": 16, "movement": "STEALTH", "speed": 1000, "cycles": 20},
            {"microsteps": 32, "movement": "INTERPOLATED", "speed": 500, "cycles": 15},
            {"microsteps": 64, "movement": "CONTINUOUS", "speed": 2000, "cycles": 10},
        ]
        
        total_tests = len(endurance_configs)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Endurance Movements", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            for config_idx, config in enumerate(endurance_configs):
                endurance_start = time.time()
                test_name = f"Endurance {config_idx+1}: {config['microsteps']} steps, {config['movement']}, {config['cycles']} cycles"
                
                # Apply configuration
                config_success = True
                config_success &= self.controller.set_microsteps(config['microsteps'])
                config_success &= self.controller.set_movement_type(config['movement'])
                config_success &= self.controller.set_speed(config['speed'])
                
                if not config_success:
                    self.log_test_result(test_name, False,
                                       error="Failed to apply endurance configuration",
                                       duration=time.time() - endurance_start)
                    continue
                
                self.controller.home_position()
                time.sleep(0.5)
                
                # Perform endurance cycles
                endurance_success = True
                total_distance = 0
                
                for cycle in range(config['cycles']):
                    # Alternate direction each cycle
                    step_count = 200 if cycle % 2 == 0 else -200
                    
                    initial_status = self.controller.get_status()
                    initial_position = initial_status.get('Position', 0) if initial_status else 0
                    
                    if self.controller.move_steps(step_count):
                        if self.controller.wait_for_movement_complete(timeout=30.0):
                            final_status = self.controller.get_status()
                            if final_status:
                                final_position = final_status.get('Position', 0)
                                if final_position == initial_position + step_count:
                                    total_distance += abs(step_count)
                                else:
                                    endurance_success = False
                                    break
                            else:
                                endurance_success = False
                                break
                        else:
                            endurance_success = False
                            break
                    else:
                        endurance_success = False
                        break
                    
                    # Brief pause between cycles
                    time.sleep(0.1)
                
                if endurance_success:
                    passed_tests += 1
                    self.log_test_result(test_name, True,
                                       f"Completed {config['cycles']} cycles, total distance: {total_distance} steps",
                                       duration=time.time() - endurance_start)
                else:
                    self.log_test_result(test_name, False,
                                       error=f"Endurance test failed at cycle {cycle+1}",
                                       duration=time.time() - endurance_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Endurance Movements", overall_passed,
                               f"Passed {passed_tests}/{total_tests} endurance tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Endurance Movements", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def test_stress_configurations(self) -> bool:
        """Test rapid configuration changes and extreme combinations."""
        start_time = time.time()
        passed_tests = 0
        
        # Extreme configuration combinations
        stress_configs = [
            {"speed": 100, "microsteps": 256, "movement": "INTERPOLATED"},  # Fastest + highest precision
            {"speed": 10000, "microsteps": 1, "movement": "CONTINUOUS"},    # Slowest + lowest precision
            {"speed": 100, "microsteps": 1, "movement": "STEALTH"},         # Fastest + lowest precision
            {"speed": 10000, "microsteps": 256, "movement": "STEALTH"},     # Slowest + highest precision
            {"speed": 1000, "microsteps": 64, "movement": "INTERPOLATED"},  # Balanced extreme
        ]
        
        total_tests = len(stress_configs)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Stress Configurations", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            for config_idx, config in enumerate(stress_configs):
                stress_start = time.time()
                test_name = f"Stress Config {config_idx+1}: {config['speed']}μs, {config['microsteps']} steps, {config['movement']}"
                
                # Apply extreme configuration
                config_success = True
                config_success &= self.controller.set_speed(config['speed'])
                config_success &= self.controller.set_microsteps(config['microsteps'])
                config_success &= self.controller.set_movement_type(config['movement'])
                
                if not config_success:
                    self.log_test_result(test_name, False,
                                       error="Failed to apply stress configuration",
                                       duration=time.time() - stress_start)
                    continue
                
                # Verify all settings applied correctly
                status = self.controller.get_status()
                if not status:
                    self.log_test_result(test_name, False,
                                       error="Could not verify stress configuration",
                                       duration=time.time() - stress_start)
                    continue
                
                settings_correct = (
                    status.get('Speed') == config['speed'] and
                    status.get('Microsteps') == config['microsteps'] and
                    status.get('Movement') == config['movement']
                )
                
                if not settings_correct:
                    self.log_test_result(test_name, False,
                                       error=f"Configuration mismatch. Expected: {config}, Got: Speed={status.get('Speed')}, Microsteps={status.get('Microsteps')}, Movement={status.get('Movement')}",
                                       duration=time.time() - stress_start)
                    continue
                
                # Test movement under stress configuration
                self.controller.home_position()
                time.sleep(0.5)
                
                test_steps = 500  # Moderate movement for stress test
                if self.controller.move_steps(test_steps):
                    # Use longer timeout for extreme configurations
                    timeout = 60.0 if config['speed'] > 5000 else 30.0
                    if self.controller.wait_for_movement_complete(timeout=timeout):
                        final_status = self.controller.get_status()
                        if final_status and final_status.get('Position') == test_steps:
                            passed_tests += 1
                            self.log_test_result(test_name, True,
                                               f"Stress configuration successful, movement completed",
                                               duration=time.time() - stress_start)
                        else:
                            self.log_test_result(test_name, False,
                                               error="Position incorrect after stress test movement",
                                               duration=time.time() - stress_start)
                    else:
                        self.log_test_result(test_name, False,
                                           error="Movement timeout under stress configuration",
                                           duration=time.time() - stress_start)
                else:
                    self.log_test_result(test_name, False,
                                       error="Movement command failed under stress configuration",
                                       duration=time.time() - stress_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Stress Configurations", overall_passed,
                               f"Passed {passed_tests}/{total_tests} stress configuration tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Stress Configurations", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def test_boundary_conditions(self) -> bool:
        """Test boundary conditions and edge cases."""
        start_time = time.time()
        passed_tests = 0
        
        # First, ensure motor is completely stopped
        try:
            self.controller.emergency_stop()
            time.sleep(0.5)
        except:
            pass
        
        boundary_tests = [
            # Speed boundaries
            {"type": "speed", "value": 100, "description": "Minimum speed"},
            {"type": "speed", "value": 10000, "description": "Maximum speed"},
            
            # Invalid values (should fail gracefully)
            {"type": "speed", "value": 50, "description": "Below minimum speed", "should_fail": True},
            {"type": "speed", "value": 15000, "description": "Above maximum speed", "should_fail": True},
            {"type": "microsteps", "value": 3, "description": "Invalid microsteps", "should_fail": True},
            {"type": "microsteps", "value": 512, "description": "Invalid microsteps high", "should_fail": True},
            
            # Large movements (reduced size to prevent excessive test time)
            {"type": "movement", "value": 2000, "description": "Large positive movement"},
            {"type": "movement", "value": -2000, "description": "Large negative movement"},
        ]
        
        total_tests = len(boundary_tests)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Boundary Conditions", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            # Set reasonable defaults
            self.controller.set_speed(1000)
            self.controller.set_microsteps(16)
            self.controller.set_movement_type("CONTINUOUS")
            
            for test in boundary_tests:
                boundary_start = time.time()
                test_name = f"Boundary: {test['description']}"
                should_fail = test.get('should_fail', False)
                
                if test['type'] == 'speed':
                    result = self.controller.set_speed(test['value'])
                elif test['type'] == 'microsteps':
                    result = self.controller.set_microsteps(test['value'])
                elif test['type'] == 'movement':
                    self.controller.home_position()
                    time.sleep(0.5)
                    
                    # Emergency stop any ongoing movement first
                    self.controller.emergency_stop()
                    time.sleep(0.2)
                    
                    result = self.controller.move_steps(test['value'])
                    if result and not should_fail:
                        # Wait for large movement to complete with shorter timeout
                        result = self.controller.wait_for_movement_complete(timeout=30.0)
                        if result:
                            status = self.controller.get_status()
                            result = status and status.get('Position') == test['value']
                        else:
                            # Movement timed out - emergency stop and mark as failed
                            self.controller.emergency_stop()
                            time.sleep(0.5)
                            result = False
                else:
                    result = False
                
                # Check if result matches expectation
                test_passed = (not should_fail and result) or (should_fail and not result)
                
                if test_passed:
                    passed_tests += 1
                    expected_outcome = "failed as expected" if should_fail else "succeeded as expected"
                    self.log_test_result(test_name, True,
                                       f"Boundary test {expected_outcome}",
                                       duration=time.time() - boundary_start)
                else:
                    expected_outcome = "should have failed but succeeded" if should_fail else "should have succeeded but failed"
                    self.log_test_result(test_name, False,
                                       error=f"Boundary test {expected_outcome}",
                                       duration=time.time() - boundary_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Boundary Conditions", overall_passed,
                               f"Passed {passed_tests}/{total_tests} boundary tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Boundary Conditions", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            # Emergency stop to ensure motor stops moving
            try:
                self.controller.emergency_stop()
                time.sleep(0.5)
                self.controller.disable_motor()
            except:
                pass  # Ignore errors during cleanup
    
    def test_rapid_configuration_changes(self) -> bool:
        """Test rapid configuration changes and system stability."""
        start_time = time.time()
        passed_tests = 0
        
        # Rapid change scenarios
        rapid_scenarios = [
            {
                "name": "Speed Changes",
                "changes": [("speed", speed) for speed in [1000, 500, 2000, 100, 5000, 1000]],
                "movement_between": True
            },
            {
                "name": "Microstep Changes", 
                "changes": [("microsteps", ms) for ms in [16, 32, 8, 64, 4, 16]],
                "movement_between": True
            },
            {
                "name": "Movement Type Changes",
                "changes": [("movement", mt) for mt in ["STEALTH", "INTERPOLATED", "CONTINUOUS", "STEALTH"]],
                "movement_between": True
            },
            {
                "name": "Mixed Rapid Changes",
                "changes": [
                    ("speed", 500), ("microsteps", 32), ("movement", "STEALTH"),
                    ("speed", 1000), ("microsteps", 16), ("movement", "INTERPOLATED"),
                    ("speed", 2000), ("microsteps", 64), ("movement", "CONTINUOUS")
                ],
                "movement_between": False
            }
        ]
        
        total_tests = len(rapid_scenarios)
        
        try:
            if not self.controller.enable_motor():
                self.log_test_result("Rapid Configuration Changes", False,
                                   error="Failed to enable motor",
                                   duration=time.time() - start_time)
                return False
            
            for scenario in rapid_scenarios:
                rapid_start = time.time()
                test_name = f"Rapid {scenario['name']}"
                
                scenario_success = True
                self.controller.home_position()
                time.sleep(0.2)
                
                for change_type, value in scenario['changes']:
                    # Apply change rapidly
                    if change_type == "speed":
                        result = self.controller.set_speed(value)
                    elif change_type == "microsteps":
                        result = self.controller.set_microsteps(value)
                    elif change_type == "movement":
                        result = self.controller.set_movement_type(value)
                    
                    if not result:
                        scenario_success = False
                        break
                    
                    # Brief verification
                    status = self.controller.get_status()
                    if not status:
                        scenario_success = False
                        break
                    
                    # Verify the change was applied
                    if change_type == "speed" and status.get('Speed') != value:
                        scenario_success = False
                        break
                    elif change_type == "microsteps" and status.get('Microsteps') != value:
                        scenario_success = False
                        break
                    elif change_type == "movement" and status.get('Movement') != value:
                        scenario_success = False
                        break
                    
                    # Optional movement between changes
                    if scenario['movement_between']:
                        small_movement = 50
                        initial_pos = status.get('Position', 0)
                        if self.controller.move_steps(small_movement):
                            if not self.controller.wait_for_movement_complete(timeout=10.0):
                                scenario_success = False
                                break
                            final_status = self.controller.get_status()
                            if not final_status or final_status.get('Position') != initial_pos + small_movement:
                                scenario_success = False
                                break
                        else:
                            scenario_success = False
                            break
                    
                    # Very brief pause to not overwhelm the system
                    time.sleep(0.05)
                
                if scenario_success:
                    passed_tests += 1
                    self.log_test_result(test_name, True,
                                       f"Rapid configuration changes completed successfully",
                                       duration=time.time() - rapid_start)
                else:
                    self.log_test_result(test_name, False,
                                       error="Rapid configuration change sequence failed",
                                       duration=time.time() - rapid_start)
            
            overall_passed = passed_tests == total_tests
            self.log_test_result("Overall Rapid Configuration Changes", overall_passed,
                               f"Passed {passed_tests}/{total_tests} rapid change tests",
                               duration=time.time() - start_time)
            return overall_passed
            
        except Exception as e:
            self.log_test_result("Overall Rapid Configuration Changes", False,
                               error=str(e),
                               duration=time.time() - start_time)
            return False
        finally:
            self.controller.disable_motor()
    
    def run_all_tests(self) -> Dict:
        """Run all tests and return comprehensive results."""
        self.start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("ESP32 STEPPER MOTOR COMPREHENSIVE TEST SUITE")
        self.logger.info("=" * 60)
        
        test_functions = [
            self.test_basic_connection,
            self.test_motor_enable_disable,
            self.test_speed_settings,
            self.test_microstep_settings,
            self.test_movement_modes,
            self.test_basic_movements,
            self.test_precision_movements,
            self.test_speed_ramping,
            self.test_endurance_movements,
            self.test_combined_configurations,
            self.test_stress_configurations,
            self.test_boundary_conditions,
            self.test_rapid_configuration_changes
        ]
        
        try:
            for test_func in test_functions:
                test_func()
                time.sleep(0.5)  # Brief pause between tests
        
        except KeyboardInterrupt:
            self.logger.info("Test suite interrupted by user")
        
        except Exception as e:
            self.logger.error(f"Unexpected error during test suite: {e}")
        
        finally:
            try:
                self.controller.emergency_stop()
                self.controller.disable_motor()
                self.controller.disconnect()
            except:
                pass  # Ignore cleanup errors
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate comprehensive test report."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        passed_tests = [r for r in self.test_results if r['passed']]
        failed_tests = [r for r in self.test_results if not r['passed']]
        
        report = {
            'summary': {
                'total_tests': len(self.test_results),
                'passed': len(passed_tests),
                'failed': len(failed_tests),
                'success_rate': (len(passed_tests) / len(self.test_results) * 100) if self.test_results else 0,
                'total_duration': total_duration,
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat()
            },
            'test_results': self.test_results,
            'failed_tests': failed_tests,
            'configuration': {
                'test_speeds': self.test_speeds,
                'test_microsteps': self.test_microsteps,
                'test_movements': self.test_movements,
                'test_directions': self.test_directions,
                'endurance_test_steps': self.endurance_test_steps,
                'precision_test_steps': self.precision_test_steps,
                'speed_ramp_steps': self.speed_ramp_steps
            }
        }
        
        # Print summary
        self.logger.info("=" * 60)
        self.logger.info("TEST RESULTS SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Tests: {report['summary']['total_tests']}")
        self.logger.info(f"Passed: {report['summary']['passed']}")
        self.logger.info(f"Failed: {report['summary']['failed']}")
        self.logger.info(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        self.logger.info(f"Total Duration: {report['summary']['total_duration']:.2f} seconds")
        
        if failed_tests:
            self.logger.info("\nFAILED TESTS:")
            for test in failed_tests:
                self.logger.info(f"❌ {test['test_name']}: {test['error']}")
        
        # Save report to file
        report_filename = f"stepper_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2)
            self.logger.info(f"\nDetailed report saved to: {report_filename}")
        except Exception as e:
            self.logger.error(f"Could not save report to file: {e}")
        
        return report


def main():
    """Main function to run the test suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ESP32 Stepper Motor Test Suite')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baud rate (default: 115200)')
    
    args = parser.parse_args()
    
    # Create and run test suite
    test_suite = StepperTestSuite(port=args.port, baudrate=args.baudrate)
    report = test_suite.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if report['summary']['failed'] == 0 else 1
    exit(exit_code)


if __name__ == "__main__":
    main()