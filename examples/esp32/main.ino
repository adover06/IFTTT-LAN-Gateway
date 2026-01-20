#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YourWiFiSSID";
const char* WIFI_PASS = "YourWiFiPassword";

const int LED_PIN = 2;  // onboard LED (usually GPIO 2)

WebServer server(80);

unsigned long ledOffAt = 0;

void handleAlarm() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }

  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, server.arg("plain"));

  if (err) {
    server.send(400, "text/plain", "Invalid JSON");
    return;
  }

  const char* action = doc["action"] | "";
  int duration_s = doc["duration_s"] | 0;

  if (strcmp(action, "on") == 0) {
    digitalWrite(LED_PIN, HIGH);
    if (duration_s > 0) {
      ledOffAt = millis() + (unsigned long)duration_s * 1000;
    }
    Serial.println("LED ON");
  } 
  else if (strcmp(action, "off") == 0) {
    digitalWrite(LED_PIN, LOW);
    ledOffAt = 0;
    Serial.println("LED OFF");
  } 
  else {
    server.send(400, "text/plain", "Unknown action");
    return;
  }

  server.send(200, "application/json", "{\"ok\":true}");
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  WiFi.mode(WIFI_STA); //Station mode
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/alarm", HTTP_POST, handleAlarm);
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/plain", "ESP32 alarm online");
  });

  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();

  // auto turn off LED after duration
  if (ledOffAt > 0 && millis() > ledOffAt) {
    digitalWrite(LED_PIN, LOW);
    ledOffAt = 0;
    Serial.println("LED auto OFF");
  }
}