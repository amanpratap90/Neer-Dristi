from typing import Any, Dict, List, Optional


def extract_val(field: Any) -> Optional[float]:
    if field is None:
        return None
    if isinstance(field, dict) and "value" in field:
        val = field["value"]
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
    try:
        return float(field)
    except (ValueError, TypeError):
        return None


def generate_disaster_briefing(telemetry: Dict[str, Any], language: str = "en") -> Dict[str, Any]:
    """
    Generates a deterministic multilingual disaster briefing grounded in
    the validated multi-signal telemetry.
    """
    loc = telemetry.get("location", {})
    pred = telemetry.get("prediction", {})
    alert = telemetry.get("alert", {})
    overall = telemetry.get("overall_monitoring", {})
    cwc = telemetry.get("cwc_ground_truth", {}) or {}
    weather = telemetry.get("current_weather", {})
    fallback = telemetry.get("fallback_environmental", {})

    basin_name = loc.get("basin_name") or loc.get("city") or loc.get("district") or "the monitored basin"
    overall_status = overall.get("status") or alert.get("level") or "NORMAL"
    ai_risk = pred.get("risk_class") or "LOW"
    ai_prob_pct = pred.get("flood_probability_pct") or 0.0

    r24 = extract_val(weather.get("rainfall_24h")) or fallback.get("rainfall_mm") or 0.0
    cwc_status = cwc.get("status") or "UNAVAILABLE"
    cwc_stage = cwc.get("water_level_m")
    cwc_danger = cwc.get("danger_level_m")

    # Multilingual headlines and summaries
    if overall_status == "CRITICAL":
        headline_en = f"CRITICAL FLOOD EMERGENCY — {basin_name.upper()}"
        headline_hi = f"गंभीर बाढ़ आपातकाल — {basin_name.upper()}"
        summary_en = f"Active severe flood alert. CWC gauge confirms elevated stage exceeding thresholds with AI inundation probability of {ai_prob_pct:.1f}%. Immediate evacuation and emergency protocols active."
        summary_hi = f"सक्रिय गंभीर बाढ़ चेतावनी। सीडब्ल्यूसी गेज खतरनाक जलस्तर की पुष्टि करता है। कृत्रिम बुद्धिमत्ता मॉडल {ai_prob_pct:.1f}% बाढ़ संभावना दिखाता है। तत्काल निकासी आवश्यक है।"
        actions = [
            "Evacuate vulnerable riverbank and low-lying zones immediately.",
            "Activate emergency shelters and deploy National Disaster Response Force (NDRF) teams.",
            "Cut power to inundated substations and monitor flood retaining bunds continuously."
        ]
    elif overall_status == "HIGH ALERT":
        headline_en = f"HIGH FLOOD ALERT DEPLOYED — {basin_name.upper()}"
        headline_hi = f"उच्च बाढ़ चेतावनी जारी — {basin_name.upper()}"
        summary_en = f"High alert condition active. Elevated precipitation ({r24:.1f} mm/24h) and physical hydrological loading detected. River telemetry indicates rapid rise."
        summary_hi = f"उच्च चेतावनी स्थिति सक्रिय। पिछले 24 घंटों में {r24:.1f} मिमी भारी वर्षा और जलग्रहण क्षेत्र में बढ़ा हुआ जलप्रवाह दर्ज किया गया है।"
        actions = [
            "Alert district disaster response teams and stage rescue boats.",
            "Notify riverbank communities to avoid low-lying crossings.",
            "Verify backup communication systems and inspect flood embankments."
        ]
    elif overall_status == "WATCH":
        headline_en = f"FLOOD WATCH ACTIVE — {basin_name.upper()}"
        headline_hi = f"बाढ़ निगरानी सक्रिय — {basin_name.upper()}"
        summary_en = f"Hydrological flood watch active for {basin_name}. Environmental indicators and cumulative rainfall warrant continuous monitoring."
        summary_hi = f"{basin_name} के लिए बाढ़ निगरानी सक्रिय है। वर्षा और पर्यावरणीय संकेतकों पर लगातार नजर रखी जा रही है।"
        actions = [
            "Monitor hourly rainfall and upstream reservoir discharge reports.",
            "Ensure emergency equipment and communication channels are operational.",
            "Advise local administrations to prepare emergency shelters if precipitation accelerates."
        ]
    else:
        headline_en = f"NORMAL HYDROLOGICAL MONITORING — {basin_name.upper()}"
        headline_hi = f"सामान्य जल-विज्ञान निगरानी — {basin_name.upper()}"
        summary_en = f"Hydrological conditions remain within baseline parameters across {basin_name}. AI probability is {ai_prob_pct:.1f}% with normal catchment loading."
        summary_hi = f"{basin_name} में जल-विज्ञान की स्थिति सामान्य सीमा के भीतर है। बाढ़ की संभावना {ai_prob_pct:.1f}% है।"
        actions = [
            f"Continue routine hydrological monitoring across {basin_name}.",
            "No emergency deployment or evacuation required at this time.",
            "Review meteorological forecast updates every 12 hours."
        ]

    is_hindi = language == "hi"

    return {
        "headline": headline_hi if is_hindi else headline_en,
        "summary": summary_hi if is_hindi else summary_en,
        "key_risks": [
            f"24-Hour Cumulative Rainfall: {r24:.1f} mm",
            f"CWC Telemetry Status: {cwc_status} ({f'{cwc_stage:.2f} m' if cwc_stage is not None else 'Unavailable'})",
            f"AI Model Probability: {ai_prob_pct:.1f}% ({ai_risk})"
        ],
        "recommendations": actions,
        "language": language
    }


