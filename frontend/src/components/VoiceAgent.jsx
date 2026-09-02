import React, { useState, useRef, useCallback } from "react";
import { IconMic, IconMicOff } from "./Icons";

const SpeechRecognition = typeof window !== "undefined"
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null;

export default function VoiceAgent({ apiBase, telemetry, language = "en" }) {
  const [state, setState] = useState("idle"); // idle | listening | processing | speaking
  const [lastText, setLastText] = useState("");
  const [minimized, setMinimized] = useState(false);
  const recognitionRef = useRef(null);
  const synthRef = useRef(typeof window !== "undefined" ? window.speechSynthesis : null);

  const supported = !!SpeechRecognition && !!synthRef.current;

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
      recognitionRef.current = null;
    }
  }, []);

  const speak = useCallback((text) => {
    if (!synthRef.current) return;
    synthRef.current.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = language === "hi" ? "hi-IN" : language === "bn" ? "bn-IN" : language === "ta" ? "ta-IN" : language === "te" ? "te-IN" : language === "mr" ? "mr-IN" : "en-IN";
    utter.rate = 0.95;
    utter.onend = () => setState("idle");
    utter.onerror = () => setState("idle");
    setState("speaking");
    synthRef.current.speak(utter);
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
    if (!SpeechRecognition) return;
    stopListening();

    const recognition = new SpeechRecognition();
    recognition.lang = language === "hi" ? "hi-IN" : language === "bn" ? "bn-IN" : language === "ta" ? "ta-IN" : language === "te" ? "te-IN" : language === "mr" ? "mr-IN" : "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      sendToChat(text);
    };

    recognition.onerror = () => {
      setState("idle");
    };

    recognition.onend = () => {
      if (state === "listening") setState("idle");
    };

    recognitionRef.current = recognition;
    recognition.start();
    setState("listening");
  }, [language, stopListening, sendToChat, state]);

  const handleClick = () => {
    if (state === "listening") {
      stopListening();
      setState("idle");
    } else if (state === "speaking") {
      synthRef.current?.cancel();
      setState("idle");
    } else if (state === "idle") {
      startListening();
    }
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

  const stateLabels = {
    idle: "Voice Agent",
    listening: "Listening...",
    processing: "Thinking...",
    speaking: "Speaking..."
  };

  return (
    <div className="voice-agent-fab">
      {state === "listening" && <div className="voice-agent-pulse"></div>}
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
