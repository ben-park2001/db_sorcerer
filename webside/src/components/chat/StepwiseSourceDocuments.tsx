'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { SourceDocument } from '@/types/chat';

interface StepwiseSourceDocumentsProps {
  sources: SourceDocument[];
  stepNumber: number;
}

export default function StepwiseSourceDocuments({ sources, stepNumber }: StepwiseSourceDocumentsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full justify-between h-auto p-2 text-left hover:bg-muted/50"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-3 h-3 text-blue-500 flex-shrink-0" />
          <span className="text-xs font-medium text-blue-700 dark:text-blue-300">
            단계 {stepNumber} 참조 소스 ({sources.length}개)
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-3 h-3 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronDown className="w-3 h-3 text-muted-foreground flex-shrink-0" />
        )}
      </Button>

      {isExpanded && (
        <div className="space-y-2 pl-2 border-l-2 border-blue-200 dark:border-blue-700">
          {sources.map((source, index) => (
            <Card key={index} className="p-3 bg-blue-50/50 dark:bg-blue-950/20 border-blue-200/50 dark:border-blue-800/50">
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <Badge variant="outline" className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 border-blue-300 dark:border-blue-700 flex-shrink-0">
                    {source.file_name}
                  </Badge>
                  {source.distance !== undefined && (
                    <Badge variant="secondary" className="text-xs">
                      유사도: {(1 - source.distance).toFixed(3)}
                    </Badge>
                  )}
                </div>
                <Separator className="border-blue-200/50 dark:border-blue-700/50" />
                <p className="text-xs leading-relaxed text-gray-700 dark:text-gray-300 line-clamp-3">
                  {source.text}
                </p>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
