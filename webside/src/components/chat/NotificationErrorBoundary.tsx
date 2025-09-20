'use client';

import { Component, ReactNode } from 'react';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export default class NotificationErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('Notification error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-2">
          <Alert variant="destructive" className="w-80">
            <AlertTriangle className="w-4 h-4" />
            <div className="ml-2">
              <p className="text-sm font-medium">알림 시스템 오류</p>
              <p className="text-xs text-muted-foreground mt-1">
                알림을 불러오는 중 문제가 발생했습니다.
              </p>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={this.handleReset}
                className="mt-2 h-6 text-xs"
              >
                다시 시도
              </Button>
            </div>
          </Alert>
        </div>
      );
    }

    return this.props.children;
  }
}