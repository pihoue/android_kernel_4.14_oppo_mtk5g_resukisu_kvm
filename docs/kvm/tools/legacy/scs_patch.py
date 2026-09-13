#!/usr/bin/env python3
# Enable CONFIG_SHADOW_CALL_STACK with GCC.
#
# The vendor modules (bt_drv_connac1x, wlan_drv_gen4m, ...) were built with
# clang's Shadow Call Stack (because the stock kernel sets
# CONFIG_SHADOW_CALL_STACK=y).  Every one of their function prologues does
# "str x30, [x18], #8", so the kernel MUST keep x18 pointing at a valid
# per-task shadow stack, otherwise the module writes to a random address.
#
# Two things block that with GCC:
#   1. the top-level Makefile force-disables SCS for non-clang compilers
#      (clang-specific-configs list)
#   2. CC_FLAGS_SCS uses -fsanitize=shadow-call-stack, which GCC rejects
# arch/arm64/Makefile already adds -ffixed-x18 when SCS=y, so simply dropping
# the unsupported sanitize flag gives us a correct SCS setup.

import sys

MK = "/home/moao/resukisu_kernel/Makefile"
CFG = "/home/moao/resukisu_kernel/out/.config"


def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape") as f:
        return f.read()


def wr(p, d):
    with open(p, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(d)


mk = rd(MK)

# 1) keep SCS enabled even though we compile with GCC
old = "clang-specific-configs := LTO_CLANG CFI_CLANG SHADOW_CALL_STACK INIT_STACK_ALL"
new = "clang-specific-configs := LTO_CLANG CFI_CLANG INIT_STACK_ALL"
if old in mk:
    mk = mk.replace(old, new, 1)
    print("PATCH1 ok: SCS no longer force-disabled")
elif new in mk:
    print("PATCH1 already applied")
else:
    print("PATCH1 FAILED: clang-specific-configs line not found")
    sys.exit(1)

# 2) -fsanitize=shadow-call-stack is clang-only -> make it optional
old = "CC_FLAGS_SCS\t:= -fsanitize=shadow-call-stack"
if old in mk:
    mk = mk.replace(old, "CC_FLAGS_SCS\t:= $(call cc-option,-fsanitize=shadow-call-stack)", 1)
    print("PATCH2 ok: sanitize flag now optional")
elif "CC_FLAGS_SCS\t:= $(call cc-option," in mk:
    print("PATCH2 already applied")
else:
    print("PATCH2 WARN: CC_FLAGS_SCS line not matched, dumping context:")
    for line in mk.splitlines():
        if "CC_FLAGS_SCS" in line:
            print("   >>", repr(line))
    sys.exit(1)

wr(MK, mk)

# 3) enable the option in .config
cfg = rd(CFG)
if "CONFIG_SHADOW_CALL_STACK=y" in cfg:
    print("PATCH3 already enabled")
else:
    if "# CONFIG_SHADOW_CALL_STACK is not set" in cfg:
        cfg = cfg.replace("# CONFIG_SHADOW_CALL_STACK is not set", "CONFIG_SHADOW_CALL_STACK=y")
    else:
        cfg += "\nCONFIG_SHADOW_CALL_STACK=y\n"
    wr(CFG, cfg)
    print("PATCH3 ok: CONFIG_SHADOW_CALL_STACK=y")

print("ALL PATCHES DONE")
