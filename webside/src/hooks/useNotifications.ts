import { useState, useEffect, useCallback, useMemo } from 'react';

export interface Notification {
  message: string;
  summary?: string;
  timestamp: number;
  formatted_time: string;
  id: string;
  read?: boolean;
}

export interface NotificationResponse {
  user_id: string;
  message_count: number;
  messages: Omit<Notification, 'id' | 'read'>[];
}

const POLLING_INTERVAL = 30000; // 30초
const MAX_NOTIFICATIONS = 100; // 최대 알림 개수

export function useNotifications(userId: string) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchTime, setLastFetchTime] = useState<number>(0);

  // localStorage 키 생성 (메모이제이션)
  const storageKey = useMemo(() => `notifications_read_${userId}`, [userId]);

  // 읽음 상태를 localStorage에서 관리
  const getReadStatus = useCallback((timestamp: number): boolean => {
    try {
      const readNotifications = JSON.parse(localStorage.getItem(storageKey) || '[]');
      return readNotifications.includes(timestamp);
    } catch {
      return false;
    }
  }, [storageKey]);

  const markAsRead = useCallback((timestamp: number) => {
    try {
      const readNotifications = JSON.parse(localStorage.getItem(storageKey) || '[]');
      if (!readNotifications.includes(timestamp)) {
        readNotifications.push(timestamp);
        
        // 오래된 읽음 상태 정리 (100개 초과시)
        if (readNotifications.length > MAX_NOTIFICATIONS) {
          readNotifications.splice(0, readNotifications.length - MAX_NOTIFICATIONS);
        }
        
        localStorage.setItem(storageKey, JSON.stringify(readNotifications));
        
        setNotifications(prev => prev.map(notif => 
          notif.timestamp === timestamp ? { ...notif, read: true } : notif
        ));
      }
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  }, [storageKey]);

  const fetchNotifications = useCallback(async () => {
    if (!userId) return;
    
    // 중복 요청 방지 (5초 이내 재요청 무시)
    const now = Date.now();
    if (now - lastFetchTime < 5000) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10초 타임아웃
      
      const response = await fetch(`http://localhost:5001/messages/${userId}`, {
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache'
        }
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: NotificationResponse = await response.json();
      
      // 메시지를 알림 형태로 변환하고 읽음 상태 추가
      const formattedNotifications: Notification[] = data.messages
        .map(msg => ({
          ...msg,
          id: `${msg.timestamp}_${msg.message.slice(0, 10)}`,
          read: getReadStatus(msg.timestamp)
        }))
        .sort((a, b) => b.timestamp - a.timestamp) // 최신 순 정렬
        .slice(0, MAX_NOTIFICATIONS); // 최대 개수 제한
      
      setNotifications(formattedNotifications);
      setLastFetchTime(now);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('요청 시간이 초과되었습니다.');
      } else {
        setError(err instanceof Error ? err.message : '알림을 불러오는데 실패했습니다.');
      }
      console.error('Failed to fetch notifications:', err);
    } finally {
      setIsLoading(false);
    }
  }, [userId, getReadStatus, lastFetchTime]);

  // 초기 로드 및 주기적 폴링
  useEffect(() => {
    if (!userId) return;
    
    fetchNotifications();
    const interval = setInterval(fetchNotifications, POLLING_INTERVAL);
    
    return () => clearInterval(interval);
  }, [userId, fetchNotifications]);

  // 페이지 가시성 변경 시 새로고침
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && userId) {
        fetchNotifications();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [fetchNotifications, userId]);

  // 읽지 않은 알림 개수 (메모이제이션)
  const unreadCount = useMemo(() => 
    notifications.filter(notif => !notif.read).length, 
    [notifications]
  );

  return {
    notifications,
    unreadCount,
    isLoading,
    error,
    markAsRead,
    refresh: fetchNotifications
  };
}