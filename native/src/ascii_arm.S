.syntax unified
.arch armv7-a
.arm
.text
.balign 4
.global streamlite_ascii_lower
.type streamlite_ascii_lower,%function
streamlite_ascii_lower:
    cmp r1, #0
    beq 2f
1:
    ldrb r2, [r0]
    sub r3, r2, #65
    cmp r3, #25
    bhi 3f
    orr r2, r2, #32
    strb r2, [r0]
3:
    add r0, r0, #1
    subs r1, r1, #1
    bne 1b
2:
    bx lr
.size streamlite_ascii_lower, .-streamlite_ascii_lower
.section .note.GNU-stack,"",%progbits
