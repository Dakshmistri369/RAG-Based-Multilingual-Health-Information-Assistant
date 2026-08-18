"""
backend/emergency_detector.py
==============================
Rule-based emergency symptom detector for SwasthyaSetu AI.

WHY RULE-BASED (NOT LLM-BASED)?
--------------------------------
Emergency detection is on the CRITICAL PATH for user safety.  Using an LLM
for this step would introduce:
  1. Latency  — an extra LLM call before the main response
  2. Non-determinism — the same query might not always trigger detection
  3. Auditability failure — rules can be reviewed, approved, and audited
     by clinical advisors; LLM decisions cannot

A deterministic keyword-match approach is:
  - Auditable by clinicians and SIH judges
  - Instantaneous (microseconds vs. seconds)
  - Guaranteed to never "forget" a critical keyword under token pressure
  - Fail-safe: false positives (over-triggering) are acceptable;
    false negatives (missing a true emergency) are NOT.

Design philosophy:
  - Case-insensitive substring matching across both English and Hindi keywords
  - Keywords are deliberately broad to maximise sensitivity (recall > precision)
  - Each category maps to a bilingual user message and the correct Indian
    emergency helpline number
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data structure ────────────────────────────────────────────────────────────

@dataclass
class EmergencyResult:
    """Structured result returned by check_emergency()."""
    is_emergency: bool
    category: str = "none"
    message: str = ""
    helpline: str = ""
    helpline_name: str = ""


# ── Emergency pattern definitions ────────────────────────────────────────────
# Each entry: keywords list (English + Hindi + Tamil/Bengali where feasible),
# a bilingual response message, and the primary Indian helpline to surface.

EMERGENCY_PATTERNS: dict[str, dict] = {

    # 1. Cardiac emergency ─────────────────────────────────────────────────────
    "cardiac_emergency": {
        "keywords": [
            # English
            "chest pain", "chest tightness", "heart attack", "cardiac arrest",
            "heart pain", "crushing chest", "chest pressure", "jaw pain with chest",
            "left arm pain with chest", "palpitation severe", "heart failure",
            "myocardial infarction", "angina", "chest discomfort radiating",
            # Hindi
            "सीने में दर्द", "सीने में तकलीफ", "दिल का दौरा", "हार्ट अटैक",
            "छाती में दर्द", "दिल का दर्द", "सीने में जकड़न", "दिल का तेज़ धड़कना",
            # Tamil
            "நெஞ்சு வலி", "மாரடைப்பு",
            # Bengali
            "বুকে ব্যথা", "হার্ট অ্যাটাক",
        ],
        "message": (
            "⚠️ EMERGENCY — This sounds like it could be a cardiac emergency.\n\n"
            "🚨 CALL 108 IMMEDIATELY or go to the nearest emergency room NOW.\n\n"
            "While waiting for help:\n"
            "• Have the person sit or lie down in a comfortable position\n"
            "• Loosen tight clothing\n"
            "• Do NOT give food or water\n"
            "• Stay with the person until help arrives\n\n"
            "⚠️ आपातकाल — यह दिल के दौरे के लक्षण हो सकते हैं।\n"
            "🚨 तुरंत 108 पर कॉल करें या नजदीकी अस्पताल जाएं।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance",
    },

    # 2. Breathing difficulty / choking ───────────────────────────────────────
    "breathing_difficulty": {
        "keywords": [
            # English
            "can't breathe", "cannot breathe", "difficulty breathing",
            "shortness of breath", "choking", "suffocating", "gasping",
            "breathing stopped", "not breathing", "blue lips", "cyanosis",
            "wheezing severe", "respiratory distress", "airway blocked",
            "throat closing", "swallowing difficulty with breathing",
            # Hindi
            "सांस नहीं आ रही", "सांस लेने में तकलीफ", "दम घुट रहा है",
            "सांस रुक गई", "गला बंद हो रहा है", "सांस फूल रही है",
            "घुटन हो रही है",
            # Tamil
            "மூச்சு திணறல்", "சுவாசிக்க முடியவில்லை",
            # Bengali
            "শ্বাস নিতে পারছি না", "শ্বাসকষ্ট",
        ],
        "message": (
            "⚠️ EMERGENCY — Severe breathing difficulty requires IMMEDIATE help.\n\n"
            "🚨 CALL 108 IMMEDIATELY.\n\n"
            "If someone is CHOKING:\n"
            "• If they can cough, encourage them to cough\n"
            "• If they cannot cough/breathe, perform back blows (5 sharp blows "
            "between shoulder blades)\n"
            "• Call 108 while performing first aid\n\n"
            "⚠️ आपातकाल — सांस न आना बहुत गंभीर है।\n"
            "🚨 तुरंत 108 पर कॉल करें।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance",
    },

    # 3. Stroke symptoms ───────────────────────────────────────────────────────
    "stroke": {
        "keywords": [
            # English — FAST acronym symptoms
            "face drooping", "face droops", "arm weakness sudden",
            "slurred speech", "speech difficulty sudden", "sudden confusion",
            "sudden severe headache", "loss of balance sudden",
            "sudden vision loss", "face numbness", "one side weakness",
            "paralysis sudden", "stroke", "brain stroke", "brain attack",
            "cannot speak suddenly", "sudden dizziness with weakness",
            # Hindi
            "चेहरा टेढ़ा", "लकवा", "अचानक बोल नहीं पा रहे", "अचानक कमजोरी",
            "ब्रेन स्ट्रोक", "दिमाग का दौरा", "एक तरफ कमजोरी",
            "अचानक सिरदर्द बहुत तेज़",
            # Tamil
            "பக்கவாதம்", "திடீர் தலைவலி",
            # Bengali
            "স্ট্রোক", "মুখ বাঁকা",
        ],
        "message": (
            "⚠️ EMERGENCY — These are WARNING SIGNS OF STROKE. Time is critical.\n\n"
            "🚨 CALL 108 IMMEDIATELY — every minute matters in a stroke.\n\n"
            "Remember FAST:\n"
            "• Face: Is one side drooping?\n"
            "• Arms: Can they raise both arms?\n"
            "• Speech: Is speech slurred or strange?\n"
            "• Time: Call 108 NOW\n\n"
            "Do NOT give food, water, or any medication.\n\n"
            "⚠️ आपातकाल — ये ब्रेन स्ट्रोक के लक्षण हो सकते हैं।\n"
            "🚨 तुरंत 108 पर कॉल करें। हर मिनट कीमती है।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance",
    },

    # 4. Severe bleeding ───────────────────────────────────────────────────────
    "severe_bleeding": {
        "keywords": [
            # English
            "severe bleeding", "heavy bleeding", "bleeding not stopping",
            "blood not stopping", "profuse bleeding", "hemorrhage",
            "haemorrhage", "losing a lot of blood", "blood gushing",
            "deep cut bleeding", "vomiting blood", "coughing up blood",
            "blood in stool heavy", "rectal bleeding heavy",
            "haematemesis", "hematemesis",
            # Hindi
            "बहुत खून बह रहा है", "खून बंद नहीं हो रहा", "गहरी चोट से खून",
            "खून की उल्टी", "खून वाला मल",
            # Tamil
            "ரத்தம் நிறுத்தப்படவில்லை", "கடுமையான இரத்தப்போக்கு",
            # Bengali
            "রক্ত বন্ধ হচ্ছে না", "প্রচুর রক্তপাত",
        ],
        "message": (
            "⚠️ EMERGENCY — Severe or uncontrolled bleeding is life-threatening.\n\n"
            "🚨 CALL 108 IMMEDIATELY.\n\n"
            "While waiting for help:\n"
            "• Apply firm, direct pressure on the wound with a clean cloth\n"
            "• Do NOT remove the cloth — add more on top if it soaks through\n"
            "• Keep the injured limb elevated if possible\n"
            "• Keep the person lying down and warm\n\n"
            "⚠️ आपातकाल — बहुत ज़्यादा खून बहना जानलेवा हो सकता है।\n"
            "🚨 तुरंत 108 पर कॉल करें।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance",
    },

    # 5. Severe allergic reaction / anaphylaxis ────────────────────────────────
    "anaphylaxis": {
        "keywords": [
            # English
            "anaphylaxis", "anaphylactic", "severe allergic reaction",
            "throat swelling after eating", "lips swelling suddenly",
            "tongue swelling", "hives with breathing difficulty",
            "rash after insect bite with breathing problem",
            "epipen", "epinephrine needed",
            "whole body rash with dizziness",
            "severe allergy", "face swelling after food",
            # Hindi
            "खाने के बाद गला सूज गया", "अचानक होंठ सूजे", "जीभ सूज गई",
            "पूरे शरीर पर चकत्ते और सांस तकलीफ",
            "गंभीर एलर्जी",
            # Tamil
            "கடுமையான ஒவ்வாமை", "தொண்டை வீக்கம்",
            # Bengali
            "গলা ফুলে যাচ্ছে", "মারাত্মক অ্যালার্জি",
        ],
        "message": (
            "⚠️ EMERGENCY — Severe allergic reaction (anaphylaxis) can be FATAL.\n\n"
            "🚨 CALL 108 IMMEDIATELY.\n\n"
            "• If they have an EpiPen (adrenaline auto-injector), use it NOW\n"
            "• Have the person lie flat with legs raised (unless breathing is "
            "difficult — then sit them up)\n"
            "• Remove the trigger if possible (e.g. sting)\n"
            "• Stay with them and call 108\n\n"
            "⚠️ आपातकाल — गंभीर एलर्जी जानलेवा हो सकती है।\n"
            "🚨 तुरंत 108 पर कॉल करें।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance",
    },

    # 6. High fever in infant ──────────────────────────────────────────────────
    "infant_high_fever": {
        "keywords": [
            # English — very specific to young infants where fever is most dangerous
            "fever in newborn", "fever in infant", "fever 3 months",
            "baby fever 2 months", "baby fever 1 month", "baby fever high",
            "infant fever", "newborn fever", "baby temperature high",
            "3 month old fever", "2 month old fever", "baby 104 fever",
            "baby 105 fever", "baby convulsion fever",
            "fever and seizure infant", "baby not responding fever",
            # Hindi
            "नवजात को बुखार", "शिशु को बुखार", "3 महीने के बच्चे को बुखार",
            "छोटे बच्चे को तेज़ बुखार", "बच्चे का तापमान बहुत ज़्यादा",
            "शिशु को दौरा और बुखार",
            # Tamil
            "குழந்தைக்கு காய்ச்சல்", "நவஜாத குழந்தை காய்ச்சல்",
            # Bengali
            "শিশুর জ্বর", "নবজাতকের জ্বর",
        ],
        "message": (
            "⚠️ URGENT — High fever in a young infant (especially under 3 months) "
            "is a MEDICAL EMERGENCY.\n\n"
            "🚨 CALL 108 or go to the nearest hospital IMMEDIATELY.\n\n"
            "• Do NOT wait to see if it improves\n"
            "• Remove excess clothing to help cool the baby\n"
            "• Do NOT sponge with ice-cold water\n"
            "• Do NOT give adult medication\n"
            "• Keep the baby hydrated (breastfeed if possible)\n\n"
            "⚠️ आपातकाल — 3 महीने से छोटे शिशु को तेज़ बुखार बहुत खतरनाक है।\n"
            "🚨 तुरंत 108 पर कॉल करें या नजदीकी अस्पताल जाएं।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance (Pediatric)",
    },

    # 7. Mental health crisis / suicidal ideation ─────────────────────────────
    "mental_health_crisis": {
        "keywords": [
            # English
            "want to kill myself", "want to die", "suicidal", "suicide",
            "end my life", "not worth living", "life is meaningless",
            "hurting myself", "self harm", "cut myself",
            "thinking about ending it", "no reason to live",
            "everyone would be better without me", "overdose on purpose",
            "planning to suicide", "method to kill myself",
            # Hindi
            "जीना नहीं चाहता", "जीना नहीं चाहती", "मरना चाहता हूं",
            "आत्महत्या", "खुद को नुकसान", "जीवन बेकार है",
            "सब मेरे बिना बेहतर होंगे",
            # Tamil
            "தற்கொலை", "வாழ வேண்டாம்",
            # Bengali
            "আত্মহত্যা", "বাঁচতে চাই না",
        ],
        "message": (
            "💙 I hear you, and what you're feeling matters deeply.\n\n"
            "Please reach out to a trained counsellor right now:\n\n"
            "📞 KIRAN Mental Health Helpline: 1800-599-0019\n"
            "(Free, 24/7, available in 13 Indian languages)\n\n"
            "You don't have to face this alone. Trained professionals are ready "
            "to listen — no judgment, completely confidential.\n\n"
            "If you are in immediate danger, also call 108.\n\n"
            "💙 आप अकेले नहीं हैं। कृपया अभी मदद लें:\n"
            "📞 KIRAN हेल्पलाइन: 1800-599-0019 (निःशुल्क, 24/7)"
        ),
        "helpline": "1800-599-0019",
        "helpline_name": "KIRAN Mental Health Helpline",
    },

    # 8. Domestic violence ────────────────────────────────────────────────────
    "domestic_violence": {
        "keywords": [
            # English
            "husband beating me", "partner hitting me", "domestic violence",
            "being abused at home", "spouse abusing me", "physical abuse at home",
            "husband hit me", "domestic abuse", "beaten by family member",
            "in-laws hurting me", "marital violence", "intimate partner violence",
            # Hindi
            "पति मार रहा है", "पति ने मारा", "घरेलू हिंसा", "पति से मार खा रही हूं",
            "घर में मार रहे हैं", "परिवार में मार खा रही हूं", "ससुराल वाले मार रहे हैं",
            # Tamil
            "கணவன் அடிக்கிறான்", "குடும்ப வன்முறை",
            # Bengali
            "স্বামী মারছে", "পারিবারিক সহিংসতা",
        ],
        "message": (
            "🆘 You are NOT alone, and what is happening to you is NOT okay.\n\n"
            "📞 Women's Helpline: 181 (Free, 24/7)\n"
            "📞 Police: 100\n"
            "📞 National Commission for Women: 7827170170\n\n"
            "You can call these numbers from any phone, any time.\n"
            "You have the right to be safe. Trained support workers can help "
            "you find shelter, legal aid, and counselling.\n\n"
            "🆘 आप अकेली नहीं हैं। यह गलत है और आपको मदद मिल सकती है।\n"
            "📞 महिला हेल्पलाइन: 181 (निःशुल्क, 24/7)\n"
            "📞 पुलिस: 100"
        ),
        "helpline": "181",
        "helpline_name": "Women's Helpline",
    },

    # 9. Poisoning / accidental ingestion ────────────────────────────────────
    "poisoning": {
        "keywords": [
            # English
            "swallowed poison", "drank poison", "poisoning", "ingested chemical",
            "ate rat poison", "ingested bleach", "drank kerosene",
            "swallowed pills entire bottle", "overdose accidental",
            "child ate tablets", "child swallowed medicine",
            "insecticide poisoning", "organophosphate poisoning",
            "pesticide poisoning", "snake bite", "scorpion sting severe",
            # Hindi
            "ज़हर खा लिया", "ज़हर पी लिया", "कीटनाशक खा लिया",
            "बच्चे ने दवाई खा ली", "सांप ने काटा", "बिच्छू ने काटा",
            "नींद की दवाई ज़्यादा खा ली",
            # Tamil
            "விஷம் குடித்தான்", "பாம்பு கடித்தது",
            # Bengali
            "বিষ খেয়েছে", "সাপে কামড়েছে",
        ],
        "message": (
            "⚠️ EMERGENCY — Poisoning requires IMMEDIATE medical attention.\n\n"
            "🚨 CALL 108 IMMEDIATELY.\n\n"
            "• Do NOT induce vomiting unless instructed by a medical professional\n"
            "• Try to identify the substance taken and keep the container\n"
            "• Note the time it was ingested and approximate amount\n"
            "• Keep the person conscious and talking\n"
            "• For snake/scorpion bites: keep the bitten limb still and "
            "BELOW heart level — do NOT suck out the venom\n\n"
            "⚠️ आपातकाल — ज़हर खाना/पीना जानलेवा हो सकता है।\n"
            "🚨 तुरंत 108 पर कॉल करें। उल्टी मत करवाएं।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance / Poison Control",
    },

    # 10. Severe abdominal pain / pregnancy emergency ────────────────────────
    "obstetric_emergency": {
        "keywords": [
            # English
            "severe abdominal pain in pregnancy", "heavy bleeding in pregnancy",
            "pregnant and bleeding heavily", "baby not moving in third trimester",
            "fetal movement stopped", "contractions every 2 minutes",
            "water broke before 37 weeks", "preterm labour", "premature labour",
            "pre-eclampsia", "eclampsia", "pregnancy seizure",
            "placenta pain", "cord prolapse", "obstetric emergency",
            "pregnant and unconscious", "pregnant not responding",
            # Hindi
            "गर्भावस्था में तेज़ दर्द", "गर्भावस्था में ज़्यादा खून", "प्रसव पीड़ा",
            "गर्भ में बच्चा नहीं हिल रहा", "प्रीटर्म लेबर", "गर्भावस्था में दौरा",
            "प्रेगनेंसी में ब्लीडिंग", "डिलीवरी जल्दी हो रही है",
            # Tamil
            "கர்ப்பகாலத்தில் வலி", "கர்ப்பகாலத்தில் ரத்தம்",
            # Bengali
            "গর্ভাবস্থায় ব্যথা", "গর্ভাবস্থায় রক্তক্ষরণ",
        ],
        "message": (
            "⚠️ EMERGENCY — This sounds like an obstetric (pregnancy) emergency.\n\n"
            "🚨 CALL 108 IMMEDIATELY or go to the nearest hospital/maternity "
            "ward RIGHT NOW. Do NOT wait.\n\n"
            "• If there is heavy bleeding: lie down and keep feet elevated\n"
            "• If water has broken early: go to hospital immediately\n"
            "• If baby is not moving: go to hospital for fetal monitoring\n"
            "• Bring your maternity records/cards if available\n\n"
            "⚠️ आपातकाल — यह गर्भावस्था की आपातस्थिति हो सकती है।\n"
            "🚨 तुरंत 108 पर कॉल करें या नज़दीकी अस्पताल जाएं।"
        ),
        "helpline": "108",
        "helpline_name": "National Emergency Ambulance",
    },
}


# ── Core detection function ───────────────────────────────────────────────────

def check_emergency(query_text: str, language_code: str = "en") -> EmergencyResult:
    """
    Scan *query_text* for emergency keywords and return a structured result.

    This function is DETERMINISTIC and rule-based (no LLM involved).
    It runs BEFORE any retrieval or generation, making it the fastest possible
    safety gate in the pipeline.

    Args:
        query_text:     The user's raw query string.
        language_code:  Detected language code (unused in matching — matching
                        is done on raw text regardless of detected language,
                        since keyword lists are already multilingual).

    Returns:
        EmergencyResult with is_emergency=True and populated fields if a match
        is found, otherwise is_emergency=False.
    """
    if not query_text:
        return EmergencyResult(is_emergency=False)

    # Normalise to lowercase for case-insensitive matching
    query_lower = query_text.lower()

    for category, config in EMERGENCY_PATTERNS.items():
        for keyword in config["keywords"]:
            # Substring matching — sufficient for keyword safety nets
            if keyword.lower() in query_lower:
                logger.info(
                    "EMERGENCY DETECTED: category='%s' triggered by keyword='%s'",
                    category, keyword,
                )
                return EmergencyResult(
                    is_emergency=True,
                    category=category,
                    message=config["message"],
                    helpline=config["helpline"],
                    helpline_name=config["helpline_name"],
                )

    logger.debug("No emergency patterns matched for query: '%s...'", query_text[:50])
    return EmergencyResult(is_emergency=False)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_cases = [
        # (query, expected_category)
        ("I have severe chest pain and my left arm is hurting", "cardiac_emergency"),
        ("मुझे सीने में दर्द है और बाएं हाथ में दर्द है", "cardiac_emergency"),
        ("My 2-month-old baby has a very high fever", "infant_high_fever"),
        ("I want to kill myself, I can't go on", "mental_health_crisis"),
        ("मेरा पति मुझे मार रहा है, मुझे डर है", "domestic_violence"),
        ("Child swallowed some rat poison tablets", "poisoning"),
        ("गर्भावस्था में बहुत ज़्यादा खून आ रहा है", "obstetric_emergency"),
        ("face drooping and slurred speech suddenly", "stroke"),
        # Non-emergency cases — should NOT trigger
        ("What are the symptoms of the common cold?", "none"),
        ("मुझे खांसी और हल्का बुखार है, कोई घरेलू उपाय बताएं", "none"),
        ("What is Ayushman Bharat Yojana?", "none"),
        ("ডায়াবেটিস রোগীর খাদ্য তালিকা কেমন হওয়া উচিত?", "none"),
    ]

    print("=" * 70)
    print("Emergency Detector Test Results")
    print("=" * 70)

    passed = 0
    for query, expected in test_cases:
        result = check_emergency(query)
        status = "✓" if (
            (result.is_emergency and result.category == expected) or
            (not result.is_emergency and expected == "none")
        ) else "✗"
        passed += 1 if status == "✓" else 0

        print(f"\n{status} Query   : {query[:65]}{'...' if len(query) > 65 else ''}")
        print(f"  Expected : {expected}")
        print(f"  Got      : {'EMERGENCY → ' + result.category if result.is_emergency else 'NOT EMERGENCY'}")
        if result.is_emergency:
            print(f"  Helpline : {result.helpline} ({result.helpline_name})")

    print(f"\n{'=' * 70}")
    print(f"Results: {passed}/{len(test_cases)} tests passed")
    print("=" * 70)
