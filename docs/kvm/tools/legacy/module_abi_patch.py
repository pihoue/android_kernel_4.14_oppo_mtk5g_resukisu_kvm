#!/usr/bin/env python3
# Restore the module ABI that MTK's closed-source modules were built for.
#
# Those modules were compiled against a kernel with CONFIG_CFI_CLANG=y, which
# adds one extra pointer ("cfi_check_fn cfi_check") to "struct module".  A
# kernel without CFI has a struct module that is 8 bytes shorter, so the
# module loader reads mod->init / mod->exit / ... at the wrong offsets: the
# modules appear to load fine (finit_module returns 0) but their init function
# is never called, so no devices are registered - which is exactly why
# /dev/wmtWifi, /dev/stpbt and friends are missing and WiFi/Bluetooth cannot
# come up.
#
# Keeping the field unconditionally makes the layout - and therefore the
# "module_layout" CRC - match the CFI kernel the vendor modules expect.

import sys

CFI = "/home/moao/resukisu_kernel/include/linux/cfi.h"
MOD = "/home/moao/resukisu_kernel/include/linux/module.h"


def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape") as f:
        return f.read()


def wr(p, d):
    with open(p, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(d)


# --- 1) make the cfi_check_fn typedef available without CONFIG_CFI_CLANG ---
cfi = rd(CFI)
old = """#ifdef CONFIG_CFI_CLANG
#ifdef CONFIG_MODULES
typedef void (*cfi_check_fn)(uint64_t, void *, void *);
"""
new = """#ifdef CONFIG_MODULES
typedef void (*cfi_check_fn)(uint64_t, void *, void *);
#endif

#ifdef CONFIG_CFI_CLANG
#ifdef CONFIG_MODULES
"""
if old in cfi:
    cfi = cfi.replace(old, new, 1)
    wr(CFI, cfi)
    print("PATCH1 ok: typedef now available without CFI")
elif new in cfi:
    print("PATCH1 already applied")
else:
    print("PATCH1 FAILED: pattern not found in cfi.h")
    sys.exit(1)

# --- 2) keep the struct module field unconditionally ---
mod = rd(MOD)
old = """#ifdef CONFIG_CFI_CLANG
\tcfi_check_fn cfi_check;
#endif"""
new = """\t/*
\t * Always present - even without CONFIG_CFI_CLANG - so that the
\t * struct module layout (and hence the module_layout CRC) matches a
\t * clang-CFI kernel. MTK's prebuilt modules are built for such a
\t * kernel and would otherwise resolve mod->init to a wrong offset.
\t */
\tcfi_check_fn cfi_check;"""
if old in mod:
    mod = mod.replace(old, new, 1)
    wr(MOD, mod)
    print("PATCH2 ok: cfi_check field now unconditional")
elif "Always present - even without CONFIG_CFI_CLANG" in mod:
    print("PATCH2 already applied")
else:
    print("PATCH2 FAILED: pattern not found in module.h")
    sys.exit(1)

print("ALL PATCHES DONE")