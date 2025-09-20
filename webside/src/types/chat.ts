export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  isError?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  mode: 'normal' | 'deep' | 'deeper';
}

export interface ChatContextType {
  sessions: ChatSession[];
  activeSessionId: string | null;
  createNewSession: () => string;
  deleteSession: (sessionId: string) => void;
  switchSession: (sessionId: string) => void;
  updateSessionTitle: (sessionId: string, title: string) => void;
  addMessage: (message: Message, sessionId?: string) => void;
  setMode: (mode: 'normal' | 'deep' | 'deeper', sessionId?: string) => void;
}