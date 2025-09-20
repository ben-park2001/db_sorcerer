'use client';

import { Card } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Search, BrainCircuit, Loader2, Bot } from 'lucide-react';
import { RAGStatus } from '@/types/chat';

interface RAGStatusIndicatorProps {
  status: RAGStatus;
}

export default function RAGStatusIndicator({ status }: RAGStatusIndicatorProps) {
  const getIcon = () => {
    switch (status.stage) {
      case 'searching':
        return <Search className="w-4 h-4 animate-pulse" />;
      case 'analyzing':
        return <BrainCircuit className="w-4 h-4 animate-spin" />;
      case 'generating':
        return <Loader2 className="w-4 h-4 animate-spin" />;
      default:
        return <Loader2 className="w-4 h-4 animate-spin" />;
    }
  };

  if (!status.isLoading || status.stage === 'idle' || status.stage === 'complete') {
    return null;
  }

  return (
    <div className="flex gap-4 justify-start">
      <Avatar className="w-8 h-8 flex-shrink-0">
        <AvatarFallback className="bg-primary/10">
          <Bot className="w-4 h-4 text-primary" />
        </AvatarFallback>
      </Avatar>
      <div className="max-w-[85%] sm:max-w-[75%] w-full">
        <Card className="bg-muted p-3">
          <div className="flex items-center gap-3">
            {getIcon()}
            <span className="text-sm text-muted-foreground">{status.message}</span>
          </div>
        </Card>
      </div>
    </div>
  );
}