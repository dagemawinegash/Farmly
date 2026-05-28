import { api } from "./api";

export const voiceApi = {
  transcribe: async (audioFile) => {
    const formData = new FormData();
    const extension = audioFile.type.includes("ogg") ? "ogg" : "webm";
    formData.append("audio", audioFile, `voice-message.${extension}`);

    return api.post("/api/voice/transcribe", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  synthesize: async (text) => {
    return api.post(
      "/api/voice/synthesize",
      { text },
      {
        responseType: "blob",
      }
    );
  },
};

