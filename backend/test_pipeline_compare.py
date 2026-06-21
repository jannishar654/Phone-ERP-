import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.gemini import GeminiService

test_cases = [
    "sawa kilo doodh aur 5 packet parle G dus wala likh lo jaldi",
    "kal wali 2 bori chawal cancel kar do aur ek lal surf bhej do",
    "paanch kilo aata, aur paanch kilo aata aur daal dena",
    "gupta store se bol raha hu, ek surf excel chawal bhej dena",
    "chips bhej dena",
    "suno kal aisa karna 5:30 baje Gupta store jo ki Jamia Nagar Shain Bagh Okhla mein hai unke yaha 50 kilo aalu 50 kilo tamatar 15 kilo chini 5 badi si doodh ki thaili 5 packet surf excel aur 15 kilo namkeen aur 15 kilo rasgulla bhej dena aur unka naam Sahi ba hai",
    "Suno kal aisa karna 5:30 baje Guptastore mein jo ki Shaheen Bagh Okhla mein hai unke yahaan 50 kilo aloo 50 kilo tamatar les packit aur 15 packet cheeni bhej dena paisa udhaar rahega aur unka naam Shayam hai"
]

async def compare():
    print("=== Pipeline Extraction Comparison ===")
    
    for i, transcript in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Transcript: {transcript}")
        
        try:
            result = await GeminiService.extract_order_details(transcript)
            
            print(f"Message Type: {result.get('type')}")
            print(f"Confidence: {result.get('confidence')}")
            print(f"Extraction Notes: {result.get('extraction_notes')}")
            print("Items:")
            for item in result.get("items", []):
                print(f"  - {item['quantity']} {item['unit']} | {item['name']} (Matched: {item.get('matched', False)})")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(compare())
