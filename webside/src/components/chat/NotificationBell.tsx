'use client';

import { Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface NotificationBellProps {
  count: number;
  onClick: () => void;
  isOpen: boolean;
}

export default function NotificationBell({ count, onClick, isOpen }: NotificationBellProps) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      className={`relative p-2 transition-all duration-200 ${
        isOpen 
          ? 'bg-accent shadow-sm' 
          : 'hover:bg-accent hover:scale-105'
      }`}
    >
      <Bell className={`w-4 h-4 transition-transform duration-200 ${
        count > 0 ? 'animate-pulse' : ''
      } ${isOpen ? 'rotate-12' : ''}`} />
      {count > 0 && (
        <Badge 
          variant="destructive" 
          className="absolute -top-1 -right-1 min-w-[18px] h-[18px] text-xs flex items-center justify-center p-0 animate-in fade-in-0 zoom-in-50 duration-200"
        >
          {count > 99 ? '99+' : count}
        </Badge>
      )}
    </Button>
  );
}