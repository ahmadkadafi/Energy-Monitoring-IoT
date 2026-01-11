#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <PZEM004Tv30.h>
#include <ESP32Time.h>

/* ================= WIFI ================= */
const char* ssid = "Your_SSID";
const char* pass = "Your_PASSWORD";

/* ================= DEVICE ================= */
const char* device_name = "PZEM_01";

/* ================= API ================= */
const char* api_post = "your_api_endpoint_here";
const char* api_time = "your_time_api_endpoint_here";

/* ================= PZEM ================= */
#define PZEM_RX 16
#define PZEM_TX 17

HardwareSerial PZEMSerial(2);
PZEM004Tv30 pzem(PZEMSerial, PZEM_RX, PZEM_TX);

/* ================= RTC ================= */
ESP32Time rtc(0);

/* ================= DATA ================= */
float voltage, current, power, energy, frequency, pf;
String jsonString;

/* ================= JSON ================= */
void addJson(String key, String value) {
  if (jsonString.length()) jsonString += ",";
  jsonString += "\"" + key + "\":\"" + value + "\"";
}

String getJson() {
  return "{" + jsonString + "}";
}

/* ================= TIME ================= */
String getDateTime() {
  char buf[25];
  snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d",
           rtc.getYear(), rtc.getMonth() + 1, rtc.getDay(),
           rtc.getHour(true), rtc.getMinute(), rtc.getSecond());
  return String(buf);
}

/* ================= RTC SYNC ================= */
void syncRTC() {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient https;

  Serial.println("Sync RTC...");

  if (https.begin(client, api_time)) {
    int code = https.GET();
    if (code == 200) {
      String payload = https.getString();
      int idx = payload.indexOf("\"datetime\":\"");
      if (idx != -1) {
        String dt = payload.substring(idx + 12, idx + 31);

        rtc.setTime(
          dt.substring(17, 19).toInt(),
          dt.substring(14, 16).toInt(),
          dt.substring(11, 13).toInt(),
          dt.substring(8, 10).toInt(),
          dt.substring(5, 7).toInt(),
          dt.substring(0, 4).toInt()
        );

        Serial.println("RTC OK : " + getDateTime());
      }
    }
    https.end();
  }
}

/* ================= SEND DATA ================= */
void sendData() {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient https;

  jsonString = "";
  addJson("created_at", getDateTime());
  addJson("device", device_name);
  addJson("voltage", String(voltage));
  addJson("current", String(current));
  addJson("power", String(power));
  addJson("energy", String(energy));
  addJson("frequency", String(frequency));
  addJson("pf", String(pf));

  if (https.begin(client, api_post)) {
    https.addHeader("Content-Type", "application/json");
    int code = https.POST(getJson());

    Serial.println("POST CODE : " + String(code));
    Serial.println(getJson());

    https.end();
  }
}

/* ================= SETUP ================= */
void setup() {
  Serial.begin(115200);
  delay(1000);

  /* UART PZEM */
  PZEMSerial.begin(9600, SERIAL_8N1, PZEM_RX, PZEM_TX);

  /* WIFI */
  WiFi.begin(ssid, pass);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");

  syncRTC();
}

/* ================= LOOP ================= */
unsigned long lastRead = 0;
unsigned long lastSend = 0;

void loop() {
  unsigned long now = millis();

  /* ===== READ SENSOR tiap 5 detik ===== */
  if (now - lastRead >= 5000) {
    lastRead = now;

    voltage = pzem.voltage();
    current = pzem.current();
    power   = pzem.power();
    energy  = pzem.energy();
    frequency = pzem.frequency();
    pf = pzem.pf();

    if (!isnan(voltage)) {
      Serial.println("=====================");
      Serial.println(getDateTime());
      Serial.println("Voltage   : " + String(voltage));
      Serial.println("Current   : " + String(current));
      Serial.println("Power     : " + String(power));
      Serial.println("Energy    : " + String(energy));
      Serial.println("Frequency : " + String(frequency));
      Serial.println("PF        : " + String(pf));
    } else {
      Serial.println("PZEM READ FAILED");
    }
  }

  /* ===== SEND DATA tiap 2 menit ===== */
  if (now - lastSend >= 120000) {
    lastSend = now;
    if (WiFi.status() == WL_CONNECTED) {
      sendData();
    }
  }
}
