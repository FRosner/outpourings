---
title: Writing My Own VGA Driver
published: true
description: I set myself the goal to write an x86, 32 bit operating system from scratch. Now we need a simple video driver.
tags: vga, x86, os, c
cover_image: https://dev-to-uploads.s3.amazonaws.com/i/5evghtr19hiwkmhn7v89.jpg
series: Writing My Own Operating System
---

# Why a VGA Driver?

Our operating system needs some way to interact with the user. This requires us to do some form of I/O. First, we want to focus on visual output. We will rely on the VGA 80x25 text video mode as it is very convenient to handle and flexible enough for basic terminal functionality. This is the same mode that was already used by the BIOS while booting our kernel.

With VGA we can produce screen output by modifying a dedicated memory region, called the video memory, directly. In addition to that, there are specific port addresses that we can use to interact with device ports using the port I/O CPU instructions [`in`](https://c9x.me/x86/html/file_module_x86_id_139.html) and [`out`](https://c9x.me/x86/html/file_module_x86_id_222.html). This is possible because all I/O ports (including the VGA ports) are [mapped to specific memory locations](http://www.brokenthorn.com/Resources/OSDev7.html).

The task of our VGA driver will be to encapsulate these low level memory manipulations within higher level functions. Instead of issuing individual CPU instructions and modifying memory addresses we want to be able invoke a function to print a string on the screen or clear all output. In this post we are going to write such a minimal VGA driver.

The remainder of the article is structured as follows. The next section explains how we can interface with I/O ports using C. Afterwards we will put this knowledge to use and implement functions to retrieve and set the text cursor position. Then we will write code to print individual characters on the screen by writing to the video memory. We will combine the cursor manipulation with the character printing to provide functionality for printing strings to the screen. The sections after that focus on a few extensions such as handling newline characters, scrolling, as well as clearing the screen. The final section adjusts the main kernel function to make use of our newly written driver.

The [source code](https://github.com/FRosner/FrOS/tree/88aaf8a1aa7c3f913ad0cba2eb9df93e4913c752) is available on GitHub.

# Interfacing with I/O Ports from C

One important part of I/O drivers is be the ability to interface with I/O devices through ports. In our VGA driver we only need to access the ports `0x3d4` and `0x3d5` for now, in order to read and set the cursor position while in text mode.

As mentioned earlier, we can utilize the [`in`](https://c9x.me/x86/html/file_module_x86_id_139.html) and [`out`](https://c9x.me/x86/html/file_module_x86_id_222.html) instructions to read and write port data, respectively. But how do we make use of those instructions from within C?

Luckily, the C compiler supports [inline assembler code](https://gcc.gnu.org/onlinedocs/gcc/Using-Assembly-Language-with-C.html#Using-Assembly-Language-with-C) by calling the `__asm__` function that lets us write assembler code, passing C variables as input and writing results back into C variables. The assembler instruction, the output parameters, and the input parameters of the `__asm__` function are separated by `:`. The syntax is a bit different compared to NASM, e.g. the order of the instruction operands is reversed.

Let's take a look at the following two functions to read/write data from/to a specified port.

```c
unsigned char port_byte_in(unsigned short port) {
    unsigned char result;
    __asm__("in %%dx, %%al" : "=a" (result) : "d" (port));
    return result;
}

void port_byte_out(unsigned short port, unsigned char data) {
    __asm__("out %%al, %%dx" : : "a" (data), "d" (port));
}
```

For our `port_byte_in` function we map the C variable `port` into the `dx` register, execute `in al, dx`, and then store the value of the `al` register into the C variable `result`. The `port_byte_out` function looks similar. It executes `out dx, al`, mapping the `port` to `dx` and the data to `al`.  As we are only writing data there are no output parameters and the function has no return value.

# Getting and Setting the Cursor Position

With our newly written port I/O functions we are ready to interact with the VGA text mode cursor. In order to read or change the cursor position we need to modify the [VGA control register](https://wiki.osdev.org/VGA_Hardware#Port_0x3C4.2C_0x3CE.2C_0x3D4) `0x3d4` and read from or write to the respective data register `0x3d5`.

The 16 bit cursor position is encoded as 2 individual bytes, the high and the low byte. The data register will hold the low byte if the control register is set to `0x0f`, and the high byte if the value `0x0e` is used. First we will define the register addresses and the codes for our offset as C constants.

```c
#define VGA_CTRL_REGISTER 0x3d4
#define VGA_DATA_REGISTER 0x3d5
#define VGA_OFFSET_LOW 0x0f
#define VGA_OFFSET_HIGH 0x0e
```

We are going to represent our cursor offset as the video memory offset. The memory offset is twice the cursor offset, because each position in the text grid is represented by 2 bytes, one for the character and one for color information.

As we cannot fit a memory offset having twice the size of a 16 bit cursor offset into a 16 bit short, we will use a 32 bit integer. And now we can write a `set_cursor` and a `get_cursor` function that takes our internal cursor offset.

```c
void set_cursor(int offset) {
    offset /= 2;
    port_byte_out(VGA_CTRL_REGISTER, VGA_OFFSET_HIGH);
    port_byte_out(VGA_DATA_REGISTER, (unsigned char) (offset >> 8));
    port_byte_out(VGA_CTRL_REGISTER, VGA_OFFSET_LOW);
    port_byte_out(VGA_DATA_REGISTER, (unsigned char) (offset & 0xff));
}

int get_cursor() {
    port_byte_out(VGA_CTRL_REGISTER, VGA_OFFSET_HIGH);
    int offset = port_byte_in(VGA_DATA_REGISTER) << 8;
    port_byte_out(VGA_CTRL_REGISTER, VGA_OFFSET_LOW);
    offset += port_byte_in(VGA_DATA_REGISTER);
    return offset * 2;
}
```

Note that because our memory offset is double the cursor offset, we have to map the two offsets by multiplying or dividing by 2. We also have to do some bit shifting / masking in order to retrieve the high and the low byte from our integer.

# Printing a Character on Screen

Having the cursor manipulations in place, we also need to be able to print characters at a specified position on screen. We already did that in our dummy kernel in the previous post. So let's take that code and make it a bit more generic. First, we will define a few helpful constants containing the starting address for the video memory, the text grid dimensions, as well as a default coloring scheme to use for our characters.

```c
#define VIDEO_ADDRESS 0xb8000
#define MAX_ROWS 25
#define MAX_COLS 80
#define WHITE_ON_BLACK 0x0f
```

Next, let's write a function to print a character on screen by writing it to the video memory at a given memory offset. We are not going to support different colors for now but we can adjust this later if needed.

```c
void set_char_at_video_memory(char character, int offset) {
    unsigned char *vidmem = (unsigned char *) VIDEO_ADDRESS;
    vidmem[offset] = character;
    vidmem[offset + 1] = WHITE_ON_BLACK;
}
```

Now that we can print characters on screen and modify the cursor, we can implement a function that prints a string and moves the cursor accordingly.

# Printing Text and Moving the Cursor

In C a string is a 0-byte terminated sequence of ASCII encoded bytes. To print a string on the screen we need to:

1. Get the current cursor offset.
2. Loop through the bytes of the string, writing them to the video memory, incrementing the offset.
3. Update the cursor position.

Here goes the code:

```c
void print_string(char *string) {
    int offset = get_cursor();
    int i = 0;
    while (string[i] != 0) {
        set_char_at_video_memory(string[i], offset);
        i++;
        offset += 2;
    }
    set_cursor(offset);
}
```

Note that this code does neither handle newline characters, nor offsets that are out of bounds at this point. We can fix that by implementing scrolling functionality in case of our offset growing out of bounds, and moving the cursor to the next line when we detect a newline character. Let's look into handling newline characters next.

# Handling Newline Characters

A newline character is actually a non-printable character. It does not take space in the grid but instead moves the cursor to the next line. To do that we will write a function that takes a given cursor offset and computes the new offset, which is the first column in the next row.

Before we implement that we will write two small helper functions. `get_row_from_offset` takes a memory offset and returns the row number of the corresponding cell. `get_offset` returns a memory offset for a given cell.

```c
int get_row_from_offset(int offset) {
    return offset / (2 * MAX_COLS);
}

int get_offset(int col, int row) {
    return 2 * (row * MAX_COLS + col);
}
```

Combining those two functions we can easily write the function that moves the offset to the next line.

```c
int move_offset_to_new_line(int offset) {
    return get_offset(0, get_row_from_offset(offset) + 1);
}
```

With this function at our disposal we can modify the `print_string` function to handle `\n`.

```c
void print_string(char *string) {
    int offset = get_cursor();
    int i = 0;
    while (string[i] != 0) {
        if (string[i] == '\n') {
            offset = move_offset_to_new_line(offset);
        } else {
            set_char_at_video_memory(string[i], offset);
            offset += 2;
        }
        i++;
    }
    set_cursor(offset);
}
```

Next, let's look at how we can implement scrolling.

# Scrolling

As soon as the cursor offset exceeds the maximum value of 25x80x2 = 4000 the terminal output should scroll down. Without a scroll buffer the top line will be lost but this is ok for now. We can implement scrolling by executing the following steps:

1. Move all rows but the first one by 1 row upwards. We do not need to move the top row as it would be out of bounds anyway.
2. Fill the last row with blanks.
3. Correct offset to be inside our grid bounds again.

The following animation illustrates the scrolling algorithm.

{% youtube tU99KrdzuhI %}

We can implement the row movement by copying a chunk of the video memory. First, we will write a function that copies a given number of bytes `nbytes` in memory from `*source` to `*dest`.

```c
void memory_copy(char *source, char *dest, int nbytes) {
    int i;
    for (i = 0; i < nbytes; i++) {
        *(dest + i) = *(source + i);
    }
}
```

With the `memory_copy` function at our disposal we can implement a scrolling helper function that takes a given offset, copies the desired memory region, clears the last row, and adjusts the offset to be inside the grid bounds again. We will use the `get_offset` helper method to conveniently determine the offset for a given cell.

```c
int scroll_ln(int offset) {
    memory_copy(
            (char *) (get_offset(0, 1) + VIDEO_ADDRESS),
            (char *) (get_offset(0, 0) + VIDEO_ADDRESS),
            MAX_COLS * (MAX_ROWS - 1) * 2
    );

    for (int col = 0; col < MAX_COLS; col++) {
        set_char_at_video_memory(' ', get_offset(col, MAX_ROWS - 1));
    }

    return offset - 2 * MAX_COLS;
}
```

Now we only need to modify our `print_string` function so that each loop iteration it checks if the current offset exceeds the maximum value and scroll if needed. This is the final version of the function:

```c
void print_string(char *string) {
    int offset = get_cursor();
    int i = 0;
    while (string[i] != 0) {
        if (offset >= MAX_ROWS * MAX_COLS * 2) {
            offset = scroll_ln(offset);
        }
        if (string[i] == '\n') {
            offset = move_offset_to_new_line(offset);
        } else {
            set_char_at_video_memory(string[i], offset);
            offset += 2;
        }
        i++;
    }
    set_cursor(offset);
}
```

# Clearing the Screen

After the our kernel has started, the video memory will be filled with some information from the BIOS that is no longer relevant. So we need a way to clear the screen. Fortunately this function is easy to implement given our existing helper functions.

```c
void clear_screen() {
    for (int i = 0; i < MAX_COLS * MAX_ROWS; ++i) {
        set_char_at_video_memory(' ', i * 2);
    }
    set_cursor(get_offset(0, 0));
}
```

# Hello World and Scrolling in Action

We can adjust our `main` function to print a string now! We only need to include the display header file so our compiler knows that the driver functions exist.

```c
#include "../drivers/display.h"

void main() {
    clear_screen();
    print_string("Hello World!\n");
}
```

To visualize the scrolling I wrote an extended main function that prints increasing characters, launched QEMU in debug mode, attached the GNU debugger (`gdb`), put a breakpoint in the print function and executed the following debug instruction to slow down the scrolling so it becomes visible.

```
while (1)
shell sleep 0.2
continue
end
```

And this is the result:

![scrolling in action](https://dev-to-uploads.s3.amazonaws.com/i/2nvct3b3m5duz8kgvkah.gif)

Horray! We managed to write a simple, yet working video driver that allows us to print strings on the screen. It even supports scrolling! Next up: Keyboard input :)

---

Cover image by [Jason Scott](https://www.flickr.com/photos/54568729@N00/9636183501).
