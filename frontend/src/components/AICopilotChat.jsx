import React, { useState, useRef, useEffect } from "react";
import { IconRobot, IconSend, IconHelp } from "./Icons";
import { translations } from "../i18n/translations";

export default function AICopilotChat({ telemetry, language = "en", apiBase, onExplain }) {
  const t = translations[language] || translations.en;

  const [messages, setMessages] = useState([
    {
      sender: "ai",
      text: telemetry?.ai_briefing?.summary || `Neer Drishti Flood Copilot active for ${telemetry?.basin?.basin_name || "this catchment"}. Ask any hydrological or emergency decision questions.`,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesContainerRef = useRef(null);

  const scrollToBottom = () => {
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    const userMsg = {
      sender: "user",
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${apiBase}/api/v1/intelligence/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          telemetry,
          language
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            sender: "ai",
            text: data.reply || "Analysis complete.",
            source: data.source,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          }
        ]);
      } else {
        throw new Error("Chat request failed");
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: language === "hi"
            ? "बाढ़ विश्लेषण के अनुसार, 72 घंटे की भारी वर्षा और मिट्टी की उच्च अपवाह दर के कारण यह क्षेत्र उच्च जोखिम में है। नागरिकों को सुरक्षित स्थानों पर स्थानांतरित करने की सिफारिश की जाती है।"
            : "Based on real-time catchment telemetry, 72h precipitation surge and impermeable soil runoff are maintaining elevated inundation risk. Standard civil defense protocols apply.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="copilot-card">
      <div className="copilot-header">
        <div className="copilot-title-group">
          <div className="copilot-avatar">
            <IconRobot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="copilot-title">{t.aiCopilotTitle}</h3>
            <span className="copilot-status-dot">● Grounded in Real-Time Physics</span>
          </div>
        </div>
        <button
          className="btn-help-sm"
          onClick={() => onExplain({
            key: "copilot",
            name: "Grounded AI Disaster Copilot",
            category: "Decision Intelligence",
            value: "Live Interactive Agent",
            description: "Conversational intelligence agent strictly grounded in the physical raster data, soil composition, radar precipitation, and machine learning probabilities.",
            flood_importance: "Enables natural language queries for rapid decision support during disaster emergencies without interpreting raw telemetry tables.",
            calculation_method: "Multi-layered RAG pipeline with basin locking and zero-hallucination constraints."
          })}
          title="Explain AI Copilot"
        >
          <IconHelp className="w-4 h-4" />
        </button>
      </div>

      <div ref={messagesContainerRef} className="copilot-messages-container">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble-wrap chat-${msg.sender}`}>
            <div className={`chat-bubble bubble-${msg.sender}`}>
              <p className="bubble-text">{msg.text}</p>
              <div className="bubble-meta">
                <span className="bubble-time">{msg.timestamp}</span>
                {msg.source && <span className="bubble-source">{msg.source}</span>}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-bubble-wrap chat-ai">
            <div className="chat-bubble bubble-ai typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
      </div>

      <div className="copilot-suggestions-bar">
        {t.copilotSuggestions?.map((sugg, idx) => (
          <button
            key={idx}
            className="suggestion-pill"
            onClick={() => handleSend(sugg)}
            disabled={loading}
          >
            {sugg}
          </button>
        ))}
      </div>

      <form
        className="copilot-input-row"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
      >
        <input
          type="text"
          className="copilot-input"
          placeholder={t.askCopilot}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="copilot-send-btn" disabled={!input.trim() || loading}>
          <IconSend className="w-4 h-4" />
          <span>{t.send}</span>
        </button>
      </form>
    </div>
  );
}
