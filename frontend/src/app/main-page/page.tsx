"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { chatApi, ChatSessionResponse, ChatMessageResponse } from "@/lib/chat";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatArea } from "@/components/chat/ChatArea";

type AuthMeResponse = {
  onboarding_completed: boolean;
};

export default function MainPage() {
  const router = useRouter();
  const { accessToken, clearToken, isHydrated } = useAuth();
  const [checkingOnboarding, setCheckingOnboarding] = useState(true);

  // Chat State
  const [sessions, setSessions] = useState<ChatSessionResponse[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isDevMode, setIsDevMode] = useState(false);

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      router.replace("/auth-options");
      return;
    }

    api
      .get<AuthMeResponse>("/api/auth/me")
      .then(({ data }) => {
        if (!data?.onboarding_completed) {
          router.replace("/onboarding/location");
          return;
        }
        setCheckingOnboarding(false);
        fetchSessions();
      })
      .catch(() => {
        clearToken();
        router.replace("/auth-options");
      });
  }, [accessToken, clearToken, isHydrated, router]);

  const fetchSessions = async () => {
    try {
      const { data } = await chatApi.getSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        handleSelectSession(data[0].session_id);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    try {
      const { data } = await chatApi.getSessionMessages(sessionId);
      setMessages(data);
    } catch (err) {
      console.error("Failed to fetch messages", err);
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
  };

  const handleSendMessage = async (text: string, image: File | null) => {
    try {
      setIsLoading(true);
      let sessionId = activeSessionId;

      // If no active session, create one first
      if (!sessionId) {
        // use a short snippet of the text as title if available
        const titleSnippet = text.trim() ? text.slice(0, 30) : "Image Diagnosis";
        const res = await chatApi.createSession(titleSnippet);
        sessionId = res.data.session_id;
        setActiveSessionId(sessionId);
        // add to top of sessions list locally
        setSessions(prev => [res.data, ...prev]);
      }

      // Optimistically add user message if it's just text
      if (text && !image) {
        const tempUserMsg: ChatMessageResponse = {
          message_id: "temp-" + Date.now(),
          session_id: sessionId,
          sender: "user",
          content: text,
          sequence_no: messages.length + 1,
          created_at: new Date().toISOString(),
        };
        setMessages(prev => [...prev, tempUserMsg]);
      }

      // Send to backend
      const res = await chatApi.sendMessage(sessionId, text, image);
      
      // We got the real messages from backend response
      const { user_message, assistant_message, chosen_route } = res.data;
      
      // Inject chosen_route for dev mode display
      if (chosen_route) {
        assistant_message.chosen_route = chosen_route;
      }

      // Replace optimistic message and add assistant message
      setMessages(prev => {
        // filter out the temporary message we added
        const filtered = prev.filter(m => !m.message_id.startsWith("temp-"));
        return [...filtered, user_message, assistant_message];
      });

    } catch (err) {
      console.error("Failed to send message", err);
      // Could add a toast notification here
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
      />
    </div>
  );
}
