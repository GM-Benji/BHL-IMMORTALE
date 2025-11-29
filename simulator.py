import asyncio
import aiohttp
import random
import time

# Configuration
API_URL = "http://127.0.0.1:8000/api/report"
API_KEY = "SECRET_KEY_123"
SENSOR_COUNT = 50  # We will simulate 50 different devices

# Warsaw is roughly here, but the server will handle the location assignment.
# We just need to generate unique sensor names.
SENSORS = [f"warsaw_sensor_{i:03d}" for i in range(SENSOR_COUNT)]

def generate_sensor_data(sensor_name):
    """
    Generates random pollution data.
    Some sensors will be 'dirty' (high pollution) and some 'clean'.
    """
    # Create a "personality" for the sensor based on its name hash
    # This ensures sensor_001 is always generally clean or generally dirty
    is_industrial_zone = hash(sensor_name) % 3 == 0

    base_pm25 = 60 if is_industrial_zone else 15
    variance = random.uniform(-10, 10)

    # Ensure values don't go below zero
    pm25 = max(0, base_pm25 + variance)
    pm10 = max(0, pm25 * 1.5 + random.uniform(-5, 5))

    return {
        "sensor_name": sensor_name,
        "api_key": API_KEY,
        "carbon_dioxide": random.uniform(400, 1200),
        "temperature": random.uniform(10, 25), # Warsaw autumn/spring temp
        "humidity": random.uniform(40, 80),
        "voc_index": random.uniform(0, 500),
        "nox_index": random.uniform(0, 500),
        "pm1_0": max(0, pm25 * 0.5),
        "pm2_5": pm25,
        "pm10": pm10
    }

async def send_data(session, sensor_name):
    """Sends a single POST request for one sensor."""
    payload = generate_sensor_data(sensor_name)
    try:
        async with session.post(API_URL, json=payload) as response:
            # We just consume the response to ensure the request finished
            await response.text()
            # print(f"Sent data for {sensor_name}: PM2.5 = {payload['pm2_5']:.2f}")
    except Exception as e:
        print(f"Failed to send {sensor_name}: {e}")

async def main_loop():
    print(f"--- Starting Simulation for {SENSOR_COUNT} Sensors in Warsaw ---")

    async with aiohttp.ClientSession() as session:
        while True:
            tasks = []
            for sensor in SENSORS:
                tasks.append(send_data(session, sensor))

            # Send all 50 requests virtually at the same time
            await asyncio.gather(*tasks)

            print(f"Batch sent. Waiting 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Simulation stopped.")
