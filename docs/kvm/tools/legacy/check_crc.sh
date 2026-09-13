#!/bin/bash
# Compare vendor module __versions CRCs against our kernel's Module.symvers.
# MODVERSIONS refuses to load a module when any CRC differs, so this must be
# clean before flashing.
KERNEL_DIR=/home/moao/resukisu_kernel
MODS_DIR=/tmp/mods
OUR=/tmp/ourcrc.txt
MOD=/tmp/modcrc.txt

awk '{c=tolower($1); sub(/^0x/,"",c); print c"\t"$2}' "$KERNEL_DIR/out/Module.symvers" | sort -k2 -u > "$OUR"

: > "$MOD"
for f in "$MODS_DIR"/*.ko; do
	modprobe --dump-modversions "$f" 2>/dev/null
done | awk '{c=tolower($1); sub(/^0x/,"",c); print c"\t"$2}' | sort -k2 -u > "$MOD"

echo "kernel_exports=$(wc -l < "$OUR")  module_needs=$(wc -l < "$MOD")"
echo "=== PROBLEMS ==="
awk -F'\t' '
NR==FNR { c=$1; sub(/^0x/,"",c); our[tolower($2)]=c; next }
{
	c=$1; sub(/^0x/,"",c); s=tolower($2);
	if (s in our) {
		if (our[s] != c) { mm++; print "MISMATCH\t"$2"\tkernel=0x"our[s]"\tmodule=0x"c }
		else ok++
	} else { miss++; print "NOT-EXPORTED\t"$2 }
}
END {
	print "=== SUMMARY ==="
	print "ok="ok+0"  mismatch="mm+0"  missing="miss+0
}
' "$OUR" "$MOD" | head -60
