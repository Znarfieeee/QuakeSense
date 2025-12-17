from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from datetime import datetime
import joblib
import requests
import os
from sklearn.ensemble import IsolationForest
from collections import deque
import json
import time

# Database manager for persistent storage
from database.db_manager import DatabaseManager

# Enhanced ML feature extraction
from ml.feature_extractor import FeatureExtractor

app = Flask(__name__)
CORS(app)

# ============================================================
# TELEGRAM CONFIGURATION
# ============================================================
# Get your bot token from @BotFather on Telegram
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# Chat IDs to send alerts to (can be multiple recipients)
TELEGRAM_CHAT_IDS = [
    # "6836132866",  # Your personal chat ID
    # "ANOTHER_CHAT_ID",  # Family member
     "-5064595532",   # Group chat ID (starts with -)
]

# Telegram API URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# ============================================================
# DATA STORAGE
# ============================================================
# Initialize database manager for persistent storage
# This replaces in-memory deques (data now survives restarts!)
try:
    db = DatabaseManager()
    print("[OK] Database initialized for persistent event storage")
except Exception as e:
    print(f"[WARNING] Database initialization failed: {e}")
    print("   Falling back to in-memory storage (data will be lost on restart)")
    db = None
    # Fallback to in-memory storage if database fails
    ALERT_HISTORY = deque(maxlen=100)
    HISTORICAL_DATA = deque(maxlen=1000)

