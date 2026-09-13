#!/usr/bin/env python3
# ---------------------------------------------------------------
# v13: 生成 demux_c15_set() 放宽 CCSIDR 写回的正式 unified diff
# 做法: 把当前文件里的注入块反向还原成上游原始 3 行 -> 得到 "before",
#       current = "after", 用 difflib 求统一 diff (行号取自 before)
# ---------------------------------------------------------------
import difflib
import re

SRC = "/home/moao/resukisu_kernel/arch/arm64/kvm/sys_regs.c"
OUT = "/tmp/v13_demux_relax.patch"
REL = "arch/arm64/kvm/sys_regs.c"

cur = open(SRC).read()

# 注入块: 从注释起始到 (void)newval;
pat = re.compile(
    r"\t\t/\*\n"
    r"\t\t \* CCSIDR.*?"
    r"\t\t\(void\)newval;\n",
    re.DOTALL)

m = pat.search(cur)
if not m:
    raise SystemExit("ERROR: 未找到 v13 注入块, 文件可能未打补丁")

ORIG = ("\t\tif (newval != get_ccsidr(val))\n"
        "\t\t\treturn -EINVAL;\n")

before = cur[:m.start()] + ORIG + cur[m.end():]
after = cur

if before == after:
    raise SystemExit("ERROR: before == after")

print("=== 注入块字符数:", m.end() - m.start())
print("=== 还原为原始行:", ORIG.encode().decode('unicode_escape').strip('\n'))

diff = difflib.unified_diff(
    before.splitlines(keepends=True),
    after.splitlines(keepends=True),
    fromfile="a/" + REL,
    tofile="b/" + REL,
    n=3)

txt = "".join(diff)
if not txt.endswith("\n"):
    txt += "\n"

open(OUT, "w").write(txt)

# 同时保存 before/after 原件, 便于日后核对
open("/tmp/v13_sys_regs.before.c", "w").write(before)
open("/tmp/v13_sys_regs.after.c", "w").write(after)

print("=== 写完:", OUT, len(txt), "bytes")
print(txt)