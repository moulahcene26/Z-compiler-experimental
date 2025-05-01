#include "z_runtime.h"

// Standard Library Includes
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>
#include <math.h> // For Exp potentially needing pow or handling large numbers


// --- Basic Functions ---

int Mod( int a, int b) {
    if (b == 0) {
        // Handle division by zero error - maybe return 0 or specific error code?
        fprintf(stderr, "Error: Modulo by zero.\n");
        return 0; // Or exit?
    }
    return ( a % b );
}

int Min (int a, int b) {
    return (a < b) ? a : b;
}

int Max (int a, int b) {
    return (a > b) ? a : b;
}

// Simple integer exponentiation - prone to overflow
int Exp (int a, int b) {
    int i;
    long long Ex = 1; // Use long long for intermediate calculation

    if (b < 0) {
        // Handle negative exponent? Z language definition needed.
        // Return 0 for integer exponentiation.
        return 0;
    }
    if (b == 0) {
        return 1;
    }
    if (a == 0) {
        return 0;
    }

    for (i = 1; i <= b; i++) {
        Ex = Ex * a;
        // Basic overflow check (not foolproof)
        if (Ex > 2147483647 || Ex < -2147483648) {
             fprintf(stderr, "Warning: Integer overflow in Exp(%d, %d).\n", a, b);
             // Return max/min int or a specific error indicator?
             return (a > 0) ? 2147483647 : -2147483648;
        }
    }
    return (int)Ex; // Cast back to int
}

// Needs srand(time(NULL)) called once externally (e.g., in main)
int Aleanombre( int N ) {
    if (N <= 0) {
        // Return 0 or error for non-positive N?
        return 0;
    }
    return ( rand() % N );
}

// Needs srand(time(NULL)) called once externally (e.g., in main)
// Caller must free the returned string
char *Aleachaine ( int N ) {
    int k;
    if (N <= 0) {
        // Allow empty string? Or return NULL? Let's return "" for N=0.
        if (N == 0) {
            char *emptyStr = malloc(1);
            if(emptyStr) emptyStr[0] = '\0';
            return emptyStr;
        } else {
             return NULL; // Error for N < 0
        }
    }

    char *Chaine = malloc(N + 1); // +1 for null terminator
    if (!Chaine) {
        perror("malloc failed in Aleachaine");
        return NULL; // Check malloc success
    }

    // Using static avoids recreating these on every call
    static const char Chr1[] = "abcdefghijklmnopqrstuvwxyz";
    static const char Chr2[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const int len1 = sizeof(Chr1) - 1; // 26
    const int len2 = sizeof(Chr2) - 1; // 26

    for (k = 0; k < N; k++) {
        switch ( rand() % 2 ) {
            case 0 : Chaine[k] = Chr1[rand() % len1]; break;
            case 1 : Chaine[k] = Chr2[rand() % len2]; break;
        }
    }
    Chaine[k] = '\0'; // Null terminate

    return Chaine;
}

// Renamed from Longchaine for clarity, takes const char*
int ZStringLength ( const char * Ch ) {
    // Ensure Ch is not NULL before calling strlen
    return (Ch ? strlen(Ch) : 0);
}


// Renamed from Caract. Returns a new string with the char at 1-based index.
// Caller must free the returned string.
char *ZGetCharStr ( const char * Ch , int I ) {
    if (!Ch || I <= 0) {
        return NULL; // Basic validation
    }
    // Use ZStringLength to handle potential NULL inside? No, strlen is fine if Ch checked.
    int len = strlen(Ch);
    if (I > len) {
        return NULL; // Index out of bounds (1-based)
    }

    char *s = malloc(2); // Space for char + null terminator
    if (!s) {
        perror("malloc failed in ZGetCharStr");
        return NULL; // Check malloc success
    }
    s[0] = Ch[I - 1]; // Z uses 1-based index, C uses 0-based
    s[1] = '\0';
    return s;
}


// --- File Handling Stack ---

// Global head of the linked list of open files
_Ptr_Noeud _Pile_ouverts = NULL;

// Test if a file (by path) is already tracked in our list
_Ptr_Noeud _Ouvert ( char * Fp) {
    if (!Fp) return NULL; // Handle NULL filename

    _Ptr_Noeud P = _Pile_ouverts;
    while (P != NULL) {
        // Ensure P->Nom_fich is also not NULL before comparing
        if (P->Nom_fich && strcmp(P->Nom_fich, Fp) == 0) {
            return P; // Found
        }
        P = P->Suiv;
    }
    return NULL; // Not found
}

// Add a file (path and handle) to the tracking list
void _Empiler_ouvert ( char *Fp, FILE *Fl) {
    if (!Fp || !Fl) return; // Need valid path and file handle

    _Ptr_Noeud P = (_Ptr_Noeud) malloc(sizeof(struct _Noeud));
    if (!P) {
        perror("malloc failed in _Empiler_ouvert");
        // Maybe close Fl here if we can't track it? Or signal error?
        return;
    }

    P->Nom_fich = strdup(Fp); // Allocate a persistent copy of the filename
    if (!P->Nom_fich) {
        free(P);
        perror("strdup failed in _Empiler_ouvert");
        return;
    }

    P->Var_fich = Fl;
    P->Sauv_pos = ftell(Fl); // Store initial position (or 0?)
    if (P->Sauv_pos < 0) P->Sauv_pos = 0; // Reset if ftell fails

    // Link to head of list
    P->Suiv = _Pile_ouverts;
    _Pile_ouverts = P;
}

// Remove a file (specified by handle) from the tracking list
// Returns an allocated copy of the filename, caller must free. Returns NULL on failure.
char * _Depiler_ouvert ( FILE *Fl) {
    if (_Pile_ouverts == NULL || !Fl) {
        return NULL; // Empty list or invalid handle
    }

    _Ptr_Noeud P = _Pile_ouverts;
    _Ptr_Noeud Prec = NULL;

    // Find the node with the matching file handle
    while (P != NULL && P->Var_fich != Fl ) {
        Prec = P;
        P = P->Suiv;
    }

    if (P == NULL) {
        // File handle not found in our tracking list
        return NULL;
    }

    // Found the node P to remove
    char * Fp_copy = strdup(P->Nom_fich); // Make copy of name before freeing node

    // Unlink the node
    if (Prec != NULL) { // Node is not the head
        Prec->Suiv = P->Suiv;
    } else { // Node is the head
        _Pile_ouverts = P->Suiv;
    }

    // Free the removed node's resources
    free(P->Nom_fich); // Free the filename stored in the node
    free(P);           // Free the node structure itself

    if (!Fp_copy) {
        perror("strdup failed in _Depiler_ouvert while copying name");
        return NULL;
    }

    return Fp_copy; // Return the copy of the filename
}

// --- END OF RUNTIME LIBRARY ---
// Note: The generated functions for specific data types (files, lists, etc.)
// will be added by the transpiler to the final C output file, not here.
