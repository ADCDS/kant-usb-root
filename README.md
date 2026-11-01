# kant-usb-root — one-plug root + dropbear for the Samsung UN43MU6100

Target: **Samsung UN43MU6100** (2017 Kant-M), firmware **T-KTMUABC 1410.1**,
Linux **4.1.10** ARMv7, 8 KiB kernel stacks. The Kant-M `T-KTMDEUC` 1410.1 row
in Luminger's [compatibility matrix](https://github.com/Luminger/samsung-tv-usb-root/blob/main/docs/FIRMWARE-COMPATIBILITY.md)
lists the same UMH/coherent/memcpy/copy-window addresses; this port was
developed against the `T-KTMUABC` 1410.1 uImage and exFAT modules and uses the
`ldmge` at `0xc051ad5c` (the row's `ldm ip` is `0xc051adec`) and the Kant UEP at
`0xc0211c70`.

Status: **hardware-verified**. One insert gives a key-only root dropbear on
`0.0.0.0:22`; `ssh ... root@<TV_IP>` returns `uid=0(root)`. The TV stays up:
stage1 lazy-unmounts p1 early; the parked trigger thread remains, but the mount
is detached and the system does not reboot.

## Build

```sh
python3 build_stick.py \
    --authorized-keys ~/.ssh/id_ed25519.pub \
    --out out/kant-usb-dropbear.img --force
```

Dependencies: `python3`, `arm-none-eabi-as`/`arm-none-eabi-objcopy`, `qemu-arm`,
`dosfstools`, `mtools`. The repository vendors `tools/mk_trigger.py` (the exFAT
trigger builder) and `payload/dropbearmulti` (the static ARM EABI5 soft-float
musl build; see `payload/README-BUILD.md`). The image is 25 MiB (1 MiB alignment
+ 8 MiB p1 + 16 MiB p2).

The command prints the image and partition hashes. Then:

```sh
sudo dd if=out/kant-usb-dropbear.img of=/dev/sdX bs=4M conv=fsync status=progress
sudo sync
```

Use only on hardware you own. Replace `/dev/sdX` carefully.

## Use

1. Power-cycle the TV (a previous stick/mount must not be left parked).
2. Insert the stick.
3. Wait a few seconds, then:

```sh
ssh -i ~/.ssh/id_ed25519 root@<TV_IP> id
# uid=0(root) gid=0(root) ... context="System"
```

`stage1` writes `/tmp/kant-dropbear.log` (world-readable) and
`/opt/etc/dropbear/install.log`. It also detaches p1
(`umount -l /opt/media/USBDriveA1`), copies `dropbearmulti` and the keys to
`/opt`, and creates `/run/systemd/system/dropbear-root.service`.

The p2 is vfat with `fmask=0111`, so its files are not executable; the dropbear
is data there until stage1 copies it into `/opt` (vdfs4 rw, exec-capable). The
UEP patch is applied by the kernel stage at every boot; `/run` (and therefore
the service unit) is tmpfs, so **keep the stick inserted across reboots** — each
boot re-runs the stage and recreates the service. The files copied to `/opt`
persist.

## How it works

The p1 exFAT volume carries a probe media file and one crafted file set:
`SecondaryCount=58`, so `ffsReadDir` copies 57*30 = **1710 bytes** over a
560-byte stack buffer — **14 bytes under** the exact 1724-byte headroom of this
kernel. The saved `sp`/`pc` pivot through the real uImage gadgets (`ldmge` at
`0xc051ad5c`, copy window `0xc0100904`, the 16-byte r1 saver at `0xc00756f4`,
the flush wrapper at `0xc001254c`) into the zero cave at `0xc00083dc`; the stage
derives `sp` from the live `memcpy` r1, so it runs inside the same 8 KiB stack
and `current_thread_info()` stays correct.

The **288-byte** stage at `uniname+1420` then:

1. writes `mov r0,#2; bx lr` to `SfdUepVerifyFileSignature` at `0xc0211c70` and
   flushes those 8 bytes with `v7_coherent_kern_range` (`0xc001bfbc`) — this is
   what lets the unsigned dropbear run;
2. calls `call_usermodehelper("/bin/sh", {"-c",
   "sh</opt/media/USBDriveA2/s"}, NULL, UMH_NO_WAIT)` — the signed shell reads
   stage1 from p2 as its stdin (no script exec, no UEP script gate);
3. parks the readdir thread with `b .` (preemptible); the queued stage1 then
   detaches p1 and installs the dropbear.

`stage1` is derived from the Luminger stage: it atomically takes
`/tmp/.samsung-usb-rooted`, lazy-unmounts p1, copies the dropbear/keys to
`/opt`, and starts the service. The p2 (`sda2`, `/opt/media/USBDriveA2`) stays
mounted.

Addresses (shipped uImage, load `0xc0008000`): UEP `0xc0211c70`, coherent
`0xc001bfbc`, UMH `0xc00389c4`, ldmge `0xc051ad5c`, copy window `0xc0100904`,
memcpy `0xc023e740`, flush wrapper `0xc001254c`. The p1 trigger's epilogue slots
are `r6=0xc00083dc`, `fp=0xc0008424`, `sp=0xc0008e00`, `pc=0xc051ad5c`.

## Caveats

* Exact firmware only. A different build can hang or reboot the set; the
  addresses above are from this target's uImage. Do not cross-flash.
* The p1 trigger parks the media-scanner readdir while it holds p1's root inode
  mutex. stage1's early `umount -l` detaches the mount so the scanner's other
  workers stop; the parked thread remains and the scanner process may be killed
  by its watchdog, but the TV stays up. Do not have the helper open anything on
  p1 — that is why the command reads stage1 from p2.
* The UEP patch is runtime-only: it is re-applied on every boot from the stick.
  No firmware or rootfs is modified. `/opt` writes (dropbear, keys,
  authorized_keys) persist; `/run` and `/tmp` do not.
* The p2 mounts with `fmask=0111` (no execute bits); the direct `dropbear -V`
  from p2 returns EACCES. That is expected: the dropbear is copied to
  `/opt/bin`, where it executes. The `/opt/bin/dropbearmulti -V` logged by
  stage1 is the real UEP check.
* The `.samsung-usb-rooted` guard is boot-local; the stick must be inserted at
  boot for the service to be recreated. Do not leave the stick in a TV you do
  not want rooted.
* No device-private certificates, keys, serial numbers or firmware are
  included. The operator key is supplied at build time; host keys are generated
  per stick.

## License and credits

**AGPL-3.0** (see [`LICENSE`](LICENSE)). Derived from
[`Luminger/samsung-tv-usb-root`](https://github.com/Luminger/samsung-tv-usb-root)
(AGPL-3.0): the vendored `tools/mk_trigger.py`, the stage1 design, and the
dropbear recipe/build. See [`CREDITS.md`](CREDITS.md). Dropbear is MIT; see
[`LICENSES/Dropbear.txt`](LICENSES/Dropbear.txt).
