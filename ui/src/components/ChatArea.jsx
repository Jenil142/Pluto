import { useState, useRef, useEffect } from 'react';
import { ThinkingOrb } from 'thinking-orbs';
import ReactMarkdown from 'react-markdown';

const STARTER_PROMPTS = [
  'Check system status',
  'Explain Pluto perception-action pipeline',
  'Design an autonomous warehouse navigation node',
];

function getStatusLabel(state) {
  switch (state) {
    case 'listening':
      return 'Listening...';
    case 'connecting':
      return 'Connecting...';
    case 'searching':
      return 'Searching...';
    case 'solving':
      return 'Reasoning...';
    case 'working':
      return 'Executing...';
    case 'shaping':
      return 'Attention';
    case 'breathing':
    default:
      return 'Pluto Ready';
  }
}

export default function ChatArea({
  activeSession,
  onSendMessage,
  isProcessing,
  orbState,
  onInputFocus,
  onInputBlur,
  onToggleSidebar,
}) {
  const [inputText, setInputText] = useState('');
  const [pendingCommand, setPendingCommand] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    let interval;
    if (isProcessing) {
      interval = setInterval(async () => {
        try {
          const res = await fetch('/api/pending_confirmation');
          const data = await res.json();
          if (data.pending && data.command) {
            setPendingCommand(data.command);
          } else {
            setPendingCommand(null);
          }
        } catch (err) {
          // ignore network errors during polling
        }
      }, 1000);
    } else {
      setPendingCommand(null);
    }
    return () => clearInterval(interval);
  }, [isProcessing]);

  const handleConfirmCommand = async (allow) => {
    try {
      await fetch('/api/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allow }),
      });
      setPendingCommand(null);
    } catch (err) {
      console.error('Confirmation error', err);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (pendingCommand && e.key === 'Enter') {
        e.preventDefault();
        handleConfirmCommand(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [pendingCommand]);

  const messages = activeSession?.messages;
  const messageList = messages || [];
  const isEmpty = messageList.length === 0 && !isProcessing;

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  // Adjust textarea height dynamically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [inputText]);

  // Restore focus to input whenever processing completes or active session changes
  useEffect(() => {
    if (!isProcessing && textareaRef.current) {
      const timer = setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isProcessing, activeSession?.id]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed || isProcessing) return;

    onSendMessage(trimmed);
    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChipClick = (promptText) => {
    if (isProcessing) return;
    onSendMessage(promptText);
  };

  return (
    <main className="chat-area flex flex-col h-full">
      {/* Persistent Chat Header */}
      <header className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button 
            onClick={onToggleSidebar}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--pluto-text-secondary)' }}
            title="Toggle Sidebar"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <h1 className="chat-header-title">
            {activeSession?.title || 'New Chat'}
          </h1>
        </div>

        {/* ThinkingOrb Status Indicator Pill */}
        <div className="orb-status-pill" title={`Pluto State: ${orbState}`}>
          <img src="/pluto-icon.png" width="20" height="20" alt="Pluto" style={{ objectFit: 'contain' }} />
          <span>{getStatusLabel(orbState)}</span>
        </div>
      </header>

      {/* Message Stream */}
      <div className="messages-container">
        {isEmpty ? (
          <div className="empty-state-container animate-message">
            <div className="empty-state-orb-wrap">
              <img src="/pluto-icon.png" width="80" height="80" alt="Pluto Logo" style={{ objectFit: 'contain' }} />
            </div>
            <h2 className="empty-state-title">What should Pluto build today?</h2>
          </div>
        ) : (
          <div className="messages-inner-wrapper">
            {messageList.map((msg) => {
              if (msg.role === 'user') {
                return (
                  <div key={msg.id} className="user-message-bubble animate-message">
                    {msg.content}
                  </div>
                );
              }

              return (
                <div
                  key={msg.id}
                  className={`assistant-message-card animate-message ${msg.status === 'error' ? 'error-card' : ''}`}
                >
                  <div className="assistant-card-header">
                    <div className="assistant-avatar-orb">
                      <img src="/pluto-icon.png" width="20" height="20" alt="Pluto" style={{ objectFit: 'contain' }} />
                    </div>
                    <span className="assistant-name">Pluto</span>
                    {msg.timestamp && (
                      <span className="assistant-timestamp">{msg.timestamp}</span>
                    )}
                  </div>
                  <div className="assistant-card-body">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                </div>
              );
            })}

            {/* In-flight Processing Indicator */}
            {isProcessing && (
              <div className="thinking-indicator-card animate-message">
                <img src="/pluto-icon.png" width="20" height="20" alt="Pluto" style={{ objectFit: 'contain' }} />
                <span>Pluto is processing query...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Pinned Bottom Input Bar */}
      <footer className="input-bar-container">
        <div className="input-bar-wrapper">
          {pendingCommand && (
            <div className="confirmation-modal-overlay">
              <div className="confirmation-modal">
                <h3>Pluto requests permission</h3>
                <p>Pluto wants to execute the following terminal command:</p>
                <pre className="command-preview">{pendingCommand}</pre>
                <div className="confirmation-modal-actions">
                  <button type="button" className="btn-deny" onClick={() => handleConfirmCommand(false)}>Deny</button>
                  <button type="button" className="btn-allow" onClick={() => handleConfirmCommand(true)}>Allow (Enter)</button>
                </div>
              </div>
            </div>
          )}

          <form className="input-box" onSubmit={handleSubmit}>
            <textarea
              ref={textareaRef}
              className="input-textarea"
              placeholder="Ask Pluto a question or describe an engineering task..."
              rows={1}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={onInputFocus}
              onBlur={onInputBlur}
              disabled={isProcessing}
            />

            <button
              type="submit"
              className="send-btn"
              disabled={!inputText.trim() || isProcessing}
              title="Send message"
              aria-label="Send message"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </button>
          </form>

          <div className="input-hint-text">
            Pluto connects to FastAPI on port 8000. Verified local execution.
          </div>
        </div>
      </footer>
    </main>
  );
}
