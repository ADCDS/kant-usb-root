# dropbearmulti (vendored)

`dropbearmulti` is the stripped, static ARMv7 EABI5 soft-float Dropbear 2022.83
used by the upstream project, patched so root's allowlist is
`/opt/etc/dropbear/authorized_keys`. It is vendored so this standalone builder
works without nix; the TV's `/usr/bin/bash` is the same ARM EABI5 soft-float.

Source and reproducible build (nix flake, musl cross, the authorized-keys
patch): <https://github.com/Luminger/samsung-tv-usb-root>

* `payload/README-BUILD.md`
* `payload/dropbear-authorized-keys-opt.patch`
* `flake.nix`

Vendored binary:

```text
SHA-256 cc4bb32fa9f79b185391873598003dcb8776e17d99ab4646c0cfa533e37dd89c
ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked, stripped
Flags: 0x5000200, Version5 EABI, soft-float ABI
```

Dropbear is MIT; see [`../LICENSES/Dropbear.txt`](../LICENSES/Dropbear.txt).
Host keys are generated per stick with this binary's `dropbearkey` under
`qemu-arm`; the operator key is supplied with `--authorized-keys`. The runtime
lifecycle (stage1: p1 detach, `/opt` install, `dropbear-root.service`) is
described in [`../README.md`](../README.md).
