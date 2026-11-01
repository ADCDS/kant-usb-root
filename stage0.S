.syntax unified
.arm
.global _start
_start:
    mov r0, r4
    mov r1, r5
    ldr r3, coh
    blx r3
    mov pc, r4
coh: .word 0xc001bfbc
