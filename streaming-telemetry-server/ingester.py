from typing import Any
from dotenv import load_dotenv
import logging
import sys
import os
from google import genai
from pydantic import BaseModel, Field
import asyncio
import re
import csv
import random
import json
from datetime import datetime, timezone

# app libraries
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import uvicorn

# <-----  I.    LOAD ENVIRONMENT VARIABLES (AT TOP) ------>
load_dotenv()


# <-----  II.    CONFIGURE LOGGING  (AT TOP)------>

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ingest.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

print("✅ LOGGERS ARE CONFIGURED, LOADED AND READY TO GO!")


# <-----  III.   INITIATE VERTEX AI  (AT TOP)------>

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
client = None

if PROJECT_ID:
    try:
        logger.info(
            f"🔄 Initializing modern Google Gen AI Client for Vertex AI... project: ({PROJECT_ID})"
        )
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        logger.error(f"Failed to initialize modern Google Gen AI Client: {e}")
        client = None
else:
    logger.error(
        "NO PROJECT_ID FOUND IN ENVIRONMENT VARIABLES. AI FEATURES WILL NOT WORK."
    )


# <-----  IV.    DATA STRUCTURES & CLASSES  ------>


class CoachingRequest(BaseModel):
    prompt: str
    model: str = MODEL_NAME
    generationConfig: dict = Field(default_factory=dict)


class BroadCaster:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[Any]] = set()

    async def publish(self, message):
        for queue in self.subscribers:
            await queue.put(message)

    async def subscribe(self):
        queue = asyncio.Queue()
        self.subscribers.add(queue)
        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            self.subscribers.remove(queue)


class MockUpdate(BaseModel):
    enabled: bool


broadcaster = BroadCaster()
mock_settings = {"enabled": True, "track_data": [], "track_index": 0}


# <-----  V.    HELPER FUNCTIONS  ------>


async def broadcast_data(data: str) -> None:
    await broadcaster.publish(data)


def parse_vbox_coord(coord_str: str) -> float:
    """
    Parses VBOX coordinate string like '38°9.631176 N' to decimal degrees.
    """

    try:
        match = re.match(r"(\d+)°([\d\.]+)\s+([NSEW])", coord_str.strip())

        if not match:
            return 0.0

        degrees = int(match.group(1))
        minutes = float(match.group(2))
        direction = match.group(3)
        decimal_degrees = degrees + (minutes / 60.0)

        if direction in ["S", "W"]:
            decimal_degrees = -decimal_degrees

        return decimal_degrees

    except Exception as e:
        logger.error(f"ERROR PARSING COORDINATES '{coord_str}': {e}")
        return 0.0


def load_track_data(filepath: str):
    """
    Loads track data from VBOX csv.
    """

    data = []
    try:
        if not os.path.exists(filepath):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(script_dir, "SampleStream2024.csv")

        if not os.path.exists(filepath):
            logger.error(f"VBOX CSV FILE NOT FOUND AT {filepath}")
            return []

        logger.info(f"LOADING TRACK DATA FROM: {filepath}")

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            count = 0

            for row in reader:
                try:
                    lat = parse_vbox_coord(row["Latitude"])
                    lon = parse_vbox_coord(row["Longitude"])
                    speed_kmh = float(row["Speed (km/h)"]) or 0
                    heading = float(row["Heading (Degrees)"]) or 0

                    data.append(
                        {
                            "lat": lat,
                            "lon": lon,
                            "speed_kmh": speed_kmh,
                            "heading": heading,
                        }
                    )

                    count += 1

                except (ValueError, KeyError) as e:
                    continue

            logger.info(f"LOADED ({count}) TRACK POINTS FROM CSV.")
            return data

    except Exception as e:
        logger.error(f"FAILED TO LOAD TRACK DATA: {e}")
        return []


