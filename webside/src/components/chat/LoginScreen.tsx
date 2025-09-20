'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Bot } from 'lucide-react';

interface LoginScreenProps {
  onLogin: (userId: string) => void;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
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