# ============================================================
# AI MODEL CONFIGURATION
# ============================================================
class SeismicAIClassifier:
    """
    AI Model for classifying seismic events vs false alarms
    Uses Isolation Forest for anomaly detection with 18 enhanced features
    """

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.feature_extractor = FeatureExtractor()  # NEW: 18-feature extraction
        self.load_or_initialize_model()
    
    def load_or_initialize_model(self):
        """Load existing model or create new one"""
        # Try to load the new Random Forest model first
        rf_model_path = "models/seismic_model_rf.pkl"
        old_model_path = "models/seismic_model.pkl"

        # Create models directory if it doesn't exist
        os.makedirs("models", exist_ok=True)

        # Try Random Forest model first (preferred)
        if os.path.exists(rf_model_path):
            try:
                self.model = joblib.load(rf_model_path)
                self.is_trained = True
                self.model_type = 'random_forest'
                print("[OK] Random Forest model loaded successfully (18-feature enhanced)")
            except Exception as e:
                print(f"[WARNING] Error loading Random Forest model: {e}")
                self._try_load_old_model(old_model_path)
        elif os.path.exists(old_model_path):
            self._try_load_old_model(old_model_path)
        else:
            self._initialize_new_model()

    def _try_load_old_model(self, old_model_path):
        """Try to load old Isolation Forest model as fallback"""
        try:
            self.model = joblib.load(old_model_path)
            self.is_trained = True
            self.model_type = 'isolation_forest'
            print("[OK] Isolation Forest model loaded (fallback)")
        except Exception as e:
            print(f"[WARNING] Error loading old model: {e}")
            self._initialize_new_model()

    def _initialize_new_model(self):
        """Initialize a new Isolation Forest model (fallback)"""
        from sklearn.ensemble import IsolationForest
        self.model = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.model_type = 'isolation_forest'
        print("[OK] New Isolation Forest model initialized (train with data for better accuracy)")
    
    def extract_features(self, event_data):
        """
        Extract 18 enhanced features from seismic event for AI analysis

        Features (18 total):
        - Original 6: horizontal_accel, total_accel, sound_level, accel-to-sound ratio,
                      sound_correlated, rate_of_change
        - NEW 12: acceleration components (4), frequency domain (3), temporal (3), wave detection (2)

        Returns:
            numpy array of 18 features
        """
        features = self.feature_extractor.extract_all_features(event_data)
        return features.tolist()  # Convert numpy array to list for compatibility
    
    def predict(self, event_data):
        """
        Predict if event is genuine seismic activity or false alarm
        
        Returns:
        - classification: "genuine_earthquake", "false_alarm", or "uncertain"
        - confidence: 0.0 to 1.0
        - reasoning: explanation
        """
        features = self.extract_features(event_data)
        
        # Rule-based quick checks (override AI if obvious)
        if event_data['sound_correlated']:
            return {
                'classification': 'false_alarm',
                'confidence': 0.95,
                'reasoning': 'Strong sound correlation indicates external impact/noise',
                'features': features
            }

        # TEMPORARY: Heuristic override for real ESP32 data
        # Until we retrain with actual sensor readings
        horizontal = event_data.get('horizontal_accel', 0)
        duration = event_data.get('duration_ms', 0)
        sound = event_data.get('sound_level', 0)

        # Strong shake: high accel + sustained duration + low sound = likely earthquake
        if horizontal > 1.5 and duration > 250 and sound < 2500 and not event_data.get('sound_correlated', False):
            return {
                'classification': 'genuine_earthquake',
                'confidence': 0.85,
                'reasoning': 'Heuristic: High sustained acceleration without sound correlation (ESP32 calibrated)',
                'features': features
            }
        
        if not self.is_trained:
            # Model not trained - use heuristics
            if event_data['horizontal_accel'] > 3.0 and not event_data['sound_correlated']:
                classification = 'genuine_earthquake'
                confidence = 0.75
                reasoning = 'High horizontal acceleration without sound (heuristic - model not loaded)'
            else:
                classification = 'uncertain'
                confidence = 0.5
                reasoning = 'Model not loaded - using basic heuristics'
        else:
            # Use AI model
            prediction = self.model.predict([features])[0]

            # Handle different model types
            if hasattr(self, 'model_type') and self.model_type == 'random_forest':
                # Random Forest: 1 = genuine, 0 = false alarm
                if prediction == 1:
                    classification = 'genuine_earthquake'
                    # Get probability if available
                    if hasattr(self.model, 'predict_proba'):
                        proba = self.model.predict_proba([features])[0]
                        confidence = float(max(proba))
                    else:
                        confidence = 0.90
                    reasoning = 'Random Forest AI: Genuine earthquake pattern detected (18-feature model)'
                else:
                    classification = 'false_alarm'
                    if hasattr(self.model, 'predict_proba'):
                        proba = self.model.predict_proba([features])[0]
                        confidence = float(max(proba))
                    else:
                        confidence = 0.90
                    reasoning = 'Random Forest AI: False alarm pattern detected'
            else:
                # Isolation Forest (fallback): -1 = anomaly (earthquake), 1 = normal (false alarm)
                score = self.model.score_samples([features])[0]
                if prediction == -1:
                    classification = 'genuine_earthquake'
                    confidence = min(abs(score) * 0.5 + 0.5, 0.95)
                    reasoning = 'Isolation Forest: Anomalous seismic pattern'
                else:
                    classification = 'false_alarm'
                    confidence = min(abs(score) * 0.5 + 0.5, 0.95)
                    reasoning = 'Isolation Forest: Normal vibration pattern'

        # Feature history is now managed by FeatureExtractor internally
        
        return {
            'classification': classification,
            'confidence': confidence,
            'reasoning': reasoning,
            'features': features
        }
    
    def train_incremental(self, labeled_data):
        """
        Incrementally train the model with new labeled data
        
        labeled_data: list of (features, label) tuples
        label: 1 = genuine, -1 = false alarm
        """
        if len(labeled_data) < 10:
            print("⚠️  Need at least 10 samples to train")
            return False
        
        features = [sample[0] for sample in labeled_data]
        
        try:
            self.model.fit(features)
            self.is_trained = True
            
            # Save model
            joblib.dump(self.model, "models/seismic_model.pkl")
            print(f"✓ Model trained with {len(labeled_data)} samples")
            return True
        except Exception as e:
            print(f"✗ Training error: {e}")
            return False


# Initialize AI Classifier
ai_classifier = SeismicAIClassifier()

# ============================================================
# TELEGRAM MESSAGING FUNCTIONS
# ============================================================

