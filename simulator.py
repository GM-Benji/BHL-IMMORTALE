import asyncio
import aiohttp
import random
import time

# Configuration
API_URL = "http://127.0.0.1:8000/api/report"
API_KEY = "SECRET_KEY_123"
SENSOR_COUNT = 60  # Reduced to 60 for cleaner map

class SimulatedSensor:
    def __init__(self, name):
        self.name = name
        self.api_key = API_KEY

        # 1. Give each sensor a "Personality" (Industrial vs Residential)
        is_industrial = hash(name) % 4 == 0

        if is_industrial:
            self.pm25 = random.uniform(40, 80)
            self.voc = random.uniform(150, 300)
            self.nox = random.uniform(100, 250)
        else:
            self.pm25 = random.uniform(5, 25)
            self.voc = random.uniform(10, 80)
            self.nox = random.uniform(10, 60)

        # Environmental baselines
        self.co2 = random.uniform(400, 600)
        self.temp = random.uniform(15, 25)
        self.humidity = random.uniform(40, 60)
        self.pm10 = self.pm25 * 1.5
        self.pm1_0 = self.pm25 * 0.5

    def update(self):
        """
        Drift values slightly to simulate real-world changes.
        """
        # Small random walk
        self.pm25 += random.uniform(-1.5, 1.5)
        self.pm25 = max(0, min(self.pm25, 300))

        # Correlated values
        self.pm10 = self.pm25 * (1.5 + random.uniform(-0.1, 0.1))
        self.pm1_0 = self.pm25 * (0.5 + random.uniform(-0.05, 0.05))

        self.voc += random.uniform(-5, 5)
        self.voc = max(0, min(self.voc, 500))

        self.nox += random.uniform(-3, 3)
        self.nox = max(0, min(self.nox, 500))

        self.co2 += random.uniform(-2, 2)
        self.temp += random.uniform(-0.1, 0.1)
        self.humidity += random.uniform(-0.5, 0.5)

    def to_json(self):
        return {
            "sensor_name": self.name,
            "api_key": self.api_key,
            "carbon_dioxide": round(self.co2, 2),
            "temperature": round(self.temp, 2),
            "humidity": round(self.humidity, 2),
            "voc_index": round(self.voc, 2),
            "nox_index": round(self.nox, 2),
            "pm1_0": round(self.pm1_0, 2),
            "pm2_5": round(self.pm25, 2),
            "pm10": round(self.pm10, 2)
        }

# Initialize 60 Sensors
sensors = [SimulatedSensor(f"warsaw_sensor_{i:03d}") for i in range(SENSOR_COUNT)]

async def send_data(session, sensor):
    """Updates sensor state and sends data"""
    sensor.update()
    payload = sensor.to_json()

    try:
        async with session.post(API_URL, json=payload) as response:
            await response.text()
    except Exception as e:
        print(f"Connection error for {sensor.name}: {e}")

async def main_loop():
    print(f"--- Starting Simulation for {SENSOR_COUNT} Sensors ---")

    async with aiohttp.ClientSession() as session:
        while True:
            tasks = []
            for sensor in sensors:
                tasks.append(send_data(session, sensor))

            await asyncio.gather(*tasks)
            await asyncio.sleep(5) # Wait 5 seconds between updates

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Stopped.")
