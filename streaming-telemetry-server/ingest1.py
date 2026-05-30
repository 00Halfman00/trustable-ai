import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import random
import json
import logging
import sys
from datetime import datetime, timezone
import csv
import re
import os
import vertexai
from vertexai.generative_models import GenerativeModel
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# <-----  i.    LOAD ENVIRONMENT VARIABLES  ------>
load_dotenv()  # Load environment variables earlyI

# <-----  II.    CONFIGURE LOGGING  ------>

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ingest.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
print("✅ LOGGER ARE CONFIGURED, LOADED AND READY TO GO!")


# <-----  III.   INITIATE VERTEX AI  ------>

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")

if PROJECT_ID:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    ai_model = GenerativeModel(MODEL_NAME)
    logger.info(
        f"Vertex AI initialized with project {PROJECT_ID} and model {MODEL_NAME}"
    )
else:
    ai_model = None
    logger.error("No PROJECT_ID found. AI features will not work.")


# <-----  IV.    DATA STRUCTURES & CLASSES  ------>


class CoachingRequest(BaseModel):
    prompt: str
    model: str = MODEL_NAME
    generationConfig: dict = Field(default_factory=dict)


class BroadCaster:
    def __init__(self) -> None:
        self.subscribers = set()

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


async def broadcast_data(data: str):
    await broadcaster.publish(data)


def parse_vbox_coord(coord_str: str):
    """Parses VBOX coordinate string like '38°9.631176 N' to decimal degrees."""
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
        logger.error(f"Error parsing coordinate '{coord_str}': {e}")
        return 0.0


def load_track_data(filepath: str):
    """Loads track data from VBOX CSV."""
    data = []
    try:
        if not os.path.exists(filepath):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(script_dir, "SampleStream2024.csv")

        if not os.path.exists(filepath):
            logger.error(f"VBOX CSV file not found at {filepath}")
            return []

        logger.info(f"Loading track data from {filepath}")
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                try:
                    lat = parse_vbox_coord(row["Latitude"])
                    lon = parse_vbox_coord(row["Longitude"])
                    speed_kmh = float(row["Speed (km/h)"] or 0)
                    heading = float(row["Heading (Degrees)"] or 0)
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

            logger.info(f"Loaded {count} track points from CSV.")
            return data
    except Exception as e:
        logger.error(f"Failed to load track data: {e}")
        return []


async def mock_gps_generator(mode="nmea"):
    """Generates mock GPS data from VBOX CSV."""
    logger.info(f"Starting mock GPS Generator in {mode} mode.")
    mock_settings["track_data"] = load_track_data("SampleStream2024.csv")

    if not mock_settings["track_data"]:
        logger.warning("No track data loaded. Falling back to static point.")
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
                "alt": 0,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    is_mock = os.environ.get("MOCK_MODE", "true").lower() == "true"
    is_binary = os.environ.get("BINARY_MODE", "false").lower() == "true"
    mode = "binary" if is_binary else "nmea"

    if is_mock:
        print(f"🚀 STARTING SERVER IN MOCK MODE: ({mode})")
        app.state.gps_task = asyncio.create_task(mock_gps_generator(mode))

    yield

    # SHUTDOWN
    print("🛑 SHUTTING DOWN SERVER... CLEANING UP RESOURCES.")
    if hasattr(app.state, "gps_task"):
        app.state.gps_task.cancel()
        try:
            await app.state.gps_task
        except asyncio.CancelledError:
            print("✅ GPS generator task cancelled successfully.")


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
async def update_mock_state(update: MockUpdate):
    mock_settings["enabled"] = update.enabled
    if not update.enabled:
        mock_settings["track_index"] = 0
        logger.info("MOCK DATA DISABLED AND RESET")
    else:
        logger.info("MOCK DATA ENABLED")
    return {"status": "ok", "mock_enabled": mock_settings["enabled"]}


@app.get("/events")
async def message_stream(request: Request):
    async def event_generator():
        async for message in broadcaster.subscribe():
            if await request.is_disconnected():
                break
            yield {"data": message}

    return EventSourceResponse(event_generator())


@app.post("/coach")
async def get_coach_proxy(request: CoachingRequest):
    if not ai_model:
        return {"text": "AI features are currently disabled (missing PROJECT_ID)."}

    prompt = request.prompt
    logger.info(f"RECEIVED COACHING PROMPT:\n {prompt}")
    try:
        response = ai_model.generate_content(prompt)
        logger.info("GENERATED AI RESPONSE SUCCESSFULLY.")
        return {"text": response.text}
    except Exception as e:
        logger.error(f"ERROR GENERATING AI RESPONSE: {e}")
        return {"text": "Sorry, an error occurred while generating the response."}


# <-----  VIII.    MAIN ENTRYPOINT  ------>

if __name__ == "__main__":
    server_port = int(os.environ.get("PORT", 8080))
    server_host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=server_host, port=server_port)
