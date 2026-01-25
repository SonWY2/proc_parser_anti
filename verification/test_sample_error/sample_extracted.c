#include <stdio.h>
#include <sqlca.h>

#define MAX_ID_LEN 10
#define SUCCESS_CODE 0

// Global variables (from declare section)
char in_cust_id[MAX_ID_LEN];
char out_cust_name[51];
short ind_cust_name;

int get_customer_info(char *cust_id) {
    int result = SUCCESS_CODE;
    
    // Copy input
    strncpy(in_cust_id, cust_id, MAX_ID_LEN);

    /* Get customer name */
    /* SQL: sql_001 */

    if (sqlca.sqlcode != 0) {
        return -1;
    }

    /* Update last login (Intentional error: SQL not extracted) */
    EXEC SQL UPDATE CUSTOMER
             SET LAST_LOGIN = SYSDATE
             WHERE CUST_ID = :in_cust_id;

    /* SQL: sql_003 */

    return result;
}
