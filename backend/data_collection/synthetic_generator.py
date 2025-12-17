"""
Synthetic Earthquake Data Generator
Generates realistic earthquake and false alarm patterns for ML training

Generates:
- Genuine earthquakes with P/S wave patterns (1-10 Hz)
- False alarms: doors, footsteps, vehicles, construction (>10 Hz)

Usage:
    python data_collection/synthetic_generator.py --genuine-samples 3000 --false-alarm-samples 2000
    python data_collection/synthetic_generator.py --samples 5000 --output synthetic_training.json
"""

import numpy as np
from scipy import signal
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import random
import os


class SyntheticDataGenerator:
    """Generate synthetic earthquake and false alarm training data"""

    def __init__(self, sample_rate: int = 100):
        """
        Args:
            sample_rate: Sampling rate in Hz (samples per second)
        """
        self.sample_rate = sample_rate
        random.seed(42)  # For reproducibility
        np.random.seed(42)

    def generate_dataset(self,
                        genuine_count: int = 3000,
                        false_alarm_count: int = 2000) -> List[Dict]:
        """
        Generate complete synthetic dataset

        Args:
            genuine_count: Number of genuine earthquake samples
            false_alarm_count: Number of false alarm samples

        Returns:
            List of training samples
        """
        print(f"\n[SYNTHETIC] Generating synthetic training data...")
        print(f"  Genuine earthquakes: {genuine_count}")
        print(f"  False alarms: {false_alarm_count}")
        print(f"  Total samples: {genuine_count + false_alarm_count}")

        samples = []

        # Generate genuine earthquakes
        print("\n[SYNTHETIC] Generating genuine earthquakes...")
        for i in range(genuine_count):
            sample = self._generate_genuine_earthquake()
            samples.append(sample)

            if (i + 1) % 500 == 0:
                print(f"  Generated {i + 1}/{genuine_count} earthquakes...")

        # Generate false alarms
        print("\n[SYNTHETIC] Generating false alarms...")
        false_alarm_types = ['door_slam', 'footsteps', 'vehicle', 'construction']

        for i in range(false_alarm_count):
            alarm_type = random.choice(false_alarm_types)
            sample = self._generate_false_alarm(alarm_type)
            samples.append(sample)

            if (i + 1) % 500 == 0:
                print(f"  Generated {i + 1}/{false_alarm_count} false alarms...")

        # Shuffle dataset
        random.shuffle(samples)

        print(f"\n[OK] Generated {len(samples)} total samples")
        return samples

    def _generate_genuine_earthquake(self) -> Dict:
        """
        Generate realistic earthquake signature with P/S waves

        Earthquake characteristics:
        - Magnitude 2.0-7.0
        - P-wave arrives first (vertical, compression, ~6 km/s)
        - S-wave arrives later (horizontal, shear, ~3.5 km/s)
        - Frequency: 1-10 Hz (lower for larger quakes)
        - Duration: 200ms-5000ms (longer for larger quakes)
        - Low sound correlation (minimal airborne sound)
        """
        # Random magnitude between 2.0 and 7.0
        magnitude = random.uniform(2.0, 7.0)

        # Depth (affects surface acceleration)
        depth_km = random.uniform(0, 100)

        # Base acceleration from magnitude
        base_accel = 10 ** (magnitude - 3.5)

        # Depth attenuation
        if depth_km < 10:
            depth_factor = 1.0
        elif depth_km < 30:
            depth_factor = random.uniform(0.6, 0.8)
        elif depth_km < 70:
            depth_factor = random.uniform(0.3, 0.5)
        else:
            depth_factor = random.uniform(0.1, 0.3)

        adjusted_accel = base_accel * depth_factor

        # P-wave (vertical, arrives first, ~30% of energy)
        p_wave_strength = adjusted_accel * random.uniform(0.25, 0.35)

        # S-wave (horizontal, arrives later, ~70% of energy)
        s_wave_strength = adjusted_accel * random.uniform(0.65, 0.75)

        # Split S-wave into X/Y components
        angle = random.uniform(0, 2 * np.pi)
        x_accel = s_wave_strength * np.cos(angle)
        y_accel = s_wave_strength * np.sin(angle)
        z_accel = p_wave_strength  # Vertical component

        # Total accelerations
        horizontal_accel = (x_accel**2 + y_accel**2) ** 0.5
        total_accel = (horizontal_accel**2 + z_accel**2) ** 0.5
        peak_accel = total_accel * random.uniform(1.1, 1.3)

        # Frequency (larger quakes have lower frequencies)
        if magnitude < 3.0:
            frequency = random.uniform(7.0, 10.0)
        elif magnitude < 5.0:
            frequency = random.uniform(3.0, 6.0)
        else:
            frequency = random.uniform(1.0, 3.0)

        # Duration (larger quakes last longer)
        duration_ms = int(200 * (2 ** (magnitude - 2)) * random.uniform(0.8, 1.2))
        duration_ms = min(duration_ms, 5000)  # Cap at 5 seconds

        # Sound (earthquakes produce minimal sound relative to vibration)
        if magnitude > 6.0 and depth_km < 10:
            sound_level = int(random.uniform(400, 800))
        else:
            sound_level = int(random.uniform(50, 300))

        # Add noise to make it realistic
        noise_factor = random.uniform(0.9, 1.1)

        return {
            # Acceleration components
            'horizontal_accel': round(horizontal_accel * noise_factor, 3),
            'vertical_accel': round(z_accel * noise_factor, 3),
            'x_accel': round(x_accel * noise_factor, 3),
            'y_accel': round(y_accel * noise_factor, 3),
            'z_accel': round(z_accel * noise_factor, 3),
            'total_accel': round(total_accel * noise_factor, 3),
            'peak_ground_acceleration': round(peak_accel * noise_factor, 3),

            # Sound
            'sound_level': sound_level,
            'sound_correlated': False,  # Key: earthquakes don't correlate with sound

            # Frequency
            'frequency_dominant': round(frequency, 2),
            'frequency_mean': round(frequency * random.uniform(0.9, 1.1), 2),

            # Temporal
            'duration_ms': duration_ms,
            'wave_arrival_pattern': 'p_then_s',  # P wave then S wave
            'temporal_variance': round(horizontal_accel * random.uniform(0.1, 0.2), 3),

            # Wave detection
            'p_wave_detected': True,
            's_wave_detected': True,

            # Metadata
            'timestamp': int(datetime.now().timestamp()) - random.randint(0, 86400*365),
            'device_id': 'SYNTHETIC_GEN',
            'label': 'genuine',
            'source': 'synthetic',
            'synthetic_type': 'earthquake',
            'synthetic_magnitude': round(magnitude, 2),
            'synthetic_depth_km': round(depth_km, 1),
            'notes': f"Synthetic earthquake M{magnitude:.1f} at {depth_km:.0f}km depth"
        }

    def _generate_false_alarm(self, alarm_type: str) -> Dict:
        """
        Generate false alarm patterns

        Types:
        - door_slam: High sound, medium accel, short duration, high correlation
        - footsteps: Periodic spikes, short duration, sound correlated
        - vehicle: Low-frequency rumble, moderate sound, medium duration
        - construction: Random high-amplitude, highly variable, loud
        """
        if alarm_type == 'door_slam':
            return self._generate_door_slam()
        elif alarm_type == 'footsteps':
            return self._generate_footsteps()
        elif alarm_type == 'vehicle':
            return self._generate_vehicle()
        elif alarm_type == 'construction':
            return self._generate_construction()
        else:
            return self._generate_door_slam()  # Default

    def _generate_door_slam(self) -> Dict:
        """
        Door slam characteristics:
        - High sound (3000-4000)
        - Medium acceleration (1.5-2.5 m/s²)
        - Very short duration (50-150ms)
        - HIGH sound correlation (key discriminator!)
        - Single sharp peak, no P/S wave separation
        """
        accel = random.uniform(1.5, 2.5)
        sound = random.uniform(3000, 4000)

        # Random direction
        angle = random.uniform(0, 2 * np.pi)
        x = accel * np.cos(angle) * 0.7
        y = accel * np.sin(angle) * 0.7
        z = accel * 0.3  # Mostly horizontal

        return {
            'horizontal_accel': round(accel, 3),
            'vertical_accel': round(z, 3),
            'x_accel': round(x, 3),
            'y_accel': round(y, 3),
            'z_accel': round(z, 3),
            'total_accel': round((accel**2 + z**2)**0.5, 3),
            'peak_ground_acceleration': round(accel * 1.1, 3),

            'sound_level': int(sound),
            'sound_correlated': True,  # KEY: false alarms correlate with sound!

            'frequency_dominant': round(random.uniform(15.0, 30.0), 2),  # High frequency
            'frequency_mean': round(random.uniform(20.0, 35.0), 2),

            'duration_ms': int(random.uniform(50, 150)),
            'wave_arrival_pattern': 'single_peak',  # No P/S wave separation
            'temporal_variance': round(accel * 0.3, 3),

            'p_wave_detected': False,
            's_wave_detected': False,

            'timestamp': int(datetime.now().timestamp()) - random.randint(0, 86400*365),
            'device_id': 'SYNTHETIC_GEN',
            'label': 'false_alarm',
            'source': 'synthetic',
            'synthetic_type': 'door_slam',
            'notes': 'Synthetic false alarm: door slam'
        }

    def _generate_footsteps(self) -> Dict:
        """
        Footsteps characteristics:
        - Low-medium acceleration (0.8-1.5 m/s²)
        - Moderate sound (2000-3000)
        - Short duration (100-200ms)
        - Sound correlated
        - Periodic pattern (if multiple steps)
        """
        accel = random.uniform(0.8, 1.5)
        sound = random.uniform(2000, 3000)

        angle = random.uniform(0, 2 * np.pi)
        x = accel * np.cos(angle) * 0.8
        y = accel * np.sin(angle) * 0.8
        z = accel * 0.2

        return {
            'horizontal_accel': round(accel, 3),
            'vertical_accel': round(z, 3),
            'x_accel': round(x, 3),
            'y_accel': round(y, 3),
            'z_accel': round(z, 3),
            'total_accel': round((accel**2 + z**2)**0.5, 3),
            'peak_ground_acceleration': round(accel * 1.05, 3),

            'sound_level': int(sound),
            'sound_correlated': True,

            'frequency_dominant': round(random.uniform(10.0, 20.0), 2),
            'frequency_mean': round(random.uniform(12.0, 18.0), 2),

            'duration_ms': int(random.uniform(100, 200)),
            'wave_arrival_pattern': 'single_peak',
            'temporal_variance': round(accel * 0.25, 3),

            'p_wave_detected': False,
            's_wave_detected': False,

            'timestamp': int(datetime.now().timestamp()) - random.randint(0, 86400*365),
            'device_id': 'SYNTHETIC_GEN',
            'label': 'false_alarm',
            'source': 'synthetic',
            'synthetic_type': 'footsteps',
            'notes': 'Synthetic false alarm: footsteps'
        }

    def _generate_vehicle(self) -> Dict:
        """
        Vehicle (truck/car) characteristics:
        - Low-medium acceleration (1.0-2.0 m/s²)
        - Low-medium sound (1500-2500)
        - Medium duration (300-800ms)
        - Some sound correlation
        - Low frequency rumble (5-15 Hz)
        """
        accel = random.uniform(1.0, 2.0)
        sound = random.uniform(1500, 2500)

        angle = random.uniform(0, 2 * np.pi)
        x = accel * np.cos(angle) * 0.9
        y = accel * np.sin(angle) * 0.9
        z = accel * 0.1

        return {
            'horizontal_accel': round(accel, 3),
            'vertical_accel': round(z, 3),
            'x_accel': round(x, 3),
            'y_accel': round(y, 3),
            'z_accel': round(z, 3),
            'total_accel': round((accel**2 + z**2)**0.5, 3),
            'peak_ground_acceleration': round(accel * 1.15, 3),

            'sound_level': int(sound),
            'sound_correlated': random.choice([True, False]),  # Variable

            'frequency_dominant': round(random.uniform(5.0, 15.0), 2),
            'frequency_mean': round(random.uniform(8.0, 12.0), 2),

            'duration_ms': int(random.uniform(300, 800)),
            'wave_arrival_pattern': 'single_peak',
            'temporal_variance': round(accel * 0.2, 3),

            'p_wave_detected': False,
            's_wave_detected': False,

            'timestamp': int(datetime.now().timestamp()) - random.randint(0, 86400*365),
            'device_id': 'SYNTHETIC_GEN',
            'label': 'false_alarm',
            'source': 'synthetic',
            'synthetic_type': 'vehicle',
            'notes': 'Synthetic false alarm: vehicle passing'
        }

    def _generate_construction(self) -> Dict:
        """
        Construction noise characteristics:
        - High acceleration (2.0-4.0 m/s²)
        - Very high sound (3500-4095)
        - Variable duration (200-1000ms)
        - HIGH sound correlation
        - High frequency impacts (20-40 Hz)
        """
        accel = random.uniform(2.0, 4.0)
        sound = random.uniform(3500, 4095)

        angle = random.uniform(0, 2 * np.pi)
        x = accel * np.cos(angle) * 0.85
        y = accel * np.sin(angle) * 0.85
        z = accel * 0.15

        return {
            'horizontal_accel': round(accel, 3),
            'vertical_accel': round(z, 3),
            'x_accel': round(x, 3),
            'y_accel': round(y, 3),
            'z_accel': round(z, 3),
            'total_accel': round((accel**2 + z**2)**0.5, 3),
            'peak_ground_acceleration': round(accel * 1.25, 3),

            'sound_level': int(sound),
            'sound_correlated': True,  # Very correlated!

            'frequency_dominant': round(random.uniform(20.0, 40.0), 2),
            'frequency_mean': round(random.uniform(25.0, 35.0), 2),

            'duration_ms': int(random.uniform(200, 1000)),
            'wave_arrival_pattern': 'single_peak',
            'temporal_variance': round(accel * 0.4, 3),

            'p_wave_detected': False,
            's_wave_detected': False,

            'timestamp': int(datetime.now().timestamp()) - random.randint(0, 86400*365),
            'device_id': 'SYNTHETIC_GEN',
            'label': 'false_alarm',
            'source': 'synthetic',
            'synthetic_type': 'construction',
            'notes': 'Synthetic false alarm: construction noise'
        }

    def save_to_json(self, samples: List[Dict], output_path: str):
        """Save samples to JSON"""
        try:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

            # Count labels
            genuine_count = sum(1 for s in samples if s['label'] == 'genuine')
            false_alarm_count = sum(1 for s in samples if s['label'] == 'false_alarm')

            with open(output_path, 'w') as f:
                json.dump({
                    'metadata': {
                        'source': 'Synthetic Data Generator',
                        'generated_at': datetime.now().isoformat(),
                        'sample_count': len(samples),
                        'genuine_earthquakes': genuine_count,
                        'false_alarms': false_alarm_count,
                        'sample_rate_hz': self.sample_rate
                    },
                    'samples': samples
                }, f, indent=2)

            print(f"\n[OK] Saved {len(samples)} samples to {output_path}")
            print(f"  - Genuine: {genuine_count}")
            print(f"  - False alarms: {false_alarm_count}")

        except IOError as e:
            print(f"[ERROR] Failed to save file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate synthetic earthquake and false alarm training data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 5000 samples (balanced)
  python synthetic_generator.py --samples 5000

  # Generate custom split
  python synthetic_generator.py --genuine-samples 3000 --false-alarm-samples 2000

  # Generate large dataset
  python synthetic_generator.py --samples 10000 --output large_synthetic.json
        """
    )

    parser.add_argument(
        '--samples',
        type=int,
        default=None,
        help='Total samples to generate (split 60/40 genuine/false)'
    )

    parser.add_argument(
        '--genuine-samples',
        type=int,
        default=None,
        help='Number of genuine earthquake samples'
    )

    parser.add_argument(
        '--false-alarm-samples',
        type=int,
        default=None,
        help='Number of false alarm samples'
    )

    parser.add_argument(
        '--output',
        default='synthetic_training.json',
        help='Output file path (default: synthetic_training.json)'
    )

    parser.add_argument(
        '--sample-rate',
        type=int,
        default=100,
        help='Sampling rate in Hz (default: 100)'
    )

    args = parser.parse_args()

    # Determine sample counts
    if args.samples:
        # Split 60% genuine, 40% false alarms (slight imbalance like real world)
        genuine_count = int(args.samples * 0.6)
        false_alarm_count = args.samples - genuine_count
    elif args.genuine_samples and args.false_alarm_samples:
        genuine_count = args.genuine_samples
        false_alarm_count = args.false_alarm_samples
    else:
        # Default: 3000 genuine, 2000 false alarms
        genuine_count = 3000
        false_alarm_count = 2000

    print("\n" + "="*60)
    print("Synthetic Data Generator")
    print("="*60)

    generator = SyntheticDataGenerator(sample_rate=args.sample_rate)

    samples = generator.generate_dataset(
        genuine_count=genuine_count,
        false_alarm_count=false_alarm_count
    )

    if samples:
        generator.save_to_json(samples, args.output)

        print(f"\n{'='*60}")
        print("[SUCCESS] Synthetic Data Generation Complete")
        print(f"{'='*60}")
        print(f"  Total: {len(samples)} samples")
        print(f"  Genuine: {genuine_count} ({genuine_count/len(samples)*100:.1f}%)")
        print(f"  False alarms: {false_alarm_count} ({false_alarm_count/len(samples)*100:.1f}%)")
        print(f"  Output: {args.output}")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
