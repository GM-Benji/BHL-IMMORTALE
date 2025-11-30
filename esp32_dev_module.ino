#include <Wire.h>

#include <VOCGasIndexAlgorithm.h>
#include <NOxGasIndexAlgorithm.h>

#include <ArduinoJson.h>

// WiFi
#include <WiFi.h>
#include <HTTPClient.h>
const char* WIFI_SSID = "BHLx42";
const char* WIFI_PASSWORD = "Learn2Code@42";
const char* CONTROLLER_NAME = "BHLx42_sensor";
const char* API_KEY = "SECRET_KEY_123";
const char* SERVER_URL = "http://185.55.243.192:8000/";

// pmsa003
#define TXD_PIN (GPIO_NUM_17)
#define RXD_PIN (GPIO_NUM_16)
uint8_t pmsa003_passive_data[7] = { 0x42, 0x4d, 0xe1, 0x00, 0x00, 0x01, 0x70 };
uint8_t pmsa003_sleep_data[7] =   { 0x42, 0x4d, 0xe4, 0x00, 0x00, 0x01, 0x73 };
uint8_t pmsa003_wake_data[7] =    { 0x42, 0x4d, 0xe4, 0x00, 0x01, 0x01, 0x74 };
uint8_t pmsa003_read_data[7] =    { 0x42, 0x4d, 0xe2, 0x00, 0x00, 0x01, 0x71 };
uint16_t PM1_0, PM2_5, PM10;

// sgp41
#include <SensirionI2CSgp41.h>
SensirionI2CSgp41 sgp41;
uint16_t conditioning_s = 10;
VOCGasIndexAlgorithm voc_algorithm;
NOxGasIndexAlgorithm nox_algorithm;
uint16_t voc_index;
uint16_t nox_index;

// dht11
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <DHT_U.h>

#define DHTPIN 32       // Digital pin connected to the DHT sensor
#define DHTTYPE DHT11  // DHT 11
DHT_Unified dht(DHTPIN, DHTTYPE);

// lp 36
#define MOIST_PIN 33

// servo
#include <ESP32Servo.h>
#define SERVO_PIN 25
#define SERVO_OPEN 0
#define SERVO_CLOSE 180

Servo servo;


void pmsa003_setup() {
  Serial1.begin(9600, SERIAL_8N1, RXD_PIN, TXD_PIN);
  Serial1.write(pmsa003_passive_data, 7);
  delay(500);
  Serial1.read();
}

void pmsa003_sleep() {
  Serial1.write(pmsa003_sleep_data, 7);
  delay(50);
}

void pmsa003_wake() {
  Serial1.write(pmsa003_wake_data, 7);
  delay(50);
}

int pmsa003_read() {
  Serial1.read();
  Serial1.write(pmsa003_read_data, 7);
  uint8_t data[32];
  uint16_t checksum = 0;

  while (Serial1.available() < 32) {
    delay(50);
  }

  Serial1.readBytes(data, 32);

  for (int i = 0; i < 30; i++) {
    checksum += data[i];
  }

  if (checksum != ((uint16_t)data[30] << 8 | data[31])) {
    return 0;
  }

  PM1_0 = ((uint16_t)data[10] << 8 | data[11]);
  PM2_5 = ((uint16_t)data[12] << 8 | data[13]);
  PM10 = ((uint16_t)data[14] << 8 | data[15]);
  return 1;
}   

void sgp41_read() {
  uint16_t error;
  char errorMessage[256];
  uint16_t defaultRh = 0x8000;
  uint16_t defaultT = 0x6666;
  uint16_t srawVoc = 0;
  uint16_t srawNox = 0;

  error = sgp41.measureRawSignals(defaultRh, defaultT, srawVoc, srawNox);

  if (error) {
    Serial.print("Error trying to execute measureRawSignals(): ");
    errorToString(error, errorMessage, 256);
    Serial.println(errorMessage);
  } else {
    voc_index = voc_algorithm.process(srawVoc);
    nox_index = nox_algorithm.process(srawNox);
  }
}

float temperature, humidity, co2;
int moist;

void read_sensors() {
  sensors_event_t event;
  dht.temperature().getEvent(&event);
  if (isnan(event.temperature)) {
    Serial.println(F("Error reading temperature!"));
  } else {
    temperature = event.temperature;
  }

  dht.humidity().getEvent(&event);
  if (isnan(event.relative_humidity)) {
    Serial.println(F("Error reading humidity!"));
  } else {
    humidity = event.relative_humidity;
  }

  moist = analogRead(MOIST_PIN);

  pmsa003_read();
}


void transmit_data() {
  if (moist > 1500 | PM2_5 > 50) {servo.write(SERVO_OPEN);}
  else {servo.write(SERVO_CLOSE);}

  // Serial.printf("temp: %f\n"
  //               "humid: %f\n"
  //               "voc: %u\n"
  //               "nox: %u\n"
  //               "pm 1.0: %d\n"
  //               "pm 2.5: %d\n"
  //               "pm 10: %d\n"
  //               "moist: %d\n",
  //               temperature, humidity,
  //               voc_index, nox_index,
  //               PM1_0,
  //               PM2_5,
  //               PM10,
  //               moist);

  Serial.flush();

  HTTPClient http;
  JsonDocument doc;

  doc["sensor_name"] = CONTROLLER_NAME;
  doc["api_key"] = API_KEY;

  doc["carbon_dioxide"] = 400;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;

  doc["voc_index"] = voc_index;
  doc["nox_index"] = nox_index;

  doc["pm1_0"] = PM1_0;
  doc["pm2_5"] = PM2_5;
  doc["pm10"] = PM10;

  doc["soil_humidity"] = moist;

  doc["lat"] = 52.214592;
  doc["lng"] = 21.013721;

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
  }

  http.begin(SERVER_URL + String("api/report"));

  String requestBody;
  serializeJson(doc, requestBody);
  http.addHeader("Content-Type", "application/json");
  http.POST(requestBody);

  http.end();
  WiFi.disconnect(1, 1, 100);
}


void setup() {
  Serial.begin(115200);

  while (!Serial)
    ;
  Serial.print("setup started\n");
  Wire.begin();

  servo.attach(SERVO_PIN);
  servo.write(SERVO_CLOSE);

  uint16_t error;
  char errorMessage[256];

  sgp41.begin(Wire);

  uint16_t testResult;
  error = sgp41.executeSelfTest(testResult);
  if (error) {
    Serial.print("Error trying to execute executeSelfTest(): ");
    errorToString(error, errorMessage, 256);
    Serial.println(errorMessage);
  } else if (testResult != 0xD400) {
    Serial.print("executeSelfTest failed with error: ");
    Serial.println(testResult);
  }

  uint16_t defaultRh = 0x8000;
  uint16_t defaultT = 0x6666;
  uint16_t srawVoc = 0;

  for (int i = 0; i < 10; i++) {
    // During NOx conditioning (10s) SRAW NOx will remain 0
    error = sgp41.executeConditioning(defaultRh, defaultT, srawVoc);
    delay(1000);
  }

  pmsa003_setup();
  dht.begin();

  Serial.print("setup complete\n");
}

#define uS_TO_S_FACTOR 1000000ULL /* Conversion factor for micro seconds to seconds */
#define TIME_TO_SLEEP  10          /* Time ESP32 will go to sleep (in seconds) */

bool servo_pos = 0;

void loop() {
  for (uint8_t i = 0; i<5; i++) {
    esp_sleep_enable_timer_wakeup(1 * uS_TO_S_FACTOR);
    esp_light_sleep_start();
    sgp41_read();
  }

  read_sensors();
  transmit_data();
}
