"""
LangGraph 모니터링 테스트 스크립트

마이그레이션 파이프라인 실행을 모니터링하고 결과를 시각화합니다.

사용법:
    python -m infra.agents.langchain.monitoring.run_monitored
"""

import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)


def run_with_monitoring(source_code: str, filename: str = "test.pc"):
    """
    모니터링과 함께 마이그레이션 실행
    
    Args:
        source_code: Pro*C 소스 코드
        filename: 파일명
        
    Returns:
        tuple: (result, monitor)
    """
    from .trace_wrapper import create_monitored_graph, TracingConfig
    from ..state import create_migration_state
    from ..config import LLMConfig
    
    # LLM 초기화
    try:
        from langchain_openai import ChatOpenAI
        llm_config = LLMConfig.from_env()
        llm = ChatOpenAI(**llm_config.to_dict())
        logger.info(f"LLM 로드: {llm_config.model}")
    except Exception as e:
        logger.warning(f"LLM 로드 실패, Mock 모드: {e}")
        llm = None
    
    # 모니터링된 그래프 생성
    graph, monitor = create_monitored_graph(llm)
    
    # 초기 상태
    initial_state = create_migration_state(source_code, filename)
    
    # 실행
    logger.info("="*50)
    logger.info(f"🚀 파이프라인 시작: {filename}")
    logger.info("="*50)
    
    try:
        result = graph.invoke(initial_state)
    except Exception as e:
        logger.error(f"파이프라인 에러: {e}")
        result = {"error": str(e)}
    
    return result, monitor


def main():
    """메인 함수"""
    
    # 테스트 Pro*C 코드
    test_code = '''
EXEC SQL INCLUDE sqlca;

struct order_info {
    int order_id;
    char customer_name[50];
    double total_amount;
};

int process_order(int order_id) {
    EXEC SQL BEGIN DECLARE SECTION;
        int v_count;
        struct order_info order;
    EXEC SQL END DECLARE SECTION;
    
    EXEC SQL SELECT COUNT(*) INTO :v_count 
             FROM orders 
             WHERE id = :order_id;
    
    if (v_count > 0) {
        EXEC SQL SELECT order_id, customer_name, total_amount
                 INTO :order
                 FROM orders
                 WHERE id = :order_id;
    }
    
    return v_count;
}

int update_order_status(int order_id, char* new_status) {
    EXEC SQL BEGIN DECLARE SECTION;
        char v_status[20];
    EXEC SQL END DECLARE SECTION;
    
    strcpy(v_status, new_status);
    
    EXEC SQL UPDATE orders
             SET status = :v_status
             WHERE id = :order_id;
    
    EXEC SQL COMMIT;
    
    return 0;
}
'''
    
    # 실행
    result, monitor = run_with_monitoring(test_code, "order.pc")
    
    # 결과 요약
    print("\n")
    monitor.print_summary()
    
    # Mermaid 다이어그램
    print("\n📊 Mermaid Diagram:")
    print("```mermaid")
    print(monitor.export_mermaid())
    print("```")
    
    # State 결과 요약
    print("\n📝 결과 요약:")
    if "error" in result:
        print(f"  ❌ 에러: {result['error']}")
    else:
        print(f"  ✓ 검증 에러: {len(result.get('validation_errors', []))}개")
        print(f"  ✓ Draft XML: {len(result.get('draft_xmls', []))}개")
        print(f"  ✓ Refined SQL: {len(result.get('refined_sqls', []))}개")
        print(f"  ✓ Java 코드: {len(result.get('java_code', ''))} chars")
        print(f"  ✓ Mapper XML: {len(result.get('mapper_xml', ''))} chars")
    
    # HTML 리포트 저장
    report_path = Path("./pipeline_report.html")
    monitor.export_html_report(str(report_path))
    print(f"\n📄 HTML 리포트 저장됨: {report_path.absolute()}")
    
    # JSON 로그 저장
    json_path = Path("./pipeline_trace.json")
    monitor.export_json(str(json_path))
    print(f"📄 JSON 트레이스 저장됨: {json_path.absolute()}")


if __name__ == "__main__":
    main()