async def chat_with_copilot(
    message: str,
    telemetry: Dict[str, Any],
    language: str = "en",
    history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Context-aware Copilot Chat for flood decision support.
    Answers queries grounded strictly in current telemetry.
    """
    loc = telemetry.get("location", {})
    overall = telemetry.get("overall_monitoring", {})
    pred = telemetry.get("prediction", {})
    cwc = telemetry.get("cwc_ground_truth", {})
    weather = telemetry.get("current_weather", {})

    status = overall.get("status", "NORMAL")
    prob = pred.get("flood_probability_pct", 0.0)
    cwc_status = cwc.get("status", "UNAVAILABLE")
    stage = cwc.get("water_level_m")
    city = loc.get("city") or loc.get("district") or loc.get("basin_name") or "monitored location"

    msg_lower = message.lower()
    risk_terms = ("risk", "danger", "status", "जोखिम", "खतरा", "स्थिति", "ঝুঁকি", "धोका", "ప్రమాదం", "ஆபத்து")
    rain_terms = ("rain", "rainfall", "weather", "बारिश", "वर्षा", "मौसम", "বৃষ্টি", "पाऊस", "వర్ష", "மழை")
    river_terms = ("cwc", "gauge", "water level", "river", "नदी", "जलस्तर", "জলস্তর", "नदीची", "నీటి మట్టం", "ஆற்றின்")
    evacuation_terms = ("evacuat", "shelter", "safe", "निकासी", "बचाव", "आश्रय", "উচ্ছেদ", "निवारा", "తరలింపు", "வெளியேற்ற")

    is_hindi = language == "hi"
    is_bengali = language == "bn"
    is_marathi = language == "mr"
    is_telugu = language == "te"
    is_tamil = language == "ta"

    if any(term in msg_lower for term in river_terms):
        if stage is not None:
            if is_hindi:
                reply = f"{city} के निकटतम CWC गेज का वर्तमान जलस्तर {stage:.2f} मीटर है। स्थिति: {cwc.get('condition', 'NORMAL')}।"
            else:
                reply = f"The nearest CWC gauge for {city} is {cwc.get('station_name', 'CWC Gauge')} on River {cwc.get('river', 'Ganga')}. Current observed water level is {stage:.2f} m. Status: {cwc.get('condition', 'NORMAL')}."
        else:
            reply = f"{city} के लिए लाइव CWC गेज स्थिति {cwc_status} है।" if is_hindi else f"For {city}, live CWC gauge telemetry is currently {cwc_status}."
    elif any(term in msg_lower for term in evacuation_terms):
        reply = f"{city} में पहचाने गए बाढ़ जोखिम क्षेत्रों और सुरक्षित आश्रयों को प्राथमिकता दें। वर्तमान स्थिति: {status}." if is_hindi else f"Evacuation planning should target identified flood-risk zones around {city}. Current status: {status}."
    elif any(term in msg_lower for term in risk_terms):
        if is_hindi:
            reply = f"{city} की वर्तमान बाढ़ निगरानी स्थिति {status} है। एआई बाढ़ संभावना {prob:.1f}% है।"
        else:
            reply = f"The current overall flood monitoring status for {city} is {status} ({overall.get('confidence', 'HIGH CONFIDENCE')}). AI flood probability is {prob:.1f}%. Decision basis: {' + '.join(overall.get('basis', ['AI_MODEL']))}."
    elif any(term in msg_lower for term in rain_terms):
        r24 = extract_val(weather.get("rainfall_24h")) or 0.0
        reply = f"{city} में पिछले 24 घंटों की वर्षा {r24:.1f} मिमी है। बेसिन की लगातार निगरानी हो रही है।" if is_hindi else f"Recorded 24-hour rainfall in {city} is {r24:.1f} mm. Catchment conditions are being monitored in real time."
    else:
        reply = f"ChetakAI Monitoring Summary for {city}: Status is {status}. AI inundation probability is {prob:.1f}%, CWC telemetry is {cwc_status}. Operational confidence: {overall.get('confidence', 'MEDIUM CONFIDENCE')}."

    return {
        "reply": reply,
        "status": status,
        "language": language
    }
