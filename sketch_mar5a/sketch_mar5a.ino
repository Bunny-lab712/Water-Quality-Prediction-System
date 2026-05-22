#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <SD.h>

// --- Pin Map ---
#define TRIG_PIN 13
#define ECHO_PIN 27
#define SD_CS    5
#define SPI_SCK  18
#define SPI_MISO 19
#define SPI_MOSI 23

// --- Google Configuration ---
const char* google_script = "https://script.google.com/macros/s/AKfycbzWCZpcxlYV9UsOsAePD9dx7Y-pB2GCoq4He-RL_4fJXBrHHJzFtoPXEgo_pa6ebYc/exec";
const char* SECRET_KEY = "MyFarmSecret123"; // Matches your Google Script exactly

void setup() {
  Serial.begin(115200);
  delay(6000);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Serial.println("\n--- SYSTEM STARTING ---");

  // Initialize SD Card with explicit pins
  SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("[SD] Error: Card not found.");
  } else {
    Serial.println("[SD] Success: Card Ready.");
  }

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
}

void loop() {
  // 1. WiFi Management
  if (WiFi.status() != WL_CONNECTED) {
    connectToOpenWiFi();
  }

  // 2. Sensor Logic
  long distance = getDistance();
  String waterStatus = "";

  if (distance <= 0 || distance > 35) {
    waterStatus = "Sensor_Error";
  } else if (distance <= 15) {
    waterStatus = "Water_Full";
  } else {
    waterStatus = "Less_Water";
  }

  // 3. Packaging Payload (Matches your Script's 'level', 'status', and 'key')
  String dataPayload = "level=" + String(distance) + "&status=" + waterStatus + "&key=" + String(SECRET_KEY);
  
  Serial.println("---------- STATUS ----------");
  Serial.print(" Dist: "); Serial.print(distance); Serial.println(" cm");
  Serial.print(" Lvl:  "); Serial.println(waterStatus);

  // 4. Send or Save Logic
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WIFI] Online: "); Serial.println(WiFi.SSID());
    flushSDData(); // Send backlog first
    sendToGoogle(dataPayload); // Send live reading
  } else {
    Serial.println("[SD] Offline. Saving to card.");
    saveToSD(dataPayload);
  }

  Serial.println("----------------------------");
  delay(10000); // 10 second delay
}

// --- Helper Functions (The code was missing these!) ---

long getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 0;
  return (duration * 0.034 / 2);
}

void connectToOpenWiFi() {
  Serial.println("[WIFI] Scanning for Open Networks...");
  int n = WiFi.scanNetworks();
  if (n == 0) {
    Serial.println("[WIFI] No networks found.");
  } else {
    for (int i = 0; i < n; ++i) {
      if (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) {
        String ssid = WiFi.SSID(i);
        Serial.print("[WIFI] Found Open WiFi: "); Serial.println(ssid);
        WiFi.begin(ssid.c_str());
        
        int timeout = 0;
        while (WiFi.status() != WL_CONNECTED && timeout < 20) {
          delay(500);
          Serial.print(".");
          timeout++;
        }
        if (WiFi.status() == WL_CONNECTED) {
          Serial.println("\n[WIFI] Connected!");
          return;
        }
      }
    }
  }
}

void sendToGoogle(String params) {
  HTTPClient http;
  String fullURL = String(google_script) + "?" + params;
  
  if (http.begin(fullURL)) {
    // Correct redirect enum for your ESP32 Core version
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    
    int httpCode = http.GET();
    String response = http.getString(); 
    
    if (httpCode > 0) {
      Serial.print("[CLOUD] Server Response: "); Serial.println(response);
    } else {
      Serial.print("[CLOUD] HTTP Error: "); Serial.println(http.errorToString(httpCode).c_str());
    }
    http.end();
  }
}

void saveToSD(String data) {
  File file = SD.open("/data.txt", FILE_APPEND);
  if (file) {
    file.println(data);
    file.close();
  } else {
    Serial.println("[SD] Write Error!");
  }
}

void flushSDData() {
  if (!SD.exists("/data.txt")) return;

  Serial.println("[SD] Syncing backlog data...");
  File file = SD.open("/data.txt");
  if (file) {
    while (file.available()) {
      String line = file.readStringUntil('\n');
      line.trim();
      if (line.length() > 0) {
        sendToGoogle(line);
        delay(500); 
      }
    }
    file.close();
    SD.remove("/data.txt");
    Serial.println("[SD] Backlog cleared.");
  }
}