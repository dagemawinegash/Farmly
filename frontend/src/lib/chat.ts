import { api } from "./api";

export type ChatSessionResponse = {
  session_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessageResponse = {
  message_id: string;
  session_id: string;
  sender: "user" | "assistant";
  content: string;
  sequence_no: number;
  created_at: string;
  chosen_route?: string; // added for Dev Mode
};

export type ChatSendResponse = {
  session_id: string;
  user_message: ChatMessageResponse;
  assistant_message: ChatMessageResponse;
  chosen_route: string;
};

export const chatApi = {
  getSessions: async (limit = 20, offset = 0) => {
    return api.get<ChatSessionResponse[]>("/api/chat/sessions", {
      params: { limit, offset },
    });
  },

  createSession: async (title?: string) => {
    return api.post<ChatSessionResponse>("/api/chat/sessions", { title });
  },

  getSessionMessages: async (sessionId: string, limit = 50, offset = 0) => {
    return api.get<ChatMessageResponse[]>(`/api/chat/sessions/${sessionId}/messages`, {
      params: { limit, offset },
    });
  },

  sendMessage: async (sessionId: string, message?: string, imageFile?: File) => {
    const formData = new FormData();
    if (message) {
      formData.append("message", message);
    }
    if (imageFile) {
      formData.append("image", imageFile);
    }

    return api.post<ChatSendResponse>(`/api/chat/sessions/${sessionId}/messages`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },
};
