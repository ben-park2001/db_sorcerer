'use client';

import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { User } from 'lucide-react';

interface ChatHeaderProps {
  userId: string;
  mode: 'normal' | 'deep' | 'deeper';
  serverStatus: 'checking' | 'online' | 'offline';
  isLoading: boolean;
  onLogout: () => void;
  onModeChange: (mode: 'normal' | 'deep' | 'deeper') => void;
}

export default function ChatHeader({ 
  userId, 
  mode, 
  serverStatus, 
  isLoading, 
  onLogout, 
  onModeChange 
}: ChatHeaderProps) {
  return (
    <div className="border-b border-border p-4 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">DB Sorcerer</h1>
          <p className="text-sm text-muted-foreground">
            RAG 기반 데이터베이스 질의응답 시스템
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          {/* 사용자 정보 */}
          <div className="hidden sm:flex items-center gap-2 text-sm">
            <User className="w-4 h-4 text-muted-foreground" />
            <span className="text-muted-foreground">{userId}</span>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={onLogout}
              className="text-xs"
            >
              로그아웃
            </Button>
          </div>
          
          {/* 모드 선택 */}
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-sm text-muted-foreground">모드:</span>
            <Select value={mode} onValueChange={onModeChange} disabled={isLoading}>
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
  );
}