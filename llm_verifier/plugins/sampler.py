"""
스마트 샘플러 플러그인

검증 대상 선별: 복잡한 케이스, 에지 케이스, 의심 케이스.
"""

from typing import List, Dict, Any

from .base import VerifierPlugin, PluginPhase
from . import register_plugin
from ..types import VerificationContext, CheckStatus


@register_plugin
class SamplerPlugin(VerifierPlugin):
    """스마트 샘플러 플러그인
    
    LLM 검증 효율성을 위해 중요한 샘플만 선별합니다.
    """
    
    name = "sampler"
    stage = "all"
    phase = PluginPhase.PRE_VERIFY
    priority = 20
    description = "검증 대상 샘플 선별"
    
    # 샘플링 설정
    max_samples = 10
    include_complex = True
    include_edge = True
    include_suspicious = True
    
    def process(self, context: VerificationContext) -> VerificationContext:
        """샘플 선별"""
        result = context.result
        
        if not isinstance(result, list) or len(result) == 0:
            return context
        
        samples = []
        
        # 1. 복잡한 케이스 (가장 긴 항목)
        if self.include_complex:
            complex_sample = self._select_complex(result)
            if complex_sample:
                samples.extend(complex_sample)
        
        # 2. 에지 케이스 (첫 번째, 마지막)
        if self.include_edge:
            edge_samples = self._select_edge(result)
            samples.extend(edge_samples)
        
        # 3. 의심 케이스 (정적 체크 실패)
        if self.include_suspicious:
            suspicious_samples = self._select_suspicious(context, result)
            samples.extend(suspicious_samples)
        
        # 중복 제거 및 최대 개수 제한
        seen_indices = set()
        unique_samples = []
        for sample in samples:
            idx = sample.get('_sample_index', id(sample))
            if idx not in seen_indices:
                seen_indices.add(idx)
                unique_samples.append(sample)
            if len(unique_samples) >= self.max_samples:
                break
        
        context.samples = unique_samples
        context.metadata['sample_count'] = len(unique_samples)
        context.metadata['total_count'] = len(result)
        
        return context
    
    def _select_complex(self, result: List[Dict]) -> List[Dict]:
        """복잡한 케이스 선택 (raw_content 길이 기준)"""
        samples = []
        
        # raw_content 또는 내용 길이로 정렬
        sorted_items = sorted(
            enumerate(result),
            key=lambda x: len(str(x[1].get('raw_content', x[1].get('content', '')))),
            reverse=True
        )
        
        # 상위 2개 선택
        for idx, item in sorted_items[:2]:
            sample = dict(item)
            sample['_sample_index'] = idx
            sample['_sample_reason'] = 'complex'
            samples.append(sample)
        
        return samples
    
    def _select_edge(self, result: List[Dict]) -> List[Dict]:
        """에지 케이스 선택 (첫 번째, 마지막)"""
        samples = []
        
        if len(result) > 0:
            first = dict(result[0])
            first['_sample_index'] = 0
            first['_sample_reason'] = 'edge_first'
            samples.append(first)
        
        if len(result) > 1:
            last = dict(result[-1])
            last['_sample_index'] = len(result) - 1
            last['_sample_reason'] = 'edge_last'
            samples.append(last)
        
        return samples
    
    def _select_suspicious(self, context: VerificationContext, result: List[Dict]) -> List[Dict]:
        """의심 케이스 선택 (정적 체크 실패 관련)"""
        samples = []
        
        # 정적 체크 실패가 있으면 관련 항목 선택
        failed_checks = [c for c in context.static_checks if c.status == CheckStatus.FAIL]
        
        if failed_checks:
            # 첫 번째 실패 체크의 영향을 받는 항목 선택
            for check in failed_checks[:2]:
                if 'line_range' in check.check_id and len(result) > 0:
                    # 라인 범위 문제 - 중간 항목 선택
                    mid_idx = len(result) // 2
                    mid_item = dict(result[mid_idx])
                    mid_item['_sample_index'] = mid_idx
                    mid_item['_sample_reason'] = f'suspicious_{check.check_id}'
                    samples.append(mid_item)
        
        return samples
