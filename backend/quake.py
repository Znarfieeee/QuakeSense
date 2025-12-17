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
ALERT_HISTORY = deque(maxlen=100)  # Store last 100 events
HISTORICAL_DATA = deque(maxlen=1000)  # For AI training

# ============================================================
# AI MODEL CONFIGURATION
# ============================================================
class SeismicAIClassifier:
    """
    AI Model for classifying seismic events vs false alarms
    Uses Isolation Forest for anomaly detection
    """
    
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.feature_history = []
        self.load_or_initialize_model()
    
    def load_or_initialize_model(self):
        """Load existing model or create new one"""
        model_path = "models/seismic_model.pkl"
        
        # Create models directory if it doesn't exist
        os.makedirs("models", exist_ok=True)
        
        if os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
                self.is_trained = True
                print("✓ AI Model loaded successfully")
            except Exception as e:
                print(f"⚠️  Error loading model: {e}")
                self._initialize_new_model()
        else:
            self._initialize_new_model()
    
    def _initialize_new_model(self):
        """Initialize a new Isolation Forest model"""
        self.model = IsolationForest(
            contamination=0.1,  # Expect 10% of data to be anomalies
            random_state=42,
            n_estimators=100
        )
        print("✓ New AI Model initialized")
    
    def extract_features(self, event_data):
        """
        Extract features from seismic event for AI analysis
        
        Features:
        - Horizontal acceleration magnitude
        - Total acceleration magnitude
        - Sound level
        - Acceleration to sound ratio (key discriminator!)
        - Rate of change (if we have historical data)
        """
        features = [
            event_data['horizontal_accel'],
            event_data['total_accel'],
            event_data['sound_level'],
            # Ratio: high accel + low sound = likely earthquake
            event_data['horizontal_accel'] / max(event_data['sound_level'], 1),
            1 if event_data['sound_correlated'] else 0
        ]
        
        # Add temporal features if we have history
        if len(self.feature_history) > 0:
            recent = self.feature_history[-1]
            features.append(event_data['horizontal_accel'] - recent[0])  # Rate of change
        else:
            features.append(0)
        
        return features
    
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
        
        if not self.is_trained or len(self.feature_history) < 10:
            # Not enough data for AI - use heuristics
            if event_data['horizontal_accel'] > 3.0 and not event_data['sound_correlated']:
                classification = 'genuine_earthquake'
                confidence = 0.75
                reasoning = 'High horizontal acceleration without sound (heuristic)'
            else:
                classification = 'uncertain'
                confidence = 0.5
                reasoning = 'Insufficient training data for AI classification'
        else:
            # Use AI model
            prediction = self.model.predict([features])[0]
            score = self.model.score_samples([features])[0]
            
            # Isolation Forest: -1 = anomaly (earthquake), 1 = normal (false alarm)
            if prediction == -1:
                classification = 'genuine_earthquake'
                confidence = min(abs(score) * 0.5 + 0.5, 0.95)
                reasoning = 'AI detected anomalous seismic pattern'
            else:
                classification = 'false_alarm'
                confidence = min(abs(score) * 0.5 + 0.5, 0.95)
                reasoning = 'AI classified as normal vibration pattern'
        
        # Store features for future predictions
        self.feature_history.append(features)
        if len(self.feature_history) > 50:
            self.feature_history.pop(0)
        
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
        
        # Store in history
        ALERT_HISTORY.append(data)
        HISTORICAL_DATA.append(data)
        
        # Log event
        print(f"\n{'='*60}")
        print(f"🌍 SEISMIC EVENT RECEIVED")
        print(f"{'='*60}")
        print(f"Device ID: {data['device_id']}")
        print(f"Horizontal Accel: {data['horizontal_accel']:.2f} m/s²")
        print(f"Total Accel: {data['total_accel']:.2f} m/s²")
        print(f"Sound Level: {data['sound_level']}")
        print(f"Sound Correlated: {data['sound_correlated']}")
        print(f"\n🤖 AI ANALYSIS:")
        print(f"Classification: {ai_result['classification'].upper()}")
        print(f"Confidence: {ai_result['confidence']*100:.1f}%")
        print(f"Reasoning: {ai_result['reasoning']}")
        print(f"{'='*60}\n")
        
        # Calculate severity
        severity = calculate_severity(data)
        
        # Send Telegram alert for genuine earthquakes or uncertain high-magnitude events
        telegram_sent = False
        if ai_result['classification'] == 'genuine_earthquake' and ai_result['confidence'] > 0.7:
            telegram_results = send_telegram_alert(data, severity, ai_result)
            telegram_sent = any(success for _, success, _ in telegram_results)
            print(f"📱 Telegram alert sent to {len(telegram_results)} recipient(s)")
        elif ai_result['classification'] == 'uncertain' and data['horizontal_accel'] > 3.0:
            # Send alert for uncertain but high acceleration events
            telegram_results = send_telegram_alert(data, severity, ai_result)
            telegram_sent = any(success for _, success, _ in telegram_results)
            print(f"📱 Telegram alert sent (uncertain high magnitude)")
        else:
            print(f"📱 Telegram alert NOT sent (classification: {ai_result['classification']})")
        
        return jsonify({
            'status': 'success',
            'received': True,
            'ai_analysis': ai_result,
            'severity': severity,
            'telegram_sent': telegram_sent,
            'event_id': len(ALERT_HISTORY)
        }), 200
        
    except Exception as e:
        print(f"Error processing event: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events', methods=['GET'])
def get_events():
    """Get recent seismic events"""
    limit = request.args.get('limit', 50, type=int)

    # Get events from history (most recent first)
    events = list(ALERT_HISTORY)[-limit:]
    # Reverse to show most recent first
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