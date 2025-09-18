# 1. 여러 확장자 파일 읽기
# 2. 길이가 길면 자르기(앞뒤 조각은 약간씩 겹치게 자르기)
# -> LLM 이 잘라주기 전에,
# -> LLM 이 감당하기 힘들 정도로 길면
# -> LLM 이 감당 가능한 길이로 조절해줘야 함

# input : 여러 파일
# output : 여러개의 text chunk(해당 chunk 가, 해당 파일의 어디부터 어디까지인지도 전달해줘야 함)

# Gemini 로 바이브 코딩, 딱 봤을때 문제는 없는듯 (20250915 19:39)
# 그런데 여기선 file path 를 받는데 FE에서 drag drop 받아와서 해야될듯

import os
from docx import Document
import pdfplumber


def read_file(file_path: str) -> str:
    """
    주어진 경로의 파일(.txt, .docx, .pdf, .hwp)을 읽어 텍스트 내용을 문자열로 반환합니다.
    한국어 파일에 최적화되어 있습니다.

    Args:
        file_path (str): 읽을 파일의 경로

    Returns:
        str: 파일에서 추출한 텍스트 내용

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 경우 발생합니다.
        ValueError: 지원하지 않는 파일 형식일 경우 발생합니다.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"오류: '{file_path}' 파일을 찾을 수 없습니다.")

    # 파일 확장자를 소문자로 추출
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    full_text = ""

    try:
        if extension == '.txt':
            # UTF-8으로 먼저 시도하고, 오류 발생 시 CP949로 재시도 (Windows 환경 호환)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='cp949') as f:
                    full_text = f.read()

        elif extension == '.docx':
            doc = Document(file_path)
            text_list = [para.text for para in doc.paragraphs]
            full_text = '\n'.join(text_list)

        elif extension == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                text_list = [page.extract_text() for page in pdf.pages if page.extract_text()]
                full_text = '\n'.join(text_list)

        elif extension == '.hwp':
            hwp = Hwp()
            hwp.open(file_path)
            hwp.MoveDocBegin()  # 문서 시작으로 이동
            hwp.MoveSelDocEnd()  # 문서 끝까지 선택
            full_text = hwp.GetTextFile("TEXT", "")
            hwp.quit()  # 한글 프로그램 종료
            del hwp  # 메모리에서 객체 명시적으로 해제

        else:
            raise ValueError(
                f"지원하지 않는 파일 형식입니다: '{extension}'. "
                "지원 형식: .txt, .docx, .pdf, .hwp"
            )
            
    except Exception as e:
        # 파일 처리 중 발생할 수 있는 모든 예외를 처리합니다.
        print(f"'{file_path}' 파일 처리 중 오류 발생: {e}")
        return "" # 오류 발생 시 빈 문자열 반환

    return full_text


