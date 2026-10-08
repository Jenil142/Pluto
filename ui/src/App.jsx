import { useState, useEffect, useMemo } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import SettingsModal from './components/SettingsModal';
import { sendChatMessage, mapAgentStateToOrb } from './services/api';
import './App.css';

const DEFAULT_SETTINGS = {
  apiEndpoint: 'http://localhost:8000',
  model: 'pluto-core-v1',
  theme: 'light',
};

function createInitialSession() {
  const id = `session-${Date.now()}`;
  return {
    id,
    title: 'New Chat',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

export default function App() {
  // 1. Sessions state with localStorage restoration
  const [sessions, setSessions] = useState(() => {
    try {
      const stored = localStorage.getItem('pluto_chat_sessions');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (e) {
      console.warn('Failed to parse saved chat sessions:', e);
    }
    return [createInitialSession()];
  });

  // 2. Active session ID state
  const [activeSessionId, setActiveSessionId] = useState(() => {
    try {
      const savedId = localStorage.getItem('pluto_active_session_id');
      if (savedId) return savedId;
    } catch (e) {
      console.warn('Failed to read active session id:', e);
    }
    return sessions[0]?.id || '';
  });

  // 3. User settings state
  const [settings, setSettings] = useState(() => {
    try {
      const savedSettings = localStorage.getItem('pluto_settings');
      if (savedSettings) {
        return JSON.parse(savedSettings);
      }
    } catch (e) {
      console.warn('Failed to read saved settings:', e);
    }
    return DEFAULT_SETTINGS;
  });

  // 4. Modal and processing state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [orbState, setOrbState] = useState('breathing');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Synchronize sessions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('pluto_chat_sessions', JSON.stringify(sessions));
    } catch (e) {
      console.error('LocalStorage write error for sessions:', e);
    }
  }, [sessions]);

  // Synchronize activeSessionId to localStorage
  useEffect(() => {
    if (activeSessionId) {
      try {
        localStorage.setItem('pluto_active_session_id', activeSessionId);
      } catch (e) {
        console.error('LocalStorage write error for activeSessionId:', e);
      }
    }
  }, [activeSessionId]);

  // Synchronize settings to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('pluto_settings', JSON.stringify(settings));
    } catch (e) {
      console.error('LocalStorage write error for settings:', e);
    }
  }, [settings]);

  // Derived active session object
  const activeSession = useMemo(() => {
    return (
      sessions.find((s) => s.id === activeSessionId) ||
      sessions[0] ||
      createInitialSession()
    );
  }, [sessions, activeSessionId]);

  // Handlers
  const handleNewChat = () => {
    const newSession = createInitialSession();
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    if (!isProcessing) {
      setOrbState('breathing');
    }
  };

  const handleSelectSession = (id) => {
    setActiveSessionId(id);
    if (!isProcessing) {
      setOrbState('breathing');
    }
  };

  const handleDeleteSession = (id) => {
    setSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== id);
      if (remaining.length === 0) {
        const fresh = createInitialSession();
        setActiveSessionId(fresh.id);
        return [fresh];
      }
      if (activeSessionId === id) {
        setActiveSessionId(remaining[0].id);
      }
      return remaining;
    });
  };

  const handleInputFocus = () => {
    if (!isProcessing) {
      setOrbState('listening');
    }
  };

  const handleInputBlur = () => {
    if (!isProcessing) {
      setOrbState('breathing');
    }
  };

  const handleSendMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || isProcessing) return;

    const userMsg = {
      id: `msg-${Date.now()}-user`,
      role: 'user',
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    // Append user message and auto-title if first message
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSession.id) {
          const isFresh = s.title === 'New Chat' && s.messages.length === 0;
          const autoTitle = isFresh
            ? trimmed.length > 28
              ? `${trimmed.slice(0, 28)}...`
              : trimmed
            : s.title;

          return {
            ...s,
            title: autoTitle,
            updatedAt: Date.now(),
            messages: [...s.messages, userMsg],
          };
        }
        return s;
      })
    );

    setIsProcessing(true);
    // Enter 'working' state when waiting for API response
    setOrbState('working');

    // Progression timers for deep query reasoning and search deliberation
    const searchTimer = setTimeout(() => {
      setOrbState('searching');
    }, 2000);
    const solvingTimer = setTimeout(() => {
      setOrbState('solving');
    }, 4000);

    try {
      const data = await sendChatMessage(trimmed, activeSession.id, settings.apiEndpoint);
      clearTimeout(searchTimer);
      clearTimeout(solvingTimer);

      const nextOrbState = mapAgentStateToOrb(data?.state || 'idle');
      setOrbState(nextOrbState);

      const assistantMsg = {
        id: `msg-${Date.now()}-assistant`,
        role: 'assistant',
        content: data.reply || 'No reply received from Pluto.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: 'complete',
      };

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSession.id) {
            return {
              ...s,
              updatedAt: Date.now(),
              messages: [...s.messages, assistantMsg],
            };
          }
          return s;
        })
      );
    } catch (err) {
      clearTimeout(searchTimer);
      clearTimeout(solvingTimer);
      setOrbState('shaping');

      const errorMsg = {
        id: `msg-${Date.now()}-err`,
        role: 'assistant',
        content: `Error: ${err.message || 'Unable to communicate with Pluto backend.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: 'error',
      };

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSession.id) {
            return {
              ...s,
              updatedAt: Date.now(),
              messages: [...s.messages, errorMsg],
            };
          }
          return s;
        })
      );
    } finally {
      setTimeout(() => {
        setOrbState('breathing');
        setIsProcessing(false);
      }, 350);
    }
  };

  const handleClearAllChats = () => {
    const fresh = createInitialSession();
    setSessions([fresh]);
    setActiveSessionId(fresh.id);
    setOrbState('breathing');
  };

  const handleSaveSettings = (newSettings) => {
    setSettings(newSettings);
  };

  return (
    <div className="app-layout">
      {/* Left Sidebar */}
      {isSidebarOpen && (
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSession.id}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />
      )}

      {/* Main Chat Area */}
      <ChatArea
        activeSession={activeSession}
        onSendMessage={handleSendMessage}
        isProcessing={isProcessing}
        orbState={orbState}
        onInputFocus={handleInputFocus}
        onInputBlur={handleInputBlur}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSaveSettings={handleSaveSettings}
        onClearAllChats={handleClearAllChats}
      />
    </div>
  );
}