async def mock_generator(mode="nmea"):
    """
    Generates mock GPS data from VBOX csv.
    """

    logger.info(f"STARTING MOCK GPS GENERATOR IN ({mode}) mode.")
    mock_settings["track_data"] = load_track_data("SampleStream2024.csv")

    if not mock_settings["track_data"]:
        logger.warning("NO TRACK DATA LOADED. FALLING BACK TO STATIC POINT.")
        mock_settings["track_data"] = [
            {"lat": 37.7749, "lon": -122.4194, "speed_kmh": 0, "heading": 0}
        ]

    while True:
        if not mock_settings["enabled"]:
            await asyncio.sleep(0.5)
            continue

        idx = mock_settings["track_index"]
        track_data = mock_settings["track_data"]

        if idx >= len(track_data):
            idx = 0

        point = track_data[idx]
        mock_settings["track_index"] = idx + 1  # Increment index

        if mode == "binary":
            dummy_bytes = random.randbytes(16)
            data = json.dumps(
                {
                    "class": "BINARY",
                    "data": dummy_bytes.hex().upper(),
                    "device": "/dev/mock",
                }
            )
        else:
            speed_mps = point["speed_kmh"] / 3.6
            current_time = datetime.now(timezone.utc).isoformat()
            tpv = {
                "class": "TPV",
                "device": "/dev/mock",
                "mode": 3,
                "time": current_time,
                "lat": point["lat"],
                "lon": point["lon"],
                "speed": speed_mps,
                "track": point["heading"],
                "climb": 0,
                "epx": 0.5,
                "epy": 0.5,
                "epv": 1.0,
            }
            data = json.dumps(tpv)

        await broadcast_data(data)
        await asyncio.sleep(0.1)


# <-----  VI.    LIFESPAN & APP INIT  ------>


# An async context manager must be a generator function, and in Python,
# a function only becomes a generator if it contains the yield keyword.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP: Everything BEFORE the yield runs
    is_mock = os.environ.get("MOCK_MODE", "true").lower() == "true"
    is_binary = os.environ.get("BINARY_MODE", "false").lower() == "true"
    mode = "binary" if is_binary else "nmea"

    if is_mock:
        print(f"🚀 STARTING IN MOCK MODE WITH VBOX DATA STREAM...")
        app.state.gps_task = asyncio.create_task(mock_generator(mode=mode))

    yield  # <--- FastAPI pauses here and starts receiving web requests

    # 2. SHUTDOWN: Everything AFTER the yield runs on
    print("🛑 SHUTTING DOWN SERVER AND CLEANING UP RESOURCES...")
    if hasattr(app.state, "gps_task"):
        app.state.gps_task.cancel()
        try:
            await app.state.gps_task
        except asyncio.CancelledError:
            print("✅ GPS GENERATOR TASK CANCELLED SUCCESSFULLY.")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# <-----  VII.    API ROUTES  ------>


@app.get("/state")
async def get_state():
    return {"mock_enabled": mock_settings["enabled"]}


@app.post("/mock")
async def update_mock_settings(update: MockUpdate):
    mock_settings["enabled"] = update.enabled
    if not update.enabled:
        mock_settings["track_index"] = 0  # Reset track index when disabling mock mode
        logger.info("MOCK MODE DISABLED. TRACK INDEX RESET TO 0.")
        return {"status": "success", "mock_enabled": mock_settings["enabled"]}
    else:
        logger.info("MOCK MODE ENABLED. STARTING FROM CURRENT TRACK INDEX.")
        return {"status": "success", "mock_enabled": mock_settings["enabled"]}


@app.get("/events")
async def message_stream(request: Request):
    async def event_generator():
        async for message in broadcaster.subscribe():
            if await request.is_disconnected():
                break
            yield {"data": message}

    return EventSourceResponse(event_generator())


@app.post("/coach")
async def get_coach_proxy(pydantic_model: CoachingRequest):
    if not client:
        return {"text": "AI CLIENT NOT AVAILABLE. PLEASE CHECK SERVER CONFIGURATION."}

    prompt = pydantic_model.prompt
    logger.info(f"RECEIVED COACHING REQUEST WITH PROMPT: {prompt[:50]}...")

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        logger.info("AI CLIENT GENERATED RESPONSE SUCCESSFULLY.")
        return {"text": response.text}
    except Exception as e:
        logger.error(f"ERROR GENERATING AI RESPONSE: {e}")
        return {"text": "ERROR GENERATING AI RESPONSE. PLEASE TRY AGAIN LATER."}


# <-----  VIII.    MAIN ENTRYPOINT  ------>

if __name__ == "__main__":
    server_port = int(os.environ.get("PORT", 8080))
    server_host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=server_host, port=server_port)
