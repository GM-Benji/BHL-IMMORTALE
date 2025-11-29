import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse

app = FastAPI()

# --- 1. THE BACKEND DATA ---

# Leaflet prefers coordinates as [Latitude, Longitude] arrays.
# We will draw the same "Bermuda Triangle" as the previous example.
BORDER_DATA = [
    [25.774, -80.190],  # Miami
    [18.466, -66.118],  # Puerto Rico
    [32.321, -64.757]  # Bermuda
]


@app.get("/api/zone-borders")
async def get_borders():
    return {"coordinates": BORDER_DATA}


# --- 2. THE FRONTEND (Leaflet.js + OSM) ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse("static/map.html")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
