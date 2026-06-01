import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { Bot, Square, User, Volume2 } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

const IMAGE_UPLOAD_PLACEHOLDER = "[image uploaded for diagnosis]";
const COPY = {
  en: {
    uploadedCrop: "Uploaded crop",
    stopResponse: "Stop response",
    playResponse: "Play response",
    route: "route",
  },
  am: {
    uploadedCrop: "የተጫነ የሰብል ምስል",
    stopResponse: "መልሱን አቁም",
    playResponse: "መልሱን አጫውት",
    route: "route",
  },
};

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function MessageBubble({ message, isDevMode, onSpeak, isSpeaking }) {
  const { language } = useLanguage();
  const copy = COPY[language] || COPY.en;
  const isUser = message.sender === "user";
  const imageUrl = message.image_preview_url || message.imagePreviewUrl || "";
  const showUserText = Boolean(
    message.content && (!imageUrl || message.content !== IMAGE_UPLOAD_PLACEHOLDER)
  );

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
            "rounded-2xl text-sm",
            isUser && imageUrl ? "p-1" : "px-4 py-3",
            isUser 
              ? "bg-primary text-primary-foreground rounded-tr-sm" 
              : "bg-card text-foreground rounded-tl-sm border border-border shadow-sm"
          )}>
            {isUser ? (
              <div className="flex max-w-full flex-col gap-2">
                {imageUrl && (
                  <img
                    src={imageUrl}
                    alt={copy.uploadedCrop}
                    className="max-h-64 max-w-full rounded-xl object-cover"
                  />
                )}
                {showUserText && (
                  <p className={cn("whitespace-pre-wrap", imageUrl && "px-2 pb-1")}>
                    {message.content}
                  </p>
                )}
              </div>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none break-words prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground prose-headings:text-foreground">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-1 px-1">
            <span className="text-[10px] text-muted-foreground">
              {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            {!isUser && onSpeak && (
              <button
                type="button"
                onClick={() => onSpeak(message)}
                className={cn(
                  "inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-muted",
                  isSpeaking
                    ? "text-red-600 hover:text-red-700"
                    : "text-muted-foreground hover:text-foreground"
                )}
                title={isSpeaking ? copy.stopResponse : copy.playResponse}
                aria-label={isSpeaking ? copy.stopResponse : copy.playResponse}
              >
                {isSpeaking ? (
                  <Square className="h-3.5 w-3.5 fill-current" />
                ) : (
                  <Volume2 className="h-3.5 w-3.5" />
                )}
              </button>
            )}
          </div>

          {isDevMode && !isUser && message.chosen_route && (
            <div className="mt-1 bg-black/80 text-green-400 text-[10px] font-mono px-2 py-1 rounded w-fit border border-green-500/30 shadow-inner">
              <span className="opacity-70">{copy.route}:</span> {message.chosen_route}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
