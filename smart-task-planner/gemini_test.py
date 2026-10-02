from google import genai
from google.genai import types

print("Starting Gemini test...")

client = genai.Client(
    http_options=types.HttpOptions(
        timeout=15000,
        retry_options=types.HttpRetryOptions(
            attempts=1
        )
    )
)

print("Client created. Sending request...")

try:

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents="Say only: OK"
    )

    print("SUCCESS:")
    print(response.text)

except Exception as e:

    print("ERROR:")
    print(type(e).__name__)
    print(e)