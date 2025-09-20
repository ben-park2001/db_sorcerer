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
import { Send, Loader2, User, Bot, AlertCircle, Menu, X } from 'lucide-react';
import { sendChatMessage, checkServerHealth } from '@/lib/api';
import { Message } from '@/types/chat';
import { useChatSessions } from '@/hooks/useChatSessions';
import ChatSidebar from './ChatSidebar';

function LoginScreen({ onLogin }: { onLogin: (userId: string) => void }) {
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (userId.trim()) {
      onLogin(userId.trim());
    }
  };

  return (
    <div className="h-screen w-full flex items-center justify-center bg-background">
      <Card className="w-full max-w-md p-8">
        <div className="text-center space-y-4 mb-8">
          <Avatar className="w-16 h-16 mx-auto">
            <AvatarFallback className="bg-primary/10">
              <Bot className="w-8 h-8 text-primary" />
            </AvatarFallback>
          </Avatar>
          <h1 className="text-2xl font-bold">DB Sorcerer</h1>
          <p className="text-muted-foreground">
            로그인하여 RAG 시스템을 사용해보세요
          </p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="userId" className="block text-sm font-medium mb-2">
              사용자 ID
            </label>
            <Input
              id="userId"
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="사용자 ID를 입력하세요"
              required
            />
          </div>
          
          <div>
            <label htmlFor="password" className="block text-sm font-medium mb-2">
              비밀번호
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요 (MVP용 - 아무값이나 입력)"
            />
          </div>
          
          <Button type="submit" className="w-full" disabled={!userId.trim()}>
            로그인
          </Button>
        </form>
        
        <p className="text-xs text-muted-foreground text-center mt-4">
          * MVP 버전입니다. 비밀번호는 검증하지 않습니다.
        </p>
      </Card>
    </div>
  );
}

export default function ChatInterface() {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [serverStatus, setServerStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [userId, setUserId] = useState<string>('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const {
    sessions,
    activeSession,
    activeSessionId,
    createNewSession,
    deleteSession,
    switchSession,
    updateSessionTitle,
    addMessage,
    setMode
  } = useChatSessions(userId);

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
    localStorage.removeItem('db_sorcerer_user_id');
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    // 활성 세션이 없으면 새로 생성
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      currentSessionId = createNewSession();
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      role: 'user',
      timestamp: new Date(),
    };

    // 세션 ID를 명시적으로 전달
    addMessage(userMessage, currentSessionId);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        message: userMessage.content,
        mode: activeSession?.mode || 'deep',
        user_id: userId,
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response.status === 'success' ? response.response! : response.error!,
        role: 'assistant',
        timestamp: new Date(),
        isError: response.status === 'error',
      };

      // 세션 ID를 명시적으로 전달
      addMessage(assistantMessage, currentSessionId);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: '예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        role: 'assistant',
        timestamp: new Date(),
        isError: true,
      };
      // 세션 ID를 명시적으로 전달
      addMessage(errorMessage, currentSessionId);
    } finally {
      setIsLoading(false);
    }
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
    <div className="h-screen flex bg-background">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300 overflow-hidden flex-shrink-0`}>
        <ChatSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onCreateNew={createNewSession}
          onSelectSession={switchSession}
          onDeleteSession={deleteSession}
          onUpdateTitle={updateSessionTitle}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b border-border p-4 bg-background/80 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2"
              >
                {sidebarOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
              </Button>
              
              <div>
                <h1 className="text-xl font-semibold text-foreground">
                  {activeSession?.title || 'DB Sorcerer'}
                </h1>
                <p className="text-sm text-muted-foreground">
                  RAG 기반 데이터베이스 질의응답 시스템
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {/* 사용자 정보 */}
              <div className="hidden sm:flex items-center gap-2 text-sm">
                <User className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">{userId}</span>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={handleLogout}
                  className="text-xs"
                >
                  로그아웃
                </Button>
              </div>
              
              {/* 모드 선택 */}
              <div className="hidden sm:flex items-center gap-2">
                <span className="text-sm text-muted-foreground">모드:</span>
                <Select 
                  value={activeSession?.mode || 'deep'} 
                  onValueChange={(value) => setMode(value as 'normal' | 'deep' | 'deeper')} 
                  disabled={isLoading}
                >
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
              
              {/* 서버 상태 */}
              <div className="flex items-center gap-2">
                <Badge 
                  variant={serverStatus === 'online' ? 'default' : serverStatus === 'offline' ? 'destructive' : 'secondary'}
                  className="text-xs"
                >
                  <div className={`w-2 h-2 rounded-full mr-1 ${
                    serverStatus === 'online' ? 'bg-green-500' : 
                    serverStatus === 'offline' ? 'bg-white' : 'bg-yellow-500'
                  }`} />
                  {serverStatus === 'online' ? '연결됨' : 
                   serverStatus === 'offline' ? '연결 끊김' : '확인 중...'}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <ScrollArea className="flex-1">
          <div className="max-w-4xl mx-auto p-4 space-y-6">
            {!activeSession || activeSession.messages.length === 0 ? (
              <div className="flex items-center justify-center h-[60vh]">
                <div className="text-center space-y-4 max-w-md mx-auto px-4">
                  <Avatar className="w-16 h-16 mx-auto">
                    <AvatarFallback className="bg-primary/10">
                      <Bot className="w-8 h-8 text-primary" />
                    </AvatarFallback>
                  </Avatar>
                  <h3 className="text-xl font-medium text-foreground">
                    안녕하세요! 무엇을 도와드릴까요?
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    데이터베이스에 관련된 질문을 자유롭게 해보세요. <br />
                    복잡한 쿼리나 데이터 분석도 도와드릴 수 있습니다.
                  </p>
                </div>
              </div>
            ) : (
              activeSession.messages.map((message) => (
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

            {/* Loading indicator */}
            {isLoading && (
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
            {serverStatus === 'offline' && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.
                </AlertDescription>
              </Alert>
            )}
            
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
                <Select 
                  value={activeSession?.mode || 'deep'} 
                  onValueChange={(value) => setMode(value as 'normal' | 'deep' | 'deeper')} 
                  disabled={isLoading}
                >
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
              {activeSession?.mode !== 'deep' && (
                <span className="text-xs text-primary font-medium">
                  현재 모드: {activeSession?.mode?.toUpperCase()}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}