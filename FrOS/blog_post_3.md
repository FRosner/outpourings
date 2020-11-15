---
title: Writing My Own Keyboard Driver
published: true
description: I set myself the goal to write an x86, 32 bit operating system from scratch. This time we will write a keyboard driver.
tags: hardware, x86, os, c
cover_image: https://dev-to-uploads.s3.amazonaws.com/i/dn820lhfuueyl8jglqip.png
series: Writing My Own Operating System
---

# Introduction

In the previous post we implemented a video driver so that we are able to print text on the screen. For an operating system to be useful to the user however, we also want them to be able to input commands. Text input and output will be the foundation for future shell functionality.

But how does the communication between the keyboard and our operating system work? The keyboard is connected to the computer through a physical port (e.g. serial, PS/2, USB). In case of PS/2 the data is received by a microcontroller which is located on the motherboard. When a key is pressed, the microcontroller stores the relevant information inside the I/O port `0x60` and sends an interrupt request [IRQ 1](https://en.wikipedia.org/wiki/Interrupt_request_(PC_architecture)) to the programmable interrupt controller ([PIC](https://en.wikipedia.org/wiki/Programmable_interrupt_controller)).

The PIC then interrupts the CPU with a predefined interrupt number based on the external IRQ. On receiving the interrupt, the CPU will consult the interrupt descriptor table ([IDT](https://en.wikipedia.org/wiki/Interrupt_descriptor_table)) to look up the respective interrupt handler it should invoke. After the handler has completed its task, the CPU will resume regular execution from before the interrupt.

For the complete chain to work we need to do some preparations during the kernel initialization. First, we have to setup the correct mapping inside the PIC so that our IRQs get translated to actual interrupts correctly. Then, we must create and load a valid IDT that contains a reference to our keyboard handler. The handler then reads all relevant data from the respective I/O ports and converts it to text that we can show to the user, such as `LCTRL` or `A`.

Now that we know the high level overview of what we need to do, let's jump into it! The remainder of this post is structured as follows. The next section focuses on defining and loading the IDT. Afterwards we will implement the keyboard interrupt handler and register it. Last but not least we extend the kernel functionality to execute the newly written code in the correct order.

The [source code](https://github.com/FRosner/FrOS/tree/3f5c58c8e41bf7b58f310a2d47900caafce21bf9) is available at GitHub. The code examples of this post use type aliases from `#include <stdint.h>` which are a bit more structured than the original C types. `uint16_t` corresponds to an unsigned 2 byte (16 bit) value, for example.

# Setting Up The IDT

## IDT Structure

The IDT consists of 256 descriptor entries, called gates. Each of those gates is 8 bytes long and corresponds to exactly one interrupt number, determined from its position in the table. There are three types of gates: task gates, interrupt gates, and trap gates. Interrupt and trap gates can invoke custom handler functions, with interrupt gates temporarily disabling hardware interrupt handling during the handler invocation, which makes it useful for processing hardware interrupts. Task gates cause allow using the hardware task switch mechanism to pass control of the processor to another program.

We only need to define interrupt gates for now. An interrupt gate contains the following information:

- **Offset.** The 32 bit offset represents the memory address of the interrupt handler within the respective code segment.
- **Selector.** The 16 bit selector of the code segment to jump to when invoking the handler. This will be our kernel code segment.
- **Type.** 3 bits indicating the gate type. Will be set to `110` as we are defining an interrupt gate.
- **D.** 1 bit indicating whether the code segment is 32 bit. Will be set to `1`.
- **DPL.** 2 bits The descriptor privilege level indicates what privilege is required to invoke the handler. Will be set to `00`.
- **P.** 1 bit indicating whether the gate is active. Will be set to `1`.
- **0.** Some bits that always need to be set to `0` for interrupt gates.

The diagram below illustrates the layout of an IDT gate.

![IDT gate structure](https://dev-to-uploads.s3.amazonaws.com/i/3wpdqrqks46fjl3iwlw4.png)

To create an IDT gate in C, we first define the `idt_gate_t` struct type. `__attribute__((packed))` tells `gcc` to pack the data inside the struct as tight as they are defined. Otherwise the compiler might include padding to optimize the struct layout with respect to the CPU cache size, for example.

```c
typedef struct {
    uint16_t low_offset;
    uint16_t selector;
    uint8_t always0;
    uint8_t flags;
    uint16_t high_offset;
} __attribute__((packed)) idt_gate_t;
```

Now we can define our IDT as an array of 256 gates and implement a setter function `set_idt_gate` to register a `handler` for interrupt `n`. We will make use of two small helper functions to split the 32 bit memory address of the handler.

```c
#define low_16(address) (uint16_t)((address) & 0xFFFF)
#define high_16(address) (uint16_t)(((address) >> 16) & 0xFFFF)

idt_gate_t idt[256];

void set_idt_gate(int n, uint32_t handler) {
    idt[n].low_offset = low_16(handler);
    idt[n].selector = 0x08; // see GDT
    idt[n].always0 = 0;
    // 0x8E = 1  00 0 1  110
    //        P DPL 0 D Type
    idt[n].flags = 0x8E;
    idt[n].high_offset = high_16(handler);
}
```

## Setting Up Internal ISRs

An interrupt handler is also referred to as a interrupt service routines (ISR). The first 32 ISRs are reserved for CPU specific interrupts, such as exceptions and faults. Setting these up is crucial as they are the only way for us to know if we are doing something wrong when remapping the PIC and defining the IRQs later. You can find a full list either in the source code or on [Wikipedia](https://en.wikipedia.org/wiki/Interrupt_descriptor_table).

First, we define a generic ISR handler function in C. It can extract all necessary information related to the interrupt and act accordingly. For now we will have a simple lookup array that contains a string representation for each interrupt number.

```c
char *exception_messages[] = {
    "Division by zero",
    "Debug",
    \\ ...
    "Reserved"
};

void isr_handler(registers_t *r) {
    print_string(exception_messages[r->int_no]);
    print_nl();
}
```

To make sure we have all information available, we are going to pass a struct of type `registers_t` to the function that is defined as follows:

```c
typedef struct {
    // data segment selector
    uint32_t ds;
    // general purpose registers pushed by pusha
    uint32_t edi, esi, ebp, esp, ebx, edx, ecx, eax;
    // pushed by isr procedure
    uint32_t int_no, err_code;
    // pushed by CPU automatically
    uint32_t eip, cs, eflags, useresp, ss;
} registers_t;
```

The reason this struct is so complex lies in the fact that we are going to invoke the handler function (which is written in C) from within assembly. Before a function is invoked, C expects the arguments to be present on the stack. The stack will contain some information already and we are extending it with additional information.

Below is an excerpt of the assembly code that defines the first 32 ISRs. Unfortunately there is no way to know which gate was used to invoke the handler so we need one handler for each gate. We have to define the labels as `global` so that we can reference them from our C code later.

```assembly
global isr0
global isr1
; ...
global isr31

; 0: Divide By Zero Exception
isr0:
    push byte 0
    push byte 0
    jmp isr_common_stub

; 1: Debug Exception
isr1:
    push byte 0
    push byte 1
    jmp isr_common_stub

; ...

; 12: Stack Fault Exception
isr12:
    ; error info pushed by CPU
    push byte 12
    jmp isr_common_stub

; ...

; 31: Reserved
isr31:
    push byte 0
    push byte 31
    jmp isr_common_stub
```

Each procedure makes sure that `int_no` and `err_code` are on the stack before handing over to the common ISR procedure, which we will look at in a moment. The first push (`err_code`), if present, represents error information that is specific to certain exceptions like stack faults. If such an exception occurs, the CPU will push this error information to the stack for us. To have a consistent stack for all ISRs, we are pushing a `0` byte in the cases where no error information is available. The second push corresponds to the interrupt number.

Now let's look at the common ISR procedure. It will fill the stack with all information required for `registers_t`, prepare the segment pointers to invoke our kernel ISR handler `isr_handler`, push the stack pointer (which is a pointer to `registers_t` actually) to the stack, call `isr_handler`, and clean up afterwards so that the CPU can resume where it was interrupted. `isr_handler` has to be marked as `extern`, because it will be defined in C.

```assembly
[extern isr_handler]

isr_common_stub:
    ; push general purpose registers
    pusha

    ; push data segment selector
    mov ax, ds
    push eax

    ; use kernel data segment
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    ; hand over stack to C function
    push esp
    ; and call it
    call isr_handler
    ; pop stack pointer again
    pop eax

    ; restore original segment pointers segment
    pop eax
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax

    ; restore registers
    popa

    ; remove int_no and err_code from stack
    add esp, 8

    ; pops cs, eip, eflags, ss, and esp
    ; https://www.felixcloutier.com/x86/iret:iretd
    iret
```

Last but not least, we can register the first 32 ISRs in our IDT using the `set_idt_gate` function from before. We are wrapping all the invocations inside `isr_install`.

```c
void isr_install() {
    set_idt_gate(0, (uint32_t) isr0);
    set_idt_gate(1, (uint32_t) isr1);
    // ...
    set_idt_gate(31, (uint32_t) isr31);
}
```

Now that we have the CPU internal interrupt handlers in place, we can move to remapping the PIC and setting up the IRQ handlers.

## Remapping the PIC

In our x86 system, the [8259 PIC](https://wiki.osdev.org/8259_PIC) is responsible for managing hardware interrupts. Note that an updated standard, the advanced programmable interrupt controller ([APIC](https://wiki.osdev.org/APIC)), exists for modern computers but this is beyond the scope of this post. We will utilize a cascade of two PICs, whereas each of them can handle 8 different IRQs. The secondary chip is connected to the primary chip through an IRQ, effectively giving us 15 different IRQs to handle.

The BIOS programs the PIC with reasonable default values for the 16 bit real mode, where the first 8 IRQs are mapped to the first 8 gates in the IDT. In protected mode however, these conflict with the first 32 gates that are reserved for CPU internal interrupts. Thus, we need to reprogram (remap) the PIC to avoid conflicts.

Programming the PIC can be done by accessing the respective I/O ports. The primary PIC uses ports `0x20` (command) and `0x21` (data). The secondary PIC uses ports `0xA0` (command) and `0xA1` (data). The programming happens by sending four initialization command words (ICWs). If the following paragraphs are confusing, I recommend reading this comprehensive [documentation](http://www.thesatya.com/8259.html).

First, we have to send the initialize command ICW1 (`0x11`) to both PICs. They will then wait for the following three inputs on the data ports:

- ICW2 (IDT offset). Will be set to `0x20` (32) for the primary and `0x28` (40) for the secondary PIC.
- ICW3 (wiring between PICs). We will tell the primary PIC to accept IRQs from the secondary PIC on IRQ 2 (`0x04`, which is `0b00000100`). The secondary PIC will be marked as secondary by setting `0x02` = `0b00000010`.
- ICW4 (mode). We set `0x01` = `0b00000001` in order to enable 8086 mode.

We finally send the first operational command word (OCW1) `0x00` = `0b00000000` to enable all IRQs (no masking). Equipped with the `port_byte_out` function from the previous post we can extend `isr_install` to perform the PIC remapping as follows.

```c
void isr_install() {
    // internal ISRs
    // ...

    // ICW1
    port_byte_out(0x20, 0x11);
    port_byte_out(0xA0, 0x11);

    // ICW2
    port_byte_out(0x21, 0x20);
    port_byte_out(0xA1, 0x28);

    // ICW3
    port_byte_out(0x21, 0x04);
    port_byte_out(0xA1, 0x02);

    // ICW4
    port_byte_out(0x21, 0x01);
    port_byte_out(0xA1, 0x01);

    // OCW1
    port_byte_out(0x21, 0x0);
    port_byte_out(0xA1, 0x0);
}
```

Now that we successfully remapped the PIC to send IRQs to the interrupt gates 32-47 we can register the respective ISRs.

# Setting Up IRQ Handlers

Adding the ISRs to handle IRQs is very similar to the first 32 CPU internal ISRs we created. First, we extend the IDT by adding gates for our IRQs 0-15.

```c
void isr_install() {
    // internal ISRs
    // ...

    // PIC remapping
    // ...

    // IRQ ISRs (primary PIC)
    set_idt_gate(32, (uint32_t)irq0);
    // ...
    set_idt_gate(39, (uint32_t)irq7);

    // IRQ ISRs (secondary PIC)
    set_idt_gate(40, (uint32_t)irq8);
    // ...
    set_idt_gate(47, (uint32_t)irq15);
}
```

Then, we add the IRQ procedure labels to our assembler code. We are pushing the IRQ number as well as the interrupt number to the stack before calling the `irq_common_stub`.

```assembly
global irq0
; ...
global irq15

irq0:
	push byte 0
	push byte 32
	jmp irq_common_stub

; ...

irq15:
	push byte 15
	push byte 47
	jmp irq_common_stub
```

`irq_common_stub` is defined analogous to the `isr_common_stub` and it will call a C the function `irq_handler`. The IRQ handler will be defined a bit more modular though, as we want to be able to add individual handlers dynamically when loading the kernel, such as our keyboard handler. To do that we initialize an array of interrupt handlers `isr_t` which are functions that take the previously defined `registers_t`.

```c
typedef void (*isr_t)(registers_t *);

isr_t interrupt_handlers[256];
```

Based on that we can write our general purpose `irq_handler`. It will retrieve the respective handler from the array based on the interrupt number and invoke it with the given `registers_t`. Note that due to the PIC protocol we must send an end of interrupt ([EOI](https://wiki.osdev.org/8259_PIC)) command to the involved PICs (only primary for IRQ 0-7, both for IRQ 8-15). This is required for the PIC to know that the interrupt is handled and it can send further interrupts. Here goes the code:

```c
void irq_handler(registers_t *r) {
    if (interrupt_handlers[r->int_no] != 0) {
        isr_t handler = interrupt_handlers[r->int_no];
        handler(r);
    }

    port_byte_out(0x20, 0x20); // primary EOI
    if (r->int_no < 40) {
        port_byte_out(0xA0, 0x20); // secondary EOI
    }
}
```

Now we are almost done. The IDT is defined and we only need to tell the CPU to load it.

## Loading the IDT

The IDT can be loaded using the [`lidt`](https://c9x.me/x86/html/file_module_x86_id_156.html) instruction. To be precise, `lidt` does not load the IDT but instead an IDT descriptor. The IDT descriptor contains the size (limit in bytes) and the base address of the IDT. We can model the descriptor as a struct like so:

```c
typedef struct {
    uint16_t limit;
    uint32_t base;
} __attribute__((packed)) idt_register_t;
```

We can then call `lidt` inside a new function called `load_idt`. It sets the base by obtaining the pointer to the `idt` gate array and computes the memory limit by multiplying the number of IDT gates (256) with the size of each gate. As usual, the limit is the size - 1.

```c
idt_register_t idt_reg;

void load_idt() {
    idt_reg.base = (uint32_t) &idt;
    idt_reg.limit = IDT_ENTRIES * sizeof(idt_gate_t) - 1;
    asm volatile("lidt (%0)" : : "r" (&idt_reg));
}
```

And here goes the final modification of our `isr_install` function, loading the IDT after we installed all ISRs.

```c
void isr_install() {
    // internal ISRs
    // ...

    // PIC remapping
    // ...

    // IRQ ISRs
    // ...

    load_idt();
}
```

This concludes the IDT section of this post and we can finally move to keyboard specific code. It is supposed to be a blog post about a keyboard driver after all, am I right?

# Keyboard Handler

When a key is pressed, we need a way to identify which key it was. This can be done by reading the [scan code](https://www.win.tue.nl/~aeb/linux/kbd/scancodes-1.html) of the respective keys. Note that the scan codes distinguish between a key being pressed (down) or being released (up). The scan code for releasing a key can be calculated by adding `0x80` to the respective key down code.

A `switch` statement contains all key down scan codes we want to handle right now. If a scan code does not match any of those cases, this can have 3 reasons. Either it is an unknown key down, or a released key. If the released key is within our expected range, we simply subtract `0x80` from the code. We can put this logic into a `print_letter` function:

```c
void print_letter(uint8_t scancode) {
    switch (scancode) {
        case 0x0:
            print_string("ERROR");
            break;
        case 0x1:
            print_string("ESC");
            break;
        case 0x2:
            print_string("1");
            break;
        case 0x3:
            print_string("2");
            break;
        // ...
        case 0x39:
            print_string("Space");
            break;
        default:
            if (scancode <= 0x7f) {
                print_string("Unknown key down");
            } else if (scancode <= 0x39 + 0x80) {
                print_string("key up ");
                print_letter(scancode - 0x80);
            } else {
                print_string("Unknown key up");
            }
            break;
    }
}
```

Note that scan codes are keyboard specific. The ones above are valid for IBM PC compatible PS/2 keyboards, for example. USB keyboards use different scan codes. Next, we have to implement and register an interrupt handler function for key presses. The PIC saves the scan code in port `0x60` after IRQ 1 is sent. So let's implement `keyboard_callback` and register it at IRQ 1, which is mapped to interrupt number 33.

```c
static void keyboard_callback(registers_t *regs) {
    uint8_t scancode = port_byte_in(0x60);
    print_letter(scancode);
    print_nl();
}
```

```c
#define IRQ1 33

void init_keyboard() {
    register_interrupt_handler(IRQ1, keyboard_callback);
}
```

We are almost done! The only thing left to do is to modify the main kernel function.

# New Kernel

The new kernel function needs to put all the pieces together. It has to install the ISRs, effectively loading our IDT. Then it will enable external interrupts by setting the interrupt flag using [`sti`](https://c9x.me/x86/html/file_module_x86_id_304.html). Finally, we can call the `init_keyboard` function that registers the keyboard interrupt handler.

```c
void main() {
    clear_screen();
    print_string("Installing interrupt service routines (ISRs).\n");
    isr_install();

    print_string("Enabling external interrupts.\n");
    asm volatile("sti");

    print_string("Initializing keyboard (IRQ 1).\n");
    init_keyboard();
}
```

Now let's boot and type something...

![demo](https://dev-to-uploads.s3.amazonaws.com/i/vlg3s39o167s3v88w5ut.gif)

Amazing! Having a VGA driver and a keyboard driver in place, we can work on a simple shell in the next post :)

---

<span>Cover image by <a href="https://unsplash.com/@jk2kphotos?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">John Karlo Mendoza</a> on <a href="https://unsplash.com/s/photos/keyboard?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">Unsplash</a></span>
