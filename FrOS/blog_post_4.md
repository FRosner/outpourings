---
title: Writing My Own Shell
published: true
description: I set myself the goal to write an x86, 32 bit operating system from scratch. This time we will write a shell.
tags: terminal, x86, shell, c
cover_image: https://dev-to-uploads.s3.amazonaws.com/i/ogzz3bxhp37ds08xu8dr.png
series: Writing My Own Operating System
---

# Introduction

Operating systems provide high level functionality to interact with the computer hardware. This functionality needs to be made available to the user in some way, e.g. by a layer around the kernel, exposing simple commands. This outer layer is typically called a "shell".

As we only have a very simple text based VGA driver we will write a command-line shell. Graphical shells are beyond the scope of this series. The remainder of the post is structured as follows.

First, we will implement a key buffer that stores the user input and modify our keyboard callback to fill the buffer in addition to printing on screen. Next, we are going to add backspace functionality so we can correct typos. Thirdly, we will implement a very simple command parsing when the enter key is pressed. Finally, we modify our kernel entry to display a prompt after all initialization work is done.

# Key Buffer

Our shell should support complex commands potentially having subcommands and arguments. This means having single key commands is not going to get us very far but we would rather have the user type commands consisting of multiple characters. We need a place to store the command as it is being typed, however. This is where the key buffer comes in.

We can implement the key buffer as an array of characters. It will be initialized with `0` bytes and key presses will be recorded from index 0 upwards. Inspecting this data structure a bit closer you will notice that this is just how we encoded strings. A series of characters, terminated by a `0` byte.

To work with the key buffer efficiently we need two more string utility functions: A function to calculate the length of a string and a function to append a character to a given string. The latter function is going to make use of the former.

```c
int string_length(char s[]) {
    int i = 0;
    while (s[i] != '\0') {
        ++i;
    }
    return i;
}

void append(char s[], char n) {
    int len = string_length(s);
    s[len] = n;
    s[len + 1] = '\0';
}
```

Next, we can make a few adjustments to our keyboard callback function from the previous post. First, we want to get rid of the humongous switch statement and replace it by an array lookup based on the scan code. Secondly, we ignore all key up and non-alphanumeric scan codes. Lastly, we record each key in the key buffer and output it to the screen.

```c
#define SC_MAX 57

static char key_buffer[256];

const char scancode_to_char[] = {
  '?', '?', '1', '2', '3', '4', '5',
  '6', '7', '8', '9', '0', '-', '=',
  '?', '?', 'Q', 'W', 'E', 'R', 'T',
  'Y', 'U', 'I', 'O', 'P', '[', ']',
  '?', '?', 'A', 'S', 'D', 'F', 'G',
  'H', 'J', 'K', 'L', ';', '\', '`',
  '?', '\\', 'Z', 'X', 'C', 'V', 'B',
  'N', 'M', ',', '.', '/', '?', '?',
  '?', ' '
};

static void keyboard_callback(registers_t *regs) {
    uint8_t scancode = port_byte_in(0x60);

    if (scancode > SC_MAX) return;

    char letter = scancode_to_char[(int) scancode];
    append(key_buffer, letter);
    char str[2] = {letter, '\0'};
    print_string(str);
}
```

This method works but it has two problems. First, it does not check the boundaries of the key buffer before appending, risking a buffer overflow. Secondly, it does not leave any room for mistakes when typing a command. We will leave fixing the buffer overflow to the reader and implement backspace functionality next.

# Backspace

The user should be able to correct typos by pressing backspace, effectively deleting the last character from the buffer and from the screen.

Implementing the buffer modification can be done by reversing the `append` function. We simply set the last non-`0` byte in the buffer to `0`. The method will return `true` if we successfully removed an element from the buffer and `false` otherwise. Note that you have to import the type definition for `bool` using `#include <stdbool.h>`.

```c
bool backspace(char buffer[]) {
    int len = string_length(buffer);
    if (len > 0) {
        buffer[len - 1] = '\0';
        return true;
    } else {
        return false;
    }
}
```

