#ifndef _SPAA010P_H_
#define _SPAA010P_H_

typedef struct {
	char                	rfrn_strt_date      	[      8 + 1];	//조회시작일자
	char                	rfrn_end_date       	[      8 + 1];	//조회종료일자
	char                	shrt_iscd           	[      6 + 1];	//단축종목코드
	char                	acnt_no             	[     20 + 1];	//계좌번호
	char                	prft_cntr_enty_code 	[      5 + 1];	//실적점코드
	char                	actn_rslt_code      	             ;	//조치결과코드
	char                	unfr_etra_type_code 	[      5 + 1];	//불공정적출유형코드
	char                	a_brnh_prce_yn      	             ;	//지점처리여부
	char                	it_isus_yn          	             ;	//IT종목여부
	char                	isus_shcd           	[     12 + 1];	//종목단축코드
	long                	a_nxt_sqno          	             ;	//다음일련번호
	char                	a_hdof_prce_yn      	             ;	//본사처리여부
} spaa010p_inrec1;

typedef struct {
	spaa010p_inrec1     	inrec1              	             ;	//InRec1
} spaa010p_in_t;

int spaa010p_in_stp[] =
{
	'w',	    12,	     1,	     sizeof(spaa010p_inrec1),
	's',	     8,	     9,	     8,
	's',	     8,	     9,	     8,
	's',	     6,	     7,	     6,
	's',	    20,	    21,	     20,
	's',	     5,	     6,	     5,
	'c',	     1,	     0,	     1,
	's',	     5,	     6,	     5,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	's',	    12,	    13,	     12,
	'l',	    11,	     0,	     10,
	'c',	     1,	     0,	     1,
	'0',	     0,	     0,	     0
};


typedef struct {
	long                	a_cont              	             ;	//건수
} spaa010p_outrec3;

typedef struct {
	long                	a_nxt_sqno          	             ;	//다음일련번호
} spaa010p_outrec2;

typedef struct {
	char                	infm_date           	[      8 + 1];	//통보일자
	char                	prft_cntr_enty_name 	[     60 + 1];	//실적점명
	char                	mngg_brnh_enty_name 	[     90 + 1];	//관리점명
	long                	acnt_id             	             ;	//계좌ID
	char                	acnt_no             	[     20 + 1];	//계좌번호
	char                	crfl_acnt_yn        	             ;	//요주의계좌여부
	char                	otcp_pmnt_yn        	             ;	//타사납입여부
	char                	acnt_name           	[     90 + 1];	//계좌명
	char                	rrno_cryp           	[     64 + 1];	//주민등록번호암호문
	char                	empy_name           	[     30 + 1];	//사원명
	char                	acnt_mngr_empy_no   	[     16 + 1];	//계좌관리자사원번호
	char                	unfr_etra_type_code 	[      5 + 1];	//불공정적출유형코드
	char                	actn_dmnd_acnt_etra_type_name	[     60 + 1];	//조치요구계좌적출유형명
	char                	ttdd_rpt_sect_code  	             ;	//당일반복구분코드
	char                	ofrg_sect_name      	[     25 + 1];	//모집구분명
	char                	infm_yn             	             ;	//통보여부
	long                	past_etra_cont      	             ;	//과거적출건수
	long                	rslt_cont           	             ;	//결과건수
	char                	strt_date           	[      8 + 1];	//시작일자
	char                	end_date            	[      8 + 1];	//종료일자
	char                	mngg_brnh_enty_code 	[      5 + 1];	//관리점코드
	char                	prft_cntr_enty_code 	[      5 + 1];	//실적점코드
	char                	unfr_detl_etra_type_code	[      3 + 1];	//불공정세부적출유형코드
	char                	iscd                	[     12 + 1];	//종목코드
	char                	isus_name           	[    150 + 1];	//종목명
	char                	unus_isus_yn        	             ;	//특이종목여부
	long                	dm_cont             	             ;	//DM건수
	char                	actn_rslt_code      	             ;	//조치결과코드
	char                	mngn_perd_code      	             ;	//관리기간코드
	char                	last_prce_date      	[      8 + 1];	//최종처리일자
	char                	frst_prce_date      	[      8 + 1];	//최초처리일자
	char                	actn_date           	[      8 + 1];	//조치일자
	long                	ofln_ordr_cont      	             ;	//오프라인주문건수
	long                	ofln_ctra_amnt      	             ;	//오프라인체결금액
	long                	un_actn_acml_cont   	             ;	//미조치누적건수
	double              	pair_rate           	             ;	//PAIR비율
	char                	past_actn_date      	[      8 + 1];	//과거조치일자
	char                	past_actn_step_code 	             ;	//과거조치단계코드
	char                	trst_prdt_type_name 	[     60 + 1];	//신탁상품유형명
	long                	past_actn_acnt_id   	             ;	//과거조치계좌ID
	char                	past_brnh_actn_step_code	             ;	//과거지점조치단계코드
	char                	etra_actn_ctnt      	[     30 + 1];	//적출조치내용
	int                 	grop_sqno           	             ;	//그룹일련번호
	long                	past_prvn_actn_dmnd_cont	             ;	//과거예방조치요구건수
	char                	prce_rjct_resn_ctnt 	[    150 + 1];	//처리거부사유내용
	char                	plrl_stdg_agnt_yn   	             ;	//복수상임대리인여부
	char                	rprg_rgsn_yn        	             ;	//보고등록여부
	int                 	etra_cnt            	             ;	//적출횟수
	char                	etc_prce_date       	[      8 + 1];	//기타처리일자
	char                	adrv_appn_sect_code 	             ;	//감리지정구분코드
	char                	etra_date           	[      8 + 1];	//적출일자
	char                	acnt_hold_yn        	             ;	//계좌보유여부
	char                	tmpr_acnt_no        	[     20 + 1];	//임시계좌번호
	long                	a_seq_no            	             ;	//일련번호
	char                	trdg_date           	[      8 + 1];	//거래일자
	char                	fkrq_stnr_sect_code 	             ;	//허수기준구분코드
	char                	smpr_yn             	             ;	//동일인여부
	char                	otcp_acnt_opng_date 	[      8 + 1];	//타사계좌개설일자
	char                	acnt_actn_date      	[      8 + 1];	//계좌조치일자
	char                	ctxt_ctnt           	[     50 + 1];	//등록사유내용
	char                	mntn_yn             	             ;	//모니터링여부
	char                	clpr_cncr_focs_dlng_yn	             ;	//종가관여집중매매여부
	char                	a_odnr_mntn_trpn_yn 	             ;	//상시모니터링대상자여부
} spaa010p_outrec1;

