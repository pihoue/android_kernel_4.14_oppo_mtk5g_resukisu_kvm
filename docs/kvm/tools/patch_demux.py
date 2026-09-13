#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# v13: 放宽 demux_c15_set() 的 CCSIDR 严格比较
#
# 现象: QEMU 8.2 `-cpu host` 偶发/必现
#         qemu-system-aarch64: Failed to put registers after init: Invalid argument
#
# 链路:
#   1. QEMU 的 kvm_arm_reg_syncs_via_cpreg_list() 只排除 KVM_REG_ARM_CORE 和
#      KVM_REG_ARM64_SVE，因此 KVM_REG_ARM_DEMUX(CCSIDR) 会被纳入 cpreg 列表
#      （src: target/arm/kvm64.c:645）
#   2. 内核把它列进 KVM_GET_REG_LIST
#      （arch/arm64/kvm/sys_regs.c: kvm_arm_num_sys_reg_descs() += num_demux_regs()）
#   3. QEMU 先 read（write_kvmstate_to_list），稍后再原值写回
#      （write_list_to_kvmstate）
#   4. 内核 demux_c15_set() 里:
#          if (newval != get_ccsidr(val)) return -EINVAL;
#      而 get_ccsidr() 读的是**当前所在物理核**的 CCSIDR。
#      本项目 SoC（天玑700 = A76 + A55 大小核）两簇 cache 几何不同，
#      两次 ioctl 一旦落在不同簇 -> 值不等 -> EINVAL
#   5. QEMU 的 write_list_to_kvmstate() 因此 ok=false -> kvm_arch_put_registers()
#      返回 -EINVAL -> 报错退出
#
# 实测: 同一个 208 寄存器"读->原值写回"探针，两次运行分别得到 FAILS=1 与 FAILS=0，
#       唯一可能失败的就是 demux CCSIDR，证明其依赖调用发生在哪个簇。
#
# 语义说明: CCSIDR 是只读的宿主缓存几何视图，内核无法"设置"它，
#           get 永远返回真实值，因此放宽比较不会改变任何客户机可见行为。
# ---------------------------------------------------------------------------
import os, shutil, sys

KR = "/home/moao/resukisu_kernel/arch/arm64/kvm/sys_regs.c"

OLD = ("\t\tif (newval != get_ccsidr(val))\n"
       "\t\t\treturn -EINVAL;\n")

NEW = ("\t\t/*\n"
       "\t\t * CCSIDR 是只读的宿主缓存几何视图，内核本就无法\"设置\"它，\n"
       "\t\t * get 永远返回真实值。而在大小核(big.LITTLE)系统上，\n"
       "\t\t * 生成该值的读操作与本次写回可能落在不同簇，两簇 CCSIDR 不同，\n"
       "\t\t * 于是严格比较会让 QEMU 的 KVM_PUT_FULL_STATE 失败并报\n"
       "\t\t * \"Failed to put registers after init: Invalid argument\"\n"
       "\t\t * (demux 寄存器会通过 KVM_GET_REG_LIST 暴露并被原值写回)。\n"
       "\t\t * 因此接受写入并忽略其值。\n"
       "\t\t */\n"
       "\t\t(void)newval;\n")

if not os.path.exists(KR + ".pre_v13"):
    shutil.copy2(KR, KR + ".pre_v13")
    print("backup ->", KR + ".pre_v13")

s = open(KR).read()
if "(void)newval;" in s:
    print("!! 已打过 v13")
    sys.exit(1)
if OLD not in s:
    print("!! 锚点缺失")
    sys.exit(1)
s = s.replace(OLD, NEW, 1)
open(KR, "w").write(s)
print("patched: demux_c15_set() no longer returns -EINVAL on mismatch")

# 复核
t = open(KR).read()
i = t.find("static int demux_c15_set")
print("----- demux_c15_set() 现状 -----")
print(t[i:i + 950])
print("V13_PATCH_OK")