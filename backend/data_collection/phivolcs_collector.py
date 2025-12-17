"""
PHIVOLCS Earthquake Data Collector
Collects Philippine earthquake data from PHIVOLCS (Philippine Institute of Volcanology and Seismology)

Note: PHIVOLCS doesn't have an official API, so this uses ethical web scraping
with rate limiting and respectful practices.

Usage:
    python data_collection/phivolcs_collector.py --start-date 2024-01-01 --output phivolcs_training.json
    python data_collection/phivolcs_collector.py --year 2024
"""

import requests
from bs4 import BeautifulSoup
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import time
import os
import re


class PHIVOLCSCollector:
    """Collect earthquake data from PHIVOLCS website"""

    def __init__(self):
        self.base_url = "https://earthquake.phivolcs.dost.gov.ph"
        self.rate_limit_delay = 2.0  # 2 seconds between requests (be very respectful)
        self.user_agent = "QuakeSense/1.0 (Educational earthquake monitoring; contact: your@email.com)"

    def fetch_earthquakes(self,
                          start_date: str,
                          end_date: str = None,
                          min_magnitude: float = 2.0) -> List[Dict]:
        """
        Fetch earthquake data from PHIVOLCS

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD, default: today)
            min_magnitude: Minimum magnitude to collect

        Returns:
            List of earthquake events in QuakeSense format
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n[PHIVOLCS] Collecting Philippine earthquake data...")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Minimum magnitude: {min_magnitude}")
        print(f"  Rate limit: {self.rate_limit_delay}s between requests")

        # PHIVOLCS Website Structure (as of 2025):
        # Option 1: Latest earthquakes bulletin page
        # Option 2: Monthly earthquake bulletins
        # Option 3: CSV/Text data if available

        samples = []

        # Try to fetch from latest earthquakes page
        print("\n[PHIVOLCS] Attempting to fetch from latest earthquakes page...")
        latest_samples = self._fetch_latest_earthquakes()
        if latest_samples:
            samples.extend(latest_samples)
            print(f"[OK] Retrieved {len(latest_samples)} recent earthquakes")

        # Note: For historical data, PHIVOLCS may require contacting them directly
        # or checking if they have CSV/downloadable bulletins

        # Filter by date range and magnitude
        filtered_samples = self._filter_samples(samples, start_date, end_date, min_magnitude)

        return filtered_samples

    def _fetch_latest_earthquakes(self) -> List[Dict]:
        """
        Fetch latest earthquakes from PHIVOLCS website

        Note: This is a template implementation. The actual PHIVOLCS website
        structure may vary, and you should update the selectors accordingly.
        """
        try:
            # Respect rate limiting
            time.sleep(self.rate_limit_delay)

            headers = {
                'User-Agent': self.user_agent
            }

            # Example URL - update with actual PHIVOLCS earthquake page
            url = f"{self.base_url}/index.php"

            print(f"[PHIVOLCS] Fetching from {url}...")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Parse earthquake data from HTML
            # This is a template - adjust selectors based on actual website structure
            samples = self._parse_earthquake_table(soup)

            return samples

        except requests.exceptions.RequestException as e:
            print(f"[WARNING] Failed to fetch from PHIVOLCS: {e}")
            print("  PHIVOLCS website may be unavailable or structure changed")
            return []

    def _parse_earthquake_table(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse earthquake data from HTML table

        This is a template implementation. Update based on actual PHIVOLCS HTML structure.
        """
        samples = []

        # Look for earthquake table - common patterns
        # Update these selectors based on actual PHIVOLCS website
        table_selectors = [
            'table.earthquake-table',
            'table#earthquake-list',
            'div.earthquake-data table',
            'table'  # Fallback: any table
        ]

        table = None
        for selector in table_selectors:
            table = soup.select_one(selector)
            if table:
                print(f"[OK] Found table with selector: {selector}")
                break

        if not table:
            print("[WARNING] Could not find earthquake data table")
            print("  The PHIVOLCS website structure may have changed")
            print("  Please update the selectors in phivolcs_collector.py")
            return []

        # Parse table rows
        rows = table.find_all('tr')[1:]  # Skip header row

        for row in rows:
            try:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue

                # Common PHIVOLCS table format (adjust as needed):
                # Date | Time | Latitude | Longitude | Depth | Magnitude | Location

                # Example parsing - update based on actual table structure
                date_time = cols[0].text.strip() + ' ' + cols[1].text.strip()
                latitude = float(cols[2].text.strip())
                longitude = float(cols[3].text.strip())
                depth_km = float(cols[4].text.strip())
                magnitude = float(cols[5].text.strip())
                location = cols[6].text.strip() if len(cols) > 6 else 'Philippines'

                # Convert to QuakeSense format
                sample = self._create_sample_from_phivolcs_data(
                    date_time, latitude, longitude, depth_km, magnitude, location
                )

                samples.append(sample)

            except (ValueError, IndexError, AttributeError) as e:
                print(f"[WARNING] Failed to parse row: {e}")
                continue

        return samples

    def _create_sample_from_phivolcs_data(self,
                                          date_time: str,
                                          latitude: float,
                                          longitude: float,
                                          depth_km: float,
                                          magnitude: float,
                                          location: str) -> Dict:
        """
        Create QuakeSense training sample from PHIVOLCS data

        Similar to USGS collector, we estimate sensor values from seismic parameters
        """
        # Parse date/time
        try:
            # Try common formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%d-%b-%Y %H:%M:%S', '%m/%d/%Y %H:%M']:
                try:
                    dt = datetime.strptime(date_time, fmt)
                    timestamp = int(dt.timestamp())
                    break
                except ValueError:
                    continue
            else:
                timestamp = int(datetime.now().timestamp())
        except:
            timestamp = int(datetime.now().timestamp())

        # Estimate accelerations (same logic as USGS collector)
        estimated_accel = self._estimate_acceleration(magnitude, depth_km)

        sample = {
            # Sensor approximations
            'horizontal_accel': estimated_accel['horizontal'],
            'total_accel': estimated_accel['total'],
            'vertical_accel': estimated_accel['vertical'],
            'x_accel': estimated_accel['x'],
            'y_accel': estimated_accel['y'],
            'z_accel': estimated_accel['z'],
            'peak_ground_acceleration': estimated_accel['peak'],

            # Sound (earthquakes don't correlate with sound)
            'sound_level': self._estimate_sound_level(magnitude, depth_km),
            'sound_correlated': False,

            # Seismic features
            'frequency_dominant': self._estimate_frequency(magnitude),
            'frequency_mean': self._estimate_frequency(magnitude),
            'duration_ms': self._estimate_duration(magnitude),
            'wave_arrival_pattern': 'p_then_s',
            'p_wave_detected': True,
            's_wave_detected': True,
            'temporal_variance': estimated_accel['horizontal'] * 0.15,

            # Metadata
            'timestamp': timestamp,
            'device_id': 'PHIVOLCS_DATA',
            'label': 'genuine',

            # Verification
            'verified': True,
            'verified_magnitude': magnitude,
            'phivolcs_location': location,
            'latitude': latitude,
            'longitude': longitude,
            'depth_km': depth_km,
            'source': 'phivolcs',
            'notes': f"PHIVOLCS M{magnitude} at {depth_km}km - {location}"
        }

        return sample

    def _estimate_acceleration(self, magnitude: float, depth_km: float) -> Dict[str, float]:
        """Estimate accelerations from magnitude and depth"""
        base_accel = 10 ** (magnitude - 3.5)

        # Depth attenuation
        if depth_km < 10:
            depth_factor = 1.0
        elif depth_km < 30:
            depth_factor = 0.7
        elif depth_km < 70:
            depth_factor = 0.4
        else:
            depth_factor = 0.2

        adjusted = base_accel * depth_factor
        horizontal = adjusted
        vertical = adjusted * 0.6
        x = horizontal / 1.414
        y = horizontal / 1.414
        z = vertical
        total = (horizontal**2 + vertical**2) ** 0.5
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
        """Estimate sound level"""
        if magnitude > 6.0 and depth_km < 10:
            return int(500 + magnitude * 50)
        else:
            return int(100 + magnitude * 20)

    def _estimate_frequency(self, magnitude: float) -> float:
        """Estimate dominant frequency"""
        if magnitude < 3.0:
            return 9.0
        elif magnitude < 5.0:
            return 4.5
        else:
            return 2.0

    def _estimate_duration(self, magnitude: float) -> int:
        """Estimate duration"""
        duration = 200 * (2 ** (magnitude - 2))
        return int(min(duration, 10000))

    def _filter_samples(self,
                       samples: List[Dict],
                       start_date: str,
                       end_date: str,
                       min_magnitude: float) -> List[Dict]:
        """Filter samples by date range and magnitude"""
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())

        filtered = []
        for sample in samples:
            ts = sample.get('timestamp', 0)
            mag = sample.get('verified_magnitude', 0)

            if start_ts <= ts <= end_ts and mag >= min_magnitude:
                filtered.append(sample)

        return filtered

    def save_to_json(self, samples: List[Dict], output_path: str):
        """Save samples to JSON"""
        try:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump({
                    'metadata': {
                        'source': 'PHIVOLCS (Philippine Institute of Volcanology and Seismology)',
                        'collected_at': datetime.now().isoformat(),
                        'sample_count': len(samples),
                        'note': 'Data collected via ethical web scraping with rate limiting'
                    },
                    'samples': samples
                }, f, indent=2)

            print(f"\n[OK] Saved {len(samples)} samples to {output_path}")

        except IOError as e:
            print(f"[ERROR] Failed to save file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Collect earthquake data from PHIVOLCS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect recent earthquakes
  python phivolcs_collector.py --start-date 2024-01-01

  # Collect earthquakes from specific year
  python phivolcs_collector.py --start-date 2024-01-01 --end-date 2024-12-31

Note:
  PHIVOLCS doesn't have an official API. This collector uses ethical web scraping
  with rate limiting. If the website structure changes, the selectors may need updating.

Alternative:
  Consider contacting PHIVOLCS directly for bulk historical data access.
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
        default=2.0,
        help='Minimum magnitude (default: 2.0)'
    )

    parser.add_argument(
        '--output',
        default='phivolcs_training.json',
        help='Output file path (default: phivolcs_training.json)'
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("PHIVOLCS Data Collector")
    print("="*60)
    print("\nIMPORTANT NOTES:")
    print("  1. PHIVOLCS website structure may change")
    print("  2. Rate limiting: 2s between requests")
    print("  3. For large datasets, contact PHIVOLCS directly")
    print("  4. Alternative: Use USGS data for Philippine region")
    print("="*60)

    collector = PHIVOLCSCollector()

    samples = collector.fetch_earthquakes(
        start_date=args.start_date,
        end_date=args.end_date,
        min_magnitude=args.min_magnitude
    )

    if samples:
        collector.save_to_json(samples, args.output)

        print(f"\n{'='*60}")
        print("[SUCCESS] PHIVOLCS Data Collection Complete")
        print(f"{'='*60}")
        print(f"  Total samples: {len(samples)}")
        print(f"  Source: PHIVOLCS")
        print(f"  Output: {args.output}")
        print(f"{'='*60}\n")
    else:
        print("\n[WARNING] No data collected from PHIVOLCS")
        print("\nAlternative: Use USGS collector for Philippine earthquakes:")
        print("  python usgs_collector.py --start-date 2024-01-01 \\")
        print("    --latitude 12.8797 --longitude 121.7740 --radius-km 2000")


if __name__ == '__main__':
    main()
