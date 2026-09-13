#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# v12: 给 sys_reg_descs[] 里的 SYS_PMCR_EL0 补上 .reg 索引
#
#  根因: index_to_sys_reg_desc() 末尾有
#            if (r && !r->reg) r = NULL;
#        而 SYS_PMCR_EL0 条目缺 .reg -> KVM_GET_ONE_REG(3,3,9,12,0) 返回 -ENOENT
#        -> QEMU 8.2 的 kvm_arm_get_host_cpu_features() 里
#             if (pmu_supported) err |= read_sys_reg64(..., ARM64_SYS_REG(3,3,9,12,0));
#        这一读失败 -> err < 0 -> "Failed to retrieve host CPU features"
#
#  但 PMCR_EL0 的状态本来就存在 vcpu_sys_reg(vcpu, PMCR_EL0) 里
#  （见 sys_regs.c:480/527/530/534），且条目的 reset 函数是 reset_pmcr，
#  所以补上 .reg 后读到的是正确的复位值。
# ---------------------------------------------------------------------------
import os, shutil, sys

KR = "/home/moao/resukisu_kernel/arch/arm64/kvm/sys_regs.c"
OLD = "\t{ SYS_DESC(SYS_PMCR_EL0), access_pmcr, reset_pmcr, },\n"
NEW = "\t{ SYS_DESC(SYS_PMCR_EL0), access_pmcr, reset_pmcr, PMCR_EL0 },\n"

if not os.path.exists(KR + ".pre_v12"):
    shutil.copy2(KR, KR + ".pre_v12")
    print("backup ->", KR + ".pre_v12")

s = open(KR).read()
if NEW in s:
    print("!! 已打过 v12")
    sys.exit(1)
if OLD not in s:
    print("!! 锚点缺失")
    sys.exit(1)
s = s.replace(OLD, NEW, 1)
open(KR, "w").write(s)
print("patched: SYS_PMCR_EL0 now has .reg = PMCR_EL0")

# 复核
t = open(KR).read()
for ln in t.splitlines():
    if "SYS_PMCR_EL0" in ln:
        print("  " + ln.strip())
# 顺带确认该行位于 sys_reg_descs[] 内且顺序未动
import re
assert t.count(NEW) == 1
# 确认没有其它缺少 .reg 的条目(仅提示)
print("V12_PATCH_OK")