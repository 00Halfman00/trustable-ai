# Koru: Building Trustable AI at 100 MPH

Koru is a real-time AI driving coach for track days, designed to demonstrate the principles of **Trustable AI** in high-velocity environments. By combining local heuristic rules with cloud-based generative AI (Gemini), Koru provides split-second feedback to drivers while maintaining deep, physics-based reasoning for post-corner analysis.

![koru landing page](koru-application/screenshot.png)

## 🏎️ Overview

You're mid-session at the track. You brake too early, coast through the apex, and get on throttle late. Koru catches all three mistakes and tells you what to fix—in real time. It balances the need for immediate, reliable feedback (Safety & Performance) with complex, contextual reasoning (Explainability).

### The Split-Brain Architecture

To achieve "Trustable AI," Koru implements a multi-path coaching strategy:

- **🔥 Hot Path (Local Heuristics):** Rules fire in under 50ms locally. No cloud round-trip. "Trail brake!" "Commit!" These are deterministic and reliable.
- **❄️ Cold Path (Gemini Flash/Pro):** Analyzes multi-frame telemetry via Vertex AI. Provides physics-based explanations with weight transfer context.
- **🛰️ Feedforward:** Geofence triggers 150m before each corner. You hear advice *before* you need it.
- **🔮 Predictive:** Tracks mistake zones from previous laps. 8-second lookahead alerts before you repeat errors.

---

## 🛠️ Project Structure

This repository is organized into three main components:

- **[`koru-application/`](./koru-application/):** A React + TypeScript dashboard. Visualizes live telemetry, handles AI coaching orchestration, and provides session replay/analysis tools.
- **[`streaming-telemetry-server/`](./streaming-telemetry-server/):** A Python FastAPI service that simulates or streams GPS data (NMEA) over Server-Sent Events (SSE).
- **[`codelab/`](./codelab/):** Detailed step-by-step instructions for building and understanding the Trustable AI principles implemented here.

---

## 🚀 Quick Start

### 1. Google Cloud Setup
This project uses Gemini on Vertex AI for deep coaching analysis.

```bash
# Initialize your GCP project and enable billing
./init.sh

# Set up environment variables
source set_env.sh

# Verify Vertex AI connectivity
python3 test_models.py
```

### 2. Start the Telemetry Server
Simulate a car driving around Thunderhill Raceway.

```bash
cd streaming-telemetry-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python ingest.py --mock
```
*The server is now streaming telemetry at `http://localhost:8000/stream`.*

### 3. Start the Koru Application
Launch the coaching dashboard.

```bash
cd koru-application
npm install
npm run dev
```
*Open [http://localhost:5173](http://localhost:5173) in your browser.*

---

## 🤖 Meet the Coaches

Koru features five AI personas, each with a distinct communication style and pedagogical approach:

| Coach | Style | Focus |
|-------|-------|-------|
| **Tony** | Motivational | Confidence and commitment. |
| **Rachel** | Technical | Vehicle dynamics and weight transfer. |
| **AJ** | Direct | Specific execution points (Braking, Apex). |
| **Garmin** | Data | Delta-V and theoretical potential. |
| **Super AJ** | Adaptive | Dynamically switches style based on error type. |

---

## 🧪 Tech Stack

- **Frontend:** React, TypeScript, Vite, Recharts, Tailwind CSS.
- **AI/ML:** Gemini 1.5 Flash/Pro (Vertex AI), Google Cloud TTS.
- **Backend:** Python, FastAPI, SSE (Server-Sent Events).
- **Infrastructure:** Google Cloud Project, gcloud CLI.

## 📄 License

This project is licensed under the MIT License.
