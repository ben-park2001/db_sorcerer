'use client';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

interface ServerOfflineAlertProps {
  isOffline: boolean;
}

export default function ServerOfflineAlert({ isOffline }: ServerOfflineAlertProps) {
  if (!isOffline) return null;

  return (
    <Alert variant="destructive" className="mb-4">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>
        백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.
      </AlertDescription>
    </Alert>
  );
}