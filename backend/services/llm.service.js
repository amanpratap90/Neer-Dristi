/**
 * Multilingual AI Briefings Generator
 * Uses ONLY canonical telemetry data — never fabricates values.
 *
 * STRICT RULE:
 * The deterministic backend calculates overall monitoring status (CRITICAL, HIGH, ELEVATED, NORMAL).
 * The LLM MUST NOT calculate or override this status; it only generates natural-language
 * explanations grounded in the already-calculated status.
 */

/**
 * Extract a numeric value from either a raw number or a structured {value, unit, ...} object.
 */
function extractValue(field) {
  if (field === null || field === undefined) return null;
  if (typeof field === "object" && "value" in field) {
    return field.value !== null && field.value !== undefined ? Number(field.value) : null;
  }
  const n = Number(field);
  return Number.isFinite(n) ? n : null;
}

function safeNum(val, fallbackLabel = "Unavailable") {
  if (val === null || val === undefined || !Number.isFinite(val)) return fallbackLabel;
  return val.toFixed(1);
}

/**
 * Generate risk-appropriate recommendations based on validated conditions.
 */
function generateRecommendations({ riskClass, overallStatus, cwcStatus, basinName, exposedPopStr, language }) {
  const actions = {
    LOW: {
      en: [
        `Continue normal hydrological monitoring for ${basinName}.`,
        `No emergency resource deployment required at this time.`,
        `Review forecast updates every 12 hours for potential changes.`
      ],
      hi: [
        `${basinName} के लिए सामान्य जल-विज्ञान निगरानी जारी रखें।`,
        `इस समय किसी आपातकालीन संसाधन तैनाती की आवश्यकता नहीं है।`,
        `हर 12 घंटे में पूर्वानुमान अपडेट की समीक्षा करें।`
      ]
    },
    MODERATE: {
      en: [
        `Increase monitoring frequency for rainfall and river levels in ${basinName}.`,
        `Prepare local emergency resources for potential deployment.`,
        `Alert district-level disaster management authorities.`,
        `Ensure communication channels with at-risk communities are active.`
      ],
      hi: [
        `${basinName} में वर्षा और नदी जलस्तर की निगरानी बढ़ाएं।`,
        `स्थानीय आपातकालीन संसाधनों को तैनाती के लिए तैयार रखें।`,
        `जिला-स्तरीय आपदा प्रबंधन अधिकारियों को सतर्क करें।`
      ]
    },
    HIGH: {
      en: [
        `Pre-position State Disaster Response Force (SDRF) boats along low-lying embankments in ${basinName}.`,
        exposedPopStr !== "Unavailable"
          ? `Issue early SMS advisories to ${exposedPopStr} residents living within the active floodplain.`
          : `Prepare targeted public advisories for identified risk areas once exposure data is available.`,
        `Inspect structural integrity of river sluice gates, bridges, and culverts given precipitation surge.`,
        `Deploy emergency medical and drinking water relief kits to designated relief camps.`
      ],
      hi: [
        `${basinName} के निचले तटबंधों पर SDRF को तैनात करें।`,
        exposedPopStr !== "Unavailable"
          ? `बाढ़ क्षेत्र में रहने वाले ${exposedPopStr} नागरिकों को एसएमएस चेतावनी जारी करें।`
          : `जोखिम क्षेत्रों के लिए लक्षित सार्वजनिक सलाह तैयार करें।`,
        `पुलों, तटबंधों और जल निकासी द्वारों का निरीक्षण करें।`,
        `राहत शिविरों में पेयजल और प्राथमिक चिकित्सा किट सुरक्षित करें।`
      ]
    },
    SEVERE: {
      en: [
        `IMMEDIATE: Activate full emergency response coordination for ${basinName}.`,
        exposedPopStr !== "Unavailable"
          ? `Evacuate ${exposedPopStr} residents from active floodplain zones.`
          : `Begin evacuation of identified flood-risk areas immediately.`,
        `Deploy all available NDRF/SDRF resources to critical embankments.`,
        `Establish emergency communication links with all block-level officers.`,
        `Prepare helicopter/boat rescue for stranded populations.`
      ],
      hi: [
        `तत्काल: ${basinName} के लिए पूर्ण आपातकालीन प्रतिक्रिया सक्रिय करें।`,
        exposedPopStr !== "Unavailable"
          ? `बाढ़ क्षेत्र से ${exposedPopStr} नागरिकों को तुरंत स्थानांतरित करें।`
          : `पहचाने गए बाढ़ जोखिम क्षेत्रों से तुरंत निकासी शुरू करें।`,
        `सभी उपलब्ध NDRF/SDRF संसाधनों को तैनात करें।`,
        `हेलीकॉप्टर/नाव बचाव की तैयारी करें।`
      ]
    }
  };

  // Base actions on overall monitoring status if higher than risk class
  const effectiveLevel = (overallStatus === "CRITICAL" || overallStatus === "SEVERE") ? "SEVERE"
    : overallStatus === "HIGH" ? "HIGH"
    : overallStatus === "ELEVATED" ? "MODERATE"
    : (actions[riskClass] ? riskClass : "LOW");

  const level = actions[effectiveLevel] || actions.LOW;
  const langActions = level[language] || level.en;

  // If CWC gauge is above warning or danger but ML says LOW, add an explicit independence note
  if ((cwcStatus === "ABOVE_WARNING" || cwcStatus === "ABOVE_DANGER" || cwcStatus === "EXTREME") && riskClass === "LOW") {
    const caveat = language === "hi"
      ? `⚠️ आधिकारिक CWC अवलोकन: नदी जलस्तर चेतावनी/खतरे के स्तर से ऊपर है। यद्यपि AI मॉडल कम जलभराव का अनुमान लगाता है, जल-स्तर की स्थिति के कारण बढ़ी हुई निगरानी आवश्यक है।`
      : `⚠️ Official CWC Ground Truth: River stage is ${cwcStatus.replace("_", " ")}. Although the AI model currently estimates low inundation probability, observed river conditions dictate ${overallStatus} monitoring.`;
    return [caveat, ...langActions];
  }

  return langActions;
}

