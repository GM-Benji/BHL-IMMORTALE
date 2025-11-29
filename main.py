import uvicorn
import random
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# Mount the static folder so we can serve the HTML file easily
# Ensure the directory exists to prevent errors
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- DATA MODELS ---
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

# --- STORAGE ---

# We store the fixed location of every sensor here
# Format: { "sensor_name": { "lat": 52.x, "lng": 21.x } }
sensor_locations: Dict[str, Dict[str, float]] = {}

# We store the latest reading here
latest_readings: Dict[str, SensorData] = {}

def generate_warsaw_location():
    """Generates a random coordinate roughly within Warsaw city limits."""
    # Warsaw Center approx: 52.2297, 21.0122
    # Lat variation: +/- 0.06
    # Lng variation: +/- 0.10
    lat_base = 52.2297
    lng_base = 21.0122

    return {
        "lat": lat_base + random.uniform(-0.06, 0.06),
        "lng": lng_base + random.uniform(-0.10, 0.10)
    }

# --- API ENDPOINTS ---

@app.post("/api/report")
async def report_pollution(data: SensorData):
    """
    Endpoint for C++ Clients (and Simulator).
    """
    if data.api_key != "SECRET_KEY_123":
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 1. AUTO-DISCOVERY LOGIC
    # If we haven't seen this sensor before, assign it a spot in Warsaw
    if data.sensor_name not in sensor_locations:
        sensor_locations[data.sensor_name] = generate_warsaw_location()
        print(f"New sensor discovered: {data.sensor_name} -> Assigned to Warsaw Map.")

    # 2. Store the reading
    latest_readings[data.sensor_name] = data
    return {"status": "success"}

@app.get("/api/pollution-data")
async def get_pollution_map():
    """
    Returns list of sensors with their location AND latest pollution data.
    """
    response_data = []

    for name, location in sensor_locations.items():
        reading = latest_readings.get(name)

        # Only return sensors that have reported data
        if reading:
            response_data.append({
                "name": name,
                "lat": location["lat"],
                "lng": location["lng"],
                "pm2_5": reading.pm2_5,
                "details": reading.dict()
            })

    return response_data

# --- FRONTEND ---

@app.get("/")
async def read_root():
    return FileResponse("static/map.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
