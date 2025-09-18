import zmq
from FileProcessor.text_chunker import llm_guided_sentence_chunk
from FileProcessor.embedding import build_embeddings
from db import create_data, delete_data

#클라이언트는 요약하는 애는 전부다 sllm으로 수정 필요
class FilePostprocessor:
    def __init__(self, pull_port=5558, llm_client=None, embedding_client=None):
        self.context = zmq.Context()
        self.pull_socket = self.context.socket(zmq.PULL)
        self.pull_socket.connect(f"tcp://localhost:{pull_port}")
        self.running = False
        self.llm_client = llm_client
        self.embedding_client = embedding_client

    def handle_create(self, message):
        """파일 생성 처리"""
        file_path = message.get('file_path')
        content = message.get('content')
        print(f"CREATE: {file_path}")

        if content and self.llm_client and self.embedding_client:
            chunks, offsets = self._chunk_content(content, file_path)
            embeddings = self._process_content(chunks, file_path, offsets)
            self._upload_embeddings(embeddings, file_path)
            self._summarize(chunks, file_path)

    def handle_update(self, message):
        """파일 수정 처리"""
        file_path = message.get('file_path')
        content = message.get('content')
        print(f"UPDATE: {file_path}")
        diff_content = message.get('diff_content')
        delete_data(file_path)
        
        if diff_content and self.llm_client: 
            summary = self.llm_client(f"다음 변경사항을 1~2문장으로 요약해주세요: {diff_content}")
            file_name = file_path.split('\\')[-1]
            print(f"{file_name} 파일이 수정되었습니다. 경로: {file_path}, 변경사항: {summary}")
        
        if content and self.llm_client and self.embedding_client:
            chunks, offsets = self._chunk_content(content, file_path)
            embeddings = self._process_content(chunks, file_path, offsets)
            self._upload_embeddings(embeddings, file_path)

    def handle_delete(self, message):
        """파일 삭제 처리"""
        file_path = message.get('file_path')
        print(f"DELETE: {file_path}")
        delete_data(file_path)

    def _chunk_content(self, content, file_path):
        """텍스트 청킹"""
        chunking_result = llm_guided_sentence_chunk(content, self.llm_client)
        chunks = [chunk.text for chunk in chunking_result.chunks]
        
        offsets = []
        for chunk in chunking_result.chunks:
            offsets.append({
                "chunk_index": chunk.chunk_index,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "word_start": chunk.word_start,
                "word_end": chunk.word_end
            })
        
        return chunks, offsets

    def _process_content(self, chunks, file_path, offsets):
        """임베딩 생성"""
        embeddings = build_embeddings(
            chunks=chunks,
            file_path=file_path,
            filetype=file_path.split('.')[-1] if '.' in file_path else 'unknown',
            offsets=offsets,
            embedder=self.embedding_client
        )
        return embeddings

    def _summarize(self, chunks, file_path):
        """병렬 청크 요약 후 최종 요약"""
        chunk_summaries = []
        for chunk in chunks:
            summary = self.llm_client(f"다음 텍스트를 1~2문장으로 요약해주세요: {chunk}")
            chunk_summaries.append(summary)
        
        combined_summaries = "\n".join(chunk_summaries)
        final_summary = self.llm_client(f"다음 요약들을 종합하여 최종 요약을 2~3문장으로 만들어주세요: {combined_summaries}")
        
        file_name = file_path.split('\\')[-1]
        print(f"{file_name} 파일이 생성되었습니다. 경로: {file_path}, 내용: {final_summary}")

    def _upload_embeddings(self, embeddings, file_path):
        """임베딩을 ChromaDB에 업로드"""
        for embedding_data in embeddings:
            create_data(
                file_path=file_path,
                start_idx=embedding_data['offset']['char_start'],
                end_idx=embedding_data['offset']['char_end'],
                embedding=embedding_data['embedding']
            )

    def process_message(self, message):
        """메시지 처리"""
        event_type = message.get('event_type')

        if event_type == 'create':
            self.handle_create(message)
        elif event_type == 'update':
            self.handle_update(message)
        elif event_type == 'delete':
            self.handle_delete(message)
        else:
            print(f"Unknown event: {event_type}")

    def start(self):
        """서비스 시작"""
        self.running = True
        print("File Postprocessor 시작...")

        try:
            while self.running:
                if self.pull_socket.poll(timeout=1000):
                    message = self.pull_socket.recv_json()
                    self.process_message(message)

        except KeyboardInterrupt:
            print("종료 중...")
        finally:
            self.pull_socket.close()
            self.context.term()

if __name__ == "__main__":
    # LLM과 임베딩 클라이언트는 외부에서 주입
    postprocessor = FilePostprocessor(
        llm_client=None,        # 실제 LLM 클라이언트로 교체
        embedding_client=None   # 실제 임베딩 클라이언트로 교체
    )
    postprocessor.start()