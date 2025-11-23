#ifndef SAMPLE_H
#define SAMPLE_H

#define VERSION "1.0.0"

struct Config {
    char db_url[100];
    int timeout;
};

void db_connect();
void process_employee(int emp_id);

#endif
