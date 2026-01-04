#ifndef COMMON_H
#define COMMON_H

#define MAX_SIZE 100
#define VERSION "1.0"

typedef struct {
    int id;
    char name[50];
} CommonStruct;

int common_init();

#endif
