import React, { useState, useRef, useCallback } from "react";
import { IconMic, IconMicOff, IconSend } from "./Icons";
import { translations } from "../i18n/translations";

const SpeechRecognition = typeof window !== "undefined"
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null;

const speechLocale = (language) => ({
  en: "en-US", hi: "hi-IN", bn: "bn-IN", mr: "mr-IN", te: "te-IN", ta: "ta-IN"
}[language] || "en-US");

const recognitionLocale = (language) => ({
  en: "en-US", hi: "hi-IN", bn: "bn-IN", mr: "mr-IN", te: "te-IN", ta: "ta-IN"
}[language] || "en-US");

export default function VoiceAgent({ apiBase, telemetry, language = "en" }) {
  const [state, setState] = useState("idle"); // idle | listening | processing | speaking
  const [lastText, setLastText] = useState("");
  const [textInput, setTextInput] = useState("");
  const [minimized, setMinimized] = useState(false);
  const recognitionRef = useRef(null);
  const recognitionTimerRef = useRef(null);
  const synthRef = useRef(typeof window !== "undefined" ? window.speechSynthesis : null);
  const speechRetryRef = useRef(0);

  const supported = !!SpeechRecognition && !!synthRef.current;

  const stopListening = useCallback(() => {
    if (recognitionTimerRef.current) {
      window.clearTimeout(recognitionTimerRef.current);
      recognitionTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
      recognitionRef.current = null;
    }
  }, []);

  const speak = useCallback((text) => {
    const synth = synthRef.current;
    if (!synth || !text) return;
    const locale = speechLocale(language);
    synth.cancel();
    synth.resume();
    const utter = new SpeechSynthesisUtterance(String(text));
    utter.lang = locale;
    utter.rate = 0.95;
    const voices = synth.getVoices();
    const voice = voices.find((item) => item.lang?.toLowerCase() === locale.toLowerCase())
      || voices.find((item) => item.lang?.toLowerCase().startsWith(language.toLowerCase()));
    if (voice) utter.voice = voice;
    utter.onend = () => {
      speechRetryRef.current = 0;
      setState("idle");
    };
    utter.onerror = (event) => {
      if (speechRetryRef.current === 0 && event.error !== "canceled" && event.error !== "interrupted") {
        speechRetryRef.current = 1;
        window.setTimeout(() => speak(text), 250);
        return;
      }
      speechRetryRef.current = 0;
      setState("idle");
    };
    setState("speaking");
    synth.speak(utter);
  }, [language]);

  const sendToChat = useCallback(async (message) => {
    setState("processing");
    setLastText(message);
    try {
      const res = await fetch(`${apiBase}/api/v1/intelligence/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, telemetry, language })
      });
      if (res.ok) {
        const data = await res.json();
        const reply = data.reply || "Analysis complete.";
        speak(reply);
      } else {
        speak("Sorry, I could not process your request.");
      }
    } catch {
      speak("Network error. Please try again.");
    }
  }, [apiBase, telemetry, language, speak]);

  const startListening = useCallback(() => {
    if (!SpeechRecognition) {
      return;
    }
    stopListening();

    const recognition = new SpeechRecognition();
    recognition.lang = recognitionLocale(language);
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = true;

    recognition.onresult = (event) => {
      const text = Array.from(event.results)
        .slice(event.resultIndex)
        .filter((result) => result.isFinal)
        .map((result) => result[0].transcript)
        .join(" ")
        .trim();
      if (!text) return;
      stopListening();
      sendToChat(text);
    };

    recognition.onerror = (event) => {
      stopListening();
      if (event.error !== "aborted") {
        speak("I could not hear you. Please check your microphone and try again.");
      } else {
        setState("idle");
      }
    };

    recognition.onend = () => {
      if (recognitionRef.current === recognition) {
        recognitionRef.current = null;
        if (recognitionTimerRef.current) {
          window.clearTimeout(recognitionTimerRef.current);
          recognitionTimerRef.current = null;
        }
        setState((currentState) => currentState === "listening" ? "idle" : currentState);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setState("listening");
      recognitionTimerRef.current = window.setTimeout(() => {
        if (recognitionRef.current !== recognition) return;
        stopListening();
        speak("I did not hear a question. Please try speaking again.");
      }, 10000);
    } catch {}
  }, [language, stopListening, sendToChat, speak]);

  const handleClick = () => {
    if (state === "listening") {
      stopListening();
      setState("idle");
    } else if (state === "speaking") {
      speechRetryRef.current = 0;
      synthRef.current?.cancel();
      synthRef.current?.resume();
      setState("idle");
    } else if (state === "idle") {
      startListening();
    }
  };

  const handleTextSubmit = (event) => {
    event.preventDefault();
    const message = textInput.trim();
    if (!message || state === "processing") return;
    stopListening();
    setTextInput("");
    sendToChat(message);
  };

  if (minimized) {
    return (
      <div className="voice-agent-fab minimized" onClick={() => setMinimized(false)}>
        <button className="voice-agent-btn-mini" title="Open Voice Agent">
          <IconMic className="w-4 h-4" />
        </button>
      </div>
    );
  }

  const ui = { ...(translations.en.ui || {}), ...((translations[language] || {}).ui || {}) };
  const stateLabels = {
    idle: ui.voiceAgent || "Voice Agent",
    listening: language === "hi" ? "सुन रहा है..." : language === "bn" ? "শুনছে..." : language === "mr" ? "ऐकत आहे..." : language === "te" ? "వింటోంది..." : language === "ta" ? "கேட்கிறது..." : "Listening...",
    processing: language === "hi" ? "सोच रहा है..." : language === "bn" ? "ভাবছে..." : language === "mr" ? "विचार करत आहे..." : language === "te" ? "ఆలోచిస్తోంది..." : language === "ta" ? "சிந்திக்கிறது..." : "Thinking...",
    speaking: language === "hi" ? "बोल रहा है..." : language === "bn" ? "বলছে..." : language === "mr" ? "बोलत आहे..." : language === "te" ? "మాట్లాడుతోంది..." : language === "ta" ? "பேசுகிறது..." : "Speaking..."
  };

  return (
    <div className="voice-agent-fab">
      {state === "listening" && <div className="voice-agent-pulse"></div>}
      <form className="voice-agent-input" onSubmit={handleTextSubmit}>
        <input
          value={textInput}
          onChange={(event) => setTextInput(event.target.value)}
          placeholder="Type a question"
          aria-label="Type a question for the Voice Agent"
          disabled={state === "processing"}
        />
        <button type="submit" aria-label="Send question" title="Send question" disabled={!textInput.trim() || state === "processing"}>
          <IconSend className="w-4 h-4" />
        </button>
      </form>
      <button
        className={`voice-agent-btn ${state}`}
        onClick={handleClick}
        disabled={state === "processing"}
        title={supported ? stateLabels[state] : "Voice not supported in this browser"}
      >
        {state === "processing" ? (
          <span className="mini-spinner white"></span>
        ) : state === "listening" ? (
          <IconMicOff className="w-5 h-5" />
        ) : (
          <IconMic className="w-5 h-5" />
        )}
      </button>
      <span className="voice-agent-label">{stateLabels[state]}</span>
      <button className="voice-agent-close" onClick={() => setMinimized(true)} title="Minimize">×</button>
    </div>
  );
}