def send_telegram_message(message, parse_mode='Markdown', disable_notification=False):
    """
    Send message to all configured Telegram chat IDs
    
    Args:
        message: Text message to send
        parse_mode: 'Markdown' or 'HTML' for formatting
        disable_notification: If True, sends silently (for low priority)
    
    Returns:
        List of (chat_id, success, response) tuples
    """
    results = []
    
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }
            
            response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ Telegram message sent to {chat_id}")
                results.append((chat_id, True, response.json()))
            else:
                print(f"✗ Failed to send to {chat_id}: {response.text}")
                results.append((chat_id, False, response.text))
                
        except Exception as e:
            print(f"✗ Error sending to {chat_id}: {e}")
            results.append((chat_id, False, str(e)))
    
    return results


def send_telegram_alert(event_data, severity, ai_result):
    """
    Send formatted seismic alert via Telegram
    
    Args:
        event_data: Dictionary with event information
        severity: "low", "medium", "high", or "critical"
        ai_result: AI classification result
    """
    # Emoji mapping for severity
    severity_emoji = {
        'low': '⚠️',
        'medium': '🚨',
        'high': '🔴',
        'critical': '🆘'
    }
    
    # Build message with Markdown formatting
    message = f"{severity_emoji.get(severity, '⚠️')} *SEISMIC ALERT*\n"
    message += f"*Severity:* {severity.upper()}\n\n"

    # Event details
    message += f"📍 *Device:* `{event_data['device_id']}`\n"
    message += f"📊 *Horizontal Accel:* `{event_data['horizontal_accel']:.2f} m/s²`\n"
    message += f"📈 *Total Accel:* `{event_data['total_accel']:.2f} m/s²`\n"
    message += f"🔊 *Sound Level:* `{event_data['sound_level']}`\n"
    message += f"🔗 *Sound Correlated:* {'Yes ❌' if event_data['sound_correlated'] else 'No ✅'}\n\n"
    
    # AI Analysis
    message += f"🤖 *AI Analysis:*\n"
    message += f"• Classification: `{ai_result['classification'].replace('_', ' ').title()}`\n"
    message += f"• Confidence: `{ai_result['confidence']*100:.0f}%`\n"
    message += f"• Reasoning: _{ai_result['reasoning']}_\n\n"
    
    # Safety instructions based on severity
    if severity in ['high', 'critical']:
        message += "🏃 *IMMEDIATE ACTION REQUIRED:*\n"
        message += "• Drop, Cover, and Hold On\n"
        message += "• Move away from windows\n"
        message += "• Stay away from heavy objects\n"
        message += "• Prepare to evacuate\n\n"
    elif severity == 'medium':
        message += "⚡ *STAY ALERT:*\n"
        message += "• Be prepared for aftershocks\n"
        message += "• Identify safe spots nearby\n"
        message += "• Keep emergency kit accessible\n\n"
    else:
        message += "🔍 *MONITORING:*\n"
        message += "• Minor seismic activity detected\n"
        message += "• Stay aware of your surroundings\n\n"
    
    # Timestamp
    message += f"🕐 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Determine if notification should be silent
    silent = (severity == 'low')
    
    # Send message
    results = send_telegram_message(message, parse_mode='Markdown', disable_notification=silent)
    
    return results


def send_telegram_status_update(status_type, message):
    """
    Send system status updates (startup, errors, etc.)
    
    Args:
        status_type: "info", "warning", "error", "success"
        message: Status message text
    """
    emoji_map = {
        'info': 'ℹ️',
        'warning': '⚠️',
        'error': '❌',
        'success': '✅'
    }
    
    formatted_message = f"{emoji_map.get(status_type, 'ℹ️')} *System Status*\n\n{message}"
    
    # Send silently for info messages
    silent = (status_type == 'info')
    
    return send_telegram_message(formatted_message, disable_notification=silent)


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ai_trained': ai_classifier.is_trained,
        'total_events': len(ALERT_HISTORY),
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS)
    })


