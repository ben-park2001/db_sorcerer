'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Edit2, 
  Check, 
  X,
  Bot 
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ChatSession } from '@/types/chat';

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onCreateNew: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onUpdateTitle: (sessionId: string, title: string) => void;
}

export default function ChatSidebar({
  sessions,
  activeSessionId,
  onCreateNew,
  onSelectSession,
  onDeleteSession,
  onUpdateTitle,
}: ChatSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const handleEditStart = (session: ChatSession) => {
    setEditingId(session.id);
    setEditTitle(session.title);
  };

  const handleEditSave = () => {
    if (editingId && editTitle.trim()) {
      onUpdateTitle(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const handleEditCancel = () => {
    setEditingId(null);
    setEditTitle('');
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
      return date.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } else if (days === 1) {
      return '어제';
    } else if (days < 7) {
      return `${days}일 전`;
    } else {
      return date.toLocaleDateString('ko-KR', { 
        month: 'short', 
        day: 'numeric' 
      });
    }
  };

  return (
    <div className="h-full flex flex-col bg-background border-r border-border">
      {/* Header */}
      <div className="p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Bot className="w-6 h-6 text-primary" />
          <h2 className="font-semibold text-foreground">DB Sorcerer</h2>
        </div>
        
        <Button 
          onClick={onCreateNew}
          className="w-full justify-start gap-2"
          size="sm"
        >
          <Plus className="w-4 h-4" />
          새 채팅
        </Button>
      </div>

      <Separator />

      {/* Chat List */}
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-2 py-2">
          {sessions.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-8">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>아직 채팅이 없습니다</p>
            </div>
          ) : (
            sessions
              .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
              .map((session) => (
                <Card
                  key={session.id}
                  className={`p-3 cursor-pointer hover:bg-accent/50 transition-colors group ${
                    activeSessionId === session.id 
                      ? 'bg-accent border-primary/50' 
                      : 'bg-background'
                  }`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <div className="space-y-2">
                    {/* Title */}
                    <div className="flex items-center justify-between">
                      {editingId === session.id ? (
                        <div className="flex items-center gap-1 flex-1">
                          <Input
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            className="h-6 text-sm"
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleEditSave();
                              if (e.key === 'Escape') handleEditCancel();
                            }}
                            autoFocus
                          />
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="h-6 w-6 p-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditSave();
                            }}
                          >
                            <Check className="w-3 h-3" />
                          </Button>
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="h-6 w-6 p-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditCancel();
                            }}
                          >
                            <X className="w-3 h-3" />
                          </Button>
                        </div>
                      ) : (
                        <>
                          <h3 className="font-medium text-sm truncate flex-1">
                            {session.title}
                          </h3>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditStart(session);
                              }}
                            >
                              <Edit2 className="w-3 h-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteSession(session.id);
                              }}
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{session.messages.length}개 메시지</span>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs px-1 py-0">
                          {session.mode.toUpperCase()}
                        </Badge>
                        <span>{formatTime(new Date(session.updatedAt))}</span>
                      </div>
                    </div>
                  </div>
                </Card>
              ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}