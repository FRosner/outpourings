---
title: Writing My Own Dynamic Memory Management
published: true
description: I set myself the goal to write an x86, 32 bit operating system from scratch. This time we will implement dynamic memory allocation.
tags: memory, algorithms, datastructures, c
cover_image: https://dev-to-uploads.s3.amazonaws.com/i/dpnyr5h7nza418hixdyy.png
series: Writing My Own Operating System
---

# Introduction

So far, whenever we needed some memory, e.g. to store a string, we allocated it like that: `char my_string[10]`. This statement tells the C compiler to allocate 10 consecutive bytes in memory that we can use to store our characters.

But what if we do not know the size of the array at compile time? Let's say the user wants to specify the length of the string. We could of course allocate a fixed amount of memory, e.g. 256 bytes. There is a high chance that this is too much, however, effectively wasting memory. Another outcome would be that the statically allocated memory is not enough, making the program crash.
 
Dynamic memory management can solve this problem. Our OS should offer a way to allocate a flexible amount of memory that is determined at run time. To reduce the risk of running out of memory we also need functionality to make memory available again that is no longer used. In this blog post we want to design and implement a simple algorithm for dynamic memory management.

The remainder of this post is structured as follows. First, we design the data structure that we will use to manage dynamic memory, as well as the allocation and deallocation algorithm. Then, we implement a dynamic memory management for our kernel based on the theory from the previous section.

# Design

## Data Structure

To implement dynamic memory management, we will statically allocate a large memory region from which individual chunks can be borrowed to parts of our program. When the borrowed memory is no longer needed it can be returned to the pool.

The question is: How do we keep track of the chunks that have been borrowed, i.e. dynamically allocated? We need a data structure that allows us to find available memory of at least the requested size. We also want to pick the smallest possible free region in order to avoid ending up with many small memory fragments. Additionally it would be great if this operation can be performed with minimal effort.
 
For our simple implementation we will used a doubly linked list. Each element holds information about its chunk, specifically the address and size, whether it is currently allocated, as well as pointers to the previous and next element. We can find the optimal, i.e. the smallest possible, region by iterating through the entire list in *O(n)*, where *n* is the number of elements in the list. Of course there are more efficient alternatives such as heaps but they are more complex to implement so we are going to stick to the list.

Now where do we store the list? We cannot statically allocate memory for it because we do not know how many chunks will be requested and thus how many elements the list will contain. But we also cannot allocate it dynamically because we are building dynamic memory allocation just now.

We can overcome this problem by embedding the list elements within the large memory region that we reserve for dynamic allocation. For each chunk that is requested we store the respective list element just in front of that chunk. The following figure illustrates the initial state of a 1024 byte dynamic memory region. It contains a single 16 byte list element (the small dark green part in the beginning) indicating that the remaining 1008 bytes are free.

