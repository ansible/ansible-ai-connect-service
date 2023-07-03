#!/bin/env bash
echo "ClamAV Virus Definition DB Files:"
echo "----"
ls -rla /var/lib/clamav
for dbfile in $(ls /var/lib/clamav/*.cvd)
do
  echo "----"
  sigtool --info ${dbfile}
done
echo "----"
echo "Scanning Results:"
clamscan --version
clamscan -ri --max-filesize=4000M --max-scansize=4000M --exclude-dir=/dev --exclude-dir=/proc --exclude-dir=/sys /
