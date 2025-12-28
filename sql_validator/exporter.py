"""
데이터 내보내기 모듈

검증 결과를 YAML 파일로 내보내는 기능을 제공합니다.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from loguru import logger


def export_items(
    items: List[Dict[str, Any]],
    statuses: Dict[int, str],
    output_path: str,
    status_filter: str,
    include_analysis: bool = False,
    analysis_results: Optional[List] = None
) -> int:
    """
    필터링된 SQL 항목을 YAML로 내보냅니다.
    
    Args:
        items: SQL 항목 리스트
        statuses: {index: 'approved' | 'rejected'} 상태 딕셔너리
        output_path: 출력 파일 경로
        status_filter: 'approved', 'rejected', 'all'
        include_analysis: 분석 결과 포함 여부
        analysis_results: 분석 결과 리스트 (index별)
        
    Returns:
        내보낸 항목 수
    """
    filtered_items = []
    
    for i, item in enumerate(items):
        item_status = statuses.get(i)
        
        # 상태 필터링
        if status_filter == 'approved' and item_status != 'approved':
            continue
        elif status_filter == 'rejected' and item_status != 'rejected':
            continue
        
        export_item = {
            'sql': item.get('sql', ''),
            'parsed_sql': item.get('parsed_sql', '')
        }
        
        # 메타데이터 포함
        if 'metadata' in item and item['metadata']:
            for k, v in item['metadata'].items():
                export_item[k] = v
        
        # 검증 상태 포함
        if item_status:
            export_item['validation_status'] = item_status
        
        # 코멘트 포함
        if 'comment' in item and item['comment']:
            export_item['comment'] = item['comment']
        
        # 분석 결과 포함
        if include_analysis and analysis_results and i < len(analysis_results):
            result = analysis_results[i]
            if result:
                export_item['analysis'] = {
                    'pass_count': result.pass_count,
                    'fail_count': result.fail_count,
                    'warning_count': result.warning_count,
                    'passed': result.passed
                }
        
        filtered_items.append(export_item)
    
    if not filtered_items:
        logger.warning("내보낼 항목이 없습니다")
        return 0
    
    # YAML 파일 작성
    try:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, 'w', encoding='utf-8') as f:
            yaml.dump(
                filtered_items, 
                f, 
                allow_unicode=True, 
                default_flow_style=False,
                sort_keys=False
            )
        
        logger.info(f"{len(filtered_items)}개 항목을 {output_path}에 내보냄")
        return len(filtered_items)
        
    except Exception as e:
        logger.error(f"내보내기 실패: {e}")
        raise


def export_approved(
    items: List[Dict[str, Any]],
    statuses: Dict[int, str],
    output_path: str
) -> int:
    """승인된 항목만 내보내기"""
    return export_items(items, statuses, output_path, 'approved')


def export_rejected(
    items: List[Dict[str, Any]],
    statuses: Dict[int, str],
    output_path: str
) -> int:
    """거부된 항목만 내보내기"""
    return export_items(items, statuses, output_path, 'rejected')


def export_all_with_status(
    items: List[Dict[str, Any]],
    statuses: Dict[int, str],
    output_path: str,
    analysis_results: Optional[List] = None
) -> int:
    """모든 항목을 검증 결과와 함께 내보내기"""
    return export_items(
        items, statuses, output_path, 'all',
        include_analysis=True, analysis_results=analysis_results
    )


def generate_export_filename(prefix: str = 'export', extension: str = 'yaml') -> str:
    """타임스탬프가 포함된 파일명 생성"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{prefix}_{timestamp}.{extension}"
