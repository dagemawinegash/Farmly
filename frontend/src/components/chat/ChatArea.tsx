import { useEffect, useRef } from "react";
import { ChatMessageResponse } from "@/lib/chat";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { Menu, Sprout, CloudRain, Bug, Leaf } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatAreaProps {
  messages: ChatMessageResponse[];
  onSendMessage: (text: string, image: File | null) => void;
  isLoading: boolean;
  onOpenSidebar: () => void;
  isDevMode: boolean;
  setIsDevMode: (val: boolean) => void;
}

const QUICK_ACTIONS = [
  { icon: Sprout, label: "Recommend a crop", text: "Can you recommend a crop suitable for my location?" },
  { icon: CloudRain, label: "Check the weather", text: "What is the weather forecast for the next few days?" },
  { icon: Bug, label: "Diagnose my plant", text: "I have a problem with my plant. (Upload a photo)" },
  { icon: Leaf, label: "Fertilizer advice", text: "What fertilizer should I use for my farm?" },
];

export function ChatArea({ 
  messages, 
  onSendMessage, 
  isLoading, 
  onOpenSidebar,
  isDevMode,
  setIsDevMode
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex flex-1 flex-col h-[100dvh] bg-background">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4 shadow-sm relative z-10">
        <div className="flex items-center gap-2">
          <Button 
            variant="ghost" 
            size="icon" 
            className="md:hidden -ml-2"
            onClick={onOpenSidebar}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className="text-lg font-semibold text-foreground">Farmly Assistant</h1>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <label htmlFor="dev-mode" className="hidden sm:inline-block cursor-pointer">
            Dev Mode
          </label>
          <input 
            type="checkbox" 
            id="dev-mode" 
            checked={isDevMode} 
            onChange={(e) => setIsDevMode(e.target.checked)}
            className="accent-primary h-4 w-4 cursor-pointer"
          />
        </div>
      </header>

      {/* Messages / Empty State */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center max-w-2xl mx-auto">
            <div className="mb-8 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Leaf className="h-8 w-8" />
            </div>
            <h2 className="mb-2 text-2xl font-bold text-center">Welcome to Farmly</h2>
            <p className="mb-8 text-center text-muted-foreground">
              Your personal agricultural assistant. Ask me anything or choose an option below.
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
              {QUICK_ACTIONS.map((action, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(action.text, null)}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-all hover:bg-muted hover:shadow-sm"
                >
                  <div className="rounded-full bg-primary/10 p-2 text-primary">
                    <action.icon className="h-5 w-5" />
                  </div>
                  <span className="font-medium text-sm">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl">
            {messages.map((msg) => (
              <MessageBubble key={msg.message_id} message={msg} isDevMode={isDevMode} />
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-muted-foreground p-4">
                <div className="h-2 w-2 animate-bounce rounded-full bg-primary/50" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-primary/50 delay-75" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-primary/50 delay-150" />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput onSend={onSendMessage} disabled={isLoading} />
    </div>
  );
}
