# Security / responsible use

This is a working kernel exploit for one exact Samsung TV firmware family
(Kant-M, 1410.1). Use it only on hardware you own or are explicitly authorized
to test.

Before testing:

* Exact firmware only. A different build can hang or reboot the set; the
  addresses are from the `T-KTMUABC` 1410.1 target. Do not cross-flash.
* Keep the official firmware recovery image available.
* Verify the generated image checksum and destination block device before
  flashing.
* A failed p1 trigger can require a power cycle.

What the exploit changes:

* The kernel stage patches Samsung UEP at runtime and parks a readdir thread.
  No firmware or rootfs is modified.
* `/opt` (rw) receives the dropbear and keys; `/run` receives the service unit
  (tmpfs). The stick must be inserted at boot to re-apply the stage.
* Do not leave the stick in a TV you do not want rooted.

Do not submit device-private certificates, keys, serial numbers, live
inventory, or proprietary firmware/modules to this repository.
