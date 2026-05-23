import { useState } from "react";
import { Plus, MessageSquare, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatSessionResponse } from "@/lib/chat";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

interface ChatSidebarProps {
  sessions: ChatSessionResponse[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  isOpen,
  setIsOpen,
}: ChatSidebarProps) {
  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 md:hidden" 
          onClick={() => setIsOpen(false)}
        />
      )}
      
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 flex-col border-r border-border bg-card transition-transform duration-300 md:static md:flex md:w-64 md:translate-x-0",
          isOpen ? "translate-x-0 flex" : "-translate-x-full hidden md:flex"
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <Button onClick={onNewSession} className="w-full justify-start gap-2" variant="default">
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
          <Button 
            variant="ghost" 
            size="icon" 
            className="md:hidden ml-2" 
            onClick={() => setIsOpen(false)}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          <div className="flex flex-col gap-2">
            {sessions.map((session) => (
              <button
                key={session.session_id}
                onClick={() => {
                  onSelectSession(session.session_id);
                  setIsOpen(false);
                }}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors text-left truncate",
                  activeSessionId === session.session_id
                    ? "bg-secondary text-secondary-foreground font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <span className="truncate">{session.title || "New Chat"}</span>
              </button>
            ))}
            {sessions.length === 0 && (
              <p className="text-xs text-center text-muted-foreground mt-4">
                No previous chats.
              </p>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
