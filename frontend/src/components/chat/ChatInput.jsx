import { useEffect, useRef, useState } from "react";
import { Loader2, Mic, Send, Square, Image as ImageIcon, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const MAX_RECORDING_MS = 45000;
const AUDIO_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
];

function getSupportedAudioMimeType() {
  if (typeof window === "undefined" || !window.MediaRecorder) {
    return "";
  }
  return AUDIO_MIME_TYPES.find((type) => window.MediaRecorder.isTypeSupported(type)) || "";
}

export function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [recordingState, setRecordingState] = useState("idle");
  const [recordingError, setRecordingError] = useState("");
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingTimeoutRef = useRef(null);

  useEffect(() => {
    return () => {
      clearTimeout(recordingTimeoutRef.current);
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      mediaRecorderRef.current?.stream?.getTracks().forEach((track) => track.stop());
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleTextChange = (e) => {
    setText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  const handleImageChange = (e) => {
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

  const stopRecording = () => {
    clearTimeout(recordingTimeoutRef.current);
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state !== "recording") return;
    setRecordingState("processing");
    recorder.stop();
  };

  const startRecording = async () => {
    if (disabled || recordingState !== "idle") return;
    setRecordingError("");

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setRecordingError("Voice recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getSupportedAudioMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      audioChunksRef.current = [];
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setRecordingError("Recording failed. Please try again.");
        setRecordingState("idle");
        clearTimeout(recordingTimeoutRef.current);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.onstop = () => {
        clearTimeout(recordingTimeoutRef.current);
        stream.getTracks().forEach((track) => track.stop());
        const audioType = recorder.mimeType || mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: audioType });
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;

        if (!audioBlob.size) {
          setRecordingError("No audio was recorded.");
          setRecordingState("idle");
          return;
        }

        onSend("", image, audioBlob);
        setText("");
        removeImage();
        setRecordingState("idle");
      };

      recorder.start();
      setRecordingState("recording");
      recordingTimeoutRef.current = window.setTimeout(stopRecording, MAX_RECORDING_MS);
    } catch (err) {
      console.error("Failed to start recording", err);
      setRecordingError("Microphone permission is needed for voice messages.");
      setRecordingState("idle");
    }
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    if ((!text.trim() && !image) || disabled || recordingState !== "idle") return;
    
    onSend(text.trim(), image, null);
    setText("");
    removeImage();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isRecording = recordingState === "recording";
  const isProcessingAudio = recordingState === "processing";

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
            disabled={disabled || isRecording || isProcessingAudio}
            title="Attach image"
            aria-label="Attach image"
          >
            <ImageIcon className="h-5 w-5" />
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={`shrink-0 rounded-full ${
              isRecording
                ? "bg-destructive/10 text-destructive hover:bg-destructive/15 hover:text-destructive"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={disabled || isProcessingAudio}
            title={isRecording ? "Stop recording" : "Record voice message"}
            aria-label={isRecording ? "Stop recording" : "Record voice message"}
          >
            {isProcessingAudio ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : isRecording ? (
              <Square className="h-4 w-4 fill-current" />
            ) : (
              <Mic className="h-5 w-5" />
            )}
          </Button>

          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask Farmly for advice..."
            className="flex-1 resize-none bg-transparent py-2 px-1 outline-none min-h-[40px] max-h-[150px] text-sm custom-scrollbar"
            rows={1}
            disabled={disabled || isRecording || isProcessingAudio}
          />

          <Button
            type="submit"
            size="icon"
            className="shrink-0 rounded-full h-9 w-9"
            disabled={(!text.trim() && !image) || disabled || isRecording || isProcessingAudio}
            title="Send message"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        {(isRecording || isProcessingAudio || recordingError) && (
          <div className="px-2 text-xs">
            {isRecording && <span className="text-destructive">Recording...</span>}
            {isProcessingAudio && <span className="text-muted-foreground">Processing audio...</span>}
            {recordingError && <span className="text-destructive">{recordingError}</span>}
          </div>
        )}
      </form>
    </div>
  );
}
