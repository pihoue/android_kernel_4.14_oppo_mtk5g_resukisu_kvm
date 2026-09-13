#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# v11 (rev C): 12 个新增 ID 寄存器全部使用"返回 0"的 getter
#
#  原因:
#   1) clang-11 的汇编器不认识部分 mrs 寄存器名（构建报
#      "<inline asm>:1:10: error: expected readable system register"）
#   2) MVFR0/1/2、ID_MMFR4/ISAR6、ID_PFR2/DFR1/MMFR5 以及
#      ID_AA64ZFR0/SMFR0/DFR1/ISAR2 在 A55(Armv8.2) 上未必已分配，
#      对未分配编码执行 MRS 是 UNDEFINED —— 风险不值得冒
#
#  QEMU 8.2 只需要这些寄存器"读得到"（否则 err<0，直接报
#  "Failed to retrieve host CPU features" 退出）；取值 0 表示"该 ID 字段未实现"，
#  对纯 AArch64 guest 无任何影响。
# ---------------------------------------------------------------------------
import os, re, shutil, sys

K  = "/home/moao/resukisu_kernel"
SR = K + "/arch/arm64/include/asm/sysreg.h"
KR = K + "/arch/arm64/kvm/sys_regs.c"


def rd(p):
    return open(p).read()


def wr(p, s):
    open(p, "w").write(s)


# 还原（保证 sysreg.h 不动）
if os.path.exists(SR + ".pre_v11"):
    shutil.copy2(SR + ".pre_v11", SR)
    print("sysreg.h restored")
if os.path.exists(KR + ".pre_v11"):
    shutil.copy2(KR + ".pre_v11", KR)
    print("sys_regs.c restored")

s = rd(KR)

anchor = "FUNCTION_INVARIANT(id_aa64mmfr2_el1)\n"
if anchor not in s:
    print("!! getter 锚点缺失")
    sys.exit(1)

NEW = [
    "id_mmfr4_el1", "id_isar6_el1", "mvfr0_el1", "mvfr1_el1", "mvfr2_el1",
    "id_pfr2_el1", "id_dfr1_el1", "id_mmfr5_el1",
    "id_aa64zfr0_el1", "id_aa64smfr0_el1", "id_aa64dfr1_el1", "id_aa64isar2_el1",
]

lines = [
    "",
    "/*",
    " * 以下 12 个 ID 寄存器是 QEMU 8.2 的 kvm_arm_get_host_cpu_features() 在能读到",
    " * ID_AA64PFR0_EL1 之后会一并读取的（进入\"严格分支\"）。任何一个返回 -ENOENT，",
    " * QEMU 都会以 \"Failed to retrieve host CPU features\" 退出。",
    " *",
    " * 这些寄存器在 Cortex-A55(Armv8.2) 上未必已分配编码，且 clang-11 的汇编器",
    " * 不认识其中部分寄存器名，因此统一返回 0 —— 这正是\"ID 字段未实现\"的架构取值。",
    " */",
    "#define FUNCTION_INVARIANT_ZERO(reg)\t\t\t\t\\",
    "\tstatic void get_##reg(struct kvm_vcpu *v,\t\t\\",
    "\t\t\t      const struct sys_reg_desc *r)\t\t\\",
    "\t{\t\t\t\t\t\t\t\\",
    "\t\t((struct sys_reg_desc *)r)->val = 0;\t\t\\",
    "\t}",
]
lines += ["FUNCTION_INVARIANT_ZERO(%s)" % n for n in NEW]
lines += [""]
s = s.replace(anchor, anchor + "\n".join(lines), 1)

ISAR6   = "sys_reg(3, 0, 0, 2, 7)"
PFR2    = "sys_reg(3, 0, 0, 3, 4)"
DFR1_32 = "sys_reg(3, 0, 0, 3, 5)"
MMFR5   = "sys_reg(3, 0, 0, 3, 6)"
ZFR0    = "sys_reg(3, 0, 0, 4, 4)"
SMFR0   = "sys_reg(3, 0, 0, 4, 5)"
ISAR2   = "sys_reg(3, 0, 0, 6, 2)"

