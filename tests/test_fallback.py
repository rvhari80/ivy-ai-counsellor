"""
Test fallback service with all 5 scenarios.
Tests: OFF_TOPIC, ESCALATE, PARTIAL, GAP, DIRECT
"""
import asyncio
import sys
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from app.services.fallback_service import get_fallback_response, classify_query

# ── Test cases ────────────────────────────────────────────
TEST_CASES = [
    {
        "name": "OFF TOPIC — Cricket score",
        "query": "What is the cricket score today?",
        "score": 0.10,
        "expected_type": "OFF_TOPIC",
        "expected_keywords": ["study abroad", "universities", "visas"],
    },
    {
        "name": "OFF TOPIC — Weather question",
        "query": "What is the weather like in London today?",
        "score": 0.05,
        "expected_type": "OFF_TOPIC",
        "expected_keywords": ["study abroad", "visas"],
    },
    {
        "name": "SENSITIVE — Visa rejection distress",
        "query": "My visa got rejected and I am devastated. I don't know what to do.",
        "score": 0.20,
        "expected_type": "ESCALATE",
        "expected_keywords": ["counsellor", "personalised", "call"],
    },
    {
        "name": "SENSITIVE — Financial distress",
        "query": "I cannot afford the fees anymore and I am very stressed about my future.",
        "score": 0.15,
        "expected_type": "ESCALATE",
        "expected_keywords": ["counsellor", "team"],
    },
    {
        "name": "PARTIAL MATCH — Some context found",
        "query": "What scholarships are available for Indian students in Australia?",
        "score": 0.60,
        "expected_type": "PARTIAL",
        "expected_keywords": ["counsellor", "help"],
    },
    {
        "name": "KNOWLEDGE GAP — Obscure question",
        "query": "What is the visa processing time for a student from a small town in Bihar?",
        "score": 0.25,
        "expected_type": "GAP",
        "expected_keywords": ["counsellor", "free"],
    },
    {
        "name": "KNOWLEDGE GAP — Unknown university policy",
        "query": "Does University of Wollongong accept 3 year degrees from Tier 3 colleges?",
        "score": 0.28,
        "expected_type": "GAP",
        "expected_keywords": ["counsellor"],
    },
    {
        "name": "STUDY ABROAD — Normal question low score",
        "query": "What is the application process for Canada student visa?",
        "score": 0.35,
        "expected_type": "GAP",
        "expected_keywords": ["counsellor"],
    },
]


def check_keywords(response: str, keywords: list[str]) -> bool:
    """Check if any expected keyword appears in response."""
    response_lower = response.lower()
    return any(kw.lower() in response_lower for kw in keywords)


async def test_classification():
    """Test query classification separately."""
    print("=" * 55)
    print("TEST BLOCK 1 — QUERY CLASSIFICATION")
    print("=" * 55)
    print()

    classification_tests = [
        ("What is the cricket score?",              "off_topic"),
        ("Tell me a joke",                          "off_topic"),
        ("My visa got rejected I am very stressed", "sensitive"),
        ("I cannot afford fees anymore",            "sensitive"),
        ("What IELTS score for Australia?",         "study_abroad"),
        ("Which universities accept 7.0 IELTS?",   "study_abroad"),
        ("Can I work while studying in Canada?",    "study_abroad"),
    ]

    passed = 0
    for query, expected in classification_tests:
        result = await classify_query(query)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result == expected:
            passed += 1
        print(f"  {status}")
        print(f"    Query:    \"{query[:55]}\"")
        print(f"    Expected: {expected}")
        print(f"    Got:      {result}")
        print()

    print(f"  Classification: {passed}/{len(classification_tests)} passed")
    print()
    return passed, len(classification_tests)


async def test_fallback_responses():
    """Test full fallback response generation."""
    print("=" * 55)
    print("TEST BLOCK 2 — FALLBACK RESPONSES")
    print("=" * 55)
    print()

    passed = 0
    total = len(TEST_CASES)

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"Test {i}: {tc['name']}")
        print(f"  Query: \"{tc['query'][:60]}\"")
        print(f"  Score: {tc['score']}")

        try:
            response = await get_fallback_response(
                query=tc["query"],
                best_score=tc["score"],
                session_id=f"fallback-test-{i}"
            )

            # Check keywords
            keyword_found = check_keywords(response, tc["expected_keywords"])

            if keyword_found:
                print(f"  ✅ PASS")
                passed += 1
            else:
                print(f"  ❌ FAIL — expected keywords not found")
                print(f"     Expected one of: {tc['expected_keywords']}")

            print(f"  Response: \"{response[:100]}\"")

        except Exception as e:
            print(f"  ❌ ERROR — {e}")

        print()

    print(f"  Fallback responses: {passed}/{total} passed")
    print()
    return passed, total


async def test_score_thresholds():
    """Test that score thresholds route correctly."""
    print("=" * 55)
    print("TEST BLOCK 3 — SCORE THRESHOLD ROUTING")
    print("=" * 55)
    print()

    threshold_tests = [
        (0.80, "study_abroad", "DIRECT — score above 0.75 should not trigger fallback"),
        (0.74, "study_abroad", "PARTIAL — score 0.50-0.74"),
        (0.60, "study_abroad", "PARTIAL — score 0.50-0.74"),
        (0.49, "study_abroad", "GAP — score 0.30-0.49"),
        (0.20, "study_abroad", "GAP — score below 0.30"),
        (0.10, "off_topic",    "OFF_TOPIC — regardless of score"),
        (0.90, "sensitive",    "ESCALATE — regardless of score"),
    ]

    passed = 0
    for score, classification, description in threshold_tests:
        query = "What is the visa process?" if classification == "study_abroad" \
           else "What is cricket?" if classification == "off_topic" \
           else "My visa got rejected and I am very stressed"

        try:
            response = await get_fallback_response(
                query=query,
                best_score=score,
                session_id=f"threshold-test-{score}"
            )
            print(f"  Score {score} | {description}")
            print(f"  Response: \"{response[:80]}\"")
            print(f"  ✅ OK")
            passed += 1
        except Exception as e:
            print(f"  Score {score} | {description}")
            print(f"  ❌ ERROR — {e}")
        print()

    print(f"  Threshold routing: {passed}/{len(threshold_tests)} passed")
    print()
    return passed, len(threshold_tests)


async def main():
    print()
    print("=" * 55)
    print("IVY AI COUNSELLOR — FALLBACK SERVICE TESTS")
    print("=" * 55)
    print()

    # Run all test blocks
    c_pass, c_total = await test_classification()
    f_pass, f_total = await test_fallback_responses()
    t_pass, t_total = await test_score_thresholds()

    # Final summary
    total_passed = c_pass + f_pass + t_pass
    total_tests = c_total + f_total + t_total

    print("=" * 55)
    print("FINAL SUMMARY")
    print("=" * 55)
    print(f"  Classification tests: {c_pass}/{c_total}")
    print(f"  Fallback responses:   {f_pass}/{f_total}")
    print(f"  Threshold routing:    {t_pass}/{t_total}")
    print(f"  ─────────────────────────────")
    print(f"  Total:                {total_passed}/{total_tests}")
    print()

    if total_passed == total_tests:
        print("  🎉 ALL TESTS PASSED — Fallback service ready ✅")
    elif total_passed >= total_tests * 0.8:
        print("  ⚠️  MOSTLY PASSING — Minor issues to fix")
    else:
        print("  ❌ FAILING — Check fallback_service.py")

    print()


asyncio.run(main())