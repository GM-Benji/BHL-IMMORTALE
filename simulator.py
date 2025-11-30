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
# We define "Hotspots" (Pollution sources) and "Clean Zones" (Sinks)
# The simulation will calculate values based on distance to these points.

POLLUTION_SOURCES = [
    # City Center Intersection (High Traffic -> High NOx, PM)
    {"lat": 52.20929, "lng": 20.95874, "strength": 50.0, "type": "traffic"},
    # Industrial Area North (High PM, VOC)
    {"lat": 52.2600, "lng": 21.0000, "strength": 0.0, "type": "industrial"},
]

CLEAN_ZONES = [
    # Pole Mokotowskie (Park)
    {"lat": 52.24273, "lng": 21.05504, "strength": 0.5},
    # Las Kabacki (Forest - South)
    {"lat": 52.1300, "lng": 21.0400, "strength": 2.2},
]

# Clusters to spawn sensors around
CLUSTERS = [
    {"name": "Lazenki", "lat": 52.21496, "lng": 21.03371, "spread": 0.005, "count": 10},
    {"name": "Pola", "lat": 52.21323, "lng": 21.00054, "spread": 0.005, "count": 10},
    {"name": "park", "lat": 52.24281, "lng": 21.05586, "spread": 0.005, "count": 10},
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

        # Random offset for individuality
        self.seed = random.random()

    def update(self, time_tick):
        """
        Calculate values based on:
        1. Distance to sources (Traffic/Industry)
        2. Distance to sinks (Parks)
        3. Global sine wave (Wind/Time of day)
        """

        # Reset to baseline clean air
        pm25_accum = 5.0
        voc_accum = 10.0
        nox_accum = 10.0

        # --- Add Pollution from Sources ---
        for source in POLLUTION_SOURCES:
            # Simple Euclidean distance approximation (good enough for local city scale)
            dist = math.hypot(self.lat - source["lat"], self.lng - source["lng"])

            # Inverse distance weighting (pollution drops off as you move away)
            # Added 0.002 to avoid division by zero
            intensity = (source["strength"] * 0.005) / (dist**2 + 0.0001)
            intensity = min(intensity, 200.0) # Cap max effect

            if source["type"] == "traffic":
                nox_accum += intensity * 1.5
                pm25_accum += intensity * 0.8
            elif source["type"] == "industrial":
                pm25_accum += intensity * 1.2
                voc_accum += intensity * 1.0

        # --- Subtract Pollution from Clean Zones ---
        for sink in CLEAN_ZONES:
            dist = math.hypot(self.lat - sink["lat"], self.lng - sink["lng"])
            # Cleaning effect is stronger when close
            cleaning = (sink["strength"] * 0.002) / (dist**2 + 0.0005)
            cleaning = min(cleaning, 0.8) # Max 80% reduction

            pm25_accum *= (1.0 - cleaning)
            nox_accum *= (1.0 - cleaning)
            voc_accum *= (1.0 - cleaning)

        # --- Add Global Time Variance (Wind/Day-Night) ---
        # A wave that moves across the map
        wave = math.sin(self.lat * 10.0 + time_tick * 0.1) + math.cos(self.lng * 10.0 + time_tick * 0.15)

        self.pm25 = pm25_accum + (wave * 5.0) + (random.random() * 5.0)
        self.nox = nox_accum + (wave * 10.0) + (random.random() * 10.0)
        self.voc = voc_accum + (wave * 20.0) + (random.random() * 15.0)

        # Enforce physical limits
        self.pm25 = max(2.0, self.pm25)
        self.nox = max(5.0, self.nox)
        self.voc = max(0.0, self.voc)

        # Derived values
        self.pm10 = self.pm25 * 1.5
        self.pm1_0 = self.pm25 * 0.6
        self.temp = 20.0 - (self.lat - 52.2) * 5.0 + math.sin(time_tick * 0.05) # Temp varies N-S
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
        # Gaussian distribution around cluster center
        lat = random.gauss(cluster["lat"], cluster["spread"] * 0.5)
        lng = random.gauss(cluster["lng"], cluster["spread"] * 0.8) # Lon is stretched slightly

        name = f"waw_{cluster['name'].lower()}_{sensor_id:03d}"
        sensors.append(SpatiallyAwareSensor(name, lat, lng))
        sensor_id += 1

async def send_data(session, sensor, time_tick):
    """Updates sensor state and sends data"""
    sensor.update(time_tick)
    payload = sensor.to_json()

    try:
        async with session.post(API_URL, json=payload) as response:
            await response.text()
    except Exception as e:
        print(f"X", end="", flush=True) # visual indicator of error

async def main_loop():
    print(f"--- Starting GEOGRAPHIC Simulation for {len(sensors)} Sensors ---")
    print(f"Sources: {len(POLLUTION_SOURCES)} | Clean Zones: {len(CLEAN_ZONES)}")

    tick = 0
    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()
            tasks = []
            print(".", end="", flush=True) # Heartbeat

            for sensor in sensors:
                tasks.append(send_data(session, sensor, tick))

            await asyncio.gather(*tasks)
            tick += 1

            # Keep loop roughly timed
            elapsed = time.time() - start_time
            sleep_time = max(0, 2.0 - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nStopped.")