/**
 * Multilingual AI Briefings Generator
 */
export function generateDisasterBriefing({ telemetry, language = "en" }) {
  const basinName =
    telemetry?.location?.basin_name ||
    telemetry?.location?.district ||
    "Regional Basin";

  const probability = extractValue(telemetry?.prediction?.flood_probability_pct);
  const riskClass = telemetry?.prediction?.risk_class || "UNKNOWN";

  const rain72h = extractValue(telemetry?.current_weather?.rainfall_72h);
  const rain24h = extractValue(telemetry?.current_weather?.rainfall_24h);

  const observedHydro = telemetry?.cwc_ground_truth || telemetry?.observed_hydrology_status || {};
  const overall = telemetry?.overall_monitoring || {};
  const overallStatus = overall.status || (riskClass === "HIGH" || riskClass === "SEVERE" || riskClass === "VERY HIGH" ? "HIGH ALERT" : riskClass === "MODERATE" || riskClass === "MEDIUM" ? "WATCH" : "NORMAL");

  const riverStageVal = observedHydro.water_level_m ?? observedHydro.stageM ?? telemetry?.hydrology?.river_stage?.value ?? null;
  const cwcStatus = observedHydro.condition || observedHydro.status || "UNAVAILABLE";

  const exposedPopVal = extractValue(telemetry?.exposure?.population);
  const exposedPopStr = exposedPopVal !== null ? exposedPopVal.toLocaleString() : "Unavailable";

  const probStr = safeNum(probability, "Unavailable");
  const rain72hStr = safeNum(rain72h, "Unavailable");

  const recommendations = generateRecommendations({
    riskClass,
    overallStatus,
    cwcStatus,
    basinName,
    exposedPopStr,
    language
  });

  const riverStageDesc = (riverStageVal !== null && riverStageVal !== undefined && Number.isFinite(Number(riverStageVal)))
    ? `${Number(riverStageVal).toFixed(2)} m (${String(cwcStatus).replace("_", " ")})`
    : `Unavailable (${observedHydro.reason || observedHydro.failureReason || "Live CWC API unavailable"})`;

  const contentMap = {
    en: {
      headline: overall.message
        ? `${overallStatus} Monitoring: ${basinName}`
        : `${riskClass} Flood Risk Detected for ${basinName}`,
      summary: `AI Flood Risk: ${probStr}% (${riskClass}). Observed River Condition: ${riverStageDesc}. Overall Monitoring: ${overallStatus}. ${overall.message || ""}`,
      urgency: overallStatus === "CRITICAL"
        ? "CRITICAL FLOOD DEFENSE EMERGENCY"
        : overallStatus === "HIGH"
          ? "FLOOD ALERT / HIGH HAZARD"
          : overallStatus === "ELEVATED"
            ? "ELEVATED CATCHMENT SURVEILLANCE"
            : "NORMAL MONITORING STATUS"
    },
    hi: {
      headline: `${basinName}: ${overallStatus === "CRITICAL" ? "अत्यधिक आपातकालीन" : overallStatus === "HIGH" ? "उच्च सतर्कता" : overallStatus === "ELEVATED" ? "उन्नत" : "सामान्य"} निगरानी स्थिति`,
      summary: `AI जोखिम: ${probStr}% (${riskClass})। प्रेक्षित नदी जलस्तर: ${riverStageDesc}। समग्र निगरानी: ${overallStatus}। AI पूर्वानुमान और आधिकारिक CWC प्रेक्षण स्वतंत्र संकेत हैं।`,
      urgency: overallStatus === "CRITICAL" ? "अत्यधिक आपातकालीन चेतावनी" : overallStatus === "HIGH" ? "तत्काल राहत और निकासी सतर्कता" : overallStatus === "ELEVATED" ? "सक्रिय जलसंभर निगरानी" : "सामान्य निगरानी"
    }
  };

  const selected = contentMap[language] || contentMap.en;

  return {
    language,
    headline: selected.headline,
    summary: selected.summary,
    urgency: selected.urgency,
    actions: recommendations,
    ai_provenance: "AI prediction and observed river conditions are independent signals. Overall monitoring status calculated deterministically by ChetakAI decision engine.",
    generated_at: new Date().toISOString()
  };
}

