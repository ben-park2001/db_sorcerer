'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Send, Loader2, User, Bot, AlertCircle, Search, FileText, BrainCircuit, ChevronDown, ChevronUp
} from 'lucide-react';
import { sendChatMessageStream, checkServerHealth } from '@/lib/api';
import { Message, RAGStatus, SourceDocument, StreamEvent } from '@/types/chat';
import LoginScreen from './LoginScreen';
import SourceDocuments from './SourceDocuments';
import RAGStatusIndicator from './RAGStatusIndicator';
import ChatHeader from './ChatHeader';
import EmptyState from './EmptyState';
import ServerOfflineAlert from './ServerOfflineAlert';

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [serverStatus, setServerStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [mode, setMode] = useState<'normal' | 'deep' | 'deeper'>('deep');
  const [userId, setUserId] = useState<string>('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [ragStatus, setRagStatus] = useState<RAGStatus>({
    isLoading: false,
    stage: 'idle',
    message: '',
    sources: [],
    finalAnswer: '',
  });

  // 서버 상태 확인
  useEffect(() => {
    const checkStatus = async () => {
      const isOnline = await checkServerHealth();
      setServerStatus(isOnline ? 'online' : 'offline');
    };
    
    checkStatus();
    const interval = setInterval(checkStatus, 30000); // 30초마다 확인
    
    return () => clearInterval(interval);
  }, []);

  // 로컬 스토리지에서 user_id 복원
  useEffect(() => {
    const savedUserId = localStorage.getItem('db_sorcerer_user_id');
    if (savedUserId) {
      setUserId(savedUserId);
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogin = (inputUserId: string) => {
    const trimmedUserId = inputUserId.trim();
    if (trimmedUserId) {
      setUserId(trimmedUserId);
      setIsLoggedIn(true);
      localStorage.setItem('db_sorcerer_user_id', trimmedUserId);
    }
  };

  const handleLogout = () => {
    setUserId('');
    setIsLoggedIn(false);
    setMessages([]);
    localStorage.removeItem('db_sorcerer_user_id');
  };

  const handleSend = async () => {
    if (!input.trim() || ragStatus.isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      role: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setRagStatus({
      isLoading: true,
      stage: 'starting',
      message: '연결 중...',
      sources: [],
      finalAnswer: '',
    });

    // 어시스턴트 메시지 placeholder 추가
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessagePlaceholder: Message = {
      id: assistantMessageId,
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      sources: [],
    };
    setMessages(prev => [...prev, assistantMessagePlaceholder]);

    await sendChatMessageStream(
      {
        message: userMessage.content,
        mode: mode,
        user_id: userId,
      },
      (event: StreamEvent) => {
        switch (event.type) {
          case 'start':
            setRagStatus(prev => ({ ...prev, stage: 'starting', message: `[${event.mode} 모드] 응답 시작...` }));
            break;
          case 'search_query':
            setRagStatus(prev => ({ ...prev, stage: 'searching', message: `"${event.query}" 검색 중... (단계 ${event.iteration})` }));
            break;
          case 'search_results':
            setRagStatus(prev => ({
              ...prev,
              stage: 'analyzing',
              message: `${event.count}개 문서 조각 발견. 분석 중...`,
              sources: [...prev.sources, ...event.results],
            }));
            break;
          case 'intermediate_answer':
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: event.answer }
                : msg
            ));
            setRagStatus(prev => ({ ...prev, stage: 'generating', message: '답변 생성 중...' }));
            break;
          case 'final_answer':
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: event.answer }
                : msg
            ));
            break;
          case 'complete':
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, sources: ragStatus.sources }
                : msg
            ));
            setRagStatus({ isLoading: false, stage: 'complete', message: '완료', sources: [], finalAnswer: '' });
            setIsLoading(false);
            break;
          case 'error':
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: `오류: ${event.error}`, isError: true }
                : msg
            ));
            setRagStatus({ isLoading: false, stage: 'error', message: event.error, sources: [], finalAnswer: '' });
            setIsLoading(false);
            break;
        }
      }
    );
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 로그인되지 않은 경우 로그인 화면 표시
  if (!isLoggedIn) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <ChatHeader 
        userId={userId}
        mode={mode}
        serverStatus={serverStatus}
        isLoading={isLoading}
        onLogout={handleLogout}
        onModeChange={(value) => setMode(value)}
      />

      {/* Messages Area */}
      <ScrollArea className="flex-1">
        <div className="max-w-4xl mx-auto p-4 space-y-6">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-4 ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role === 'assistant' && (
                  <Avatar className="w-8 h-8 flex-shrink-0 mt-1">
                    <AvatarFallback className="bg-primary/10">
                      <Bot className="w-4 h-4 text-primary" />
                    </AvatarFallback>
                  </Avatar>
                )}
                
                <div className={`max-w-[85%] sm:max-w-[75%] ${
                  message.role === 'user' ? 'order-1' : ''
                }`}>
                  <Card className={`p-4 ${
                    message.role === 'user' 
                      ? 'bg-primary text-primary-foreground ml-auto' 
                      : message.isError
                      ? 'bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800'
                      : 'bg-muted'
                  }`}>
                    {message.isError && (
                      <div className="flex items-center gap-2 mb-3">
                        <AlertCircle className="w-4 h-4 text-red-500" />
                        <span className="text-sm text-red-600 dark:text-red-400 font-medium">오류</span>
                      </div>
                    )}
                    <p className={`text-sm leading-relaxed whitespace-pre-wrap ${
                      message.isError ? 'text-red-700 dark:text-red-300' : ''
                    }`}>{message.content}</p>
                    <SourceDocuments sources={message.sources || []} />
                  </Card>
                  
                  <div className={`flex items-center gap-2 mt-2 px-1 ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}>
                    <span className="text-xs text-muted-foreground">
                      {message.timestamp.toLocaleTimeString('ko-KR', { 
                        hour: '2-digit', 
                        minute: '2-digit' 
                      })}
                    </span>
                  </div>
                </div>

                {message.role === 'user' && (
                  <Avatar className="w-8 h-8 flex-shrink-0 mt-1 order-2">
                    <AvatarFallback className="bg-muted">
                      <User className="w-4 h-4 text-muted-foreground" />
                    </AvatarFallback>
                  </Avatar>
                )}
              </div>
            ))
          )}

          {/* RAG Status Indicator */}
          <RAGStatusIndicator status={ragStatus} />

          {/* Loading indicator (legacy, might be removed) */}
          {isLoading && messages.length > 0 && !ragStatus.isLoading && (
            <div className="flex gap-4 justify-start">
              <Avatar className="w-8 h-8 flex-shrink-0">
                <AvatarFallback className="bg-primary/10">
                  <Bot className="w-4 h-4 text-primary" />
                </AvatarFallback>
              </Avatar>
              <div className="max-w-[85%] sm:max-w-[75%] space-y-2">
                <Card className="bg-muted p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">응답을 생성하고 있습니다...</span>
                  </div>
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                </Card>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t border-border bg-background/80 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto p-4">
          <ServerOfflineAlert isOffline={serverStatus === 'offline'} />
          
          {/* 모바일에서 사용자 정보 및 모드 선택 */}
          <div className="sm:hidden mb-3 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <User className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">{userId}</span>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleLogout}
                className="text-xs"
              >
                로그아웃
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">모드:</span>
              <Select value={mode} onValueChange={(value) => setMode(value as typeof mode)} disabled={isLoading}>
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="deep">Deep</SelectItem>
                  <SelectItem value="deeper">Deeper</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <div className="flex gap-3">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={serverStatus === 'offline' ? '서버 연결 대기 중...' : '메시지를 입력하세요...'}
              disabled={isLoading || serverStatus === 'offline'}
              className="flex-1 min-h-[44px]"
            />
            <Button 
              onClick={handleSend} 
              disabled={!input.trim() || isLoading || serverStatus === 'offline'}
              size="icon"
              className="h-[44px] w-[44px]"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mt-3">
            <p className="text-xs text-muted-foreground">
              Enter를 눌러 전송 • Shift+Enter로 줄바꿈
            </p>
            {mode !== 'deep' && (
              <span className="text-xs text-primary font-medium">
                현재 모드: {mode.toUpperCase()}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}