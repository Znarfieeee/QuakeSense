"""
Database Initialization Script for QuakeSense
Initializes PostgreSQL or SQLite database with schema

Usage:
    python scripts/init_database.py
    python scripts/init_database.py --type postgresql
    python scripts/init_database.py --type sqlite --path quakesense.db
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_manager import DatabaseManager


def init_database(db_type='postgresql', db_path=None):
    """
    Initialize database with schema

    Args:
        db_type: 'postgresql' or 'sqlite'
        db_path: Path to SQLite database file (if using SQLite)
    """
    print("=" * 60)
    print("QuakeSense Database Initialization")
    print("=" * 60)

    # Set environment variables if provided
    if db_type:
        os.environ['DATABASE_TYPE'] = db_type
    if db_path:
        os.environ['DATABASE_PATH'] = db_path

    print(f"\n[INIT] Initializing {db_type.upper()} database...")

    try:
        # Create database manager (this automatically initializes schema)
        db = DatabaseManager(db_type=db_type)

        # Update db_type if it was changed by DatabaseManager (e.g., fallback to SQLite)
        actual_db_type = db.db_type

        print("\n[OK] Database connection established")
        print("[OK] Schema initialized successfully")

        # Test database operations
        print("\n[TEST] Testing database operations...")

        # Test 1: Check if tables exist
        if actual_db_type == 'postgresql':
            db.cursor.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
        else:
            db.cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)

        tables = [row[0] if isinstance(row, tuple) else row['name'] for row in db.cursor.fetchall()]
        print(f"   Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table}")

        # Test 2: Insert a test event
        print("\n[TEST] Inserting test event...")
        test_event = {
            'device_id': 'TEST_DEVICE',
            'horizontal_accel': 2.5,
            'total_accel': 3.1,
            'sound_level': 1200,
            'sound_correlated': False
        }
        test_ai_result = {
            'classification': 'genuine_earthquake',
            'confidence': 0.85,
            'reasoning': 'Test event for database initialization'
        }
        test_severity = 'medium'

        event_id = db.insert_event(test_event, test_ai_result, test_severity)
        print(f"   [OK] Test event inserted with ID: {event_id}")

        # Test 3: Retrieve the test event
        print("\n[TEST] Retrieving test event...")
        events = db.get_recent_events(limit=1)
        if events:
            print(f"   [OK] Successfully retrieved {len(events)} event(s)")
            print(f"   - Device: {events[0].get('device_id')}")
            print(f"   - Classification: {events[0].get('ai_classification')}")
            print(f"   - Confidence: {events[0].get('ai_confidence')}")
        else:
            print("   [WARNING] No events found")

        # Test 4: Get statistics
        print("\n[TEST] Testing statistics calculation...")
        stats = db.get_aggregate_statistics()
        print(f"   [OK] Total events: {stats['total']}")
        print(f"   [OK] Today's events: {stats['today']}")
        print(f"   [OK] False alarms: {stats['false_alarms']}")
        print(f"   [OK] Accuracy: {stats['accuracy']}%")

        # Clean up test data
        print("\n[CLEANUP] Cleaning up test data...")
        if actual_db_type == 'postgresql':
            db.cursor.execute("DELETE FROM seismic_events WHERE device_id = %s", ('TEST_DEVICE',))
        else:
            db.cursor.execute("DELETE FROM seismic_events WHERE device_id = ?", ('TEST_DEVICE',))
        db.connection.commit()
        print("   [OK] Test data removed")

        print("\n" + "=" * 60)
        print("[SUCCESS] Database initialization complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Update .env with your database credentials")
        print("  2. Start the backend: python quake.py")
        print("  3. Test with Arduino sensor or API calls")
        print("\n" + "=" * 60)

        db.close()
        return True

    except Exception as e:
        print(f"\n[ERROR] Database initialization failed:")
        print(f"   Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check file permissions for database directory")
        print("  2. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("  3. Try deleting the database file and reinitializing")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Initialize QuakeSense database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize PostgreSQL (default)
  python scripts/init_database.py

  # Initialize SQLite
  python scripts/init_database.py --type sqlite

  # Initialize SQLite with custom path
  python scripts/init_database.py --type sqlite --path /data/quakesense.db

Environment Variables:
  DATABASE_TYPE      - postgresql or sqlite (default: postgresql)
  DATABASE_HOST      - PostgreSQL host (default: localhost)
  DATABASE_PORT      - PostgreSQL port (default: 5432)
  DATABASE_NAME      - Database name (default: quakesense)
  DATABASE_USER      - Database user (default: quakeuser)
  DATABASE_PASSWORD  - Database password
  DATABASE_PATH      - SQLite database path (default: quakesense.db)
        """
    )

    parser.add_argument(
        '--type',
        choices=['postgresql', 'sqlite'],
        default=None,
        help='Database type (default: from .env or postgresql)'
    )

    parser.add_argument(
        '--path',
        type=str,
        default=None,
        help='SQLite database path (only for sqlite type)'
    )

    args = parser.parse_args()

    # Get database type from args or environment
    db_type = args.type or os.environ.get('DATABASE_TYPE', 'postgresql')

    success = init_database(db_type=db_type, db_path=args.path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
