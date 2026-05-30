import os
from google import genai
from google.genai import types


def test_vertex_connection():
    print("🔄 Initializing modern Google Gen AI Client for Vertex AI...")

    # This automatically picks up your ADC credentials and local gcloud project config
    client = genai.Client(vertexai=True, location="us-central1")

    # Using 2.5-flash to avoid the 404 restriction on new projects
    model_id = "gemini-2.5-flash-lite"
    prompt = "Reply with 'Vertex AI is online' and nothing else."

    try:
        print(f"📡 Sending test prompt to {model_id} via Vertex AI...")
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
        )
        print(f"\n✅ Success! Response: {(response.text or '').strip()}")

    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")
        print("\n💡 Tip: If you get an API_DISABLED error, run this command to fix it:")
        print("   gcloud services enable aiplatform.googleapis.com")


if __name__ == "__main__":
    test_vertex_connection()
