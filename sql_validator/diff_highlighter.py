"""
Diff 시각화 모듈

A/B Side-by-Side 뷰를 위한 diff 분석 및 하이라이트 정보를 제공합니다.
줄바꿈과 들여쓰기 차이는 무시하면서 실제 변경 부분만 하이라이트합니다.
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class DiffType(Enum):
    """Diff 유형"""
    EQUAL = "equal"      # 동일
    REPLACE = "replace"  # 변경
    DELETE = "delete"    # 삭제 (asis에만 있음)
    INSERT = "insert"    # 추가 (tobe에만 있음)


@dataclass
class DiffBlock:
    """하나의 diff 블록"""
    diff_type: DiffType
    asis_start: int      # asis에서의 시작 위치
    asis_end: int        # asis에서의 끝 위치
    tobe_start: int      # tobe에서의 시작 위치
    tobe_end: int        # tobe에서의 끝 위치
    asis_text: str       # asis 텍스트
    tobe_text: str       # tobe 텍스트


class DiffHighlighter:
    """A/B Side-by-Side Diff 분석기"""
    
    # 정규화에서 무시할 패턴들
    WHITESPACE_PATTERN = re.compile(r'\s+')
    
    def __init__(self, ignore_whitespace: bool = True, ignore_case: bool = False):
        """
        Args:
            ignore_whitespace: 공백 차이 무시 여부
            ignore_case: 대소문자 차이 무시 여부
        """
        self.ignore_whitespace = ignore_whitespace
        self.ignore_case = ignore_case
        logger.debug(f"DiffHighlighter: ignore_whitespace={ignore_whitespace}, ignore_case={ignore_case}")
    
    def normalize_for_compare(self, text: str) -> str:
        """
        비교를 위해 텍스트를 정규화합니다.
        원본 텍스트는 유지하고, 비교용 문자열만 생성합니다.
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정규화된 텍스트 (비교용)
        """
        normalized = text
        
        if self.ignore_whitespace:
            # 연속된 공백을 단일 공백으로 (줄바꿈 유지)
            normalized = self.WHITESPACE_PATTERN.sub(' ', normalized)
            normalized = normalized.strip()
        
        if self.ignore_case:
            normalized = normalized.lower()
        
        return normalized
    
    def compute_diff(self, asis: str, tobe: str) -> List[DiffBlock]:
        """
        asis와 tobe의 diff를 계산합니다.
        
        Args:
            asis: 원본 텍스트
            tobe: 변환된 텍스트
            
        Returns:
            DiffBlock 리스트
        """
        # 토큰 단위로 분할 (공백과 단어 구분)
        asis_tokens = self._tokenize(asis)
        tobe_tokens = self._tokenize(tobe)
        
        # 의미 있는 토큰만 추출 (공백 제외), 위치 정보 포함
        asis_meaningful = []  # [(token_index, token, normalized)]
        tobe_meaningful = []
        
        for i, token in enumerate(asis_tokens):
            normalized = self.normalize_for_compare(token)
            if normalized:  # 공백만 있는 토큰은 제외
                asis_meaningful.append((i, token, normalized))
        
        for i, token in enumerate(tobe_tokens):
            normalized = self.normalize_for_compare(token)
            if normalized:
                tobe_meaningful.append((i, token, normalized))
        
        # 정규화된 토큰만으로 비교
        asis_normalized = [m[2] for m in asis_meaningful]
        tobe_normalized = [m[2] for m in tobe_meaningful]
        
        matcher = SequenceMatcher(None, asis_normalized, tobe_normalized)
        
        blocks = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue  # 같은 부분은 스킵
            
            # asis 범위 계산: 첫 토큰부터 마지막 토큰까지 (사이 공백 포함)
            if i1 < i2:
                first_token_idx = asis_meaningful[i1][0]
                last_token_idx = asis_meaningful[i2 - 1][0]
                asis_start = sum(len(t) for t in asis_tokens[:first_token_idx])
                asis_end = sum(len(t) for t in asis_tokens[:last_token_idx + 1])
                asis_text = ''.join(asis_tokens[first_token_idx:last_token_idx + 1])
            else:
                asis_start = 0
                asis_end = 0
                asis_text = ''
            
            # tobe 범위 계산
            if j1 < j2:
                first_token_idx = tobe_meaningful[j1][0]
                last_token_idx = tobe_meaningful[j2 - 1][0]
                tobe_start = sum(len(t) for t in tobe_tokens[:first_token_idx])
                tobe_end = sum(len(t) for t in tobe_tokens[:last_token_idx + 1])
                tobe_text = ''.join(tobe_tokens[first_token_idx:last_token_idx + 1])
            else:
                tobe_start = 0
                tobe_end = 0
                tobe_text = ''
            
            if tag == 'replace':
                diff_type = DiffType.REPLACE
            elif tag == 'delete':
                diff_type = DiffType.DELETE
            elif tag == 'insert':
                diff_type = DiffType.INSERT
            else:
                continue
            
            blocks.append(DiffBlock(
                diff_type=diff_type,
                asis_start=asis_start,
                asis_end=asis_end,
                tobe_start=tobe_start,
                tobe_end=tobe_end,
                asis_text=asis_text,
                tobe_text=tobe_text
            ))
        
        logger.debug(f"Diff 계산 완료: {len(blocks)} 블록")
        return blocks
    
    def _tokenize(self, text: str) -> List[str]:
        """
        텍스트를 토큰으로 분할합니다.
        단어, 공백, 특수문자를 각각 별도 토큰으로 분리합니다.
        """
        tokens = []
        current = ""
        
        for char in text:
            if char.isalnum() or char == '_':
                current += char
            else:
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char)
        
        if current:
            tokens.append(current)
        
        return tokens
    
    def get_highlight_ranges(self, asis: str, tobe: str) -> Dict[str, List[Tuple[int, int, str]]]:
        """
        Tkinter Text 위젯용 하이라이트 범위를 반환합니다.
        
        Args:
            asis: 원본 텍스트
            tobe: 변환된 텍스트
            
        Returns:
            {
                'asis': [(start, end, tag), ...],
                'tobe': [(start, end, tag), ...]
            }
            tag는 'replace', 'delete', 'insert' 중 하나
        """
        blocks = self.compute_diff(asis, tobe)
        
        asis_highlights = []
        tobe_highlights = []
        
        for block in blocks:
            if block.diff_type == DiffType.EQUAL:
                continue
            
            tag = block.diff_type.value
            
            if block.diff_type in (DiffType.REPLACE, DiffType.DELETE):
                if block.asis_start < block.asis_end:
                    asis_highlights.append((block.asis_start, block.asis_end, tag))
            
            if block.diff_type in (DiffType.REPLACE, DiffType.INSERT):
                if block.tobe_start < block.tobe_end:
                    tobe_highlights.append((block.tobe_start, block.tobe_end, tag))
        
        return {
            'asis': asis_highlights,
            'tobe': tobe_highlights
        }
    
    def get_similarity_ratio(self, asis: str, tobe: str) -> float:
        """
        두 텍스트의 유사도를 계산합니다. (0.0 ~ 1.0)
        """
        asis_normalized = self.normalize_for_compare(asis)
        tobe_normalized = self.normalize_for_compare(tobe)
        
        matcher = SequenceMatcher(None, asis_normalized, tobe_normalized)
        return matcher.ratio()
    
    def get_change_summary(self, asis: str, tobe: str) -> Dict[str, Any]:
        """
        변경 사항 요약을 반환합니다.
        """
        blocks = self.compute_diff(asis, tobe)
        
        equal_count = sum(1 for b in blocks if b.diff_type == DiffType.EQUAL)
        replace_count = sum(1 for b in blocks if b.diff_type == DiffType.REPLACE)
        delete_count = sum(1 for b in blocks if b.diff_type == DiffType.DELETE)
        insert_count = sum(1 for b in blocks if b.diff_type == DiffType.INSERT)
        
        return {
            'total_blocks': len(blocks),
            'equal': equal_count,
            'replace': replace_count,
            'delete': delete_count,
            'insert': insert_count,
            'similarity': self.get_similarity_ratio(asis, tobe),
            'has_changes': replace_count > 0 or delete_count > 0 or insert_count > 0
        }
