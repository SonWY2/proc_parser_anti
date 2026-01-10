/*******************************************************************************
 * 파일명: enterprise_complex_sql.pc
 * 설명: 엔터프라이즈급 복잡도의 Pro*C SQL 예제
 *       - 금융 거래 정산 및 리스크 분석 시스템
 *       - 재귀 CTE, MODEL 절, PIVOT, 계층 쿼리
 *       - 정규식, 복잡한 상관 서브쿼리, 분석 함수
 * 작성일: 2026-01-09
 ******************************************************************************/
/* TODO: 이거 나중에 정리해야 함 */
// 이 주석은 C++ 스타일임
#include <stdio.h>
#include <stdlib.h>  /* 표준 라이브러리 - 필요한가? */
#include <string.h>
    /* 여기 뭔가 추가해야 할 것 같은데... */

EXEC SQL INCLUDE sqlca;  // sqlca 포함 - 에러 처리용
    EXEC SQL INCLUDE oraca; /* oraca도 필요함 */

/* ========= 변수 선언부 시작 =========== */
    /* 들여쓰기가 이상하지만 일단 둠 */
/* @SQL_EXTRACTED: sql_001 | TYPE: BEGIN */
    /* 입력 파라미터 */  // 이중 주석
    char p_base_date[11];  /* 기준일자 YYYY-MM-DD 형식 */
        char p_from_branch[10]; // 시작 지점
    char p_to_branch[10];/* 공백없이 주석 */
char p_currency[4];  /*
        여러 줄
        주석도 
        가능 */
    int p_risk_threshold;  // threshold값
    double p_variance_limit;  /* variance 한계치 - 2.5 권장 */ // <- 이런식으로
    
    /* 결과 구조체 - 아래 정의 */ // 또 이중주석
    typedef struct {
        char settlement_id[30];  /* 정산 ID */
            char entity_path[500];  // 엔티티 경로 - 최대 500자
        int hierarchy_level; /* 계층 레벨 */
        double original_amount;/* 원래금액 */
        double converted_amount;  // 변환된 금액
            double risk_score;
        double anomaly_index;  /* 이상치 인덱스 */ // 뭔가 중요함
        char alert_code[20]; /* 알림코드 - ALERT_CRITICAL 등 */
    } result_t;  /* result 타입 정의 완료 */
    
    result_t result;  // 결과 변수
    int fetch_count;  /* 페치 카운트 - 나중에 사용 */
    
/* @SQL_EXTRACTED: sql_002 | TYPE: END */
    /* ========= 변수 선언부 끝 =========== */

/* 함수 프로토타입 선언 */ // forward declarations
void init_parameters(void);  /* 파라미터 초기화 */
int connect_database(void);  // DB 연결
    void declare_main_cursor(void); /* 커서 선언 - 복잡한 SQL */
int process_results(void);  /* 결과 처리 */ // fetch loop
void cleanup_and_exit(int status);  // 정리 및 종료

/*==============================================================================
 * 함수: init_parameters
 * 설명: 입력 파라미터 초기화
 *==============================================================================*/
    /* 파라미터 초기화 함수 */
void init_parameters(void)  // 파라미터 설정
{  /* 함수 시작 */
    strcpy(p_base_date, "2025-12-31");  /* 기준일 설정 */
    strcpy(p_from_branch, "BR001");  // from branch
        strcpy(p_to_branch, "BR999");  /* to branch - 왜 999까지? */
    strcpy(p_currency, "KRW");  // 한국 원화
    p_risk_threshold = 75;  /* 리스크 임계값 */
    p_variance_limit = 2.5;  // variance limit
    
    printf("파라미터 초기화 완료\n");  /* 로그 출력 */
}  /* init_parameters 끝 */

/*==============================================================================
 * 함수: connect_database
 * 설명: 데이터베이스 연결
 *==============================================================================*/
/* DB 연결 함수 */ // returns 0 on success
int connect_database(void)
{  // 함수 시작
    /* @SQL_EXTRACTED: sql_003 | TYPE: CONNECT */
    
    if (sqlca.sqlcode != 0) {  /* 연결 실패 체크 */
        printf("DB 연결 실패: %s\n", sqlca.sqlerrm.sqlerrmc);  // 에러 출력
return -1;  /* 실패 */
    }
    
    printf("DB 연결 성공\n");  /* 성공 로그 */
    return 0;  // 성공
}  /* connect_database 끝 */

