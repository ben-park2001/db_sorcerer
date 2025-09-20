'use client';

import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Bot } from 'lucide-react';

export default function EmptyState() {
  return (
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
  );
}