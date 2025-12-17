"""
Collect Training Data from Real ESP32 Sensor
This script helps you collect labeled training data from your actual device

Usage:
    1. Start backend: python quake.py
    2. Run this script: python collect_esp32_training_data.py
    3. Shake device and label each event
    4. Retrain model with real data
"""

import json
import time
import requests
from datetime import datetime
import os

class ESP32TrainingCollector:
    """Collect and label real ESP32 sensor data"""

    def __init__(self, backend_url='http://localhost:5000'):
        self.backend_url = backend_url
        self.training_samples = []
        self.last_event_count = 0

    def fetch_latest_event(self):
        """Get the most recent event from backend"""
        try:
            response = requests.get(f"{self.backend_url}/api/events?limit=1")
            if response.status_code == 200:
                data = response.json()
                if data.get('events'):
                    return data['events'][0]
        except Exception as e:
            print(f"[ERROR] Failed to fetch events: {e}")
        return None

    def collect_labeled_data(self, target_genuine=50, target_false_alarm=50):
        """
        Interactive data collection

        Args:
            target_genuine: Number of genuine earthquake samples to collect
            target_false_alarm: Number of false alarm samples to collect
        """
        genuine_count = 0
        false_alarm_count = 0

        print("\n" + "="*60)
        print("ESP32 Training Data Collector")
        print("="*60)
        print("\nInstructions:")
        print("  1. Shake/tap your ESP32 device")
        print("  2. Wait for event to appear")
        print("  3. Label it as 'g' (genuine) or 'f' (false alarm)")
        print("  4. Repeat until you have enough samples")
        print("\nTips:")
        print("  - GENUINE: Sustained shaking (simulate earthquake)")
        print("  - FALSE ALARM: Quick taps, door slams, footsteps")
        print("\nPress Ctrl+C to finish and save data")
        print("="*60)

        print(f"\nTarget: {target_genuine} genuine, {target_false_alarm} false alarms")
        print(f"Progress: {genuine_count}/{target_genuine} genuine, {false_alarm_count}/{target_false_alarm} false alarms\n")

        last_timestamp = None

        while genuine_count < target_genuine or false_alarm_count < target_false_alarm:
            try:
                # Wait for new event
                print("\n[WAITING] Shake device to generate event...")

                while True:
                    event = self.fetch_latest_event()

                    if event and event.get('timestamp') != last_timestamp:
                        last_timestamp = event['timestamp']
                        break

                    time.sleep(0.5)

                # Display event data
                print("\n" + "-"*60)
                print("[NEW EVENT DETECTED]")
                print("-"*60)
                print(f"Horizontal Accel: {event.get('horizontal_accel', 0):.2f} m/s²")
                print(f"Total Accel: {event.get('total_accel', 0):.2f} m/s²")
                print(f"Duration: {event.get('duration_ms', 0)} ms")
                print(f"Sound Level: {event.get('sound_level', 0)}")
                print(f"Sound Correlated: {event.get('sound_correlated', False)}")
                print(f"Peak Accel: {event.get('peak_ground_acceleration', 0):.2f} m/s²")
                print("-"*60)

                # Get user label
                while True:
                    label_input = input("\nLabel this event? [g=genuine, f=false alarm, s=skip]: ").strip().lower()

                    if label_input == 's':
                        print("[SKIPPED]")
                        break
                    elif label_input in ['g', 'f']:
                        # Add label to event
                        event['label'] = 'genuine' if label_input == 'g' else 'false_alarm'
                        self.training_samples.append(event)

                        if label_input == 'g':
                            genuine_count += 1
                            print(f"[OK] Labeled as GENUINE ({genuine_count}/{target_genuine})")
                        else:
                            false_alarm_count += 1
                            print(f"[OK] Labeled as FALSE ALARM ({false_alarm_count}/{target_false_alarm})")

                        print(f"\nProgress: {genuine_count}/{target_genuine} genuine, {false_alarm_count}/{target_false_alarm} false alarms")
                        break
                    else:
                        print("[ERROR] Invalid input. Use 'g', 'f', or 's'")

                # Check if target reached
                if genuine_count >= target_genuine and false_alarm_count >= target_false_alarm:
                    print("\n" + "="*60)
                    print("[SUCCESS] Target samples collected!")
                    print("="*60)
                    break

            except KeyboardInterrupt:
                print("\n\n[INTERRUPTED] Stopping data collection...")
                break

        # Save collected data
        if self.training_samples:
            self.save_training_data()
        else:
            print("\n[WARNING] No samples collected")

    def save_training_data(self, filename='esp32_real_training_data.json'):
        """Save collected samples to JSON file"""
        output_path = filename

        try:
            with open(output_path, 'w') as f:
                json.dump({
                    'metadata': {
                        'source': 'ESP32 Real Sensor Data',
                        'collected_at': datetime.now().isoformat(),
                        'sample_count': len(self.training_samples),
                        'device': 'ESP32_QuakeSense_001'
                    },
                    'samples': self.training_samples
                }, f, indent=2)

            genuine = sum(1 for s in self.training_samples if s.get('label') == 'genuine')
            false_alarms = len(self.training_samples) - genuine

            print(f"\n[OK] Saved {len(self.training_samples)} samples to {output_path}")
            print(f"     Genuine: {genuine}")
            print(f"     False alarms: {false_alarms}")

            # Instructions for next steps
            print("\n" + "="*60)
            print("NEXT STEPS - Retrain Model with Real Data")
            print("="*60)
            print("\n1. Merge with existing data (optional):")
            print(f"   python data_collection/merge_datasets.py \\")
            print(f"     --input {output_path} synthetic_training.json usgs_training.json \\")
            print(f"     --output final_esp32_training.json \\")
            print(f"     --balance-classes\n")
            print("2. Train new model:")
            print(f"   python train_model_supervised.py \\")
            print(f"     --data {output_path} \\")
            print(f"     --output models/seismic_model_rf.pkl\n")
            print("3. Restart backend to load new model:")
            print(f"   python quake.py\n")
            print("="*60)

        except Exception as e:
            print(f"[ERROR] Failed to save training data: {e}")


def main():
    print("\n" + "="*60)
    print("QuakeSense - ESP32 Training Data Collector")
    print("="*60)
    print("\nThis tool helps you collect labeled training data from your")
    print("actual ESP32 sensor for better AI accuracy.\n")

    # Configuration
    target_genuine = int(input("How many GENUINE samples to collect? [default: 50]: ") or "50")
    target_false_alarm = int(input("How many FALSE ALARM samples to collect? [default: 50]: ") or "50")

    print("\n[OK] Starting data collection...")
    print("     Make sure your backend is running (python quake.py)\n")

    collector = ESP32TrainingCollector()
    collector.collect_labeled_data(target_genuine, target_false_alarm)


if __name__ == '__main__':
    main()
