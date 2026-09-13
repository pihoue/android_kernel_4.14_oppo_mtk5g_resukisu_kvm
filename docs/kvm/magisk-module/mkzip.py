#!/usr/bin/env python3
# Build a flashable KernelSU/Magisk module zip from a module source dir.
import os
import sys
import zipfile

src = sys.argv[1] if len(sys.argv) > 1 else "/sdcard/Download/Operit/tmp/kvm_access"
out = sys.argv[2] if len(sys.argv) > 2 else "/sdcard/Download/Operit/tmp/kvm_access.zip"

if os.path.exists(out):
    os.remove(out)

z = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
count = 0
for root, dirs, files in os.walk(src):
    dirs.sort()
    for f in sorted(files):
        p = os.path.join(root, f)
        arc = os.path.relpath(p, src).replace(os.sep, "/")
        st = os.stat(p)
        # /sdcard is FUSE and does not keep permission bits -> force sane modes
        mode = st.st_mode & 0o7777
        base = arc.rsplit("/", 1)[-1]
        if base.endswith(".sh") or base in ("update-binary", "updater-script"):
            mode = 0o755
        else:
            mode = 0o644
        zi = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
        zi.create_system = 3                      # Unix -> external_attr = unix mode
        zi.external_attr = (mode & 0xFFFF) << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        with open(p, "rb") as fh:
            z.writestr(zi, fh.read())
        print("  + %-56s mode=%o size=%d" % (arc, mode, st.st_size))
        count += 1
z.close()
print("ZIP_OK files=%d -> %s (%d bytes)" % (count, out, os.path.getsize(out)))

# verification: module.prop must be at zip root
with zipfile.ZipFile(out) as zz:
    names = zz.namelist()
print("ROOT_HAS_MODULE_PROP =", "module.prop" in names)
print("ENTRIES =", names)