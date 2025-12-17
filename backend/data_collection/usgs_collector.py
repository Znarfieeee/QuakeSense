"""
USGS Earthquake Data Collector
Fetches real historical earthquake data from USGS GeoJSON API

Usage:
    python data_collection/usgs_collector.py --start-date 2023-01-01 --output usgs_training.json
    python data_collection/usgs_collector.py --latitude 14.5995 --longitude 120.9842 --radius-km 500
"""

import requests
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import time
import os


class USGSCollector:
    """Collect earthquake data from USGS Earthquake Hazards Program API"""

    def __init__(self):
        self.api_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        self.rate_limit_delay = 1.0  # Seconds between requests (be respectful)

    def fetch_earthquakes(self,
                          start_date: str,
                          end_date: str = None,
                          min_magnitude: float = 2.5,
                          max_magnitude: float = 10.0,
                          latitude: float = None,
                          longitude: float = None,
                          radius_km: float = 500,
                          limit: int = 20000) -> List[Dict]:
        """
        Fetch earthquake data from USGS API

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (default: today)
            min_magnitude: Minimum earthquake magnitude
            max_magnitude: Maximum earthquake magnitude
            latitude: Center latitude for geographic filtering
            longitude: Center longitude for geographic filtering
            radius_km: Radius in kilometers around lat/lon
            limit: Maximum number of events to retrieve

        Returns:
            List of earthquake events in QuakeSense format
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n[USGS] Fetching earthquake data...")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Magnitude: {min_magnitude}+ (max: {max_magnitude})")

        if latitude and longitude:
            print(f"  Location: {latitude}, {longitude} (radius: {radius_km} km)")

        params = {
            'format': 'geojson',
            'starttime': start_date,
            'endtime': end_date,
            'minmagnitude': min_magnitude,
            'maxmagnitude': max_magnitude,
            'limit': limit,
            'orderby': 'time-asc'
        }

        # Add geographic filtering if specified
        if latitude and longitude:
            params['latitude'] = latitude
            params['longitude'] = longitude
            params['maxradiuskm'] = radius_km

        try:
            # Respect rate limiting
            time.sleep(self.rate_limit_delay)

            print("\n[USGS] Sending request to USGS API...")
            response = requests.get(self.api_url, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()

            if 'features' not in data:
                print("[ERROR] Invalid response from USGS API")
                return []

            features = data['features']
            print(f"[OK] Retrieved {len(features)} earthquakes")

            # Transform to QuakeSense format
            training_samples = self._transform_to_training_data(features)

            return training_samples

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch data from USGS: {e}")
            return []

    def _transform_to_training_data(self, usgs_features: List[Dict]) -> List[Dict]:
        """
        Transform USGS GeoJSON format to QuakeSense training format

        USGS GeoJSON structure:
        {
            "type": "Feature",
            "properties": {
                "mag": 5.2,
                "place": "10 km NW of Manila, Philippines",
                "time": 1609459200000,  # Unix timestamp in milliseconds
                "updated": 1609459200000,
                "tz": null,
                "url": "...",
                "detail": "...",
                "felt": 123,
                "cdi": 5.5,
                "mmi": 5.1,
                "alert": "yellow",
                "status": "reviewed",
                "tsunami": 0,
                "sig": 432,
                "net": "us",
                "code": "7000dkfw",
                "ids": ",us7000dkfw,",
                "sources": ",us,",
                "types": ",origin,phase-data,",
                "nst": 45,
                "dmin": 0.123,
                "rms": 0.34,
                "gap": 56,
                "magType": "mb",
                "type": "earthquake"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [120.9842, 14.5995, 33.0]  # [lon, lat, depth_km]
            },
            "id": "us7000dkfw"
        }
        """
        training_samples = []

        for feature in usgs_features:
            try:
                props = feature['properties']
                coords = feature['geometry']['coordinates']

                magnitude = props.get('mag', 0.0)
                depth_km = coords[2] if len(coords) > 2 else 0.0
                lat = coords[1]
                lon = coords[0]

                # Estimate sensor values from magnitude and depth
                # This is an approximation - real sensors would measure differently
                estimated_accel = self._estimate_acceleration_from_magnitude(magnitude, depth_km)

                # Create QuakeSense-compatible training sample
                sample = {
                    # Raw sensor approximations
                    'horizontal_accel': estimated_accel['horizontal'],
                    'total_accel': estimated_accel['total'],
                    'vertical_accel': estimated_accel['vertical'],
                    'x_accel': estimated_accel['x'],
                    'y_accel': estimated_accel['y'],
                    'z_accel': estimated_accel['z'],

                    # Sound characteristics (earthquakes typically have low sound correlation)
                    'sound_level': self._estimate_sound_level(magnitude, depth_km),
                    'sound_correlated': False,  # Real earthquakes don't correlate with sound

                    # Seismic characteristics
                    'peak_ground_acceleration': estimated_accel['peak'],
                    'frequency_dominant': self._estimate_frequency(magnitude),
                    'frequency_mean': self._estimate_frequency(magnitude),
                    'duration_ms': self._estimate_duration(magnitude),

                    # Wave patterns
                    'wave_arrival_pattern': 'p_then_s',  # Real earthquakes have P then S waves
                    'p_wave_detected': True,
                    's_wave_detected': True,

                    # Temporal
                    'temporal_variance': estimated_accel['horizontal'] * 0.15,

                    # Metadata
                    'timestamp': props.get('time', 0) // 1000,  # Convert to seconds
                    'device_id': 'USGS_DATA',

                    # Label (all USGS events are genuine earthquakes)
                    'label': 'genuine',

                    # Verification data
                    'verified': True,
                    'verified_magnitude': magnitude,
                    'usgs_event_id': feature.get('id', ''),
                    'usgs_place': props.get('place', ''),
                    'latitude': lat,
                    'longitude': lon,
                    'depth_km': depth_km,
                    'source': 'usgs',
                    'notes': f"USGS earthquake M{magnitude} at {depth_km}km depth"
                }

                training_samples.append(sample)

            except (KeyError, TypeError, IndexError) as e:
                print(f"[WARNING] Skipping malformed feature: {e}")
                continue

        return training_samples

    def _estimate_acceleration_from_magnitude(self, magnitude: float, depth_km: float) -> Dict[str, float]:
        """
        Estimate ground acceleration from earthquake magnitude and depth

        Based on empirical attenuation relationships:
        - Stronger earthquakes produce higher acceleration
        - Deeper earthquakes have lower surface acceleration

        Returns dict with horizontal, vertical, total, x, y, z, peak accelerations
        """
        # Base acceleration (m/s²) - rough logarithmic relationship
        # Magnitude 2: ~0.5 m/s², Magnitude 5: ~5 m/s², Magnitude 7: ~50 m/s²
        base_accel = 10 ** (magnitude - 3.5)

        # Depth attenuation factor (deeper = weaker at surface)
        # Surface quakes (0-10km): 1.0x
        # Shallow (10-30km): 0.7x
        # Intermediate (30-70km): 0.4x
        # Deep (70+km): 0.2x
        if depth_km < 10:
            depth_factor = 1.0
        elif depth_km < 30:
            depth_factor = 0.7
        elif depth_km < 70:
            depth_factor = 0.4
        else:
            depth_factor = 0.2

        adjusted_accel = base_accel * depth_factor

        # Horizontal typically stronger than vertical (S-waves)
        horizontal = adjusted_accel
        vertical = adjusted_accel * 0.6  # P-waves

        # Split horizontal into X/Y components (approximately equal)
        x = horizontal / 1.414
        y = horizontal / 1.414
        z = vertical

        # Total magnitude
        total = (horizontal**2 + vertical**2) ** 0.5

        # Peak is slightly higher than average
        peak = total * 1.2

        return {
            'horizontal': round(horizontal, 3),
            'vertical': round(vertical, 3),
            'x': round(x, 3),
            'y': round(y, 3),
            'z': round(z, 3),
            'total': round(total, 3),
            'peak': round(peak, 3)
        }

    def _estimate_sound_level(self, magnitude: float, depth_km: float) -> int:
        """
        Estimate sound level - earthquakes produce low sound relative to vibration

        Returns: 0-4095 (ADC range)
        """
        # Earthquakes produce minimal airborne sound compared to ground motion
        # Only very strong, shallow earthquakes produce significant noise
        if magnitude > 6.0 and depth_km < 10:
            return int(500 + magnitude * 50)  # Some rumbling sound
        else:
            return int(100 + magnitude * 20)  # Minimal sound

    def _estimate_frequency(self, magnitude: float) -> float:
        """
        Estimate dominant frequency (Hz)

        Larger earthquakes have lower frequencies:
        - Small (M2-3): 8-10 Hz
        - Medium (M3-5): 3-6 Hz
        - Large (M5+): 1-3 Hz
        """
        if magnitude < 3.0:
            return 9.0
        elif magnitude < 5.0:
            return 4.5
        else:
            return 2.0

    def _estimate_duration(self, magnitude: float) -> int:
        """
        Estimate event duration in milliseconds

        Larger earthquakes last longer:
        - M2: ~200-500ms
        - M3: ~500-1000ms
        - M5: ~1000-3000ms
        - M7+: 3000-10000ms
        """
        # Rough exponential relationship
        duration = 200 * (2 ** (magnitude - 2))
        return int(min(duration, 10000))  # Cap at 10 seconds

    def save_to_json(self, training_samples: List[Dict], output_path: str):
        """Save training samples to JSON file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump({
                    'metadata': {
                        'source': 'USGS Earthquake Hazards Program',
                        'collected_at': datetime.now().isoformat(),
                        'sample_count': len(training_samples),
                        'api_url': self.api_url
                    },
                    'samples': training_samples
                }, f, indent=2)

            print(f"\n[OK] Saved {len(training_samples)} samples to {output_path}")

        except IOError as e:
            print(f"[ERROR] Failed to save file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Collect earthquake training data from USGS API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect 2 years of earthquakes in Philippines region
  python usgs_collector.py --start-date 2023-01-01 --latitude 14.5995 --longitude 120.9842 --radius-km 500

  # Collect global earthquakes magnitude 5+
  python usgs_collector.py --start-date 2024-01-01 --min-magnitude 5.0

  # Collect recent California earthquakes
  python usgs_collector.py --start-date 2024-12-01 --latitude 36.7783 --longitude -119.4179 --radius-km 300
        """
    )

    parser.add_argument(
        '--start-date',
        required=True,
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        default=None,
        help='End date (YYYY-MM-DD, default: today)'
    )

    parser.add_argument(
        '--min-magnitude',
        type=float,
        default=2.5,
        help='Minimum magnitude (default: 2.5)'
    )

    parser.add_argument(
        '--max-magnitude',
        type=float,
        default=10.0,
        help='Maximum magnitude (default: 10.0)'
    )

    parser.add_argument(
        '--latitude',
        type=float,
        default=None,
        help='Center latitude for geographic filtering'
    )

    parser.add_argument(
        '--longitude',
        type=float,
        default=None,
        help='Center longitude for geographic filtering'
    )

    parser.add_argument(
        '--radius-km',
        type=float,
        default=500,
        help='Radius in kilometers (default: 500)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=20000,
        help='Maximum events to retrieve (default: 20000)'
    )

    parser.add_argument(
        '--output',
        default='usgs_training.json',
        help='Output file path (default: usgs_training.json)'
    )

    args = parser.parse_args()

    # Create collector
    collector = USGSCollector()

    # Fetch earthquakes
    samples = collector.fetch_earthquakes(
        start_date=args.start_date,
        end_date=args.end_date,
        min_magnitude=args.min_magnitude,
        max_magnitude=args.max_magnitude,
        latitude=args.latitude,
        longitude=args.longitude,
        radius_km=args.radius_km,
        limit=args.limit
    )

    if samples:
        # Save to file
        collector.save_to_json(samples, args.output)

        # Print summary
        print(f"\n{'='*60}")
        print("[SUCCESS] USGS Data Collection Complete")
        print(f"{'='*60}")
        print(f"  Total samples: {len(samples)}")
        print(f"  All labeled as: genuine earthquakes")
        print(f"  Output file: {args.output}")
        print(f"{'='*60}\n")
    else:
        print("\n[ERROR] No data collected")


if __name__ == '__main__':
    main()
