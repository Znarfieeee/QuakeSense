import { useState, useEffect } from 'react';
import { Brain, Upload, CheckCircle, XCircle, Send, Database } from 'lucide-react';

const API_BASE_URL = 'http://192.168.1.31:5000/api';

export default function AITraining() {
  const [earthquakeData, setEarthquakeData] = useState([]);
  const [labeledData, setLabeledData] = useState([]);
  const [trainingStatus, setTrainingStatus] = useState('idle'); // idle, training, success, error
  const [message, setMessage] = useState('');
  const [testMessage, setTestMessage] = useState('');

  // Fetch unlabeled earthquake data
  useEffect(() => {
    fetchUnlabeledData();
  }, []);

  const fetchUnlabeledData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/events?limit=20`);
      if (response.ok) {
        const data = await response.json();
        setEarthquakeData(data.events || []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  const labelEvent = (event, label) => {
    const labeledEvent = {
      event: {
        horizontal_accel: event.horizontal_accel,
        total_accel: event.total_accel,
        sound_level: event.sound_level,
        sound_correlated: event.sound_correlated,
        timestamp: event.timestamp,
        device_id: event.device_id
      },
      label: label // 'genuine' or 'false_alarm'
    };

    setLabeledData([...labeledData, labeledEvent]);
    setEarthquakeData(earthquakeData.filter(e => e.timestamp !== event.timestamp));
    setMessage(`Event labeled as ${label === 'genuine' ? 'Genuine Earthquake' : 'False Alarm'}`);
    setTimeout(() => setMessage(''), 3000);
  };

  const trainModel = async () => {
    if (labeledData.length < 5) {
      setMessage('Need at least 5 labeled samples to train the model');
      return;
    }

    setTrainingStatus('training');
    setMessage('Training model...');

    try {
      const response = await fetch(`${API_BASE_URL}/train-model`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          training_data: labeledData
        })
      });

      const result = await response.json();

      if (response.ok) {
        setTrainingStatus('success');
        setMessage(`✓ ${result.message}`);
        setLabeledData([]);
      } else {
        setTrainingStatus('error');
        setMessage(`✗ Error: ${result.error}`);
      }
    } catch (error) {
      setTrainingStatus('error');
      setMessage(`✗ Error: ${error.message}`);
    }

    setTimeout(() => setTrainingStatus('idle'), 3000);
  };

  const sendTestTelegram = async () => {
    if (!testMessage.trim()) {
      setMessage('Please enter a test message');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/send-custom-telegram`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: testMessage,
          silent: false
        })
      });

      const result = await response.json();

      if (response.ok) {
        setMessage(`✓ ${result.message}`);
        setTestMessage('');
      } else {
        setMessage(`✗ Error: ${result.error}`);
      }
    } catch (error) {
      setMessage(`✗ Error: ${error.message}`);
    }

    setTimeout(() => setMessage(''), 3000);
  };

  const sendEventAsTelegram = async (event, severity = 'medium') => {
    try {
      const response = await fetch(`${API_BASE_URL}/send-custom-telegram`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          event_data: {
            horizontal_accel: event.horizontal_accel,
            total_accel: event.total_accel,
            sound_level: event.sound_level,
            sound_correlated: event.sound_correlated,
            device_id: event.device_id || 'Test Device',
            timestamp: event.timestamp,
            ai_classification: event.ai_classification || 'genuine_earthquake',
            ai_confidence: event.ai_confidence || 0.75,
            ai_reasoning: event.ai_reasoning || 'Test event'
          },
          severity: severity
        })
      });

      const result = await response.json();

      if (response.ok) {
        setMessage(`✓ Test alert sent via Telegram`);
      } else {
        setMessage(`✗ Error: ${result.error}`);
      }
    } catch (error) {
      setMessage(`✗ Error: ${error.message}`);
    }

    setTimeout(() => setMessage(''), 3000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Brain className="w-10 h-10 text-purple-500" />
          <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent">
            AI Training & Testing
          </h1>
        </div>
        <p className="text-slate-400 text-lg">Label events and test Telegram notifications</p>
      </div>

      {/* Status Message */}
      {message && (
        <div className={`mb-6 p-4 rounded-lg ${
          message.startsWith('✓') ? 'bg-green-500/20 border border-green-500/30' :
          message.startsWith('✗') ? 'bg-red-500/20 border border-red-500/30' :
          'bg-blue-500/20 border border-blue-500/30'
        }`}>
          <p className="text-sm">{message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Telegram Testing */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Send className="w-5 h-5 text-blue-500" />
            <h2 className="text-xl font-bold">Test Telegram Notifications</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Custom Message</label>
              <textarea
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                placeholder="Enter your test message..."
                className="w-full bg-slate-700 text-white rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows="4"
              />
            </div>

            <button
              onClick={sendTestTelegram}
              className="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Send className="w-4 h-4" />
              Send Test Message
            </button>
          </div>
        </div>

        {/* Training Status */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-purple-500" />
            <h2 className="text-xl font-bold">Training Status</h2>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Labeled Samples:</span>
              <span className="text-2xl font-bold text-purple-400">{labeledData.length}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-slate-400">Unlabeled Events:</span>
              <span className="text-2xl font-bold text-blue-400">{earthquakeData.length}</span>
            </div>

            <button
              onClick={trainModel}
              disabled={labeledData.length < 5 || trainingStatus === 'training'}
              className={`w-full font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 ${
                labeledData.length < 5 || trainingStatus === 'training'
                  ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : 'bg-purple-500 hover:bg-purple-600 text-white'
              }`}
            >
              <Brain className="w-4 h-4" />
              {trainingStatus === 'training' ? 'Training...' : `Train Model (Need ${Math.max(0, 5 - labeledData.length)} more)`}
            </button>

            <button
              onClick={() => setLabeledData([])}
              disabled={labeledData.length === 0}
              className="w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear Labeled Data
            </button>
          </div>
        </div>
      </div>

      {/* Event Labeling Section */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 className="text-xl font-bold mb-4">Label Events for Training</h2>

        {earthquakeData.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <p>No unlabeled events available</p>
            <button
              onClick={fetchUnlabeledData}
              className="mt-4 bg-slate-700 hover:bg-slate-600 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              Refresh Events
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {earthquakeData.slice(0, 5).map((event, index) => (
              <div key={index} className="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div>
                    <span className="text-xs text-slate-400">Horizontal Accel</span>
                    <p className="text-lg font-bold">{event.horizontal_accel?.toFixed(2)} m/s²</p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-400">Total Accel</span>
                    <p className="text-lg font-bold">{event.total_accel?.toFixed(2)} m/s²</p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-400">Sound Level</span>
                    <p className="text-lg font-bold">{event.sound_level}</p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-400">Sound Correlated</span>
                    <p className="text-lg font-bold">{event.sound_correlated ? 'Yes ❌' : 'No ✅'}</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => labelEvent(event, 'genuine')}
                    className="flex-1 bg-green-500 hover:bg-green-600 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <CheckCircle className="w-4 h-4" />
                    Genuine Earthquake
                  </button>
                  <button
                    onClick={() => labelEvent(event, 'false_alarm')}
                    className="flex-1 bg-red-500 hover:bg-red-600 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <XCircle className="w-4 h-4" />
                    False Alarm
                  </button>
                  <button
                    onClick={() => sendEventAsTelegram(event)}
                    className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                    title="Send as Telegram test"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
