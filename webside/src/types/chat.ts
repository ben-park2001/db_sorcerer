// 웹소켓이나 SSE 등에서 오는 스트리밍 데이터 타입
export type StreamEvent =
  | { type: 'start'; mode: string }
  | { type: 'search_query'; iteration: number; query: string }
  | { type: 'search_results'; results: SourceDocument[]; count: number }
  | {
      type: 'intermediate_answer';
      iteration: number;
      answer: string;
      need_more: boolean;
      next_query: string;
    }
  | { type: 'final_answer'; answer: string }
  | { type: 'complete' }
  | { type: 'error'; error: string };

// 검색된 문서 소스 정보
export interface SourceDocument {
  file_name: string;
  text: string;
  distance?: number; // 유사도 점수 (옵션)
}

// RAG 과정 실시간 상태
export interface RAGStatus {
  isLoading: boolean;
  stage:
    | 'idle'
    | 'starting'
    | 'searching'
    | 'analyzing'
    | 'generating'
    | 'complete'
    | 'error';
  message: string; // 현재 상태를 설명하는 메시지
  sources: SourceDocument[]; // 현재까지 수집된 문서
  finalAnswer: string; // 최종 답변
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

// 중간 단계 정보 (텍스트와 해당 단계에서 사용된 소스 포함)
export interface IntermediateStep {
  text: string;
  sources: SourceDocument[];
}

// 채팅 메시지 상태
export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  isError?: boolean;
  sources?: SourceDocument[]; // 답변에 참고한 문서 (전체)
  intermediateSteps?: IntermediateStep[]; // 중간 과정들 (각각 소스 포함)
  finalAnswer?: string; // 최종 답변
}