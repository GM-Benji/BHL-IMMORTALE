import asyncio
import aiohttp
import random
import math
import time

# Configuration
API_URL = "http://127.0.0.1:8000/api/report"
API_KEY = "SECRET_KEY_123"
SENSOR_COUNT = 60

# --- GEOGRAPHICAL CONFIGURATION ---
POLLUTION_SOURCES = [
    # City Center Intersection (High Traffic -> High NOx, PM, DRY Soil)
    {"lat": 52.2297, "lng": 21.0122, "strength": 1.0, "type": "traffic"},
    # Industrial Area North (High PM, VOC, DRY Soil)
    {"lat": 52.2600, "lng": 21.0000, "strength": 0.9, "type": "industrial"},
]

CLEAN_ZONES = [
    # Pole Mokotowskie (Park -> WET Soil)
    {"lat": 52.2185, "lng": 21.0060, "strength": 0.8},
    # Las Kabacki (Forest -> WET Soil)
    {"lat": 52.1300, "lng": 21.0400, "strength": 1.2},
]

# Clusters to spawn sensors around
CLUSTERS = [
    {"name": "Center", "lat": 52.2297, "lng": 21.0122, "spread": 0.015, "count": 20},
    {"name": "Mokotow", "lat": 52.2000, "lng": 21.0200, "spread": 0.02, "count": 20},
    {"name": "North_Ind", "lat": 52.2550, "lng": 20.9900, "spread": 0.015, "count": 20},
]

class SpatiallyAwareSensor:
    def __init__(self, name, lat, lng):
        self.name = name
        self.api_key = API_KEY
        self.lat = lat
        self.lng = lng

        # State variables
        self.pm25 = 10.0
        self.pm10 = 15.0
        self.voc = 50.0
        self.nox = 20.0
        self.co2 = 400.0
        self.temp = 20.0
        self.humidity = 50.0
        self.soil_humidity = 30.0 # New State Variable (0-100%)

        self.seed = random.random()

    def update(self, time_tick):
        # Reset accumulations
        pm25_accum = 5.0
        voc_accum = 10.0
        nox_accum = 10.0
        soil_accum = 20.0 # Base dry soil (concrete baseline)

        # --- Add Pollution & Subtract Soil Moisture near Sources ---
        for source in POLLUTION_SOURCES:
            dist = math.hypot(self.lat - source["lat"], self.lng - source["lng"])
            intensity = (source["strength"] * 0.005) / (dist**2 + 0.0001)
            intensity = min(intensity, 200.0)

            if source["type"] == "traffic":
                nox_accum += intensity * 1.5
                pm25_accum += intensity * 0.8
                # Traffic areas are usually concrete (dryer)
                soil_accum -= intensity * 0.2
            elif source["type"] == "industrial":
                pm25_accum += intensity * 1.2
                voc_accum += intensity * 1.0
                soil_accum -= intensity * 0.3

        # --- Subtract Pollution & Add Soil Moisture near Parks ---
        for sink in CLEAN_ZONES:
            dist = math.hypot(self.lat - sink["lat"], self.lng - sink["lng"])
            cleaning = (sink["strength"] * 0.002) / (dist**2 + 0.0005)
            cleaning = min(cleaning, 0.8)

            pm25_accum *= (1.0 - cleaning)
            nox_accum *= (1.0 - cleaning)
            voc_accum *= (1.0 - cleaning)

            # Parks are grassy/foresty -> Higher Soil Humidity
            soil_boost = (sink["strength"] * 0.003) / (dist**2 + 0.0001)
            soil_boost = min(soil_boost, 60.0) # Add up to 60% humidity
            soil_accum += soil_boost

        # --- Global Waves ---
        wave = math.sin(self.lat * 10.0 + time_tick * 0.1) + math.cos(self.lng * 10.0 + time_tick * 0.15)

        self.pm25 = pm25_accum + (wave * 5.0) + (random.random() * 5.0)
        self.nox = nox_accum + (wave * 10.0) + (random.random() * 10.0)
        self.voc = voc_accum + (wave * 20.0) + (random.random() * 15.0)

        # Soil varies slowly
        soil_wave = math.sin(time_tick * 0.02 + self.seed * 10) * 5.0
        self.soil_humidity = soil_accum + soil_wave + (random.random() * 2.0)

        # Enforce physical limits
        self.pm25 = max(2.0, self.pm25)
        self.nox = max(5.0, self.nox)
        self.voc = max(0.0, self.voc)
        self.soil_humidity = max(0.0, min(self.soil_humidity, 100.0))

        # Derived values
        self.pm10 = self.pm25 * 1.5
        self.pm1_0 = self.pm25 * 0.6
        self.temp = 20.0 - (self.lat - 52.2) * 5.0 + math.sin(time_tick * 0.05)
        self.humidity = 50.0 + wave * 5.0

    def to_json(self):
        return {
            "sensor_name": self.name,
            "api_key": self.api_key,
            "lat": self.lat,
            "lng": self.lng,
            "carbon_dioxide": round(self.co2, 0),
            "temperature": round(self.temp, 2),
            "humidity": round(self.humidity, 1),
            "soil_humidity": round(self.soil_humidity, 1), # Send to API
            "voc_index": round(self.voc, 0),
            "nox_index": round(self.nox, 0),
            "pm1_0": round(self.pm1_0, 1),
            "pm2_5": round(self.pm25, 1),
            "pm10": round(self.pm10, 1)
        }

# Initialize Sensors in Clusters
sensors = []
sensor_id = 0

for cluster in CLUSTERS:
    for _ in range(cluster["count"]):
        lat = random.gauss(cluster["lat"], cluster["spread"] * 0.5)
        lng = random.gauss(cluster["lng"], cluster["spread"] * 0.8)

        name = f"waw_{cluster['name'].lower()}_{sensor_id:03d}"
        sensors.append(SpatiallyAwareSensor(name, lat, lng))
        sensor_id += 1

async def send_data(session, sensor, time_tick):
    sensor.update(time_tick)
    payload = sensor.to_json()
    try:
        async with session.post(API_URL, json=payload) as response:
            await response.text()
    except Exception as e:
        print(f"X", end="", flush=True)

async def main_loop():
    print(f"--- Starting GEOGRAPHIC Simulation (w/ SOIL) ---")
    tick = 0
    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()
            tasks = []
            print(".", end="", flush=True)
            for sensor in sensors:
                tasks.append(send_data(session, sensor, tick))
            await asyncio.gather(*tasks)
            tick += 1
            elapsed = time.time() - start_time
            sleep_time = max(0, 2.0 - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nStopped.")
