"""
Dataset Merger for QuakeSense Training Data
Merges multiple training data sources (USGS, PHIVOLCS, synthetic) into balanced dataset

Usage:
    python data_collection/merge_datasets.py --input usgs.json phivolcs.json synthetic.json --output final_training.json
    python data_collection/merge_datasets.py --input *.json --output merged.json --balance-classes
    python data_collection/merge_datasets.py --input synthetic.json --output training.json --genuine-ratio 0.6
"""

import json
import argparse
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from collections import Counter


class DatasetMerger:
    """Merge and balance training datasets from multiple sources"""

    def __init__(self):
        self.all_samples = []
        self.source_stats = {}

    def load_json_file(self, file_path: str) -> List[Dict]:
        """
        Load samples from a JSON file

        Expected format:
        {
            "metadata": {...},
            "samples": [...]
        }
        """
        try:
            print(f"\n[LOAD] Reading {file_path}...")

            with open(file_path, 'r') as f:
                data = json.load(f)

            if 'samples' not in data:
                print(f"   [WARNING] File missing 'samples' key, treating as array")
                samples = data if isinstance(data, list) else []
            else:
                samples = data['samples']

            # Extract source from metadata or filename
            source = 'unknown'
            if 'metadata' in data and 'source' in data['metadata']:
                source = data['metadata']['source']
            else:
                source = Path(file_path).stem

            # Track statistics
            genuine_count = sum(1 for s in samples if s.get('label') == 'genuine')
            false_alarm_count = sum(1 for s in samples if s.get('label') == 'false_alarm')

            self.source_stats[source] = {
                'total': len(samples),
                'genuine': genuine_count,
                'false_alarms': false_alarm_count,
                'file': file_path
            }

            print(f"   [OK] Loaded {len(samples)} samples from {source}")
            print(f"        Genuine: {genuine_count}, False alarms: {false_alarm_count}")

            return samples

        except FileNotFoundError:
            print(f"   [ERROR] File not found: {file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"   [ERROR] Invalid JSON in {file_path}: {e}")
            return []
        except Exception as e:
            print(f"   [ERROR] Failed to load {file_path}: {e}")
            return []

    def load_multiple_files(self, file_paths: List[str]) -> List[Dict]:
        """Load samples from multiple JSON files"""
        all_samples = []

        for file_path in file_paths:
            samples = self.load_json_file(file_path)
            all_samples.extend(samples)

        self.all_samples = all_samples
        return all_samples

    def balance_classes(self, samples: List[Dict], genuine_ratio: float = 0.5) -> List[Dict]:
        """
        Balance the dataset to have specified ratio of genuine earthquakes

        Args:
            samples: List of training samples
            genuine_ratio: Ratio of genuine earthquakes (default: 0.5 for 50/50)

        Returns:
            Balanced dataset
        """
        print(f"\n[BALANCE] Balancing dataset to {genuine_ratio:.0%} genuine / {1-genuine_ratio:.0%} false alarms...")

        # Separate by label
        genuine_samples = [s for s in samples if s.get('label') == 'genuine']
        false_alarm_samples = [s for s in samples if s.get('label') == 'false_alarm']

        print(f"   Available: {len(genuine_samples)} genuine, {len(false_alarm_samples)} false alarms")

        # Calculate target counts
        if genuine_ratio >= 0.5:
            # More genuine or equal
            target_genuine = len(genuine_samples)
            target_false_alarms = int(target_genuine * (1 - genuine_ratio) / genuine_ratio)
        else:
            # More false alarms
            target_false_alarms = len(false_alarm_samples)
            target_genuine = int(target_false_alarms * genuine_ratio / (1 - genuine_ratio))

        # Ensure we have enough samples
        if len(genuine_samples) < target_genuine:
            print(f"   [WARNING] Not enough genuine samples ({len(genuine_samples)} < {target_genuine})")
            target_genuine = len(genuine_samples)
            target_false_alarms = int(target_genuine * (1 - genuine_ratio) / genuine_ratio)

        if len(false_alarm_samples) < target_false_alarms:
            print(f"   [WARNING] Not enough false alarm samples ({len(false_alarm_samples)} < {target_false_alarms})")
            target_false_alarms = len(false_alarm_samples)
            target_genuine = int(target_false_alarms * genuine_ratio / (1 - genuine_ratio))

        # Sample from each class
        selected_genuine = random.sample(genuine_samples, min(target_genuine, len(genuine_samples)))
        selected_false_alarms = random.sample(false_alarm_samples, min(target_false_alarms, len(false_alarm_samples)))

        balanced = selected_genuine + selected_false_alarms

        print(f"   [OK] Balanced dataset: {len(selected_genuine)} genuine + {len(selected_false_alarms)} false alarms = {len(balanced)} total")
        print(f"        Actual ratio: {len(selected_genuine)/len(balanced):.1%} genuine / {len(selected_false_alarms)/len(balanced):.1%} false alarms")

        return balanced

    def shuffle_dataset(self, samples: List[Dict]) -> List[Dict]:
        """Shuffle dataset randomly"""
        print(f"\n[SHUFFLE] Randomizing sample order...")
        shuffled = samples.copy()
        random.shuffle(shuffled)
        print(f"   [OK] Shuffled {len(shuffled)} samples")
        return shuffled

    def validate_samples(self, samples: List[Dict]) -> List[Dict]:
        """
        Validate samples and remove invalid ones

        Checks for:
        - Required fields
        - Valid data types
        - Reasonable value ranges
        """
        print(f"\n[VALIDATE] Checking {len(samples)} samples for completeness...")

        required_fields = [
            'horizontal_accel', 'total_accel', 'sound_level', 'label'
        ]

        valid_samples = []
        invalid_count = 0

        for idx, sample in enumerate(samples):
            # Check required fields
            missing_fields = [field for field in required_fields if field not in sample]
            if missing_fields:
                invalid_count += 1
                if invalid_count <= 5:  # Only show first 5 errors
                    print(f"   [WARNING] Sample {idx} missing fields: {missing_fields}")
                continue

            # Check label validity
            if sample['label'] not in ['genuine', 'false_alarm']:
                invalid_count += 1
                if invalid_count <= 5:
                    print(f"   [WARNING] Sample {idx} has invalid label: {sample['label']}")
                continue

            # Check reasonable ranges
            if not (0 <= sample.get('horizontal_accel', 0) <= 1000):
                invalid_count += 1
                continue

            if not (0 <= sample.get('sound_level', 0) <= 4095):
                invalid_count += 1
                continue

            valid_samples.append(sample)

        if invalid_count > 5:
            print(f"   [WARNING] ...and {invalid_count - 5} more invalid samples")

        print(f"   [OK] Valid: {len(valid_samples)}, Invalid: {invalid_count}")

        return valid_samples

    def get_statistics(self, samples: List[Dict]) -> Dict:
        """Calculate comprehensive statistics about the dataset"""
        stats = {
            'total_samples': len(samples),
            'labels': Counter(s.get('label', 'unknown') for s in samples),
            'sources': Counter(s.get('source', 'unknown') for s in samples),
            'has_verification': sum(1 for s in samples if s.get('verified', False)),
        }

        # Magnitude statistics (for genuine earthquakes with verification)
        verified_magnitudes = [
            s['verified_magnitude']
            for s in samples
            if s.get('label') == 'genuine' and 'verified_magnitude' in s
        ]

        if verified_magnitudes:
            stats['magnitude'] = {
                'count': len(verified_magnitudes),
                'min': round(min(verified_magnitudes), 1),
                'max': round(max(verified_magnitudes), 1),
                'mean': round(sum(verified_magnitudes) / len(verified_magnitudes), 1)
            }

        # Feature completeness (18 features)
        all_features = [
            'horizontal_accel', 'total_accel', 'vertical_accel',
            'x_accel', 'y_accel', 'z_accel',
            'sound_level', 'sound_correlated',
            'peak_ground_acceleration', 'frequency_dominant', 'frequency_mean',
            'duration_ms', 'wave_arrival_pattern',
            'p_wave_detected', 's_wave_detected',
            'temporal_variance'
        ]

        feature_counts = {
            feature: sum(1 for s in samples if feature in s)
            for feature in all_features
        }

        # Calculate completeness percentage
        completeness = {
            feature: round(100 * count / len(samples), 1)
            for feature, count in feature_counts.items()
        }

        stats['feature_completeness'] = completeness

        return stats

    def print_statistics(self, stats: Dict):
        """Print formatted statistics"""
        print("\n" + "=" * 60)
        print("DATASET STATISTICS")
        print("=" * 60)

        print(f"\n[TOTAL] {stats['total_samples']} samples")

        print(f"\n[LABELS]")
        for label, count in stats['labels'].items():
            percentage = 100 * count / stats['total_samples']
            print(f"   {label}: {count} ({percentage:.1f}%)")

        print(f"\n[SOURCES]")
        for source, count in stats['sources'].items():
            percentage = 100 * count / stats['total_samples']
            print(f"   {source}: {count} ({percentage:.1f}%)")

        print(f"\n[VERIFICATION]")
        print(f"   Verified events: {stats['has_verification']}")

        if 'magnitude' in stats:
            mag = stats['magnitude']
            print(f"\n[MAGNITUDE] (verified earthquakes only)")
            print(f"   Count: {mag['count']}")
            print(f"   Range: M{mag['min']} - M{mag['max']}")
            print(f"   Mean: M{mag['mean']}")

        # Show feature completeness summary (only features <100%)
        incomplete_features = {
            feature: pct
            for feature, pct in stats['feature_completeness'].items()
            if pct < 100
        }

        if incomplete_features:
            print(f"\n[FEATURE COMPLETENESS] (incomplete features only)")
            for feature, pct in incomplete_features.items():
                print(f"   {feature}: {pct}%")
        else:
            print(f"\n[FEATURE COMPLETENESS]")
            print(f"   All 18 features: 100% complete")

        print("\n" + "=" * 60)

    def save_to_json(self, samples: List[Dict], output_path: str):
        """Save merged dataset to JSON file"""
        print(f"\n[SAVE] Writing to {output_path}...")

        try:
            # Calculate statistics for metadata
            stats = self.get_statistics(samples)

            output_data = {
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'sample_count': len(samples),
                    'sources': list(self.source_stats.keys()),
                    'source_breakdown': self.source_stats,
                    'label_distribution': dict(stats['labels']),
                    'note': 'Merged training dataset for QuakeSense ML model'
                },
                'samples': samples
            }

            # Create output directory if needed
            output_dir = Path(output_path).parent
            if output_dir and not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)

            # Write JSON
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)

            print(f"   [OK] Saved {len(samples)} samples to {output_path}")

            # Print file size
            file_size = Path(output_path).stat().st_size
            if file_size > 1024 * 1024:
                print(f"   File size: {file_size / (1024 * 1024):.1f} MB")
            else:
                print(f"   File size: {file_size / 1024:.1f} KB")

        except IOError as e:
            print(f"   [ERROR] Failed to save file: {e}")
        except Exception as e:
            print(f"   [ERROR] Unexpected error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Merge multiple QuakeSense training datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge all JSON files in current directory
  python merge_datasets.py --input *.json --output merged_training.json

  # Merge specific sources with balancing
  python merge_datasets.py \\
    --input usgs_training.json phivolcs_training.json synthetic_training.json \\
    --output final_training.json \\
    --balance-classes

  # Create dataset with 60% genuine earthquakes
  python merge_datasets.py \\
    --input synthetic_training.json \\
    --output training.json \\
    --balance-classes \\
    --genuine-ratio 0.6

  # Merge without balancing or shuffling
  python merge_datasets.py \\
    --input data1.json data2.json \\
    --output combined.json \\
    --no-balance \\
    --no-shuffle
        """
    )

    parser.add_argument(
        '--input',
        nargs='+',
        required=True,
        help='Input JSON files to merge (space-separated)'
    )

    parser.add_argument(
        '--output',
        default='merged_training.json',
        help='Output file path (default: merged_training.json)'
    )

    parser.add_argument(
        '--balance-classes',
        action='store_true',
        help='Balance genuine/false alarm ratio'
    )

    parser.add_argument(
        '--no-balance',
        action='store_true',
        help='Skip class balancing (use all samples)'
    )

    parser.add_argument(
        '--genuine-ratio',
        type=float,
        default=0.5,
        help='Ratio of genuine earthquakes when balancing (default: 0.5)'
    )

    parser.add_argument(
        '--shuffle',
        action='store_true',
        default=True,
        help='Shuffle samples (default: True)'
    )

    parser.add_argument(
        '--no-shuffle',
        action='store_true',
        help='Skip shuffling'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        default=True,
        help='Validate samples before merging (default: True)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    # Set random seed if specified
    if args.seed is not None:
        random.seed(args.seed)
        print(f"[SEED] Using random seed: {args.seed}")

    print("\n" + "=" * 60)
    print("QuakeSense Dataset Merger")
    print("=" * 60)

    # Create merger
    merger = DatasetMerger()

    # Load all input files
    print(f"\n[INPUT] Loading {len(args.input)} file(s)...")
    samples = merger.load_multiple_files(args.input)

    if not samples:
        print("\n[ERROR] No samples loaded. Exiting.")
        return

    print(f"\n[OK] Total samples loaded: {len(samples)}")

    # Validate samples
    if args.validate:
        samples = merger.validate_samples(samples)

    # Balance classes if requested
    if args.balance_classes and not args.no_balance:
        samples = merger.balance_classes(samples, genuine_ratio=args.genuine_ratio)
    elif args.no_balance:
        print("\n[SKIP] Class balancing disabled")

    # Shuffle if requested
    if args.shuffle and not args.no_shuffle:
        samples = merger.shuffle_dataset(samples)
    elif args.no_shuffle:
        print("\n[SKIP] Shuffling disabled")

    # Calculate and print statistics
    stats = merger.get_statistics(samples)
    merger.print_statistics(stats)

    # Save merged dataset
    merger.save_to_json(samples, args.output)

    print("\n" + "=" * 60)
    print("[SUCCESS] Dataset Merge Complete")
    print("=" * 60)
    print(f"\nOutput: {args.output}")
    print(f"Total samples: {len(samples)}")
    print(f"Ready for training: python train_model.py --data {args.output}")
    print("\n" + "=" * 60 + "\n")


if __name__ == '__main__':
    main()
