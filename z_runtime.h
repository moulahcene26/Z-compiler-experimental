#ifndef Z_RUNTIME_H
#define Z_RUNTIME_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>

// --- Type Definitions ---

// Define string255 used in original templates - now using const char* mostly
typedef char string255[256];

// Node structure for tracking open files internally
struct _Noeud; // Forward declaration
typedef struct _Noeud * _Ptr_Noeud;


// --- Basic Built-in Function Declarations ---

int Mod( int a, int b);
int Min (int a, int b);
int Max (int a, int b);
int Exp (int a, int b);
int Aleanombre( int N );
char* Aleachaine ( int N ); // Caller must free result
int ZStringLength ( const char * Ch ); // Renamed from Longchaine
char* ZGetCharStr ( const char * Ch , int I ); // Renamed from Caract, caller must free

// --- Internal File Handling Declarations (use with caution) ---

// Node structure for tracking open files internally
struct _Noeud {
  FILE * Var_fich ;
  char * Nom_fich ; // Allocated copy
  int Sauv_pos;
  struct _Noeud *Suiv ;
};

// Global variable tracking open files (defined in z_runtime.c)
extern _Ptr_Noeud _Pile_ouverts;

// Internal functions to manage the file stack
_Ptr_Noeud _Ouvert ( char * Fp);
void _Empiler_ouvert ( char *Fp, FILE *Fl);
char * _Depiler_ouvert ( FILE *Fl); // Caller must free result


#endif // Z_RUNTIME_H
