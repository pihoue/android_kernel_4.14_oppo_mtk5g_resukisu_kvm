#!/usr/bin/env python3
# Make "struct module" layout match a clang-CFI kernel.
#
# MTK's prebuilt modules were built for a kernel with CONFIG_CFI_CLANG=y,
# which adds "cfi_check_fn cfi_check;" to struct module.  Without CFI our
# struct module is 8 bytes shorter, so the loader reads mod->init at a wrong
# offset: the modules load fine but their init never runs (no /dev/wmtWifi,
# no /dev/stpbt -> no WiFi/BT).
#
# This script (a) makes the cfi_check_fn typedef available when CFI is off and
# (b) always includes the field, so layout + module_layout CRC match.

import sys

CFI = "/home/moao/resukisu_kernel/include/linux/cfi.h"
MOD = "/home/moao/resukisu_kernel/include/linux/module.h"
TAG = "OPERIT"


def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape") as f:
        return f.read()


def wr(p, d):
    with open(p, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(d)


# ---------------------------------------------------------------- cfi.h ----
cfi = rd(CFI)
if TAG + ": typedef" in cfi:
    print("PATCH1 already applied")
else:
    anchor = "#include <linux/stringify.h>\n"
    if anchor not in cfi:
        anchor = "#define _LINUX_CFI_H\n"
    if anchor not in cfi:
        print("PATCH1 FAILED - cfi.h head follows:")
        print(repr(cfi[:300]))
        sys.exit(1)
    add = anchor + (
        "\n/* " + TAG + ": typedef kept available without CFI so that\n"
        " * struct module keeps the same layout (and module_layout CRC) as a\n"
        " * clang-CFI build - required by MTK's prebuilt modules. */\n"
        "#ifndef CONFIG_CFI_CLANG\n"
        "#ifdef CONFIG_MODULES\n"
        "typedef void (*cfi_check_fn)(uint64_t, void *, void *);\n"
        "#endif\n"
        "#endif\n"
    )
    cfi = cfi.replace(anchor, add, 1)
    wr(CFI, cfi)
    print("PATCH1 ok: typedef available without CFI")

# ------------------------------------------------------------- module.h ----
mod = rd(MOD)
if TAG + ": field" in mod:
    print("PATCH2 already applied")
else:
    applied = False
    for decl in ("\tcfi_check_fn cfi_check;\n", "        cfi_check_fn cfi_check;\n"):
        old = "#ifdef CONFIG_CFI_CLANG\n" + decl + "#endif"
        if old in mod:
            new = (
                "\t/* " + TAG + ": field kept unconditionally - matches the layout\n"
                "\t * and module_layout CRC of the clang-CFI kernel MTK's\n"
                "\t * prebuilt modules were built against. */\n"
                + decl
            )
            mod = mod.replace(old, new, 1)
            applied = True
            print("PATCH2 ok: field now unconditional")
            break
    if not applied:
        print("PATCH2 FAILED - struct module context follows:")
        idx = mod.find("\tcfi_check_fn cfi_check;")
        print(repr(mod[max(0, idx - 120):idx + 120]))
        sys.exit(1)
    wr(MOD, mod)

print("ALL PATCHES DONE")