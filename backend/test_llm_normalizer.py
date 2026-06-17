import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app.services.llm_normalizer import LLMNormalizer
import logging

logging.basicConfig(level=logging.INFO)

async def test_llm_normalizer():
    print("--- Testing LLM Normalizer Edge Cases ---")

    test_cases = [
        {
            "desc": "1. Phonetic Fraction Parsing",
            "payload": {
                "unresolved_items": [
                    {"index": 0, "raw_name": "potato", "raw_quantity": "sare saath", "raw_unit": "kilo"}
                ]
            }
        },
        {
            "desc": "2. Phonetic Time Parsing",
            "payload": {
                "unresolved_time": "kal sawa aath bje"
            }
        },
        {
            "desc": "3. Safe Product Spelling Fix (DO NOT infer specific brand)",
            "payload": {
                "unresolved_items": [
                    {"index": 0, "raw_name": "shraf", "raw_quantity": "ek", "raw_unit": "packet"},
                    {"index": 1, "raw_name": "surf", "raw_quantity": "do", "raw_unit": "packet"}
                ]
            }
        },
        {
            "desc": "4. Gibberish Input (Should return null/unresolved)",
            "payload": {
                "unresolved_items": [
                    {"index": 0, "raw_name": "asdfghjkl", "raw_quantity": "xxyz", "raw_unit": "bleh"}
                ]
            }
        }
    ]

    for i, test in enumerate(test_cases):
        print(f"\n{test['desc']}")
        print(f"Input: {test['payload']}")
        fixed = await LLMNormalizer.fix_messy_fields(test['payload'])
        print(f"Output: {fixed}")

if __name__ == "__main__":
    asyncio.run(test_llm_normalizer())
