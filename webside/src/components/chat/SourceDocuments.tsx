'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { SourceDocument } from '@/types/chat';

interface SourceDocumentsProps {
  sources: SourceDocument[];
}

export default function SourceDocuments({ sources }: SourceDocumentsProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 border-t border-border pt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4" />
          <span>참고 문서 ({sources.length}개)</span>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {isOpen && (
        <div className="mt-2 space-y-2">
          {sources.map((source, index) => (
            <Card key={index} className="p-3 bg-background/50">
              <p className="text-xs font-semibold truncate">{source.file_name}</p>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{source.text}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}