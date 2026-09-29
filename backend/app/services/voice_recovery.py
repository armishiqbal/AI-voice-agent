"""Short, truthful spoken recovery prompts for incomplete voice input."""


TRANSCRIPTION_RECOVERY_PROMPTS = {
    "ur-Latn": "Mujhe aapki poori baat samajh nahi aayi. Meherbani karke dobara boliye.",
    "ur-Arab": "مجھے آپ کی پوری بات سمجھ نہیں آئی۔ براہِ کرم دوبارہ بولیے۔",
    "en": "I didn't catch the whole request. Please say it again.",
    "hi": "आपकी पूरी बात समझ नहीं आई। कृपया दोबारा कहें।",
    "ar": "لم ألتقط طلبك بالكامل. من فضلك أعد قوله.",
    "pa": "تہاڈی پوری گل سمجھ نہیں آئی۔ مہربانی کرکے دوبارہ دسو۔",
    "bn": "আপনার পুরো কথাটি বুঝতে পারিনি। দয়া করে আবার বলুন।",
}

TELEPHONY_PROVIDER_FAILURE_PROMPTS = {
    "ur-Latn": "Maazrat, abhi call process karne mein masla aa raha hai. Baraye meherbani kuch dair baad dobara call kijiye.",
    "ur-Arab": "معذرت، ابھی کال پراسیس کرنے میں مسئلہ آ رہا ہے۔ براہِ کرم کچھ دیر بعد دوبارہ کال کیجیے۔",
    "en": "I'm having trouble processing calls right now. Please call back shortly.",
    "hi": "क्षमा कीजिए, अभी कॉल में तकनीकी समस्या आ रही है। कृपया थोड़ी देर बाद फिर कॉल करें।",
    "ar": "عذرًا، أواجه مشكلة في معالجة المكالمات الآن. يُرجى إعادة الاتصال بعد قليل.",
    "pa": "معذرت، ہنیر کال وچ مسئلہ آ ریا اے۔ مہربانی کرکے تھوڑی دیر بعد دوبارہ کال کرو۔",
    "bn": "দুঃখিত, এখন কলটি প্রক্রিয়া করতে সমস্যা হচ্ছে। অনুগ্রহ করে একটু পরে আবার কল করুন।",
}


def transcription_recovery_prompt(language: str, transcript: str | None = None) -> str | None:
    """Ask the caller to restate the request, never to act on an interim transcript."""

    prompt = TRANSCRIPTION_RECOVERY_PROMPTS.get(language)
    if prompt is None or not transcript:
        return prompt

    excerpt = " ".join(transcript.split())[:180].strip()
    if not excerpt:
        return prompt
    if len(" ".join(transcript.split())) > len(excerpt):
        excerpt = f"{excerpt.rstrip(' .,!?،۔')}…"

    restatement_prompts = {
        "ur-Latn": f'Mujhe yeh hissa sunai diya: “{excerpt}”. Poori request ek baar phir bol dein.',
        "ur-Arab": f'مجھے یہ حصہ سنائی دیا: “{excerpt}”۔ براہِ کرم پوری بات ایک بار پھر بولیے۔',
        "en": f'I caught this part: “{excerpt}”. I missed the rest. Please repeat your full request.',
        "hi": f'मैंने यह हिस्सा सुना: “{excerpt}”। बाकी बात समझ नहीं आई। कृपया पूरी बात फिर से कहें।',
        "ar": f'سمعت هذا الجزء: “{excerpt}”. لم أفهم بقية الطلب. أعد طلبك كاملًا من فضلك.',
        "pa": f'مینوں ایہ حصہ سنائی دتا: “{excerpt}”。 باقی گل نہیں سمجھ آئی۔ پوری گل اک واری فیر دسو۔',
        "bn": f'এই অংশটি শুনেছি: “{excerpt}”। বাকিটা বুঝতে পারিনি। পুরো অনুরোধটি আবার বলুন।',
    }
    return restatement_prompts.get(language, prompt)


def telephony_provider_failure_prompt(language: str) -> str:
    """Give phone callers a brief truthful message before a failed call is closed."""

    return TELEPHONY_PROVIDER_FAILURE_PROMPTS.get(
        language, TELEPHONY_PROVIDER_FAILURE_PROMPTS["en"]
    )
