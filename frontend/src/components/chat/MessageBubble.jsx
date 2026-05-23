import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { Bot, User } from "lucide-react";

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function MessageBubble({ message, isDevMode }) {
  const isUser = message.sender === "user";

  return (
    <div className={cn("flex w-full mb-6", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[85%] md:max-w-[75%] gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
        
        {/* Avatar */}
        <div className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"
        )}>
          {isUser ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
        </div>

        {/* Message Content */}
        <div className={cn(
          "flex flex-col gap-1",
          isUser ? "items-end" : "items-start"
        )}>
          <div className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser 
              ? "bg-primary text-primary-foreground rounded-tr-sm" 
              : "bg-card text-foreground rounded-tl-sm border border-border shadow-sm"
          )}>
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
          
          <span className="text-[10px] text-muted-foreground px-1">
            {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>

          {isDevMode && !isUser && message.chosen_route && (
            <div className="mt-1 bg-black/80 text-green-400 text-[10px] font-mono px-2 py-1 rounded w-fit border border-green-500/30 shadow-inner">
              <span className="opacity-70">route:</span> {message.chosen_route}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
