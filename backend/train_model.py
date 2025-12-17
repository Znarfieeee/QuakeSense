"""
AI Model Training Script for QuakeSense
========================================

This script trains the seismic event classification model
using labeled historical data.

Usage:
    python train_model.py --data labeled_data.json
    python train_model.py --interactive
"""

import argparse
import json
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import cross_val_score
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
import os
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


class SeismicModelTrainer:
    """
    Trainer for the seismic AI classification model
    Uses 18-feature extraction for enhanced accuracy
    """

    def __init__(self):
        self.model = None
        self.training_data = []
        self.labels = []

        # Import FeatureExtractor for 18-feature support
        try:
            from ml.feature_extractor import FeatureExtractor
            self.feature_extractor = FeatureExtractor()
            self.use_18_features = True
            print("[OK] Using 18-feature extraction for enhanced accuracy")
        except ImportError:
            print("[WARNING] FeatureExtractor not found, falling back to 6 basic features")
            self.feature_extractor = None
            self.use_18_features = False

    def load_training_data(self, filepath):
        """
        Load training data from JSON file

        Supports two formats:
        1. Array of samples: [{...}, {...}]
        2. Metadata wrapper: {"metadata": {...}, "samples": [{...}, {...}]}
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Handle metadata wrapper format (from data collection scripts)
            if isinstance(data, dict) and 'samples' in data:
                samples = data['samples']
                if 'metadata' in data:
                    print(f"[METADATA] Source: {data['metadata'].get('source', 'unknown')}")
                    print(f"[METADATA] Sample count: {data['metadata'].get('sample_count', len(samples))}")
            else:
                # Handle plain array format
                samples = data if isinstance(data, list) else []

            print(f"[OK] Loaded {len(samples)} training samples from {filepath}")

            skipped = 0
            for sample in samples:
                # Extract features (18 or 6 depending on availability)
                features = self.extract_features(sample)

                if features is None:
                    skipped += 1
                    continue

                self.training_data.append(features)

                # Convert label to numeric: -1 for genuine, 1 for false alarm
                label = -1 if sample.get('label') == 'genuine' else 1
                self.labels.append(label)

            if skipped > 0:
                print(f"[WARNING] Skipped {skipped} samples due to missing features")

            print(f"[OK] Processed {len(self.training_data)} valid samples")

            return True

        except FileNotFoundError:
            print(f"[ERROR] File {filepath} not found")
            return False
        except json.JSONDecodeError:
            print(f"[ERROR] Invalid JSON in {filepath}")
            return False
        except Exception as e:
            print(f"[ERROR] Loading data failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def extract_features(self, event_data):
        """
        Extract features from a seismic event
        Uses 18 features if FeatureExtractor available, otherwise 6 basic features
        """
        if self.use_18_features and self.feature_extractor:
            # Use advanced 18-feature extraction
            try:
                features = self.feature_extractor.extract_all_features(event_data)
                return features.tolist() if hasattr(features, 'tolist') else list(features)
            except Exception as e:
                print(f"[WARNING] 18-feature extraction failed: {e}, falling back to 6 features")
                # Fall through to basic extraction

        # Basic 6-feature extraction (fallback)
        try:
            horizontal_accel = event_data.get('horizontal_accel', 0)
            total_accel = event_data.get('total_accel', 0)
            sound_level = event_data.get('sound_level', 0)
            sound_correlated = 1 if event_data.get('sound_correlated', False) else 0

            # Calculate acceleration to sound ratio
            accel_sound_ratio = horizontal_accel / max(sound_level, 1)

            features = [
                horizontal_accel,
                total_accel,
                sound_level,
                accel_sound_ratio,
                sound_correlated,
                0  # Rate of change (placeholder for first sample)
            ]

            return features
        except Exception as e:
            print(f"[ERROR] Feature extraction failed: {e}")
            return None

    def train_model(self, contamination=0.1, n_estimators=100):
        """
        Train the Isolation Forest model

        Parameters:
            contamination: Expected proportion of anomalies (earthquakes)
            n_estimators: Number of trees in the forest
        """
        if len(self.training_data) < 10:
            print("[ERROR] Need at least 10 training samples")
            return False

        num_features = len(self.training_data[0]) if self.training_data else 0

        print(f"\n[TRAIN] Training AI Model...")
        print(f"   Samples: {len(self.training_data)}")
        print(f"   Features: {num_features} ({'18-feature enhanced model' if num_features > 10 else '6-feature basic model'})")
        print(f"   Contamination: {contamination}")
        print(f"   Estimators: {n_estimators}")

        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=n_estimators
        )

        # Train the model
        self.model.fit(self.training_data)

        # Evaluate using cross-validation (if enough samples)
        if len(self.training_data) >= 20:
            try:
                scores = cross_val_score(self.model, self.training_data, cv=min(3, len(self.training_data) // 10), scoring='accuracy')
                print(f"   Cross-validation accuracy: {scores.mean():.2%} (+/- {scores.std():.2%})")
            except Exception as e:
                print(f"[WARNING] Cross-validation failed: {e}")

        print("[OK] Model training complete")
        return True

    def evaluate_model(self):
        """
        Evaluate the model on training data with comprehensive metrics
        """
        if self.model is None:
            print("[ERROR] Model not trained yet")
            return

        predictions = self.model.predict(self.training_data)
        scores = self.model.score_samples(self.training_data)

        # Calculate accuracy
        correct = sum(1 for pred, label in zip(predictions, self.labels) if pred == label)
        accuracy = correct / len(predictions)

        # Calculate precision, recall, F1-score
        # Note: -1 = genuine (positive class), 1 = false alarm (negative class)
        try:
            precision = precision_score(self.labels, predictions, pos_label=-1, zero_division=0)
            recall = recall_score(self.labels, predictions, pos_label=-1, zero_division=0)
            f1 = f1_score(self.labels, predictions, pos_label=-1, zero_division=0)

            # Confusion matrix
            cm = confusion_matrix(self.labels, predictions, labels=[-1, 1])
            true_positive = cm[0][0]  # Genuine predicted as genuine
            false_negative = cm[0][1]  # Genuine predicted as false alarm
            false_positive = cm[1][0]  # False alarm predicted as genuine
            true_negative = cm[1][1]  # False alarm predicted as false alarm

        except Exception as e:
            print(f"[WARNING] Could not calculate metrics: {e}")
            precision = recall = f1 = 0
            true_positive = false_negative = false_positive = true_negative = 0

        # Count genuine vs false alarms
        genuine_count = sum(1 for label in self.labels if label == -1)
        false_alarm_count = len(self.labels) - genuine_count

        print(f"\n{'='*60}")
        print("MODEL EVALUATION RESULTS")
        print(f"{'='*60}")

        print(f"\n[DATASET]")
        print(f"   Total Samples: {len(self.training_data)}")
        print(f"   Genuine Earthquakes: {genuine_count} ({100*genuine_count/len(self.labels):.1f}%)")
        print(f"   False Alarms: {false_alarm_count} ({100*false_alarm_count/len(self.labels):.1f}%)")

        print(f"\n[PERFORMANCE METRICS]")
        print(f"   Accuracy:  {accuracy:.2%}")
        print(f"   Precision: {precision:.2%}  (of predicted genuine, how many are actually genuine)")
        print(f"   Recall:    {recall:.2%}  (of actual genuine, how many were detected)")
        print(f"   F1-Score:  {f1:.2%}  (harmonic mean of precision and recall)")

        print(f"\n[CONFUSION MATRIX]")
        print(f"                    Predicted Genuine    Predicted False Alarm")
        print(f"   Actual Genuine:        {true_positive:5}                  {false_negative:5}")
        print(f"   Actual False:          {false_positive:5}                  {true_negative:5}")

        # Interpretation
        print(f"\n[INTERPRETATION]")
        if accuracy >= 0.90:
            print(f"   [EXCELLENT] Model achieves >90% accuracy")
        elif accuracy >= 0.80:
            print(f"   [GOOD] Model achieves 80-90% accuracy")
        elif accuracy >= 0.70:
            print(f"   [FAIR] Model achieves 70-80% accuracy")
        else:
            print(f"   [POOR] Model accuracy <70%, needs more training data")

        if false_positive > 0:
            print(f"   [WARNING] {false_positive} false alarms incorrectly classified as genuine")
        if false_negative > 0:
            print(f"   [WARNING] {false_negative} genuine earthquakes missed")

        # Show some example predictions
        print(f"\n[SAMPLE PREDICTIONS]")
        for i in range(min(5, len(self.training_data))):
            pred_label = "genuine" if predictions[i] == -1 else "false_alarm"
            actual_label = "genuine" if self.labels[i] == -1 else "false_alarm"
            confidence = abs(scores[i])
            match = "[OK]" if predictions[i] == self.labels[i] else "[MISS]"
            print(f"   {match} Predicted: {pred_label:12} | Actual: {actual_label:12} | Confidence: {confidence:.3f}")

        print(f"\n{'='*60}")

    def save_model(self, filepath='models/seismic_model.pkl'):
        """
        Save the trained model to disk
        """
        if self.model is None:
            print("[ERROR] No model to save")
            return False

        try:
            # Create models directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            joblib.dump(self.model, filepath)
            print(f"[OK] Model saved to {filepath}")

            # Calculate evaluation metrics for metadata
            predictions = self.model.predict(self.training_data)
            correct = sum(1 for pred, label in zip(predictions, self.labels) if pred == label)
            accuracy = correct / len(predictions)

            # Save metadata
            num_features = len(self.training_data[0]) if self.training_data else 0

            metadata = {
                'trained_at': datetime.now().isoformat(),
                'num_samples': len(self.training_data),
                'num_features': num_features,
                'model_type': '18-feature enhanced' if num_features > 10 else '6-feature basic',
                'genuine_count': sum(1 for label in self.labels if label == -1),
                'false_alarm_count': sum(1 for label in self.labels if label == 1),
                'training_accuracy': round(accuracy, 4),
                'sklearn_version': '1.5+',
                'algorithm': 'IsolationForest'
            }

            metadata_path = filepath.replace('.pkl', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"[OK] Metadata saved to {metadata_path}")

            return True

        except Exception as e:
            print(f"[ERROR] Saving model failed: {e}")
            return False

    def interactive_training(self):
        """
        Interactive mode for manually entering training data
        """
        print("\n" + "="*60)
        print("Interactive Training Mode")
        print("="*60)
        print("Enter seismic event data to train the model.")
        print("Type 'done' when finished entering samples.\n")

        sample_count = 0

        while True:
            print(f"\nSample #{sample_count + 1}:")

            cmd = input("  Continue? (press Enter to add sample, 'done' to finish): ").strip().lower()
            if cmd == 'done':
                break

            try:
                horizontal_accel = float(input("  Horizontal acceleration (m/s²): "))
                total_accel = float(input("  Total acceleration (m/s²): "))
                sound_level = int(input("  Sound level (0-4095): "))
                sound_corr = input("  Sound correlated? (y/n): ").strip().lower() == 'y'
                label = input("  Label (genuine/false): ").strip().lower()

                if label not in ['genuine', 'false']:
                    print("  [ERROR] Invalid label. Use 'genuine' or 'false'")
                    continue

                # Create event data
                event_data = {
                    'horizontal_accel': horizontal_accel,
                    'total_accel': total_accel,
                    'sound_level': sound_level,
                    'sound_correlated': sound_corr,
                    'label': label
                }

                # Extract features and add to training data
                features = self.extract_features(event_data)
                self.training_data.append(features)
                self.labels.append(-1 if label == 'genuine' else 1)

                sample_count += 1
                print(f"  [OK] Sample added ({sample_count} total)")

            except ValueError:
                print("  [ERROR] Invalid input. Please enter numeric values.")
            except KeyboardInterrupt:
                print("\n\n  Training interrupted.")
                break

        if sample_count > 0:
            print(f"\n[OK] Collected {sample_count} training samples")
            return True
        else:
            print("\n[ERROR] No samples collected")
            return False


def main():
    parser = argparse.ArgumentParser(description='Train QuakeSense AI model')
    parser.add_argument('--data', type=str, help='Path to labeled training data JSON file')
    parser.add_argument('--interactive', action='store_true', help='Interactive training mode')
    parser.add_argument('--contamination', type=float, default=0.1, help='Expected contamination ratio (default: 0.1)')
    parser.add_argument('--estimators', type=int, default=100, help='Number of estimators (default: 100)')
    parser.add_argument('--output', type=str, default='models/seismic_model.pkl', help='Output model path')

    args = parser.parse_args()

    trainer = SeismicModelTrainer()

    print("\n" + "="*60)
    print("QuakeSense AI Model Trainer")
    print("="*60)

    # Load or collect training data
    if args.interactive:
        success = trainer.interactive_training()
    elif args.data:
        success = trainer.load_training_data(args.data)
    else:
        print("[ERROR] Must specify either --data or --interactive")
        return

    if not success:
        print("\n[ERROR] Training failed - no data loaded")
        return

    # Train the model
    if trainer.train_model(contamination=args.contamination, n_estimators=args.estimators):
        # Evaluate the model
        trainer.evaluate_model()

        # Save the model
        trainer.save_model(args.output)

        print("\n" + "="*60)
        print("[SUCCESS] Training Complete!")
        print("="*60)
        print(f"\nYou can now use the trained model in your QuakeSense backend.")
        print(f"The model will be automatically loaded on server startup.\n")


if __name__ == '__main__':
    main()
