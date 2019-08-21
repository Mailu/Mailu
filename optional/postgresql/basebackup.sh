#!/bin/sh

dest="/backup/base-$(date +%F-%H%M)"
last=$(ls -d /backup/base* | tail -n1)
mkdir $dest || exit $?

pg_basebackup --wal-method=none --pgdata=$dest --format=tar --gzip --username=postgres || exit $?

# Clean old base backups, keep the last and the current.
for d in /backup/base*; do
    if [ "$d" == "$last" ] || [ "$d" == "$dest" ]; then
        continue
    fi
    rm -r $d || exit $?
done

# Clean the wall archive
cd /backup/wal_archive || exit $?
if [ $(ls *.*.backup | wc -l) -lt 2 ]; then
    exit 0
fi
# Find the single last wal.backup point
prev_wal_start="$(ls *.*.backup | tail -n2 | head -n1 | cut -d '.' -f 1)"
for f in $(ls) ; do
    if [ "$f" \< "$prev_wal_start" ]; then
        rm -v /backup/wal_archive/$f
    fi
done
