import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: No GEMINI_API_KEY found.")
    exit(1)

genai.configure(api_key=api_key)

print("Listing available models for this key:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
