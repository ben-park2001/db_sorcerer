'use client';

import { useRef, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import { Clock, Bell } from 'lucide-react';
import { Notification } from '@/hooks/useNotifications';

interface NotificationDropdownProps {
  notifications: Notification[];
  isOpen: boolean;
  onClose: () => void;
  onNotificationClick: (timestamp: number) => void;
}

interface NotificationItemProps {
  notification: Notification;
  onClick: () => void;
}

function NotificationItem({ notification, onClick }: NotificationItemProps) {
  return (
    <div
      className={`p-3 cursor-pointer transition-all duration-200 hover:bg-accent/50 ${
        !notification.read 
          ? 'bg-gradient-to-r from-blue-50 to-transparent dark:from-blue-950/20 dark:to-transparent border-l-2 border-blue-500' 
          : 'hover:bg-accent/30'
      }`}
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <Clock className="w-3 h-3 text-muted-foreground mt-1 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-foreground line-clamp-2 leading-relaxed">
            {notification.message}
          </p>
          <p className="text-xs text-muted-foreground mt-1.5 font-medium">
            {notification.formatted_time}
          </p>
        </div>
        {!notification.read && (
          <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1 animate-pulse" />
        )}
      </div>
    </div>
  );
}

export default function NotificationDropdown({ 
  notifications, 
  isOpen, 
  onClose, 
  onNotificationClick 
}: NotificationDropdownProps) {
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 클릭 외부 감지
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        onClose();
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="absolute top-full right-0 mt-2 z-50 animate-in fade-in-0 zoom-in-95 duration-200" ref={dropdownRef}>
      <Card className="w-80 shadow-lg border-border/50 backdrop-blur-sm bg-background/95">
        <div className="p-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-sm">알림</h3>
            <Button variant="ghost" size="sm" onClick={onClose} className="h-6 px-2 text-xs hover:bg-accent/50">
              닫기
            </Button>
          </div>
        </div>
        
        <ScrollArea className="max-h-96">
          {notifications.length === 0 ? (
            <div className="p-6 text-center text-muted-foreground">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">새로운 알림이 없습니다</p>
            </div>
          ) : (
            <div>
              {notifications.map((notification, index) => (
                <div key={notification.id}>
                  <NotificationItem
                    notification={notification}
                    onClick={() => onNotificationClick(notification.timestamp)}
                  />
                  {index < notifications.length - 1 && <Separator className="opacity-50" />}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </Card>
    </div>
  );
}