Printing a backspace character on screen can be implemented by printing an empty character at the position right before the current cursor position and moving the cursor backwards. We will make use of our `get_cursor`, `set_cursor`, and `set_char_at_video_memory` functions from the VGA driver.

```c
void print_backspace() {
    int newCursor = get_cursor() - 2;
    set_char_at_video_memory(' ', newCursor);
    set_cursor(newCursor);
}
```

To complete the backspace functionality we modify the keyboard callback function by adding a branch specifically for backspace key presses. When backspace is pressed, we first attempt to delete the last character from the key buffer. If this was successful, we also show the backspace on screen. It is important to perform this check because otherwise the user would be able to backspace all the way through the screen without being stopped by prompts.

```c
#define BACKSPACE 0x0E

static void keyboard_callback(registers_t *regs) {
    uint8_t scancode = port_byte_in(0x60);
    if (scancode > SC_MAX) return;

    if (scancode == BACKSPACE) {
        if (backspace(key_buffer)) {
            print_backspace();
        }
    } else {
        char letter = scancode_to_char[(int) scancode];
        append(key_buffer, letter);
        char str[2] = {letter, '\0'};
        print_string(str);
    }
}
```

Having a key buffer and backspace functionality in place, we can move to the last step: parsing and executing commands.

# Parsing and Executing Commands

Whenever the user hits the enter key, we want to execute the given command. That typically involves parsing the command first, potentially splitting it into multiple subcommands, parsing arguments or invoking external functionality. For the sake of simplicity we will only implement very basic "parsing" that checks whether the string is a known command and if it is not, shows an error.

First, we need to write a function to compare two strings. It will go through both strings step by step, comparing the character values. Here goes the code.

```c
int compare_string(char s1[], char s2[]) {
    int i;
    for (i = 0; s1[i] == s2[i]; i++) {
        if (s1[i] == '\0') return 0;
    }
    return s1[i] - s2[i];
}
```

Next, we have to implement a function `execute_command` that executes a given command. Our first version of the shell will only recognize a single command called `EXIT` that halts the CPU. Later we can implement other commands such as rebooting or interacting with a file system. If the command is unknown, we print an error message. Finally, we print a new prompt.

```c
void execute_command(char *input) {
    if (compare_string(input, "EXIT") == 0) {
        print_string("Stopping the CPU. Bye!\n");
        asm volatile("hlt");
    }
    print_string("Unknown command: ");
    print_string(input);
    print_string("\n> ");
}
```

Finally, we adjust the keyboard callback to move the cursor to the next line, invoke `execute_command`, and reset the key buffer when the enter key is pressed.

```c
#define ENTER 0x1C

static void keyboard_callback(registers_t *regs) {
    uint8_t scancode = port_byte_in(0x60);
    if (scancode > SC_MAX) return;

    if (scancode == BACKSPACE) {
        if (backspace(key_buffer) == true) {
            print_backspace();
        }
    } else if (scancode == ENTER) {
        print_nl();
        execute_command(key_buffer);
        key_buffer[0] = '\0';
    } else {
        char letter = scancode_to_char[(int) scancode];
        append(key_buffer, letter);
        char str[2] = {letter, '\0'};
        print_string(str);
    }
}
```

We are almost done! Let's update the main kernel function.

# Updated Kernel Function

Actually, there is not much to do. We will clear the screen and display the initial prompt after all initialization work is done and that's it! The updated keyboard handler will do the rest. Here comes the code and a demo!

```c
void start_kernel() {
    clear_screen();
    print_string("Installing interrupt service routines (ISRs).\n");
    isr_install();

    print_string("Enabling external interrupts.\n");
    asm volatile("sti");

    print_string("Initializing keyboard (IRQ 1).\n");
    init_keyboard();

    clear_screen();
    print_string("> ");
}
```

![shell demo](https://dev-to-uploads.s3.amazonaws.com/i/92qz9tc8fbjgla0w2cal.gif)

Amazing, although not very practical until we add new commands :D. In the next post we will add dynamic memory allocation.

---

<span>Cover image by <a href="https://unsplash.com/@etaplus?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">ETA+</a> on <a href="https://unsplash.com/s/photos/commodore?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">Unsplash</a>.</span>