/*==============================================================================
 * 함수: declare_main_cursor
 * 설명: 메인 분석용 커서 선언 (복잡한 CTE 기반 SQL)
 *==============================================================================*/
    /* 커서 선언 함수 - 가장 복잡한 부분 */
void declare_main_cursor(void)  // cursor declaration
{
    /*==========================================================================
     * 복잡한 엔터프라이즈급 SQL 시작 (200줄 이상)
     * - 금융 거래 정산, 리스크 분석, 이상 탐지
     *==========================================================================*/
    /* 여기서부터 진짜 SQL 시작 */
    // CTE 사용할 예정
    
    /* @SQL_EXTRACTED: sql_004 | TYPE: DECLARE | IN: :p_currency, :p_currency, :p_currency, :p_base_date, :p_base_date, ... (+16) */
    
    printf("커서 선언 완료\n");  /* 로그 */
}  /* declare_main_cursor 끝 */

/*==============================================================================
 * 함수: process_results
 * 설명: 커서를 열고 결과를 처리
 *==============================================================================*/
/* 결과 처리 함수 */ // main processing loop
int process_results(void)
{  /* 함수 시작 */
    /*==========================================================================
     * 커서 실행 및 결과 처리
     *==========================================================================*/
     /* 커서 처리 시작 */ // OPEN -> FETCH -> CLOSE
    
    /* @SQL_EXTRACTED: sql_005 | TYPE: OPEN */
    
if (sqlca.sqlcode != 0) {  /* 오픈 실패 */
        printf("커서 오픈 실패: %s\n", sqlca.sqlerrm.sqlerrmc);
    return -1;
    }
    
    fetch_count = 0;  // 카운트 초기화
    while (1) {  /* 무한 루프 */
/* @SQL_EXTRACTED: sql_006 | TYPE: FETCH | OUT: :result.settlement_id, :result.entity_path, :result.hierarchy_level, :result.original_amount, :result.converted_amount, ... (+3) */
        
        if (sqlca.sqlcode == 1403) break;  /* 데이터 없음 */
if (sqlca.sqlcode != 0) {
            printf("오류: %s\n", sqlca.sqlerrm.sqlerrmc);  // 에러 출력
    break;
        }
        
        fetch_count++;  /* 카운트 증가 */
        
if (result.risk_score >= p_risk_threshold) {  // 임계값 초과시
            printf("[%s] 리스크 점수: %.2f, 알림: %s\n",
   result.settlement_id,
                   result.risk_score,
result.alert_code);
        }
    }  /* while 끝 */
    
/* @SQL_EXTRACTED: sql_007 | TYPE: CLOSE */
    
    printf("\n총 %d건 처리 완료\n", fetch_count);  // 결과 출력
    
return fetch_count;  /* 처리 건수 반환 */
}  /* process_results 끝 */

/*==============================================================================
 * 함수: cleanup_and_exit
 * 설명: 리소스 정리 및 종료
 *==============================================================================*/
    /* 정리 함수 */
void cleanup_and_exit(int status)  // cleanup function
{  /* 함수 시작 */
    if (status == 0) {  /* 성공 시 */
/* @SQL_EXTRACTED: sql_008 | TYPE: COMMIT */
        printf("정상 종료\n");  // 로그
    } else {  /* 실패 시 */
        /* @SQL_EXTRACTED: sql_009 | TYPE: ROLLBACK */
printf("비정상 종료 (status=%d)\n", status);  /* 에러 로그 */
    }
}  /* cleanup_and_exit 끝 */

/*==============================================================================
 * 함수: validate_input_params
 * 설명: 입력 파라미터 유효성 검증
 *==============================================================================*/
