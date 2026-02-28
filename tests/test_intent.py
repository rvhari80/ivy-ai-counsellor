"""
Test intent classifier with progressive 10-message conversation.
Score should climb from 0 to above 60 by end.
"""
import asyncio
import sys
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from app.utils.memory import add_message, clear_session
from app.services.intent_service import run_intent

async def test():
    session_id = "progressive-test-001"
    clear_session(session_id)

    # 10 messages — student gradually reveals profile
    conversation = [
        # Message 1-2: Generic browsing (score ~0)
        ("user",      "Hi, I want to study abroad"),
        ("assistant", "Hello! Welcome to IVY Overseas. I can help you explore study abroad options. Which country are you interested in?"),

        # Message 3-4: Country mentioned (+5)
        ("user",      "I am thinking about Canada"),
        ("assistant", "Canada is a great choice! It offers excellent universities, post-study work rights, and a welcoming environment for Indian students."),

        # Message 5-6: Course + IELTS mentioned (+5 +10)
        ("user",      "I want to do MS in Computer Science. My IELTS score is 7.0"),
        ("assistant", "With IELTS 7.0 you qualify for top Canadian universities like University of Toronto, UBC and Waterloo for MS CS."),

        # Message 7-8: Percentage + Budget mentioned (+10 +10)
        ("user",      "I have 75 percent in BTech. My budget is around 25 lakhs"),
        ("assistant", "75 percent in BTech is a solid score. With 25 lakhs budget you can comfortably cover tuition and living for one year in Canada."),

        # Message 9-10: Intake + Booking request (+15 +25)
        ("user",      "I want to apply for Fall 2025. Can I book a counselling session with IVY Overseas?"),
        ("assistant", "Absolutely! Fall 2025 applications are open now. Let me connect you with our expert counsellor for a free session."),
    ]

    print("=" * 55)
    print("PROGRESSIVE INTENT SCORING TEST")
    print("=" * 55)
    print()

    # Run classifier after each pair of messages
    pair_num = 0
    for i in range(0, len(conversation), 2):
        pair_num += 1
        user_msg = conversation[i]
        assistant_msg = conversation[i + 1]

        # Add both messages to memory
        add_message(session_id, user_msg[0], user_msg[1])
        add_message(session_id, assistant_msg[0], assistant_msg[1])

        # Run intent classifier
        result = await run_intent(session_id)

        print(f"After Message {pair_num * 2 - 1} & {pair_num * 2}:")
        print(f"  Student said:  \"{user_msg[1][:60]}...\"" if len(user_msg[1]) > 60 else f"  Student said:  \"{user_msg[1]}\"")

        if result:
            # Score bar visualisation
            bar_filled = int(result.lead_score / 5)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            print(f"  Score:         {result.lead_score:3d}/100  [{bar}]")
            print(f"  Intent:        {result.intent_level}")

            # Show what was extracted this round
            profile = result.extracted_profile
            extracted = []
            if profile.target_country:  extracted.append(f"Country={profile.target_country}")
            if profile.target_course:   extracted.append(f"Course={profile.target_course}")
            if profile.ielts_score:     extracted.append(f"IELTS={profile.ielts_score}")
            if profile.percentage:      extracted.append(f"Score={profile.percentage}")
            if profile.budget_inr:      extracted.append(f"Budget={profile.budget_inr}")
            if profile.target_intake:   extracted.append(f"Intake={profile.target_intake}")
            if profile.phone:           extracted.append(f"Phone={profile.phone}")

            if extracted:
                print(f"  Extracted:     {', '.join(extracted)}")
            else:
                print(f"  Extracted:     (nothing yet)")

            # Hot lead alert
            if result.lead_score >= 60:
                print(f"  🔥 HOT LEAD — notification would trigger!")
        else:
            print(f"  Score:         ERROR — classifier returned None")

        print()

    print("=" * 55)
    print("FINAL RESULT")
    print("=" * 55)

    final = await run_intent(session_id)
    if final:
        print(f"Intent Level:   {final.intent_level}")
        print(f"Lead Score:     {final.lead_score}/100")
        print(f"Summary:        {final.conversation_summary}")
        print(f"Action:         {final.recommended_action}")
        print()
        print("Full Profile:")
        p = final.extracted_profile
        print(f"  Name:         {p.name or 'Not provided'}")
        print(f"  Phone:        {p.phone or 'Not provided'}")
        print(f"  Email:        {p.email or 'Not provided'}")
        print(f"  Course:       {p.target_course or 'Not provided'}")
        print(f"  Country:      {p.target_country or 'Not provided'}")
        print(f"  Intake:       {p.target_intake or 'Not provided'}")
        print(f"  Budget:       {p.budget_inr or 'Not provided'}")
        print(f"  IELTS:        {p.ielts_score or 'Not provided'}")
        print(f"  Percentage:   {p.percentage or 'Not provided'}")
        print()

        # Pass/Fail
        print("=" * 55)
        print("TEST RESULTS")
        print("=" * 55)
        passed = 0
        total = 4

        # Test 1: Final score above 60
        if final.lead_score >= 60:
            print(f"  ✅ PASS — Final score {final.lead_score} is above 60")
            passed += 1
        else:
            print(f"  ❌ FAIL — Final score {final.lead_score} is below 60")

        # Test 2: Intent is HOT_LEAD
        if final.intent_level == "HOT_LEAD":
            print(f"  ✅ PASS — Intent is HOT_LEAD")
            passed += 1
        else:
            print(f"  ❌ FAIL — Intent is {final.intent_level}, expected HOT_LEAD")

        # Test 3: Country extracted
        if final.extracted_profile.target_country:
            print(f"  ✅ PASS — Country extracted: {final.extracted_profile.target_country}")
            passed += 1
        else:
            print(f"  ❌ FAIL — Country not extracted")

        # Test 4: IELTS extracted
        if final.extracted_profile.ielts_score:
            print(f"  ✅ PASS — IELTS extracted: {final.extracted_profile.ielts_score}")
            passed += 1
        else:
            print(f"  ❌ FAIL — IELTS score not extracted")

        print()
        print(f"  Result: {passed}/{total} tests passed")

        if passed == total:
            print(f"  🎉 ALL TESTS PASSED")
        else:
            print(f"  ⚠️  Some tests failed — check scoring logic")

    print()

asyncio.run(test())