![initial dynamic memory state](https://dev-to-uploads.s3.amazonaws.com/i/wjlb8f40i2w9dz7wmxjz.png)

Now let's look into the allocation algorithm.

## Allocation Algorithm

When new memory *m* of size *s<sub>m</sub>* is requested, we go through all available memory looking for an optimal chunk to use. Given our list of memory chunks *L*, we attempt to find an optimal entry *o*, such that it is free (*free(o)*), sufficiently large (*s<sub>o</sub> ≥ s<sub>m</sub>*), and there is no smaller entry available (*∀x ∈ L: free(x) → s<sub>o</sub> ≤ s<sub>x</sub>*).

Given an optimal segment *o*, we slice off the requested amount of memory to create a new segment *p* including a new list entry, effectively shrinking *o* to size *s<sub>o</sub> - s<sub>m</sub> - s<sub>l</sub>*, where *s<sub>l</sub>* is the size of a list element. The new segment will have size *s<sub>p</sub> = s<sub>m</sub> + s<sub>l</sub>*. We then return a pointer to the beginning of the allocated memory, right after the list element. If no optimal chunk exists the allocation is unsuccessful.

The following figure shows the state of the segment list after the algorithm successfully allocated 256 bytes of memory. It contains two elements. The first one refers to a free chunk which takes up 752 bytes of dynamic memory. The second one represents the memory allocated for `p1` and takes up the remaining 272 bytes.

![allocating 256 bytes of memory](https://dev-to-uploads.s3.amazonaws.com/i/amqq459ior8hyso4yxkw.png)

Next, we will define an algorithm to free allocated memory.

## Deallocation Algorithm

The basic version of the deallocation algorithm is very simple. Given a pointer to an allocated region we obtain the respective list entry by looking at the memory region right in front of it. We then mark the chunk as free so that it will be considered next time new memory is requested.

While this version of the algorithm appears to work it has a major problem: We are creating more and more list entries. This will leave the dynamic memory fragmented, making it harder and harder to allocate larger parts of memory.

To solve this problem we merge the deallocated chunk with all adjacent free chunks. This is where our doubly linked list comes in handy as we can easily determine the previous and the next chunk by following the pointers.

The following animation illustrates a more complex example of different allocations and deallocations of memory.

{% youtube CVXtq77b4Xc %}

With the theory covered, let's start implementing the functionality in C so we can use it inside our OS.

# Implementation

## Doubly Linked List

We will model a chunk of dynamic memory as a struct containing its `size` (excluding the struct size) and whether it is `used` (i.e. not free). To make it a doubly linked list we add a `prev` and a `next` pointer. Here goes the code.

```c
typedef struct dynamic_mem_node {
    uint32_t size;
    bool used;
    struct dynamic_mem_node *next;
    struct dynamic_mem_node *prev;
} dynamic_mem_node_t;
```

Next we can initialize the dynamic memory.

## Initialization

Before we can allocate dynamic memory we need to initialize it. As described in the design section we are going to start off with a single chunk covering the entire available memory. The following code initializes 4kb of dynamic memory.

```c
#define NULL_POINTER ((void*)0)
#define DYNAMIC_MEM_TOTAL_SIZE 4*1024
#define DYNAMIC_MEM_NODE_SIZE sizeof(dynamic_mem_node_t) // 16

static uint8_t dynamic_mem_area[DYNAMIC_MEM_TOTAL_SIZE];
static dynamic_mem_node_t *dynamic_mem_start;

void init_dynamic_mem() {
    dynamic_mem_start = (dynamic_mem_node_t *) dynamic_mem_area;
    dynamic_mem_start->size = DYNAMIC_MEM_TOTAL_SIZE - DYNAMIC_MEM_NODE_SIZE;
    dynamic_mem_start->next = NULL_POINTER;
    dynamic_mem_start->prev = NULL_POINTER;
}
```

Let's move on to the implementation of the memory allocation function.

## Allocation

Recall from the allocation algorithm definition: First, we look for an optimal memory block. To keep the code readable we create a separate function `find_best_mem_block` for that part of the algorithm that goes through a given list and returns the smallest free node.

```c
void *find_best_mem_block(dynamic_mem_node_t *dynamic_mem, size_t size) {
    // initialize the result pointer with NULL and an invalid block size
    dynamic_mem_node_t *best_mem_block = (dynamic_mem_node_t *) NULL_POINTER;
    uint32_t best_mem_block_size = DYNAMIC_MEM_TOTAL_SIZE + 1;

    // start looking for the best (smallest unused) block at the beginning
    dynamic_mem_node_t *current_mem_block = dynamic_mem;
    while (current_mem_block) {
        // check if block can be used and is smaller than current best
        if ((!current_mem_block->used) &&
            (current_mem_block->size >= (size + DYNAMIC_MEM_NODE_SIZE)) &&
            (current_mem_block->size <= best_mem_block_size)) {
            // update best block
            best_mem_block = current_mem_block;
            best_mem_block_size = current_mem_block->size;
        }

        // move to next block
        current_mem_block = current_mem_block->next;
    }
    return best_mem_block;
}
```

We can then use this function to implement our `mem_alloc` function that takes the requested memory size and returns a pointer to that dynamically allocated memory. It returns a null pointer in case there is no sufficiently large chunk available. Let's look at the code and then go through it step by step.

```c
void *mem_alloc(size_t size) {
    dynamic_mem_node_t *best_mem_block =
            (dynamic_mem_node_t *) find_best_mem_block(dynamic_mem_start, size);

    // check if we actually found a matching (free, large enough) block
    if (best_mem_block != NULL_POINTER) {
        // subtract newly allocated memory (incl. size of the mem node) from selected block
        best_mem_block->size = best_mem_block->size - size - DYNAMIC_MEM_NODE_SIZE;

        // create new mem node after selected node, effectively splitting the memory region
        dynamic_mem_node_t *mem_node_allocate = (dynamic_mem_node_t *) (((uint8_t *) best_mem_block) +
                                                                        DYNAMIC_MEM_NODE_SIZE +
                                                                        best_mem_block->size);
        mem_node_allocate->size = size;
        mem_node_allocate->used = true;
        mem_node_allocate->next = best_mem_block->next;
        mem_node_allocate->prev = best_mem_block;

        // reconnect the doubly linked list
        if (best_mem_block->next != NULL_POINTER) {
            best_mem_block->next->prev = mem_node_allocate;
        }
        best_mem_block->next = mem_node_allocate;

        // return pointer to newly allocated memory (right after the new list node)
        return (void *) ((uint8_t *) mem_node_allocate + DYNAMIC_MEM_NODE_SIZE);
    }

    return NULL_POINTER;
}
```

We first call the `find_best_mem_block` function to find the smallest free block. In case there is a block available that we can use, we split it by reducing its size, creating a new node with the requested size at the start of the new chunk and insert it into the list. Finally we return a pointer to the memory address directly after the newly created list node.

We can then use `mem_alloc` to dynamically allocate an array of `n` integers and store `1..n` inside. Note that thanks to the C compiler we can access the memory using array syntax instead of calculating memory offsets. It will dereference it with the correct offset.

```c
int *ptr = (int *) mem_alloc(n * sizeof(int));
for (int i = 0; i < n; ++i) {
    ptr[i] = i+1; // shorthand for *(ptr + i)
}
```

Now to the `mem_free` implementation.

## Deallocation

The `mem_free` function takes a pointer to a dynamically allocated memory region. It then loads the respective list node by decrementing the pointer memory address by the node struct size and marks it as free. Finally, it attempts to merge the deallocated memory node with the next and previous list elements. Here you go.   

```c
void mem_free(void *p) {
    // move along, nothing to free here
    if (p == NULL_POINTER) {
        return;
    }

    // get mem node associated with pointer
    dynamic_mem_node_t *current_mem_node = (dynamic_mem_node_t *) ((uint8_t *) p - DYNAMIC_MEM_NODE_SIZE);

    // pointer we're trying to free was not dynamically allocated it seems
    if (current_mem_node == NULL_POINTER) {
        return;
    }

    // mark block as unused
    current_mem_node->used = false;

    // merge unused blocks
    current_mem_node = merge_next_node_into_current(current_mem_node);
    merge_current_node_into_previous(current_mem_node);
}
```

To increase readability we move the merging to separate functions.

```c
void *merge_next_node_into_current(dynamic_mem_node_t *current_mem_node) {
    dynamic_mem_node_t *next_mem_node = current_mem_node->next;
    if (next_mem_node != NULL_POINTER && !next_mem_node->used) {
        // add size of next block to current block
        current_mem_node->size += current_mem_node->next->size;
        current_mem_node->size += DYNAMIC_MEM_NODE_SIZE;

        // remove next block from list
        current_mem_node->next = current_mem_node->next->next;
        if (current_mem_node->next != NULL_POINTER) {
            current_mem_node->next->prev = current_mem_node;
        }
    }
    return current_mem_node;
}

void *merge_current_node_into_previous(dynamic_mem_node_t *current_mem_node) {
    dynamic_mem_node_t *prev_mem_node = current_mem_node->prev;
    if (prev_mem_node != NULL_POINTER && !prev_mem_node->used) {
        // add size of previous block to current block
        prev_mem_node->size += current_mem_node->size;
        prev_mem_node->size += DYNAMIC_MEM_NODE_SIZE;

        // remove current node from list
        prev_mem_node->next = current_mem_node->next;
        if (current_mem_node->next != NULL_POINTER) {
            current_mem_node->next->prev = prev_mem_node;
        }
    }
}
```

Calling free is straightforward.

```c
int *ptr = (int *) mem_alloc(n * sizeof(int));
for (int i = 0; i < n; ++i) {
    ptr[i] = i+1; // shorthand for *(ptr + i)
}
mem_free(ptr);
```

That concludes the dynamic memory management post :) I think I will pause the FrOS project for a bit now and focus on another project. Maybe I will come back at some point and write a file system or so :D

---

<span>Cover image by <a href="https://unsplash.com/@possessedphotography?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">Possessed Photography</a> on <a href="https://unsplash.com/s/photos/memory?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">Unsplash</a></span>