/* 파라미터 검증 함수 */ // validation
int validate_input_params(void)
{  // 함수 시작
    int is_valid = 1;  /* 유효성 플래그 */
    
    // 날짜 형식 체크
    if (strlen(p_base_date) != 10) {  /* YYYY-MM-DD */
        printf("기준일자 형식 오류: %s\n", p_base_date);
is_valid = 0;
    }
    
    /* 지점 코드 체크 */
    if (strcmp(p_from_branch, p_to_branch) > 0) {  // from > to
printf("지점 범위 오류: %s ~ %s\n", p_from_branch, p_to_branch);
        is_valid = 0;
    }
    
    // 통화 코드 체크
if (strlen(p_currency) != 3) {  /* 3자리 */
        printf("통화 코드 오류: %s\n", p_currency);
    is_valid = 0;
    }
    
    /* 리스크 임계값 체크 */
    if (p_risk_threshold < 0 || p_risk_threshold > 100) {
printf("리스크 임계값 범위 오류: %d\n", p_risk_threshold);  // 0~100
        is_valid = 0;
    }
    
    // variance limit 체크
    if (p_variance_limit <= 0) {  /* 양수여야 함 */
        printf("분산 한계 오류: %.2f\n", p_variance_limit);
is_valid = 0;
    }
    
    return is_valid;  /* 1=valid, 0=invalid */
}  /* validate_input_params 끝 */

/*==============================================================================
 * 함수: print_summary_report
 * 설명: 처리 결과 요약 리포트 출력
 *==============================================================================*/
    /* 요약 리포트 출력 */
void print_summary_report(int total_count)  // summary
{  /* 함수 시작 */
    printf("\n========================================\n");  /* 구분선 */
    printf("처리 결과 요약\n");  // 헤더
printf("========================================\n");
    printf("기준일자: %s\n", p_base_date);  /* 기준일 */
    printf("지점 범위: %s ~ %s\n", p_from_branch, p_to_branch);  // 지점
printf("목표 통화: %s\n", p_currency);
    printf("리스크 임계값: %d\n", p_risk_threshold);  /* threshold */
    printf("분산 한계: %.2f\n", p_variance_limit);  // variance
printf("----------------------------------------\n");  /* 구분 */
    printf("총 처리 건수: %d\n", total_count);
printf("========================================\n");  /* 끝 */
}  /* print_summary_report 끝 */

/*==============================================================================
 * 함수: log_execution_start
 * 설명: 실행 시작 로그 기록
 *==============================================================================*/
/* 실행 시작 로그 */ // for audit
void log_execution_start(void)
{
    /* @SQL_EXTRACTED: sql_010 | TYPE: BEGIN */
        char log_timestamp[30];
    char log_user[50];
    /* @SQL_EXTRACTED: sql_011 | TYPE: END */
    
    /* 현재 시간 및 사용자 조회 */
/* @SQL_EXTRACTED: sql_012 | TYPE: SELECT | OUT: :log_timestamp, :log_user */
    
    printf("[%s] 사용자 %s 실행 시작\n", log_timestamp, log_user);  /* 로그 출력 */
    
    // 실행 로그 테이블에 기록
    /* @SQL_EXTRACTED: sql_013 | TYPE: INSERT | IN: :log_user, :p_base_date, :p_from_branch, :p_to_branch */
    
    /* 에러 무시 - 로그 테이블 없을 수 있음 */
}  /* log_execution_start 끝 */

/*==============================================================================
 * 함수: main
 * 설명: 메인 함수 - 전체 흐름 제어
 *==============================================================================*/
int main(void)  // 메인 함수 시작
{  /* 괄호 */
    int result_count;  /* 결과 건수 */
    
    printf("=== 엔터프라이즈 리스크 분석 시스템 ===\n");  // 타이틀
    
    /* 1. 파라미터 초기화 */
    init_parameters();  // 초기화 호출
    
    // 2. 파라미터 검증
    if (!validate_input_params()) {  /* 검증 실패 */
        printf("파라미터 검증 실패. 종료합니다.\n");
return -1;
    }
    
    /* 3. DB 연결 */
    if (connect_database() != 0) {  // 연결 실패
printf("DB 연결 실패. 종료합니다.\n");
        return -1;
    }
    
    // 4. 실행 시작 로그
    log_execution_start();  /* 로그 기록 */
    
    /* 5. 커서 선언 */
declare_main_cursor();  // 복잡한 SQL 커서
    
    // 6. 결과 처리
    result_count = process_results();  /* 메인 처리 */
    
    if (result_count < 0) {  /* 처리 실패 */
        cleanup_and_exit(-1);
return -1;  // 에러 종료
    }
    
    /* 7. 요약 리포트 */
    print_summary_report(result_count);  // 리포트 출력
    
    // 8. 정리 및 종료
cleanup_and_exit(0);  /* 정상 종료 */
    
return 0;  // 정상 종료
}  /* main 함수 끝 */
