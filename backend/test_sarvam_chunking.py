import sys
import os

# Add backend dir to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.sarvam import SarvamService

def test_chunking():
    passed = 0
    total = 0
    
    print("--- Testing Sarvam Chunking Strategy ---\n")
    
    # 1. Short Audio logic when duration > 28 but silences are early
    total += 1
    duration = 35.0
    silences = [5.0, 10.0]
    chunks = SarvamService._calculate_chunk_boundaries(duration, silences)
    # Expected:
    # current=0. valid=[5, 10]. ideal=none. split at 10.
    # current=10. valid=[]. split at min(10+28, 35) = 35. 
    # Since it reaches the end, no overlap is applied to start of this chunk.
    if len(chunks) == 2 and chunks == [(0.0, 10.0), (10.0, 35.0)]:
        print(f"  [PASS] Audio (35s) early silences -> {chunks}")
        passed += 1
    else:
        print(f"  [FAIL] Audio (35s) early silences -> Expected [(0.0, 10.0), (10.0, 35.0)], got {chunks}")
        
    # 2. Audio near 60s with good silences
    total += 1
    duration = 60.0
    # Silences at 5s, 14s, 25s, 38s, 50s, 58s
    silences = [5.0, 14.0, 25.0, 38.0, 50.0, 58.0]
    chunks = SarvamService._calculate_chunk_boundaries(duration, silences)
    # Expected: 
    # Current=0. IDEAL=12. Valid: 5, 14, 25. Ideal valid: 14, 25. Pick first ideal -> 14.0. Chunk 1: 0-14.
    # Current=14. IDEAL=14+12=26. Valid: 25, 38. Ideal valid: 38. Pick first ideal -> 38. Chunk 2: 14-38.
    # Current=38. IDEAL=38+12=50. Valid: 50, 58. Ideal valid: 50. Pick first ideal -> 50. Chunk 3: 38-50.
    # Current=50. IDEAL=50+12=62. Valid: 58. Ideal valid: None. Pick last valid -> 58. Chunk 4: 50-58.
    # Current=58. IDEAL=58+12=70. Valid: None. Fallback force split -> 60. Chunk 5: 58-60.
    if chunks == [(0.0, 14.0), (14.0, 38.0), (38.0, 50.0), (50.0, 58.0), (58.0, 60.0)]:
        print(f"  [PASS] 60s audio with silences -> {chunks}")
        passed += 1
    else:
        print(f"  [FAIL] 60s audio with silences -> Got {chunks}")

    # 3. Audio with NO silences (fallback force split with overlap)
    total += 1
    duration = 40.0
    silences = []
    chunks = SarvamService._calculate_chunk_boundaries(duration, silences)
    # Expected:
    # Current=0. No valid. Force split at min(28, 40) -> 28.0. Chunk 1: 0-28.
    # Overlap -> Next starts at 28.0 - 0.5 = 27.5
    # Current=27.5. No valid. Force split at min(27.5+28, 40) -> 40.0. Chunk 2: 27.5-40.
    if chunks == [(0.0, 28.0), (27.5, 40.0)]:
        print(f"  [PASS] 40s audio NO silences -> {chunks}")
        passed += 1
    else:
        print(f"  [FAIL] 40s audio NO silences -> Got {chunks}")

    # 4. Long speech, missing IDEAL silences but has valid silences before HARD_MAX
    total += 1
    duration = 50.0
    silences = [10.0, 20.0]
    chunks = SarvamService._calculate_chunk_boundaries(duration, silences)
    # Current=0. IDEAL=12. Valid: 10, 20. Ideal valid: 20. Pick -> 20. Chunk 1: 0-20.
    # Current=20. No silences > 20. Force split at 20+28=48. Chunk 2: 20-48. Next start = 47.5
    # Current=47.5. Force split at 50. Chunk 3: 47.5-50.
    if chunks == [(0.0, 20.0), (20.0, 48.0), (47.5, 50.0)]:
        print(f"  [PASS] 50s audio sparse silences -> {chunks}")
        passed += 1
    else:
        print(f"  [FAIL] 50s audio sparse silences -> Got {chunks}")

    print(f"\nTotal: {total}, Passed: {passed}, Failed: {total - passed}")

if __name__ == "__main__":
    test_chunking()
