#!/usr/bin/env python3
"""Debug: What does Gemini actually return in the response object?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

prompt = "Rewrite this Amazon title to be 180-200 characters: Kakss Neoprene Dumbbells 1+1=2 KG Pack of 1 KG Each, Anti-Slip Coated Hand Weights for Home Gym & Fitness Training -Pink. Add keywords: dumbbells set, weights, home gym equipment, neoprene dumbbell set. Output ONLY the title."

resp = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.4,
        max_output_tokens=300,
    ),
)

print("=== RESPONSE OBJECT ===")
print(f"Type: {type(resp)}")
print(f"resp.text: {repr(resp.text)}")
print()

for ci, candidate in enumerate(resp.candidates):
    print(f"Candidate {ci}:")
    print(f"  finish_reason: {candidate.finish_reason}")
    for pi, part in enumerate(candidate.content.parts):
        print(f"  Part {pi}:")
        print(f"    type: {type(part).__name__}")
        print(f"    has text: {hasattr(part, 'text')}")
        if hasattr(part, 'text'):
            print(f"    text: {repr(part.text[:200] if part.text else None)}")
        if hasattr(part, 'thought'):
            print(f"    thought: {repr(part.thought)}")
        # Check for other attributes
        attrs = [a for a in dir(part) if not a.startswith('_')]
        print(f"    attrs: {attrs}")