@app.route('/api/seismic-event', methods=['POST'])
def receive_seismic_event():
    """
    Main endpoint to receive seismic event data from Arduino
    Performs AI classification and sends Telegram alerts
    """
    try:
        # Check if request has JSON data
        if not request.is_json:
            print(f"❌ Request is not JSON. Content-Type: {request.content_type}")
            return jsonify({
                'error': 'Request must be JSON',
                'content_type': request.content_type
            }), 400

        data = request.json

        if data is None:
            print(f"❌ Request JSON is None")
            return jsonify({'error': 'Request body is empty or invalid JSON'}), 400

        # Log incoming request for debugging
        print(f"\n📥 Incoming POST request to /api/seismic-event")
        print(f"Data received: {data}")

        # Validate data
        required_fields = ['horizontal_accel', 'total_accel', 'sound_level',
                          'sound_correlated', 'timestamp', 'device_id']

        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            error_msg = f'Missing required fields: {", ".join(missing_fields)}'
            print(f"❌ Validation Error: {error_msg}")
            print(f"   Received fields: {list(data.keys())}")
            return jsonify({
                'error': error_msg,
                'missing_fields': missing_fields,
                'received_fields': list(data.keys())
            }), 400
        
        # Add server timestamp
        data['server_timestamp'] = datetime.now().isoformat()
        
        # AI Classification
        ai_result = ai_classifier.predict(data)
        data['ai_classification'] = ai_result['classification']
        data['ai_confidence'] = ai_result['confidence']
        data['ai_reasoning'] = ai_result['reasoning']

        # Calculate severity (needed for database and Telegram)
        severity = calculate_severity(data)

        # Store in database (persistent) or fallback to in-memory
        if db:
            try:
                event_id = db.insert_event(data, ai_result, severity)
                # Update device last seen timestamp
                db.update_device_last_seen(data['device_id'])
            except Exception as db_error:
                print(f"[WARNING] Database insert failed: {db_error}")
                event_id = -1
                # Fallback to in-memory if database fails
                if 'ALERT_HISTORY' in globals():
                    ALERT_HISTORY.append(data)
                    HISTORICAL_DATA.append(data)
        else:
            # Using in-memory storage
            ALERT_HISTORY.append(data)
            HISTORICAL_DATA.append(data)
            event_id = len(ALERT_HISTORY)
        
        # Log event
        print(f"\n{'='*60}")
        print(f"[SEISMIC EVENT RECEIVED]")
        print(f"{'='*60}")
        print(f"Device ID: {data['device_id']}")
        print(f"Horizontal Accel: {data['horizontal_accel']:.2f} m/s²")
        print(f"Total Accel: {data['total_accel']:.2f} m/s²")
        print(f"Sound Level: {data['sound_level']}")
        print(f"Sound Correlated: {data['sound_correlated']}")
        print(f"\n[AI ANALYSIS]")
        print(f"Classification: {ai_result['classification'].upper()}")
        print(f"Confidence: {ai_result['confidence']*100:.1f}%")
        print(f"Reasoning: {ai_result['reasoning']}")
        print(f"Severity: {severity}")

        # DEBUG: Show extracted features
        if 'features' in ai_result:
            print(f"\n[DEBUG] Extracted 18 features:")
            feature_names = [
                'horizontal_accel', 'total_accel', 'sound_level', 'accel_sound_ratio',
                'sound_correlated', 'rate_of_change', 'vertical_accel', 'x_accel',
                'y_accel', 'z_accel', 'peak_ground_accel', 'frequency_dominant',
                'frequency_mean', 'duration_ms', 'wave_arrival_pattern',
                'p_wave_detected', 's_wave_detected', 'temporal_variance'
            ]
            for i, (name, value) in enumerate(zip(feature_names, ai_result['features'][:18])):
                print(f"  {i+1}. {name}: {value}")

        print(f"{'='*60}\n")

        # Send Telegram alert for genuine earthquakes or uncertain high-magnitude events
        telegram_sent = False
        if ai_result['classification'] == 'genuine_earthquake' and ai_result['confidence'] > 0.7:
            telegram_results = send_telegram_alert(data, severity, ai_result)
            telegram_sent = any(success for _, success, _ in telegram_results)
            print(f"[TELEGRAM] Alert sent to {len(telegram_results)} recipient(s)")
        elif ai_result['classification'] == 'uncertain' and data['horizontal_accel'] > 3.0:
            # Send alert for uncertain but high acceleration events
            telegram_results = send_telegram_alert(data, severity, ai_result)
            telegram_sent = any(success for _, success, _ in telegram_results)
            print(f"[TELEGRAM] Alert sent (uncertain high magnitude)")
        else:
            print(f"[TELEGRAM] Alert NOT sent (classification: {ai_result['classification']})")
        
        return jsonify({
            'status': 'success',
            'received': True,
            'ai_analysis': ai_result,
            'severity': severity,
            'telegram_sent': telegram_sent,
            'event_id': event_id
        }), 200
        
    except Exception as e:
        print(f"Error processing event: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events', methods=['GET'])
def get_events():
    """Get recent seismic events"""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    # Get events from database or fallback to in-memory
    if db:
        try:
            events = db.get_recent_events(limit=limit, offset=offset)
        except Exception as db_error:
            print(f"[WARNING] Database query failed: {db_error}")
            # Fallback to in-memory if available
            if 'ALERT_HISTORY' in globals():
                events = list(ALERT_HISTORY)[-limit:]
                events.reverse()
            else:
                events = []
    else:
        # Using in-memory storage
        events = list(ALERT_HISTORY)[-limit:]
        events.reverse()

    return jsonify({
        'total': len(events),
        'events': events
    })


@app.route('/api/train-model', methods=['POST'])
def train_model():
    """
    Manually train/update the AI model with labeled data
    
    Expected payload:
    {
        "training_data": [
            {"event": {...}, "label": "genuine" or "false_alarm"},
            ...
        ]
    }
    """
    try:
        data = request.json
        training_data = data.get('training_data', [])
        
        if len(training_data) == 0:
            return jsonify({'error': 'No training data provided'}), 400
        
        # Convert to features and labels
        labeled_samples = []
        for sample in training_data:
            features = ai_classifier.extract_features(sample['event'])
            label = -1 if sample['label'] == 'genuine' else 1
            labeled_samples.append((features, label))
        
        # Train model
        success = ai_classifier.train_incremental(labeled_samples)
        
        if success:
            # Send success notification
            send_telegram_status_update('success', 
                f"AI Model retrained with {len(labeled_samples)} samples")
            
            return jsonify({
                'status': 'success',
                'message': f'Model trained with {len(labeled_samples)} samples',
                'model_trained': ai_classifier.is_trained
            })
        else:
            return jsonify({'error': 'Training failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/test-telegram', methods=['POST'])
def test_telegram():
    """
    Test Telegram connection
    Send a test message to verify configuration
    """
    try:
        test_message = "🧪 *Telegram Test Message*\n\n"
        test_message += "If you're seeing this, your Telegram integration is working correctly!\n\n"
        test_message += f"✅ Bot Token: Configured\n"
        test_message += f"✅ Recipients: {len(TELEGRAM_CHAT_IDS)}\n"
        test_message += f"✅ Server: Running\n\n"
        test_message += f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        results = send_telegram_message(test_message)

        success_count = sum(1 for _, success, _ in results if success)

        return jsonify({
            'status': 'success',
            'message': f'Test message sent to {success_count}/{len(TELEGRAM_CHAT_IDS)} recipients',
            'results': [{'chat_id': chat_id, 'success': success}
                       for chat_id, success, _ in results]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/send-custom-telegram', methods=['POST'])
def send_custom_telegram():
    """
    Send custom Telegram message with any data for testing

    Expected payload:
    {
        "message": "Your custom message",
        "event_data": {...},  // Optional: seismic event data
        "severity": "low|medium|high|critical",  // Optional
        "silent": false  // Optional: send silently
    }
    """
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Option 1: Send custom message directly
        if 'message' in data:
            message = data['message']
            silent = data.get('silent', False)
            results = send_telegram_message(message, disable_notification=silent)

            success_count = sum(1 for _, success, _ in results if success)

            return jsonify({
                'status': 'success',
                'message': f'Custom message sent to {success_count}/{len(TELEGRAM_CHAT_IDS)} recipients',
                'results': [{'chat_id': chat_id, 'success': success}
                           for chat_id, success, _ in results]
            })

        # Option 2: Send formatted seismic alert with custom data
        elif 'event_data' in data:
            event_data = data['event_data']
            severity = data.get('severity', 'low')

            # Create mock AI result for testing
            ai_result = {
                'classification': event_data.get('ai_classification', 'genuine_earthquake'),
                'confidence': event_data.get('ai_confidence', 0.75),
                'reasoning': event_data.get('ai_reasoning', 'Custom test event')
            }

            results = send_telegram_alert(event_data, severity, ai_result)

            success_count = sum(1 for _, success, _ in results if success)

            return jsonify({
                'status': 'success',
                'message': f'Custom alert sent to {success_count}/{len(TELEGRAM_CHAT_IDS)} recipients',
                'results': [{'chat_id': chat_id, 'success': success}
                           for chat_id, success, _ in results]
            })
        else:
            return jsonify({'error': 'Must provide either "message" or "event_data"'}), 400

    except Exception as e:
        print(f"Error sending custom Telegram message: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """
    Get aggregate statistics for dashboard

    Returns:
        - total: Total number of events
        - today: Events detected today
        - false_alarms: Number of false alarms
        - accuracy: AI accuracy percentage
    """
    try:
        if db:
            # Get statistics from database
            stats = db.get_aggregate_statistics()
        else:
            # Fallback to in-memory calculations
            if 'ALERT_HISTORY' in globals():
                events = list(ALERT_HISTORY)
                total = len(events)

                # Today's events
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today = sum(1 for e in events
                           if datetime.fromisoformat(e.get('server_timestamp', e.get('timestamp'))) >= today_start)

                # False alarms
                false_alarms = sum(1 for e in events if e.get('ai_classification') == 'false_alarm')

                # Accuracy
                accuracy = ((total - false_alarms) / total * 100) if total > 0 else 0

                stats = {
                    'total': total,
                    'today': today,
                    'false_alarms': false_alarms,
                    'accuracy': round(accuracy, 1)
                }
            else:
                stats = {'total': 0, 'today': 0, 'false_alarms': 0, 'accuracy': 0}

        return jsonify(stats)

    except Exception as e:
        print(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_severity(event_data):
    """
    Calculate severity level based on acceleration magnitude
    Returns: "low", "medium", "high", or "critical"
    """
    horizontal = event_data['horizontal_accel']
    
    if horizontal < 2.0:
        return "low"
    elif horizontal < 4.0:
        return "medium"
    elif horizontal < 7.0:
        return "high"
    else:
        return "critical"


# ============================================================
# STARTUP & RUN SERVER
# ============================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 Seismic Detection API Server Starting...")
    print("="*60)
    print(f"AI Model Status: {'Trained ✓' if ai_classifier.is_trained else 'Untrained ⚠️'}")
    print(f"Telegram Bot: {'Configured ✓' if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else 'Not Configured ⚠️'}")
    print(f"Telegram Recipients: {len(TELEGRAM_CHAT_IDS)}")
    print("="*60 + "\n")
    
    # Send startup notification if Telegram is configured
    if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' and TELEGRAM_CHAT_IDS[0] != 'YOUR_CHAT_ID_HERE':
        startup_message = "🚀 *Seismic Detection System Online*\n\n"
        startup_message += f"✅ AI Model: {'Trained' if ai_classifier.is_trained else 'Learning Mode'}\n"
        startup_message += f"✅ Server: Running on port 5000\n"
        startup_message += f"✅ Monitoring: Active\n\n"
        startup_message += f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        send_telegram_message(startup_message)
    
    # Run Flask server
    app.run(host='0.0.0.0', port=5000, debug=True)