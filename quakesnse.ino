#include <SPI.h>
#include <Adafruit_LIS3DH.h> 
#include <Adafruit_Sensor.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ============================================================
// SENSOR PIN DEFINITIONS
// ============================================================
#define LIS3DH_CS 15 
#define BUZZER_PIN 14 
#define RGB_RED_PIN 13   
#define RGB_GREEN_PIN 12
#define SOUND_SENSOR_PIN 34  

// ============================================================
// WiFi CREDENTIALS
// ============================================================
const char* ssid = "SPLT";
const char* password = "Splt3#03)85@";
const char* serverUrl = "http://192.168.1.31:5000/api/seismic-event";

Adafruit_LIS3DH lis = Adafruit_LIS3DH(LIS3DH_CS);

// ============================================================
// DETECTION THRESHOLDS & LOGIC
// ============================================================
float SHAKE_THRESHOLD_MS2 = 0.8;      // Sensitivity
int SOUND_THRESHOLD = 2000;           // Sound limit

// --- NEW LOGIC VARIABLES FOR CONTINUOUS DETECTION ---
const unsigned long MIN_SHAKE_DURATION = 350; // ms
const unsigned long SHAKE_RESET_TIMEOUT = 150; // ms

unsigned long shakeStartTime = 0;     
unsigned long lastShakeSampleTime = 0; 
bool potentialEarthquake = false;      

const int SOUND_CORRELATION_WINDOW = 1000; 

// ============================================================
// ALARM SETTINGS
// ============================================================
const long ALARM_DURATION = 10000; 
unsigned long alarmEndTime = 0;
const int BLINK_INTERVAL = 300;
unsigned long lastBlinkTime = 0;
bool blinkState = false;

// ============================================================
// BASELINE CALIBRATION
// ============================================================
float baselineX = 0.0, baselineY = 0.0, baselineZ = 0.0;
int baselineSound = 0;
unsigned long lastSoundSpikeTime = 0;

// ============================================================
// DATA STRUCTURE
// ============================================================
struct SeismicEvent {
  float horizontalAccel;
  float totalAccel;
  int soundLevel;
  bool isSoundCorrelated;
  unsigned long timestamp;
};

// Function Prototypes
void checkSerialInput();
void calibrateSensor();
void calibrateSoundSensor();
int readSoundLevel();
void sendEventToServer(SeismicEvent event);
void connectWiFi();

// ============================================================
// SETUP FUNCTION (MUST EXIST)
// ============================================================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10); 

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RGB_RED_PIN, OUTPUT);
  pinMode(RGB_GREEN_PIN, OUTPUT);
  pinMode(SOUND_SENSOR_PIN, INPUT);

  // Initial State: GREEN (Safe)
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RGB_RED_PIN, LOW);
  digitalWrite(RGB_GREEN_PIN, HIGH);

  Serial.println("==============================================");
  Serial.println("   QUAKESENSE: Early Detection Logic V2");
  Serial.println("==============================================");
  
  connectWiFi();
  
  if (! lis.begin(0x18)) { 
    Serial.println("ERROR: LIS3DH not found!");
    while (1) { delay(100); }
  }

  lis.setRange(LIS3DH_RANGE_4_G);
  lis.setDataRate(LIS3DH_DATARATE_100_HZ); 
  
  Serial.println("\nCalibrating sensors... DO NOT TOUCH.");
  delay(1000);
  calibrateSensor();
  calibrateSoundSensor();
  
  Serial.println("\n>>> SYSTEM ARMED <<<");
}

