'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileText, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { SourceDocument } from '@/types/chat';

interface SourceDocumentsProps {
  sources: SourceDocument[];
}

export default function SourceDocuments({ sources }: SourceDocumentsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  if (!sources || sources.length === 0) {
    return null;
  }

  const copyToClipboard = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('복사 실패:', err);
    }
  };

  return (
    <div className="mt-3 border-t border-border pt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4" />
          <span>참고 문서 ({sources.length}개)</span>
          <Badge variant="secondary" className="text-xs">
            {sources.length > 1 ? '다중 소스' : '단일 소스'}
          </Badge>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {isOpen && (
        <div className="mt-3 space-y-3">
          {sources.map((source, index) => (
            <Card key={index} className="p-4 bg-background/50 hover:bg-background/70 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <p className="text-sm font-semibold truncate text-primary">
                      📄 {source.file_name}
                    </p>
                    <Badge variant="outline" className="text-xs shrink-0">
                      #{index + 1}
                    </Badge>
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 mb-2">
                    <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                      {source.text}
                    </p>
                  </div>
                  {source.distance && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">관련성:</span>
                      <Badge 
                        variant={source.distance < 0.5 ? "default" : source.distance < 0.8 ? "secondary" : "outline"}
                        className="text-xs"
                      >
                        {(1 - source.distance).toFixed(3)}
                      </Badge>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => copyToClipboard(source.text, index)}
                  className="shrink-0 p-2 rounded-md hover:bg-muted transition-colors"
                  title="텍스트 복사"
                >
                  {copiedIndex === index ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Copy className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>
              </div>
            </Card>
          ))}
          <div className="text-xs text-muted-foreground text-center pt-2 border-t">
            💡 이 문서들이 답변 생성에 사용되었습니다
          </div>
        </div>
      )}
    </div>
  );
}