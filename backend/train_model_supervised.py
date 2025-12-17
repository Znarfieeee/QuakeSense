"""
Supervised AI Model Training Script for QuakeSense
Uses Random Forest Classifier for better accuracy with labeled data

Usage:
    python train_model_supervised.py --data final_training_data.json
"""

import argparse
import json
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import os
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


class SupervisedSeismicTrainer:
    """
    Supervised trainer using Random Forest Classifier
    Designed for balanced binary classification with labeled data
    """

    def __init__(self):
        self.model = None
        self.training_data = []
        self.labels = []
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None

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
        """Load training data from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Handle metadata wrapper format
            if isinstance(data, dict) and 'samples' in data:
                samples = data['samples']
                if 'metadata' in data:
                    print(f"[METADATA] Source: {data['metadata'].get('source', 'unknown')}")
                    print(f"[METADATA] Sample count: {data['metadata'].get('sample_count', len(samples))}")
            else:
                samples = data if isinstance(data, list) else []

            print(f"[OK] Loaded {len(samples)} training samples from {filepath}")

            skipped = 0
            for sample in samples:
                features = self.extract_features(sample)

                if features is None:
                    skipped += 1
                    continue

                self.training_data.append(features)

                # Convert label to numeric: 1 for genuine, 0 for false alarm
                label = 1 if sample.get('label') == 'genuine' else 0
                self.labels.append(label)

            if skipped > 0:
                print(f"[WARNING] Skipped {skipped} samples due to missing features")

            print(f"[OK] Processed {len(self.training_data)} valid samples")

            return True

        except Exception as e:
            print(f"[ERROR] Loading data failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def extract_features(self, event_data):
        """Extract features from seismic event"""
        if self.use_18_features and self.feature_extractor:
            try:
                features = self.feature_extractor.extract_all_features(event_data)
                return features.tolist() if hasattr(features, 'tolist') else list(features)
            except Exception as e:
                print(f"[WARNING] 18-feature extraction failed: {e}")

        # Basic 6-feature extraction (fallback)
        try:
            horizontal_accel = event_data.get('horizontal_accel', 0)
            total_accel = event_data.get('total_accel', 0)
            sound_level = event_data.get('sound_level', 0)
            sound_correlated = 1 if event_data.get('sound_correlated', False) else 0

            accel_sound_ratio = horizontal_accel / max(sound_level, 1)

            features = [
                horizontal_accel,
                total_accel,
                sound_level,
                accel_sound_ratio,
                sound_correlated,
                0  # Rate of change placeholder
            ]

            return features
        except Exception as e:
            print(f"[ERROR] Feature extraction failed: {e}")
            return None

    def split_data(self, test_size=0.2, random_state=42):
        """Split data into training and testing sets"""
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            self.training_data,
            self.labels,
            test_size=test_size,
            random_state=random_state,
            stratify=self.labels  # Maintain class distribution
        )

        print(f"\n[SPLIT] Data split into training and testing sets:")
        print(f"   Training: {len(self.X_train)} samples")
        print(f"   Testing: {len(self.X_test)} samples")
        print(f"   Test size: {test_size:.0%}")

    def train_model(self, n_estimators=200, max_depth=None, min_samples_split=2):
        """Train Random Forest Classifier"""
        if len(self.training_data) < 10:
            print("[ERROR] Need at least 10 training samples")
            return False

        num_features = len(self.training_data[0]) if self.training_data else 0

        print(f"\n[TRAIN] Training Random Forest Classifier...")
        print(f"   Total samples: {len(self.training_data)}")
        print(f"   Features: {num_features} ({'18-feature enhanced model' if num_features > 10 else '6-feature basic model'})")
        print(f"   Estimators: {n_estimators}")
        print(f"   Max depth: {max_depth if max_depth else 'unlimited'}")

        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=42,
            n_jobs=-1,  # Use all CPU cores
            class_weight='balanced'  # Handle class imbalance
        )

        # Train the model
        self.model.fit(self.X_train, self.y_train)

        # Cross-validation on training set
        if len(self.X_train) >= 20:
            try:
                cv_scores = cross_val_score(self.model, self.X_train, self.y_train, cv=5, scoring='accuracy')
                print(f"   Cross-validation accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")
            except Exception as e:
                print(f"[WARNING] Cross-validation failed: {e}")

        print("[OK] Model training complete")
        return True

    def evaluate_model(self):
        """Comprehensive model evaluation"""
        if self.model is None:
            print("[ERROR] Model not trained yet")
            return

        # Predictions on test set
        y_pred = self.model.predict(self.X_test)
        y_pred_train = self.model.predict(self.X_train)

        # Calculate metrics
        test_accuracy = accuracy_score(self.y_test, y_pred)
        train_accuracy = accuracy_score(self.y_train, y_pred_train)

        # Confusion matrix
        cm = confusion_matrix(self.y_test, y_pred, labels=[1, 0])
        true_positive = cm[0][0]  # Genuine predicted as genuine
        false_negative = cm[0][1]  # Genuine predicted as false alarm
        false_positive = cm[1][0]  # False alarm predicted as genuine
        true_negative = cm[1][1]  # False alarm predicted as false alarm

        # Calculate additional metrics
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Count distribution
        genuine_count_test = sum(self.y_test)
        false_alarm_count_test = len(self.y_test) - genuine_count_test

        print(f"\n{'='*60}")
        print("MODEL EVALUATION RESULTS")
        print(f"{'='*60}")

        print(f"\n[TEST SET]")
        print(f"   Total Samples: {len(self.X_test)}")
        print(f"   Genuine Earthquakes: {genuine_count_test}")
        print(f"   False Alarms: {false_alarm_count_test}")

        print(f"\n[PERFORMANCE METRICS]")
        print(f"   Training Accuracy: {train_accuracy:.2%}")
        print(f"   Testing Accuracy:  {test_accuracy:.2%}")
        print(f"   Precision: {precision:.2%}  (of predicted genuine, how many are actually genuine)")
        print(f"   Recall:    {recall:.2%}  (of actual genuine, how many were detected)")
        print(f"   F1-Score:  {f1:.2%}  (harmonic mean of precision and recall)")

        print(f"\n[CONFUSION MATRIX]")
        print(f"                    Predicted Genuine    Predicted False Alarm")
        print(f"   Actual Genuine:        {true_positive:5}                  {false_negative:5}")
        print(f"   Actual False:          {false_positive:5}                  {true_negative:5}")

        # Interpretation
        print(f"\n[INTERPRETATION]")
        if test_accuracy >= 0.90:
            print(f"   [EXCELLENT] Model achieves >90% test accuracy")
        elif test_accuracy >= 0.80:
            print(f"   [GOOD] Model achieves 80-90% test accuracy")
        elif test_accuracy >= 0.70:
            print(f"   [FAIR] Model achieves 70-80% test accuracy")
        else:
            print(f"   [POOR] Model test accuracy <70%, needs improvement")

        if false_positive > 0:
            print(f"   [WARNING] {false_positive} false alarms incorrectly classified as genuine")
        if false_negative > 0:
            print(f"   [WARNING] {false_negative} genuine earthquakes missed")

        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            print(f"\n[FEATURE IMPORTANCE] (Top 5)")
            feature_names = self._get_feature_names()
            sorted_idx = np.argsort(importances)[::-1]
            for i in range(min(5, len(importances))):
                idx = sorted_idx[i]
                print(f"   {i+1}. {feature_names[idx]}: {importances[idx]:.3f}")

        print(f"\n{'='*60}")

        # Classification report
        print(f"\n[DETAILED CLASSIFICATION REPORT]")
        target_names = ['False Alarm', 'Genuine Earthquake']
        print(classification_report(self.y_test, y_pred, target_names=target_names))

        return test_accuracy

    def _get_feature_names(self):
        """Get feature names for display"""
        if self.use_18_features:
            return [
                'horizontal_accel', 'total_accel', 'sound_level', 'accel_sound_ratio',
                'sound_correlated', 'rate_of_change', 'vertical_accel', 'x_accel',
                'y_accel', 'z_accel', 'peak_ground_accel', 'frequency_dominant',
                'frequency_mean', 'duration_ms', 'wave_arrival_pattern',
                'p_wave_detected', 's_wave_detected', 'temporal_variance'
            ]
        else:
            return [
                'horizontal_accel', 'total_accel', 'sound_level',
                'accel_sound_ratio', 'sound_correlated', 'rate_of_change'
            ]

    def save_model(self, filepath='models/seismic_model_rf.pkl'):
        """Save the trained model"""
        if self.model is None:
            print("[ERROR] No model to save")
            return False

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            joblib.dump(self.model, filepath)
            print(f"\n[OK] Model saved to {filepath}")

            # Calculate metrics
            y_pred = self.model.predict(self.X_test)
            test_accuracy = accuracy_score(self.y_test, y_pred)
            num_features = len(self.training_data[0]) if self.training_data else 0

            # Save metadata
            metadata = {
                'trained_at': datetime.now().isoformat(),
                'algorithm': 'RandomForestClassifier',
                'num_samples_total': len(self.training_data),
                'num_samples_train': len(self.X_train),
                'num_samples_test': len(self.X_test),
                'num_features': num_features,
                'model_type': '18-feature enhanced' if num_features > 10 else '6-feature basic',
                'n_estimators': self.model.n_estimators,
                'test_accuracy': round(test_accuracy, 4),
                'sklearn_version': '1.5+',
                'feature_names': self._get_feature_names()
            }

            metadata_path = filepath.replace('.pkl', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"[OK] Metadata saved to {metadata_path}")

            return True

        except Exception as e:
            print(f"[ERROR] Saving model failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Train QuakeSense AI model (Supervised)')
    parser.add_argument('--data', type=str, required=True, help='Path to labeled training data JSON file')
    parser.add_argument('--estimators', type=int, default=200, help='Number of trees (default: 200)')
    parser.add_argument('--max-depth', type=int, default=None, help='Max tree depth (default: unlimited)')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size (default: 0.2)')
    parser.add_argument('--output', type=str, default='models/seismic_model_rf.pkl', help='Output model path')

    args = parser.parse_args()

    trainer = SupervisedSeismicTrainer()

    print("\n" + "="*60)
    print("QuakeSense Supervised AI Model Trainer")
    print("Random Forest Classifier for Binary Classification")
    print("="*60)

    # Load training data
    if not trainer.load_training_data(args.data):
        print("\n[ERROR] Training failed - no data loaded")
        return

    # Split data
    trainer.split_data(test_size=args.test_size)

    # Train the model
    if trainer.train_model(n_estimators=args.estimators, max_depth=args.max_depth):
        # Evaluate the model
        accuracy = trainer.evaluate_model()

        # Save the model
        trainer.save_model(args.output)

        print("\n" + "="*60)
        print("[SUCCESS] Training Complete!")
        print("="*60)
        print(f"\nTest Accuracy: {accuracy:.2%}")
        print(f"Model saved to: {args.output}")
        print(f"\nYou can now use the trained model in your QuakeSense backend.")
        print("="*60 + "\n")


if __name__ == '__main__':
    main()