/**
 * Interactive Copilot Chat responder
 */
export async function chatWithCopilot({ message, telemetry, language = "en", history = [] }) {
  const basinName = telemetry?.location?.basin_name || telemetry?.location?.district || "Target Basin";
  const probability = extractValue(telemetry?.prediction?.flood_probability_pct);
  const riskClass = telemetry?.prediction?.risk_class || "UNKNOWN";
  const overallStatus = telemetry?.overall_monitoring?.status || "NORMAL";
  const overallMessage = telemetry?.overall_monitoring?.message || "";
  const observedHydro = telemetry?.observed_hydrology_status || {};
  const riverStageVal = observedHydro.stageM;
  const cwcStatus = observedHydro.status || "UNAVAILABLE";

  const rain24h = extractValue(telemetry?.current_weather?.rainfall_24h);
  const rain72h = extractValue(telemetry?.current_weather?.rainfall_72h);
  const slope = extractValue(telemetry?.terrain?.mean_slope_deg);
  const soilRunoff = extractValue(telemetry?.soil?.soil_runoff_proxy);
  const exposedPop = extractValue(telemetry?.exposure?.population);
  const exposedPopStr = exposedPop !== null ? exposedPop.toLocaleString() : "Unavailable";

  const probStr = safeNum(probability, "Unavailable");
  const rain72hStr = safeNum(rain72h, "Unavailable");
  const rain24hStr = safeNum(rain24h, "Unavailable");
  const slopeStr = safeNum(slope, "Unavailable");
  const soilStr = soilRunoff !== null ? String(soilRunoff) : "Unavailable";

  const cwcDesc = riverStageVal !== null
    ? `${riverStageVal.toFixed(2)} m (${cwcStatus})`
    : `Unavailable (${observedHydro.failureReason || "Live API unavailable"})`;

  // Check if external GEMINI_API_KEY is configured
  const geminiKey = process.env.GEMINI_API_KEY;
  if (geminiKey) {
    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${geminiKey}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [
              {
                role: "user",
                parts: [
                  {
                    text: `You are ChetakAI Flood Intelligence Copilot, an expert hydrologist and disaster defense AI.
Ground truth telemetry and dual-signal monitoring for the user's active coordinate:
- Basin: ${basinName}
- AI ML Inundation Probability: ${probStr}% (${riskClass} Risk)
- Observed CWC River Stage: ${cwcDesc}
- Overall Monitoring Status: ${overallStatus} (Pre-calculated deterministically)
- Note: AI prediction and observed river conditions are independent signals.
- 24h Rainfall: ${rain24hStr} mm, 72h Cumulative: ${rain72hStr} mm
- Topographical Slope: ${slopeStr} degrees
- Soil Runoff Index: ${soilStr}
- Exposed Population: ${exposedPopStr}

User Question: "${message}"
Respond in language: ${language}.
Provide an authoritative, clear, actionable answer grounded in the above physical facts. Never fabricate numbers or override the pre-calculated overall monitoring status. If a value is "Unavailable", explain why.`
                  }
                ]
              }
            ]
          })
        }
      );

      if (response.ok) {
        const json = await response.json();
        const reply = json?.candidates?.[0]?.content?.parts?.[0]?.text;
        if (reply) {
          return {
            reply: reply.trim(),
            source: "Gemini 2.0 Realtime Physical Grounding",
            language
          };
        }
      }
    } catch (err) {
      console.warn("External Gemini API call skipped:", err.message);
    }
  }

  // Resilient Local Intelligence Engine
  const q = message.toLowerCase();
  let reply = "";
  const localized = {
    en: {
      cwc: `CWC river stage is ${cwcDesc}. Overall monitoring status is ${overallStatus}.`,
      risk: `${overallMessage} AI flood risk is ${probStr}%. Overall monitoring status is ${overallStatus}.`,
      evacuate: `Evacuation planning should target identified flood-risk zones. Current status: ${overallStatus}.`,
      rain: `Current rainfall is ${rain24hStr} mm in 24 hours and ${rain72hStr} mm over 72 hours.`,
      summary: `For ${basinName}, AI flood probability is ${probStr}% (${riskClass}) and overall monitoring status is ${overallStatus}.`
    },
    hi: {
      cwc: `CWC नदी जलस्तर ${cwcDesc} है। समग्र निगरानी स्थिति ${overallStatus} है।`,
      risk: `${overallMessage} एआई बाढ़ जोखिम ${probStr}% है। समग्र निगरानी स्थिति ${overallStatus} है।`,
      evacuate: `निकासी योजना में पहचाने गए बाढ़ जोखिम क्षेत्रों को प्राथमिकता दें। वर्तमान स्थिति: ${overallStatus}।`,
      rain: `पिछले 24 घंटों में वर्षा ${rain24hStr} मिमी और 72 घंटों में ${rain72hStr} मिमी है।`,
      summary: `${basinName} के लिए एआई बाढ़ संभावना ${probStr}% (${riskClass}) है और समग्र निगरानी स्थिति ${overallStatus} है।`
    },
    bn: {
      cwc: `CWC নদীর জলস্তর ${cwcDesc}। সামগ্রিক পর্যবেক্ষণ অবস্থা ${overallStatus}।`,
      risk: `${overallMessage} এআই বন্যার ঝুঁকি ${probStr}%। সামগ্রিক পর্যবেক্ষণ অবস্থা ${overallStatus}।`,
      evacuate: `চিহ্নিত বন্যা ঝুঁকিপূর্ণ এলাকায় উচ্ছেদ পরিকল্পনা অগ্রাধিকার দিন। বর্তমান অবস্থা: ${overallStatus}।`,
      rain: `গত ২৪ ঘণ্টায় বৃষ্টিপাত ${rain24hStr} মিমি এবং ৭২ ঘণ্টায় ${rain72hStr} মিমি।`,
      summary: `${basinName}-এর এআই বন্যার সম্ভাবনা ${probStr}% (${riskClass}) এবং সামগ্রিক পর্যবেক্ষণ অবস্থা ${overallStatus}।`
    },
    mr: {
      cwc: `CWC नदीची पातळी ${cwcDesc} आहे. एकूण निरीक्षण स्थिती ${overallStatus} आहे.`,
      risk: `${overallMessage} एआय पूर जोखीम ${probStr}% आहे. एकूण निरीक्षण स्थिती ${overallStatus} आहे.`,
      evacuate: `ओळखलेल्या पूर जोखीम क्षेत्रांना स्थलांतर नियोजनात प्राधान्य द्या. सध्याची स्थिती: ${overallStatus}.`,
      rain: `मागील 24 तासांत पाऊस ${rain24hStr} मिमी आणि 72 तासांत ${rain72hStr} मिमी आहे.`,
      summary: `${basinName} साठी एआय पूर संभाव्यता ${probStr}% (${riskClass}) आणि एकूण निरीक्षण स्थिती ${overallStatus} आहे.`
    },
    te: {
      cwc: `CWC నది నీటి మట్టం ${cwcDesc}. మొత్తం పర్యవేక్షణ స్థితి ${overallStatus}.`,
      risk: `${overallMessage} AI వరద ప్రమాదం ${probStr}%. మొత్తం పర్యవేక్షణ స్థితి ${overallStatus}.`,
      evacuate: `గుర్తించిన వరద ప్రమాద ప్రాంతాలకు తరలింపు ప్రణాళికలో ప్రాధాన్యత ఇవ్వండి. ప్రస్తుత స్థితి: ${overallStatus}.`,
      rain: `గత 24 గంటల్లో వర్షపాతం ${rain24hStr} మిమీ, 72 గంటల్లో ${rain72hStr} మిమీ.`,
      summary: `${basinName} కోసం AI వరద సంభావ్యత ${probStr}% (${riskClass}), మొత్తం పర్యవేక్షణ స్థితి ${overallStatus}.`
    },
    ta: {
      cwc: `CWC ஆற்றின் நீர்மட்டம் ${cwcDesc}. ஒட்டுமொத்த கண்காணிப்பு நிலை ${overallStatus}.`,
      risk: `${overallMessage} AI வெள்ள அபாயம் ${probStr}%. ஒட்டுமொத்த கண்காணிப்பு நிலை ${overallStatus}.`,
      evacuate: `அடையாளம் காணப்பட்ட வெள்ள அபாயப் பகுதிகளுக்கு வெளியேற்றத் திட்டத்தில் முன்னுரிமை அளிக்கவும். தற்போதைய நிலை: ${overallStatus}.`,
      rain: `கடந்த 24 மணி நேர மழை ${rain24hStr} மிமீ, 72 மணி நேர மழை ${rain72hStr} மிமீ.`,
      summary: `${basinName}க்கான AI வெள்ள நிகழ்தகவு ${probStr}% (${riskClass}), ஒட்டுமொத்த கண்காணிப்பு நிலை ${overallStatus}.`
    }
  }[language] || null;

  if (q.includes("cwc") || q.includes("stage") || q.includes("river") || q.includes("level")) {
    reply = localized?.cwc || `CWC River Stage telemetry: ${cwcDesc}. Overall monitoring status is ${overallStatus}.`;
  } else if (q.includes("why") && (q.includes("risk") || q.includes("status") || q.includes("monitoring") || q.includes("elevated"))) {
    reply = localized?.risk || `${overallMessage} AI Flood Risk: ${probStr}%. Overall monitoring status is ${overallStatus}.`;
  } else if (q.includes("evacuat") || q.includes("safe") || q.includes("shelter")) {
    reply = localized?.evacuate || `Evacuation planning should target identified flood-risk zones. Current status: ${overallStatus}.`;
  } else if (q.includes("rain") || q.includes("weather")) {
    reply = localized?.rain || `Current rainfall is ${rain24hStr} mm in 24 hours and ${rain72hStr} mm over 72 hours.`;
  } else {
    reply = localized?.summary || `Based on current telemetry for ${basinName}, AI flood probability is ${probStr}% (${riskClass}) and overall monitoring status is ${overallStatus}.`;
  }

  return {
    reply,
    source: "ChetakAI Grounded Physics Engine",
    language
  };
}
