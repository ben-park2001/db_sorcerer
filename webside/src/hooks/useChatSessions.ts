'use client';

import { useState, useEffect } from 'react';
import { ChatSession, Message } from '@/types/chat';

const STORAGE_KEY = 'db_sorcerer_chat_sessions';

export function useChatSessions(userId: string) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // 로컬 스토리지에서 세션 불러오기
  useEffect(() => {
    if (!userId) return;

    const storageKey = `${STORAGE_KEY}_${userId}`;
    const savedSessions = localStorage.getItem(storageKey);
    
    if (savedSessions) {
      try {
        const parsedSessions: ChatSession[] = JSON.parse(savedSessions);
        // Date 객체 복원
        const restoredSessions = parsedSessions.map(session => ({
          ...session,
          createdAt: new Date(session.createdAt),
          updatedAt: new Date(session.updatedAt),
          messages: session.messages.map(msg => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }))
        }));
        
        setSessions(restoredSessions);
        
        // 가장 최근 세션을 활성화
        if (restoredSessions.length > 0) {
          const lastSession = restoredSessions.sort((a, b) => 
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          )[0];
          setActiveSessionId(lastSession.id);
        }
      } catch (error) {
        console.error('세션 복원 중 오류:', error);
      }
    }
  }, [userId]);

  // 세션 변경 시 로컬 스토리지에 저장
  useEffect(() => {
    if (!userId || sessions.length === 0) return;

    const storageKey = `${STORAGE_KEY}_${userId}`;
    localStorage.setItem(storageKey, JSON.stringify(sessions));
  }, [sessions, userId]);

  const generateSessionTitle = (firstMessage?: string): string => {
    if (!firstMessage) return '새 채팅';
    
    const words = firstMessage.trim().split(' ').slice(0, 4);
    return words.join(' ') + (firstMessage.length > words.join(' ').length ? '...' : '');
  };

  const createNewSession = (): string => {
    const newSession: ChatSession = {
      id: `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      title: '새 채팅',
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
      mode: 'deep'
    };

    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    return newSession.id;
  };

  const deleteSession = (sessionId: string) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId));
    
    // 삭제된 세션이 활성 세션이었다면 다른 세션으로 전환
    if (activeSessionId === sessionId) {
      setSessions(prev => {
        const remaining = prev.filter(s => s.id !== sessionId);
        if (remaining.length > 0) {
          const nextSession = remaining.sort((a, b) => 
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          )[0];
          setActiveSessionId(nextSession.id);
        } else {
          setActiveSessionId(null);
        }
        return remaining;
      });
    }
  };

  const switchSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
  };

  const updateSessionTitle = (sessionId: string, title: string) => {
    setSessions(prev => prev.map(session => 
      session.id === sessionId 
        ? { ...session, title, updatedAt: new Date() }
        : session
    ));
  };

  const addMessage = (message: Message, sessionId?: string) => {
    const targetSessionId = sessionId || activeSessionId;
    if (!targetSessionId) return;

    setSessions(prev => prev.map(session => {
      if (session.id === targetSessionId) {
        const updatedMessages = [...session.messages, message];
        
        // 첫 번째 메시지인 경우 제목 자동 생성
        let newTitle = session.title;
        if (session.messages.length === 0 && message.role === 'user') {
          newTitle = generateSessionTitle(message.content);
        }

        return {
          ...session,
          title: newTitle,
          messages: updatedMessages,
          updatedAt: new Date()
        };
      }
      return session;
    }));
  };

  const setMode = (mode: 'normal' | 'deep' | 'deeper', sessionId?: string) => {
    const targetSessionId = sessionId || activeSessionId;
    if (!targetSessionId) return;

    setSessions(prev => prev.map(session => 
      session.id === targetSessionId 
        ? { ...session, mode, updatedAt: new Date() }
        : session
    ));
  };

  const activeSession = sessions.find(s => s.id === activeSessionId) || null;

  return {
    sessions,
    activeSession,
    activeSessionId,
    createNewSession,
    deleteSession,
    switchSession,
    updateSessionTitle,
    addMessage,
    setMode
  };
}