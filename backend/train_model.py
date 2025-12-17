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
import os
from datetime import datetime


class SeismicModelTrainer:
    """
    Trainer for the seismic AI classification model
    """

    def __init__(self):
        self.model = None
        self.training_data = []
        self.labels = []

    def load_training_data(self, filepath):
        """
        Load training data from JSON file

        Expected format:
        [
            {
                "horizontal_accel": 2.5,
                "total_accel": 3.1,
                "sound_level": 1500,
                "sound_correlated": false,
                "label": "genuine"  // or "false_alarm"
            },
            ...
        ]
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            print(f"✓ Loaded {len(data)} training samples from {filepath}")

            for sample in data:
                features = self.extract_features(sample)
                self.training_data.append(features)

                # Convert label to numeric: -1 for genuine, 1 for false alarm
                label = -1 if sample['label'] == 'genuine' else 1
                self.labels.append(label)

            return True

        except FileNotFoundError:
            print(f"✗ Error: File {filepath} not found")
            return False
        except json.JSONDecodeError:
            print(f"✗ Error: Invalid JSON in {filepath}")
            return False
        except Exception as e:
            print(f"✗ Error loading data: {e}")
            return False

    def extract_features(self, event_data):
        """
        Extract features from a seismic event
        """
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

    def train_model(self, contamination=0.1, n_estimators=100):
        """
        Train the Isolation Forest model

        Parameters:
            contamination: Expected proportion of anomalies (earthquakes)
            n_estimators: Number of trees in the forest
        """
        if len(self.training_data) < 10:
            print("✗ Error: Need at least 10 training samples")
            return False

        print(f"\n🤖 Training AI Model...")
        print(f"   Samples: {len(self.training_data)}")
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
            scores = cross_val_score(self.model, self.training_data, cv=3, scoring='accuracy')
            print(f"   Cross-validation accuracy: {scores.mean():.2%} (+/- {scores.std():.2%})")

        print("✓ Model training complete")
        return True

    def evaluate_model(self):
        """
        Evaluate the model on training data
        """
        if self.model is None:
            print("✗ Error: Model not trained yet")
            return

        predictions = self.model.predict(self.training_data)
        scores = self.model.score_samples(self.training_data)

        # Calculate accuracy
        correct = sum(1 for pred, label in zip(predictions, self.labels) if pred == label)
        accuracy = correct / len(predictions)

        # Count genuine vs false alarms
        genuine_count = sum(1 for label in self.labels if label == -1)
        false_alarm_count = len(self.labels) - genuine_count

        print(f"\n📊 Model Evaluation:")
        print(f"   Total Samples: {len(self.training_data)}")
        print(f"   Genuine Earthquakes: {genuine_count}")
        print(f"   False Alarms: {false_alarm_count}")
        print(f"   Training Accuracy: {accuracy:.2%}")

        # Show some example predictions
        print(f"\n🔍 Sample Predictions:")
        for i in range(min(5, len(self.training_data))):
            pred_label = "genuine" if predictions[i] == -1 else "false_alarm"
            actual_label = "genuine" if self.labels[i] == -1 else "false_alarm"
            confidence = abs(scores[i])
            match = "✓" if predictions[i] == self.labels[i] else "✗"
            print(f"   {match} Predicted: {pred_label:12} | Actual: {actual_label:12} | Confidence: {confidence:.3f}")

    def save_model(self, filepath='models/seismic_model.pkl'):
        """
        Save the trained model to disk
        """
        if self.model is None:
            print("✗ Error: No model to save")
            return False

        try:
            # Create models directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            joblib.dump(self.model, filepath)
            print(f"✓ Model saved to {filepath}")

            # Save metadata
            metadata = {
                'trained_at': datetime.now().isoformat(),
                'num_samples': len(self.training_data),
                'genuine_count': sum(1 for label in self.labels if label == -1),
                'false_alarm_count': sum(1 for label in self.labels if label == 1)
            }

            metadata_path = filepath.replace('.pkl', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"✓ Metadata saved to {metadata_path}")

            return True

        except Exception as e:
            print(f"✗ Error saving model: {e}")
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
                    print("  ✗ Invalid label. Use 'genuine' or 'false'")
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
                print(f"  ✓ Sample added ({sample_count} total)")

            except ValueError:
                print("  ✗ Invalid input. Please enter numeric values.")
            except KeyboardInterrupt:
                print("\n\n  Training interrupted.")
                break

        if sample_count > 0:
            print(f"\n✓ Collected {sample_count} training samples")
            return True
        else:
            print("\n✗ No samples collected")
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
        print("✗ Error: Must specify either --data or --interactive")
        return

    if not success:
        print("\n✗ Training failed - no data loaded")
        return

    # Train the model
    if trainer.train_model(contamination=args.contamination, n_estimators=args.estimators):
        # Evaluate the model
        trainer.evaluate_model()

        # Save the model
        trainer.save_model(args.output)

        print("\n" + "="*60)
        print("✓ Training Complete!")
        print("="*60)
        print(f"\nYou can now use the trained model in your QuakeSense backend.")
        print(f"The model will be automatically loaded on server startup.\n")


if __name__ == '__main__':
    main()
