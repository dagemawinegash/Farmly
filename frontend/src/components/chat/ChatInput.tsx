import { useState, useRef, FormEvent, ChangeEvent } from "react";
import { Send, Image as ImageIcon, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (text: string, image: File | null) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  const handleImageChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith("image/")) {
      setImage(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
    // reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeImage = () => {
    setImage(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  };

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    if ((!text.trim() && !image) || disabled) return;
    
    onSend(text.trim(), image);
    setText("");
    removeImage();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-border bg-card p-3 md:p-4 w-full">
      <form 
        onSubmit={handleSubmit}
        className="mx-auto flex max-w-3xl flex-col gap-2 rounded-xl border border-input bg-background p-2 focus-within:ring-1 focus-within:ring-ring shadow-sm"
      >
        {previewUrl && (
          <div className="relative mb-2 inline-block w-fit px-2 pt-2">
            <img 
              src={previewUrl} 
              alt="Preview" 
              className="h-20 w-20 rounded-md object-cover border border-border"
            />
            <button
              type="button"
              onClick={removeImage}
              className="absolute -right-2 -top-2 rounded-full bg-destructive p-1 text-destructive-foreground shadow-sm transition-transform hover:scale-110"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2">
          <input 
            type="file"
            accept="image/*"
            className="hidden"
            ref={fileInputRef}
            onChange={handleImageChange}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0 rounded-full text-muted-foreground hover:text-foreground"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
          >
            <ImageIcon className="h-5 w-5" />
          </Button>

          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask Farmly for advice..."
            className="flex-1 resize-none bg-transparent py-2 px-1 outline-none min-h-[40px] max-h-[150px] text-sm custom-scrollbar"
            rows={1}
            disabled={disabled}
          />

          <Button
            type="submit"
            size="icon"
            className="shrink-0 rounded-full h-9 w-9"
            disabled={(!text.trim() && !image) || disabled}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