typedef struct {
	int                 	outrec1_count       	             ;	//OutRec1_count
	spaa010p_outrec1    	outrec1             	[     30];	//OutRec1
	spaa010p_outrec2    	outrec2             	             ;	//OutRec2
	spaa010p_outrec3    	outrec3             	             ;	//OutRec3
} spaa010p_out_t;

int spaa010p_out_stp[] =
{
	'g',	     4,	     0,	     0,
	'w',	    63,	    30,	     sizeof(spaa010p_outrec1),
	's',	     8,	     9,	     8,
	's',	    60,	    61,	     60,
	's',	    90,	    91,	     90,
	'l',	    19,	     0,	     19,
	's',	    20,	    21,	     20,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	's',	    90,	    91,	     90,
	's',	    64,	    65,	     64,
	's',	    30,	    31,	     30,
	's',	    16,	    17,	     16,
	's',	     5,	     6,	     5,
	's',	    60,	    61,	     60,
	'c',	     1,	     0,	     1,
	's',	    25,	    26,	     25,
	'c',	     1,	     0,	     1,
	'l',	    11,	     0,	     10,
	'l',	    11,	     0,	     10,
	's',	     8,	     9,	     8,
	's',	     8,	     9,	     8,
	's',	     5,	     6,	     5,
	's',	     5,	     6,	     5,
	's',	     3,	     4,	     3,
	's',	    12,	    13,	     12,
	's',	   150,	   151,	     150,
	'c',	     1,	     0,	     1,
	'l',	    11,	     0,	     10,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	's',	     8,	     9,	     8,
	's',	     8,	     9,	     8,
	's',	     8,	     9,	     8,
	'l',	    11,	     0,	     10,
	'l',	    16,	     0,	     15,
	'l',	    16,	     0,	     15,
	'd',	     7,	     2,	     7,
	's',	     8,	     9,	     8,
	'c',	     1,	     0,	     1,
	's',	    60,	    61,	     60,
	'l',	    19,	     0,	     19,
	'c',	     1,	     0,	     1,
	's',	    30,	    31,	     30,
	'i',	     6,	     0,	     5,
	'l',	    11,	     0,	     10,
	's',	   150,	   151,	     150,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	'i',	     6,	     0,	     5,
	's',	     8,	     9,	     8,
	'c',	     1,	     0,	     1,
	's',	     8,	     9,	     8,
	'c',	     1,	     0,	     1,
	's',	    20,	    21,	     20,
	'l',	    11,	     0,	     10,
	's',	     8,	     9,	     8,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	's',	     8,	     9,	     8,
	's',	     8,	     9,	     8,
	's',	    50,	    51,	     50,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	'c',	     1,	     0,	     1,
	'w',	     1,	     1,	     sizeof(spaa010p_outrec2),
	'l',	    11,	     0,	     10,
	'w',	     1,	     1,	     sizeof(spaa010p_outrec3),
	'l',	    11,	     0,	     10,
	'0',	     0,	     0,	     0
};


int spaa010p_in_sz	= sizeof(spaa010p_in_t);
int spaa010p_out_sz	= sizeof(spaa010p_out_t);

#endif //_SPAA010P_H_
/*
 *=============================================================================
 *              E N D  of the F I L E ( spaa010p.h )
 *=============================================================================
*/