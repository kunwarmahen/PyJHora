import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  MessageCircle,
  Send,
  Bot,
  User,
  Sparkles,
  ArrowLeft,
  Star,
  Calendar,
  Clock,
  MapPin,
  Info,
  X,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import "../styles/Dashboard.css";
import "../styles/Chat.css";

export const AskAstrologerPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [chartData, setChartData] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [llmProvider, setLlmProvider] = useState("qwen");
  const [showInfoModal, setShowInfoModal] = useState(false);

  const llmProviders = [
    {
      value: "qwen",
      label: "Qwen 2.5 (Local)",
      description: "Free, private, runs locally",
      icon: "🤖",
    },
    {
      value: "gemini",
      label: "Google Gemini",
      description: "Powered by Google AI",
      icon: "✨",
    },
    {
      value: "chatgpt",
      label: "ChatGPT",
      description: "OpenAI GPT-4",
      icon: "🧠",
    },
  ];

  const exampleQuestions = [
    "What are my strengths and weaknesses based on my chart?",
    "When is a good time for marriage?",
    "Which career path suits me best?",
    "What remedies can help with current challenges?",
    "How will the next 6 months be for me?",
    "What does my moon sign reveal about my personality?",
  ];

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate('/profile-selection');
      return;
    }

    // Auto-calculate chart on mount
    calculateChart();
  }, [selectedProfile, navigate]);

  const calculateChart = async () => {
    if (!selectedProfile) return;

    setLoading(true);
    setError("");

    try {
      const birthDetails = {
        name: selectedProfile.birth_details.name,
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
        latitude: parseFloat(selectedProfile.birth_details.latitude),
        longitude: parseFloat(selectedProfile.birth_details.longitude),
        timezone: parseFloat(selectedProfile.birth_details.timezone),
      };

      // Fetch both chart data and dasha data
      const [chartResponse, dashaResponse] = await Promise.all([
        astrologyService.calculateBirthChart(birthDetails),
        astrologyService.getDhasa(birthDetails, "vimsottari")
      ]);

      // Combine chart data with dasha data
      setChartData({
        ...chartResponse.data,
        dashas: dashaResponse.data
      });
      setMessages([
        {
          type: "system",
          content: `Chart ready for ${selectedProfile.birth_details.name || selectedProfile.profile_name}. Ask me anything about this birth chart!`,
        },
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to calculate chart");
    } finally {
      setLoading(false);
    }
  };

  const handleAskQuestion = async (question) => {
    if (!question.trim() || !selectedProfile) return;

    const userMessage = {
      type: "user",
      content: question,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setCurrentQuestion("");
    setLoading(true);
    setError("");

    try {
      const birthDetails = {
        name: selectedProfile.birth_details.name,
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
        latitude: parseFloat(selectedProfile.birth_details.latitude),
        longitude: parseFloat(selectedProfile.birth_details.longitude),
        timezone: parseFloat(selectedProfile.birth_details.timezone),
      };

      const response = await astrologyService.askQuestion(
        birthDetails,
        question,
        llmProvider
      );

      const aiMessage = {
        type: "ai",
        content: response.data.answer,
        provider: llmProvider,
        timestamp: new Date().toLocaleTimeString(),
        chartSummary: response.data.chart_summary,
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to get answer");
      const errorMessage = {
        type: "error",
        content: err.response?.data?.detail || "Failed to get answer from AI",
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleExampleClick = (question) => {
    handleAskQuestion(question);
  };

  const getChartDataForLLM = () => {
    if (!chartData) return "No chart data available";

    const moonData = chartData.d1_chart?.Moon || {};
    const sunData = chartData.d1_chart?.Sun || {};

    return {
      birth_details: {
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
      },
      lagna: chartData.lagna,
      moon_sign: {
        sign_name: moonData.sign_name || "Unknown",
        rasi: moonData.rasi || 0,
        nakshatra: moonData.nakshatra || "Unknown",
        nakshatra_pada: moonData.nakshatra_pada || 0,
      },
      sun_sign: {
        sign_name: sunData.sign_name || "Unknown",
        rasi: sunData.rasi || 0,
        nakshatra: sunData.nakshatra || "Unknown",
        nakshatra_pada: sunData.nakshatra_pada || 0,
      },
      planetary_positions: chartData.d1_chart || {},
      current_dasha: chartData.dashas?.current_dasha || {},
      next_dasha: chartData.dashas?.next_dasha || {},
      current_bhukthi: chartData.dashas?.current_bhukthi || {},
      dasha_sequence: chartData.dashas?.dasha_sequence || []
    };
  };

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="dashboard-container mandala-bg">
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <button onClick={() => navigate('/dashboard')} style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            color: 'var(--saffron)',
            padding: 'var(--space-sm) var(--space-md)',
            borderRadius: 'var(--radius-md)',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 153, 51, 0.1)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'none'}>
            <ArrowLeft size={20} />
            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Back</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginLeft: 'var(--space-lg)' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, var(--terracotta) 0%, var(--vermillion) 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white'
            }}>
              <MessageCircle size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Ask AI Astrologer</h1>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Get personalized insights from AI
              </p>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="dashboard-content">
        {/* Profile Banner */}
        <div className="profile-banner fade-in">
          <div className="profile-banner-left">
            <div className="profile-avatar-large">
              <User size={32} />
            </div>
            <div className="profile-info">
              <h2>{selectedProfile.profile_name}</h2>
              <div className="profile-meta">
                <span>{selectedProfile.birth_details.name || 'Anonymous'}</span>
                <span className="separator">•</span>
                <span>{selectedProfile.birth_details.dob.split('T')[0]}</span>
                <span className="separator">•</span>
                <span>{selectedProfile.birth_details.place}</span>
              </div>
            </div>
          </div>
          <button onClick={() => navigate('/profile-selection')} className="change-profile-btn">
            <Star size={16} />
            <span>Change Chart</span>
          </button>
        </div>

        {/* Display Birth Chart */}
        {chartData && (
          <div style={{ opacity: 0, animation: 'fadeIn 0.6s ease-out 0.2s forwards' }}>
            <NorthIndianChart chartData={chartData} />
          </div>
        )}

        {/* AI Model Selector and Examples */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 'var(--space-lg)',
          marginBottom: 'var(--space-xl)',
          opacity: 0,
          animation: 'fadeIn 0.6s ease-out 0.4s forwards'
        }}>
          {/* LLM Selector Card */}
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-xl)',
            boxShadow: 'var(--shadow-lg)',
            borderTop: '4px solid var(--saffron)'
          }}>
            <h3 style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              marginBottom: 'var(--space-lg)',
              color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem',
              fontWeight: 700
            }}>
              <Bot size={20} style={{ color: 'var(--saffron)' }} />
              AI Model
              <button
                onClick={() => setShowInfoModal(true)}
                style={{
                  marginLeft: 'auto',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--saffron)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-xs)',
                  padding: 'var(--space-xs)',
                  borderRadius: 'var(--radius-sm)',
                  transition: 'all 0.3s ease'
                }}
                onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 153, 51, 0.1)'}
                onMouseOut={(e) => e.currentTarget.style.background = 'none'}
                title="View chart data sent to AI"
              >
                <Info size={18} />
                <span style={{ fontSize: '0.75rem', fontWeight: 500 }}>Info</span>
              </button>
            </h3>
            <div className="llm-options">
              {llmProviders.map((provider) => (
                <label
                  key={provider.value}
                  className={`llm-option ${
                    llmProvider === provider.value ? "active" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="llm"
                    value={provider.value}
                    checked={llmProvider === provider.value}
                    onChange={(e) => setLlmProvider(e.target.value)}
                  />
                  <div className="llm-option-content">
                    <div className="llm-icon">{provider.icon}</div>
                    <div>
                      <div className="llm-name">{provider.label}</div>
                      <div className="llm-desc">{provider.description}</div>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Examples Card */}
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-xl)',
            boxShadow: 'var(--shadow-lg)',
            borderTop: '4px solid var(--saffron)'
          }}>
            <h3 style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              marginBottom: 'var(--space-lg)',
              color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem',
              fontWeight: 700
            }}>
              <MessageCircle size={20} style={{ color: 'var(--saffron)' }} />
              Example Questions
            </h3>
            {exampleQuestions.map((q, index) => (
              <button
                key={index}
                className="example-question"
                onClick={() => handleExampleClick(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <div style={{
          background: 'white',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg)',
          borderTop: '4px solid var(--saffron)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '500px',
          maxHeight: '700px',
          opacity: 0,
          animation: 'fadeIn 0.6s ease-out 0.6s forwards'
        }}>
          <div className="messages-container" style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--space-xl)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-lg)',
            background: 'var(--sacred-white)'
          }}>
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.type}`}>
                {message.type === "user" && (
                  <div className="message-header">
                    <User size={18} />
                    <span>You</span>
                    <span className="timestamp">{message.timestamp}</span>
                  </div>
                )}
                {message.type === "ai" && (
                  <div className="message-header">
                    <Bot size={18} />
                    <span>
                      AI Astrologer ({message.provider?.toUpperCase()})
                    </span>
                    <span className="timestamp">{message.timestamp}</span>
                  </div>
                )}
                {message.type === "system" && (
                  <div className="message-header">
                    <Sparkles size={18} />
                    <span>System</span>
                  </div>
                )}
                <div className="message-content">
                  {message.type === "ai" ? (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  ) : (
                    message.content
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="message ai">
                <div className="message-header">
                  <Bot size={18} />
                  <span>AI Astrologer</span>
                </div>
                <div className="message-content loading">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  Analyzing your chart...
                </div>
              </div>
            )}
          </div>

          <div className="chat-input-container" style={{
            display: 'flex',
            gap: 'var(--space-sm)',
            padding: 'var(--space-lg)',
            borderTop: '2px solid var(--sandalwood)',
            background: 'white'
          }}>
            <input
              type="text"
              className="chat-input"
              placeholder="Ask a question about your birth chart..."
              value={currentQuestion}
              onChange={(e) => setCurrentQuestion(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !loading) {
                  handleAskQuestion(currentQuestion);
                }
              }}
              disabled={loading}
            />
            <button
              className="btn-send"
              onClick={() => handleAskQuestion(currentQuestion)}
              disabled={loading || !currentQuestion.trim()}
            >
              <Send size={20} />
            </button>
          </div>
        </div>

        {/* Info Modal */}
        {showInfoModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--space-lg)',
            animation: 'fadeIn 0.3s ease-out'
          }}
          onClick={() => setShowInfoModal(false)}>
            <div style={{
              background: 'white',
              borderRadius: 'var(--radius-xl)',
              maxWidth: '800px',
              width: '100%',
              maxHeight: '80vh',
              overflow: 'auto',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
              animation: 'slideIn 0.3s ease-out'
            }}
            onClick={(e) => e.stopPropagation()}>
              {/* Modal Header */}
              <div style={{
                padding: 'var(--space-xl)',
                borderBottom: '2px solid var(--sandalwood)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                position: 'sticky',
                top: 0,
                background: 'white',
                zIndex: 1
              }}>
                <h3 style={{
                  margin: 0,
                  fontSize: '1.5rem',
                  color: 'var(--cosmic-indigo)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)'
                }}>
                  <Info size={24} style={{ color: 'var(--saffron)' }} />
                  Chart Data Sent to AI
                </h3>
                <button
                  onClick={() => setShowInfoModal(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text-secondary)',
                    padding: 'var(--space-sm)',
                    borderRadius: 'var(--radius-md)',
                    transition: 'all 0.3s ease'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = 'var(--sandalwood)';
                    e.currentTarget.style.color = 'var(--vermillion)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = 'none';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                  }}
                >
                  <X size={24} />
                </button>
              </div>

              {/* Modal Content */}
              <div style={{
                padding: 'var(--space-xl)',
                fontSize: '0.875rem',
                lineHeight: '1.6'
              }}>
                <div style={{
                  background: 'linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.1) 100%)',
                  padding: 'var(--space-lg)',
                  borderRadius: 'var(--radius-lg)',
                  marginBottom: 'var(--space-lg)',
                  border: '1px solid var(--saffron)'
                }}>
                  <p style={{ margin: 0, color: 'var(--cosmic-indigo)', fontWeight: 500 }}>
                    This is the chart information that is being sent to the AI model to provide personalized astrological insights:
                  </p>
                </div>

                <pre style={{
                  background: 'var(--sacred-white)',
                  padding: 'var(--space-lg)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--sandalwood)',
                  overflow: 'auto',
                  fontFamily: 'monospace',
                  fontSize: '0.8125rem',
                  lineHeight: '1.8',
                  color: 'var(--cosmic-indigo)'
                }}>
{JSON.stringify(getChartDataForLLM(), null, 2)}
                </pre>

                <div style={{
                  marginTop: 'var(--space-lg)',
                  padding: 'var(--space-md)',
                  background: 'rgba(52, 73, 94, 0.05)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--cosmic-indigo)',
                  fontSize: '0.8125rem'
                }}>
                  <p style={{ margin: '0 0 var(--space-sm) 0', color: 'var(--cosmic-indigo)', fontWeight: 600 }}>
                    📝 Note:
                  </p>
                  <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                    The AI model receives this structured data along with your question to provide accurate and personalized astrological guidance based on your birth chart. This includes your Lagna (Ascendant), planetary positions, nakshatras, and other relevant astrological details.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
