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
import { Send, Loader2, User, Bot, AlertCircle } from 'lucide-react';
import { sendChatMessage, checkServerHealth } from '@/lib/api';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  isError?: boolean;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [serverStatus, setServerStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [mode, setMode] = useState<'normal' | 'deep' | 'deeper'>('deep');

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

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      role: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        message: userMessage.content,
        mode: mode,
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response.status === 'success' ? response.response! : response.error!,
        role: 'assistant',
        timestamp: new Date(),
        isError: response.status === 'error',
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: '예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        role: 'assistant',
        timestamp: new Date(),
        isError: true,
      };
      setMessages(prev => [...prev, errorMessage]);
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

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border p-4 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">DB Sorcerer</h1>
            <p className="text-sm text-muted-foreground">
              RAG 기반 데이터베이스 질의응답 시스템
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            {/* 모드 선택 */}
            <div className="hidden sm:flex items-center gap-2">
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
          {messages.length === 0 ? (
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
          
          {/* 모바일에서 모드 선택 */}
          <div className="sm:hidden mb-3">
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