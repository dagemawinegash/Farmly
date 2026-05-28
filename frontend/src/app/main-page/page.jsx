import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { chatApi } from "@/lib/chat";
import { voiceApi } from "@/lib/voice";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatArea } from "@/components/chat/ChatArea";

const DEBUG_ENABLED =
  String(import.meta.env.VITE_DEBUG || import.meta.env.NEXT_PUBLIC_DEBUG || "false").toLowerCase() ===
  "true";

export default function MainPage() {
  const navigate = useNavigate();
  const { accessToken, clearToken, isHydrated } = useAuth();

  const [checkingOnboarding, setCheckingOnboarding] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isDevMode, setIsDevMode] = useState(DEBUG_ENABLED);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const audioElementRef = useRef(null);
  const audioUrlRef = useRef(null);

  useEffect(() => {
    return () => {
      audioElementRef.current?.pause();
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      navigate("/auth-options", { replace: true });
      return;
    }

    api
      .get("/api/auth/me")
      .then(({ data }) => {
        if (!data?.onboarding_completed) {
          navigate("/onboarding/location", { replace: true });
          return;
        }
        setCheckingOnboarding(false);
      })
      .catch(() => {
        clearToken();
        navigate("/auth-options", { replace: true });
      });
  }, [accessToken, clearToken, isHydrated, navigate]);

  useEffect(() => {
    if (checkingOnboarding) return;
    fetchSessions();
  }, [checkingOnboarding]);

  const fetchSessions = async () => {
    try {
      const { data } = await chatApi.getSessions();
      setSessions(data);

      const saved = localStorage.getItem("farmly_active_session_id");
      const savedExists = saved && data.some((s) => s.session_id === saved);

      if (savedExists) {
        handleSelectSession(saved);
      } else if (data.length > 0) {
        handleSelectSession(data[0].session_id);
      } else {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const handleSelectSession = async (sessionId) => {
    setActiveSessionId(sessionId);
    localStorage.setItem("farmly_active_session_id", sessionId);

    try {
      const { data } = await chatApi.getSessionMessages(sessionId);
      setMessages(data);
    } catch (err) {
      console.error("Failed to fetch messages", err);
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    localStorage.removeItem("farmly_active_session_id");
    setMessages([]);
  };

  const handleRenameSession = async (sessionId, title) => {
    try {
      const { data } = await chatApi.renameSession(sessionId, title);
      setSessions((prev) => prev.map((s) => (s.session_id === sessionId ? data : s)));
    } catch (err) {
      console.error("Failed to rename session", err);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await chatApi.deleteSession(sessionId);
      const next = sessions.filter((s) => s.session_id !== sessionId);
      setSessions(next);

      if (activeSessionId === sessionId) {
        if (next.length > 0) {
          handleSelectSession(next[0].session_id);
        } else {
          handleNewSession();
        }
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const autoTitleFromFirstMessage = useMemo(
    () => async (sessionId, text) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const shortTitle = trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed;
      await handleRenameSession(sessionId, shortTitle);
    },
    []
  );

  const playAssistantAudio = async (message) => {
    if (!message?.content) return;

    audioElementRef.current?.pause();
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }

    setSpeakingMessageId(message.message_id);
    try {
      const { data } = await voiceApi.synthesize(message.content);
      const audioUrl = URL.createObjectURL(data);
      const audio = new Audio(audioUrl);

      audioUrlRef.current = audioUrl;
      audioElementRef.current = audio;

      const resetAudioState = () => {
        if (audioUrlRef.current === audioUrl) {
          URL.revokeObjectURL(audioUrl);
          audioUrlRef.current = null;
        }
        if (audioElementRef.current === audio) {
          audioElementRef.current = null;
        }
        setSpeakingMessageId(null);
      };

      audio.onended = resetAudioState;
      audio.onerror = resetAudioState;
      await audio.play();
    } catch (err) {
      console.error("Failed to play assistant audio", err);
      setSpeakingMessageId(null);
    }
  };

  const addTempUserMessage = (sessionId, content) => {
    const trimmed = content?.trim();
    if (!trimmed) return;

    setMessages((prev) => [
      ...prev,
      {
        message_id: `temp-${Date.now()}`,
        session_id: sessionId,
        sender: "user",
        content: trimmed,
        sequence_no: prev.length + 1,
        created_at: new Date().toISOString(),
      },
    ]);
  };

  const handleSendMessage = async (text, image, audio) => {
    try {
      setIsLoading(true);
      let outgoingText = text?.trim() || "";

      if (audio) {
        const { data } = await voiceApi.transcribe(audio);
        outgoingText = data?.transcript?.trim() || "";
        if (!outgoingText) {
          throw new Error("Voice transcription returned no text.");
        }
      }

      let sessionId = activeSessionId;
      let wasNewSession = false;
      if (!sessionId) {
        const titleSnippet = outgoingText ? outgoingText.slice(0, 30) : "Image Diagnosis";
        const res = await chatApi.createSession(titleSnippet);
        sessionId = res.data.session_id;
        wasNewSession = true;
        setActiveSessionId(sessionId);
        localStorage.setItem("farmly_active_session_id", sessionId);
        setSessions((prev) => [res.data, ...prev]);
      }

      if (outgoingText && (!image || audio)) {
        addTempUserMessage(sessionId, outgoingText);
      }

      const res = await chatApi.sendMessage(sessionId, outgoingText, image, null);
      const { user_message, assistant_message, chosen_route } = res.data;

      if (chosen_route) {
        assistant_message.chosen_route = chosen_route;
      }

      setMessages((prev) => {
        const filtered = prev.filter((m) => !String(m.message_id).startsWith("temp-"));
        return [...filtered, user_message, assistant_message];
      });

      if (wasNewSession && user_message?.content) {
        await autoTitleFromFirstMessage(sessionId, user_message.content);
      }

      await fetchSessions();
      if (audio && assistant_message?.content) {
        playAssistantAudio(assistant_message);
      }
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isHydrated || checkingOnboarding) return null;

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-background">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onRenameSession={handleRenameSession}
        onDeleteSession={handleDeleteSession}
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
      />
      <ChatArea
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        onOpenSidebar={() => setIsSidebarOpen(true)}
        isDevMode={isDevMode}
        setIsDevMode={setIsDevMode}
        onSpeakMessage={playAssistantAudio}
        speakingMessageId={speakingMessageId}
      />
    </div>
  );
}
