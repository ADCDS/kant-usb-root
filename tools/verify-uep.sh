#!/bin/sh
# Prove that the USB stage's UEP neutralisation is live on this boot.
#
# Run on the TV after inserting the stick:
#   ./verify-uep.sh            # as root
#   /opt/verify-uep.sh         # or as uid 5001
#
# Success: the unsigned copy of /bin/echo executes and prints UEP-PATCH-OK.
# Failure ("Permission denied"): the stage did not run, or the TV rebooted
# and the RAM-only patch was lost.
set -e

cp /bin/echo /tmp/.uep-verify
chmod +x /tmp/.uep-verify
exec /tmp/.uep-verify UEP-PATCH-OK
