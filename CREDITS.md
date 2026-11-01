# Credits

This project is derived from Luminger's
[`samsung-tv-usb-root`](https://github.com/Luminger/samsung-tv-usb-root)
(AGPL-3.0):

* `tools/mk_trigger.py` — the exFAT volume/trigger builder.
* the stage1 design — `stage1.sh` in this repository is derived from the
  generated stage1.
* `payload/README-BUILD.md` and the static ARM dropbear recipe/build.
* the firmware-compatibility address table (Kant-M `T-KTMDEUC` 1410.1 row).

Dropbear is MIT; see [`LICENSES/Dropbear.txt`](LICENSES/Dropbear.txt).

The Kant / UN43MU6100 port — `build_compact.py`, `payload.S`, `stage0.S`,
`build_stick.py`, the Kant UEP/p1/p2 integration, and the documentation — is by
ADCDS and distributed under AGPL-3.0 (see [`LICENSE`](LICENSE)).

Hardware-verified on a Samsung UN43MU6100 (`T-KTMUABC` 1410.1, Linux 4.1.10).
No firmware, module, key, serial or device-private data is included.
