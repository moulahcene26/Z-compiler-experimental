#include "z_runtime.h"

// --- Global Declarations ---
int Age;
char UserName[51];
bool CanVote;

// --- Main Program ---
int main(int argc, char *argv[]) {
    srand(time(NULL)); // Initialize random seed
    printf("%s\n", "Please enter your username:");
    scanf(" %c", &UserName);
    printf("%s\n", "Please enter your age:");
    scanf("%d", &Age);
    if ((Age >= 18)) {
        printf("%s %c %s %d %s\n", "Hello ", UserName, ", you are ", Age, " years old.");
        printf("%s\n", "You are old enough to vote.");
        CanVote = true;
    }
    else {
        printf("%s %c %s %d %s\n", "Hello ", UserName, ", you are only ", Age, " years old.");
        printf("%s\n", "You are not old enough to vote yet.");
        CanVote = false;
    }
    printf("%s\n", "Voting status check complete.");
    return 0;
}