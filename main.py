import uvicorn
import random
import math
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Optional

app = FastAPI()

if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

class SensorData(BaseModel):
    sensor_name: str
    api_key: str
    carbon_dioxide: float
    temperature: float
    humidity: float
    voc_index: float = 0.0
    nox_index: float = 0.0
    pm1_0: float
    pm2_5: float
    pm10: float
    universal_aqi: Optional[int] = None

sensor_locations: Dict[str, Dict[str, float]] = {}
latest_readings: Dict[str, SensorData] = {}

# --- PRECISE GREEN MICRO-ZONES ---
# Smaller radii (0.0015 - 0.0025) to ensure points stay strictly on grass/trees.
GREEN_ZONES = [
    # Pole Mokotowskie (Split into safe sectors)
    {"name": "Pole Mokotowskie (Main Lawn)", "lat": 52.2185, "lng": 21.0060, "radius": 0.0025},
    {"name": "Pole Mokotowskie (Ponds Area)", "lat": 52.2195, "lng": 21.0020, "radius": 0.0020},
    {"name": "Pole Mokotowskie (East)", "lat": 52.2175, "lng": 21.0110, "radius": 0.0015},

    # Lazienki Krolewskie (Avoid Palace/Water)
    {"name": "Lazienki (Garden South)", "lat": 52.2120, "lng": 21.0350, "radius": 0.0020},
    {"name": "Lazienki (Garden North)", "lat": 52.2160, "lng": 21.0330, "radius": 0.0015},

    # Park Ujazdowski (Very specific)
    {"name": "Park Ujazdowski", "lat": 52.2220, "lng": 21.0280, "radius": 0.0012},

    # Ogrod Saski (Central)
    {"name": "Ogrod Saski", "lat": 52.2410, "lng": 21.0030, "radius": 0.0015},

    # Park Skaryszewski
    {"name": "Park Skaryszewski (West)", "lat": 52.2425, "lng": 21.0540, "radius": 0.0020},
    {"name": "Park Skaryszewski (East)", "lat": 52.2430, "lng": 21.0590, "radius": 0.0020},

    # Las Kabacki (Deep Woods)
    {"name": "Las Kabacki (Deep)", "lat": 52.1260, "lng": 21.0450, "radius": 0.0080},

    # Las Bielanski
    {"name": "Las Bielanski", "lat": 52.2960, "lng": 20.9580, "radius": 0.0040},
]

def generate_warsaw_location():
    """Generates a random coordinate strictly inside a green zone."""
    # 1. Pick a random safe zone
    zone = random.choice(GREEN_ZONES)

    # 2. Generate random point within that circle
    r = zone["radius"] * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi

    # 3. Calculate offset
    lat_offset = r * math.cos(theta)
    lng_offset = r * math.sin(theta) * 1.6 # Longitude correction

    return {
        "lat": zone["lat"] + lat_offset,
        "lng": zone["lng"] + lng_offset
    }

# --- AQI ALGORITHM ---
def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def calc_pm25_idx(pm):
    if pm <= 10.0:  return map_value(pm, 0, 10, 0, 50)
    if pm <= 25.0:  return map_value(pm, 10.1, 25, 51, 100)
    if pm <= 50.0:  return map_value(pm, 25.1, 50, 101, 150)
    if pm <= 75.0:  return map_value(pm, 50.1, 75, 151, 200)
    if pm <= 150.0: return map_value(pm, 75.1, 150, 201, 300)
    if pm > 150:    return 500
    return 0

def calc_pm10_idx(pm):
    if pm <= 20.0:  return map_value(pm, 0, 20, 0, 50)
    if pm <= 50.0:  return map_value(pm, 20.1, 50, 51, 100)
    if pm <= 80.0:  return map_value(pm, 50.1, 80, 101, 150)
    if pm <= 110.0: return map_value(pm, 80.1, 110, 151, 200)
    if pm <= 200.0: return map_value(pm, 110.1, 200, 201, 300)
    if pm > 200:    return 500
    return 0

def calculate_aqi(data: SensorData) -> int:
    i_pm25 = calc_pm25_idx(data.pm2_5)
    i_pm10 = calc_pm10_idx(data.pm10)
    i_voc = int(data.voc_index)
    i_nox = int(data.nox_index)
    return max(i_pm25, i_pm10, i_voc, i_nox)

# --- API ENDPOINTS ---

@app.post("/api/report")
async def report_pollution(data: SensorData):
    if data.api_key != "SECRET_KEY_123":
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 1. Auto-Discovery
    if data.sensor_name not in sensor_locations:
        sensor_locations[data.sensor_name] = generate_warsaw_location()
        print(f"New sensor: {data.sensor_name}")

    # 2. Calculate & Store
    data.universal_aqi = calculate_aqi(data)
    latest_readings[data.sensor_name] = data

    return {"status": "success", "aqi": data.universal_aqi}

@app.get("/api/pollution-data")
async def get_pollution_map():
    response_data = []

    for name, location in sensor_locations.items():
        reading = latest_readings.get(name)
        if reading:
            response_data.append({
                "name": name,
                "lat": location["lat"],
                "lng": location["lng"],
                "aqi": reading.universal_aqi,
                "details": reading.dict()
            })

    return response_data

@app.get("/")
async def read_root():
    return FileResponse("static/map.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
