"""
청킹 유틸리티

리스트와 텍스트를 배치 단위로 분할하는 유틸리티 함수들입니다.
"""

from typing import Generator, List, TypeVar

T = TypeVar('T')


def chunk_list(items: List[T], batch_size: int) -> Generator[List[T], None, None]:
    """
    리스트를 배치 크기로 분할
    
    Args:
        items: 분할할 리스트
        batch_size: 배치 크기
        
    Yields:
        배치 리스트
        
    Example:
        >>> list(chunk_list([1,2,3,4,5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def chunk_text(text: str, batch_size: int) -> Generator[str, None, None]:
    """
    텍스트를 배치 크기로 분할 (줄 단위 유지)
    
    Args:
        text: 분할할 텍스트
        batch_size: 배치 크기 (글자 수)
        
    Yields:
        분할된 텍스트 청크
        
    Example:
        >>> list(chunk_text("line1\\nline2\\nline3", 10))
        ['line1\\nline2', 'line3']
    """
    lines = text.split('\n')
    current_chunk: List[str] = []
    current_size = 0
    
    for line in lines:
        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > batch_size and current_chunk:
            yield '\n'.join(current_chunk)
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size
    
    if current_chunk:
        yield '\n'.join(current_chunk)


def chunk_by_tokens(
    items: List[dict], 
    max_tokens: int, 
    token_estimator=None
) -> Generator[List[dict], None, None]:
    """
    토큰 수 기준으로 분할
    
    Args:
        items: 분할할 딕셔너리 리스트
        max_tokens: 최대 토큰 수
        token_estimator: 토큰 수 추정 함수 (기본: 문자수/4)
        
    Yields:
        토큰 제한 내의 배치 리스트
    """
    import json
    
    if token_estimator is None:
        token_estimator = lambda x: len(x) // 4
    
    current_batch: List[dict] = []
    current_tokens = 0
    
    for item in items:
        item_json = json.dumps(item, ensure_ascii=False)
        item_tokens = token_estimator(item_json)
        
        if current_tokens + item_tokens > max_tokens and current_batch:
            yield current_batch
            current_batch = [item]
            current_tokens = item_tokens
        else:
            current_batch.append(item)
            current_tokens += item_tokens
    
    if current_batch:
        yield current_batch
