import { api } from "./api";

export const chatApi = {
  getSessions: async (limit = 20, offset = 0) => {
    return api.get("/api/chat/sessions", {
      params: { limit, offset },
    });
  },

  createSession: async (title) => {
    return api.post("/api/chat/sessions", { title });
  },

  renameSession: async (sessionId, title) => {
    return api.patch(`/api/chat/sessions/${sessionId}`, { title });
  },

  deleteSession: async (sessionId) => {
    return api.delete(`/api/chat/sessions/${sessionId}`);
  },

  getSessionMessages: async (sessionId, limit = 50, offset = 0) => {
    return api.get(`/api/chat/sessions/${sessionId}/messages`, {
      params: { limit, offset },
    });
  },

  sendMessage: async (sessionId, message, imageFile) => {
    const formData = new FormData();
    if (message) {
      formData.append("message", message);
    }
    if (imageFile) {
      formData.append("image", imageFile);
    }

    return api.post(`/api/chat/sessions/${sessionId}/messages`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },
};