tbl = [
    ("\t{ SYS_DESC(SYS_ID_ISAR5_EL1), NULL, get_id_isar5_el1 },\n",
     "\t{ SYS_DESC(SYS_ID_MMFR4_EL1), NULL, get_id_mmfr4_el1 },\n"
     "\t{ SYS_DESC(%s), NULL, get_id_isar6_el1 },\n" % ISAR6, "after"),
    ("\t{ SYS_DESC(SYS_ID_AA64PFR0_EL1), NULL, get_id_aa64pfr0_el1 },\n",
     "\t{ SYS_DESC(SYS_MVFR0_EL1), NULL, get_mvfr0_el1 },\n"
     "\t{ SYS_DESC(SYS_MVFR1_EL1), NULL, get_mvfr1_el1 },\n"
     "\t{ SYS_DESC(SYS_MVFR2_EL1), NULL, get_mvfr2_el1 },\n"
     "\t{ SYS_DESC(%s), NULL, get_id_pfr2_el1 },\n" % PFR2 +
     "\t{ SYS_DESC(%s), NULL, get_id_dfr1_el1 },\n" % DFR1_32 +
     "\t{ SYS_DESC(%s), NULL, get_id_mmfr5_el1 },\n" % MMFR5, "before"),
    ("\t{ SYS_DESC(SYS_ID_AA64PFR1_EL1), NULL, get_id_aa64pfr1_el1 },\n",
     "\t{ SYS_DESC(%s), NULL, get_id_aa64zfr0_el1 },\n" % ZFR0 +
     "\t{ SYS_DESC(%s), NULL, get_id_aa64smfr0_el1 },\n" % SMFR0, "after"),
    ("\t{ SYS_DESC(SYS_ID_AA64DFR0_EL1), NULL, get_id_aa64dfr0_el1 },\n",
     "\t{ SYS_DESC(SYS_ID_AA64DFR1_EL1), NULL, get_id_aa64dfr1_el1 },\n", "after"),
    ("\t{ SYS_DESC(SYS_ID_AA64ISAR1_EL1), NULL, get_id_aa64isar1_el1 },\n",
     "\t{ SYS_DESC(%s), NULL, get_id_aa64isar2_el1 },\n" % ISAR2, "after"),
]
for a2, add, mode in tbl:
    if a2 not in s:
        print("!! 表锚点缺失:", a2.strip())
        sys.exit(1)
    s = s.replace(a2, (a2 + add) if mode == "after" else (add + a2), 1)

wr(KR, s)
print("sys_regs.c patched (12 zero getters + 12 entries)")

# --- 自检 ---
t = rd(SR)
enc = {}
for m in re.finditer(
        r"#define\s+(SYS_\w+)\s+sys_reg\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", t):
    enc[m.group(1)] = tuple(int(m.group(i)) for i in range(2, 7))
body = re.search(r"invariant_sys_regs\[\]\s*=\s*\{(.*?)\n\};", s, re.S).group(1)
items = []
for m in re.finditer(r"SYS_DESC\(\s*(SYS_\w+|sys_reg\([^)]*\))\s*\)", body):
    tok = m.group(1)
    if tok in enc:
        items.append((tok, enc[tok]))
    else:
        g = re.match(r"sys_reg\(([\d, ]+)\)", tok)
        items.append((tok, tuple(int(x) for x in g.group(1).split(","))))
print("table entries:", len(items))
prev = None
ok = True
for n, e in items:
    if prev is not None and e <= prev[1]:
        print("  !! 顺序错误:", prev, "->", n, e)
        ok = False
    prev = (n, e)
assert ok, "顺序自检失败"
# 确认没有任何 mrs 依赖未知名字
assert "FUNCTION_INVARIANT(id_mmfr4_el1)" not in s
print("顺序自检通过: 严格升序, %d 项" % len(items))
print("V11_REVC_PATCH_OK")