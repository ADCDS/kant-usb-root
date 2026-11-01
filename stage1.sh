#!/bin/bash
# Idempotent native stage: persistent data in /opt, runtime units in /run.
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
P2="${P2:-/opt/media/USBDriveA2}"
OPT=/opt
CHANGED=0
MARKER=/tmp/.samsung-usb-rooted

log() { echo "$(date '+%F %T') $*" >> $OPT/etc/dropbear/install.log; echo "$(date '+%F %T') $*" >> /tmp/kant-dropbear.log; }
hash_file() { /usr/bin/sha256sum "$1" 2>/dev/null | while read h rest; do echo "$h"; done; }
copy_changed() {
    src=$1 dst=$2 mode=$3
    if [ ! -f "$dst" ] || [ "$(hash_file "$src")" != "$(hash_file "$dst")" ]; then
        /usr/bin/install -m "$mode" "$src" "$dst.new" || return 1
        /usr/bin/mv -f "$dst.new" "$dst" || return 1
        CHANGED=1
    fi
}

[ -r "$P2/dropbearmulti" ] || exit 1
# Atomic boot guard: several media workers can race through the vulnerable
# directory before p1 is detached. Exactly one stage proceeds.
mkdir "$MARKER" 2>/dev/null || exit 0
# Detach the trigger before doing slower hashing/service work. The filesystem
# and p2 remain present; a failed install retries after the next reboot.
umount -l /opt/media/USBDriveA1 2>/dev/null || true

mkdir -p $OPT/bin $OPT/etc/dropbear /run/systemd/system || exit 1
chmod 700 $OPT/etc/dropbear
log "stage acquired boot guard; p1 detached"
log "p1 unmounted; p2=$P2"

copy_changed "$P2/dropbearmulti" $OPT/bin/dropbearmulti 755 || exit 1
out=$(/opt/bin/dropbearmulti dropbear -V 2>&1); rc=$?; log "dropbear /opt -V rc=$rc: $out"
copy_changed "$P2/authorized_keys" $OPT/etc/dropbear/authorized_keys 600 || exit 1
# Preserve server identity after first install; only seed absent host keys.
[ -s $OPT/etc/dropbear/dropbear_host_ed25519 ] || /usr/bin/install -m 600 "$P2/dropbear_host_ed25519" $OPT/etc/dropbear/dropbear_host_ed25519
[ -s $OPT/etc/dropbear/dropbear_host_rsa ] || /usr/bin/install -m 600 "$P2/dropbear_host_rsa" $OPT/etc/dropbear/dropbear_host_rsa
chmod 600 $OPT/etc/dropbear/authorized_keys $OPT/etc/dropbear/dropbear_host_ed25519 $OPT/etc/dropbear/dropbear_host_rsa

cat > /run/systemd/system/dropbear-root.service.new <<'UNIT'
[Unit]
Description=Dropbear root SSH from USB bootstrap
After=network.target

[Service]
Type=simple
ExecStart=/opt/bin/dropbearmulti dropbear -F -r /opt/etc/dropbear/dropbear_host_ed25519 -r /opt/etc/dropbear/dropbear_host_rsa -p 0.0.0.0:22 -s -g
Restart=always
RestartSec=2
UNIT
/usr/bin/mv -f /run/systemd/system/dropbear-root.service.new /run/systemd/system/dropbear-root.service
systemctl daemon-reload

log "service before: $(systemctl is-active dropbear-root.service 2>&1)"
if systemctl is-active --quiet dropbear-root.service; then
    [ "$CHANGED" = 0 ] || systemctl restart dropbear-root.service
else
    for pid in $(pgrep -f '^/opt/bin/dropbearmulti dropbear ' 2>/dev/null); do kill "$pid" 2>/dev/null || true; done
    /bin/sleep 1
    systemctl start dropbear-root.service
fi
log "service after: $(systemctl is-active dropbear-root.service 2>&1); listen: $(ss -ltn 2>/dev/null | grep ':22 ' || true)"

if ! systemctl is-active --quiet dropbear-root.service; then
    log "dropbear service failed; will retry next boot"
    exit 1
fi
if ! netstat -tln 2>/dev/null | grep -q ':22 '; then
    log "dropbear has no port-22 listener; will retry next boot"
    exit 1
fi


log "dropbear active; changed=$CHANGED"
exit 0