// ============================================================
// LOOP FUNCTION (MUST EXIST)
// ============================================================
void loop() {
  sensors_event_t event;
  lis.getEvent(&event);

  float dynX = abs(event.acceleration.x - baselineX);
  float dynY = abs(event.acceleration.y - baselineY);
  float dynZ = abs(event.acceleration.z - baselineZ);
  
  float horizontalAccel = sqrt(dynX * dynX + dynY * dynY);
  float totalAccel = sqrt(dynX * dynX + dynY * dynY + dynZ * dynZ);

  // Sound Monitoring
  int currentSoundLevel = readSoundLevel();
  if (currentSoundLevel > (baselineSound + SOUND_THRESHOLD)) {
    lastSoundSpikeTime = millis();
  }

  // --- CONTINUOUS SHAKE LOGIC ---
  if (horizontalAccel > SHAKE_THRESHOLD_MS2) {
    lastShakeSampleTime = millis(); 

    if (!potentialEarthquake) {
      shakeStartTime = millis();
      potentialEarthquake = true;
      Serial.println("-> Vibration detected... analyzing duration.");
    }

    if (potentialEarthquake && (millis() - shakeStartTime > MIN_SHAKE_DURATION)) {
      
      unsigned long timeSinceSound = millis() - lastSoundSpikeTime;
      bool soundCorrelated = (timeSinceSound < SOUND_CORRELATION_WINDOW);

      SeismicEvent seismicEvent = {horizontalAccel, totalAccel, currentSoundLevel, soundCorrelated, millis()};

      if (soundCorrelated) {
        Serial.println("⚠️ Heavy Vibration ignored (Sound Correlated)");
        potentialEarthquake = false; 
        shakeStartTime = 0;          
        sendEventToServer(seismicEvent); 
        delay(1000); 
      } else {
        Serial.println("\n🚨 EARTHQUAKE DETECTED! (Continuous P-Wave) 🚨");
        alarmEndTime = millis() + ALARM_DURATION;
        sendEventToServer(seismicEvent);
        potentialEarthquake = false; 
        shakeStartTime = 0;
      }
    }
  } else {
    if (potentialEarthquake && (millis() - lastShakeSampleTime > SHAKE_RESET_TIMEOUT)) {
      Serial.println("-> Movement stopped. Counter reset.");
      potentialEarthquake = false;
      shakeStartTime = 0;
    }
  }

  // Alarm Handler
  if (millis() < alarmEndTime) {
    if (millis() - lastBlinkTime >= BLINK_INTERVAL) {
      lastBlinkTime = millis();
      blinkState = !blinkState;
      if (blinkState) {
        tone(BUZZER_PIN, 2000);
        digitalWrite(RGB_RED_PIN, HIGH);
        digitalWrite(RGB_GREEN_PIN, LOW);
      } else {
        noTone(BUZZER_PIN);
        digitalWrite(RGB_RED_PIN, LOW);
        digitalWrite(RGB_GREEN_PIN, LOW);
      }
    }
  } else {
    noTone(BUZZER_PIN);
    digitalWrite(RGB_RED_PIN, LOW);
    digitalWrite(RGB_GREEN_PIN, HIGH); 
  }

  checkSerialInput();
  delay(10); 
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================
void connectWiFi() {
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 10) {
    delay(500);
    attempts++;
  }
}

void calibrateSensor() {
  float sumX=0, sumY=0, sumZ=0;
  for(int i=0; i<40; i++) {
    sensors_event_t e; lis.getEvent(&e);
    sumX += e.acceleration.x; sumY += e.acceleration.y; sumZ += e.acceleration.z;
    delay(20);
  }
  baselineX = sumX/40; baselineY = sumY/40; baselineZ = sumZ/40;
}

void calibrateSoundSensor() {
  long sum = 0;
  for(int i=0; i<40; i++) { sum += analogRead(SOUND_SENSOR_PIN); delay(20); }
  baselineSound = sum/40;
}

int readSoundLevel() {
  long sum = 0;
  for(int i=0; i<5; i++) { sum += analogRead(SOUND_SENSOR_PIN); delay(2); }
  return sum/5;
}

void sendEventToServer(SeismicEvent event) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    StaticJsonDocument<256> doc;
    doc["horizontal_accel"] = event.horizontalAccel;
    doc["total_accel"] = event.totalAccel;  // Added missing field
    doc["sound_level"] = event.soundLevel;
    doc["sound_correlated"] = event.isSoundCorrelated;
    doc["timestamp"] = event.timestamp;
    doc["device_id"] = "ESP32_QuakeSense_001";  // Added missing field
    String jsonPayload;
    serializeJson(doc, jsonPayload);
    int httpResponseCode = http.POST(jsonPayload);

    // Print response for debugging
    if (httpResponseCode > 0) {
      Serial.print("✓ Server response: ");
      Serial.println(httpResponseCode);
      if (httpResponseCode != 200) {
        String response = http.getString();
        Serial.println("Response body: " + response);
      }
    } else {
      Serial.print("✗ Error sending data: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  } else {
    Serial.println("✗ WiFi not connected, cannot send data");
  }
}

void checkSerialInput() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input == "cal") { calibrateSensor(); calibrateSoundSensor(); }
  }
}