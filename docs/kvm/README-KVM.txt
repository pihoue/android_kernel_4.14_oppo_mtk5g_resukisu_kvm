============================================================
 OPPO A55 5G (MT6833 / PFVM10) KVM 内核补丁记录
 内核分支: /home/moao/resukisu_kernel  (oppo/mtk_s_12.1)
============================================================

【v8】按酷安帖《MTK KVM running for Windows》打补丁
记录来源：酷安 jsbsbxjxh66，2026-06-02
记录结论：kernel-irqchip=off 是 4.14 内核太老所致（主线 5.9 才修），需 3 个补丁。

 [1] window-cachability-fix.patch (Alexander Graf)
      vgic_sanitise_outer_cacheability() default: nC -> SameAsInner
      状态: 本树已经是 SameAsInner，无需处理 (vgic-mmio-v3.c:290)
 [2] KVM: arm64: Remove stage-2 read permission fault check (Marc Zyngier)
      user_mem_abort() 删除 "Unexpected L2 read permission error"
      状态: 本树无此检查 (fault_is_perm / L2 read permission 全树无命中)
 [3] 0001-KVM-arm64-vgic-its-add-CTRL-RESET.patch
      uapi kvm.h: KVM_DEV_ARM_ITS_CTRL_RESET = 4
      vgic-its.c: free_device_list/free_collection_list、ITS reset、ctrl 分发、
                  BASER 失效清缓存、has_attr/set_attr 分支
      状态: 已打入 (0001-*.patch + 0002-*.patch，合并版 0001-KVM-arm64-vgic-its-add-CTRL-RESET.patch)

【v9】修复新版 QEMU (8.x) 无法在 4.14 上初始化 KVM vCPU
实测根因:
  (1) ID_AA64PFR0/PFR1/DFR0/ISAR0/ISAR1/MMFR0/MMFR1/MMFR2_EL1 未暴露给用户态
      -> KVM_GET_ONE_REG = -ENOENT
  (2) set_invariant_sys_reg() 对不匹配写入返回 -EINVAL
      -> QEMU 8.x 在 KVM_PUT_FULL_STATE 写回 ID 寄存器时直接退出:
         "Failed to put registers after init: Invalid argument"
补丁: 0003-KVM-arm64-expose-ID-registers.patch (arch/arm64/kvm/sys_regs.c)
  A) 新增 8 个 FUNCTION_INVARIANT(id_aa64*) getter (read_sysreg 取 host 真值)
  B) 按编码升序插入 invariant_sys_regs[]（该表有 BUG_ON(排序检查)）
  C) set_invariant_sys_reg() 改为静默接受写回（(void)val），guest 仍看到 host 真值

【编译与产物】
工具链: clang-r383902 = clang 11.0.1 (与厂商官方内核同版本)，厂商完整 config + KVM
脚本:  /tmp/build_v7.sh（v7 基础）/tmp/build_v8.sh /tmp/build_v9.sh
v8: Image.gz 18358158 B, BUILD_RC=0
v9: Image.gz 18357705 B, BUILD_RC=0
两者 module_layout CRC 均为 0x409fffae（与 v7 相同 -> 闭源 MTK 模块仍兼容）

 boot_kvm_v8.img  19916800 B  MD5 0feb15c2adc283f6c8357dcceb9ac772
 boot_kvm_v9.img  19916800 B  MD5 b8dfe95b808bbde36ed9d4d31268e2f3  <- 当前已刷入

【刷入 / 回滚】
 刷入 v9 : dd if=/sdcard/Download/Operit/tmp/boot_kvm_v9.img of=/dev/block/sdc44 bs=4096 && sync
 回 v8   : dd if=/sdcard/Download/Operit/tmp/boot_kvm_v8.img of=/dev/block/sdc44 bs=4096 && sync
 回 v7   : dd if=/sdcard/Download/Operit/tmp/boot_kvm_v7.img of=/dev/block/sdc44 bs=4096 && sync
 回原厂 : dd if=/sdcard/Download/Operit/tmp/backup/boot_before_v7.img of=/dev/block/sdc44 bs=4096 && sync

【重启后验证】
 bash /sdcard/Download/Operit/tmp/verify_v9.sh
 预期:
   1) ID_AA64PFR0_EL1 等 GET_OK（v8 及以前是 GET_ERR(2 ENOENT)）
   2) QEMU 8.2 用 -M virt,its=on -accel kvm -cpu host 能启动 guest 内核到用户态
      不再出现 "Failed to put registers after init"
      不再出现 "warning: ITS KVM: full reset is not supported by the host kernel"
   3) dmesg 仍有 kvm [1]: VHE mode initialized successfully

============================================================
[v10] CONFIG_MTK_CHARGER_UNLIMITED —— 结论：在本机无效，已还原
============================================================
目标: 用户要求"把内核快充打开"

【开关定位】
  drivers/power/supply/mediatek/charger/Kconfig:182
    config MTK_CHARGER_UNLIMITED  (bool "MediaTek Charger Unlimited")
    help: "Say Yes to release charging current restrictions" (放开充电电流限制)
  代码唯一使用点: mtk_charger.c:7153  #ifdef CONFIG_MTK_CHARGER_UNLIMITED
    -> info->usb_unlimited = true;
       info->enable_sw_safety_timer = false;
       charger_dev_enable_safety_timer(info->chg1_dev, false);

【关键结论: mtk_charger.c 在本机不参与编译】
  证据1) Makefile 分支
    drivers/power/supply/mediatek/charger/Makefile 是多分支结构。
    本机 CONFIG_OPLUS_CHARGER_MTK6833=y 命中第一个 OPLUS 分支:
      obj-y += charger_class.o mtk_switch_charging.o mtk_pdc_intf.o
               mtk_chg_type_det.o mtk_pe40_intf.o mtk_linear_charging.o
               adapter_class.o mtk_pd_adapter.o
               mtk_switch_charging2.o mtk_intf.o mtk_pe40.o mtk_pdc.o
    mtk_charger.o 只出现在最后的 else 分支 -> 本机不编译。
  证据2) kbuild 记录
    out/drivers/power/supply/mediatek/charger/.built-in.o.cmd 对象清单
    = 上述 12 个 .o，没有 mtk_charger.o
  证据3) 产物
    find out -name "mtk_charger*"  ->  空
  证据4) 调用链
    mtk_switch_charging_init2() 的唯一调用者 = mtk_charger.c:2863
    -> 整条 MTK 充电管理栈(含充电算法)在本机是"编译了但永不执行"的死代码

  => CONFIG_MTK_CHARGER_UNLIMITED 改与不改，对内核行为零影响。
     之前"只重编 3 个文件(kernel/configs.o, drivers/kernelsu/core/init.o,
     init/version.o)"不是 kbuild 的 bug：没有任何已编译文件用这个符号，
     本来就没有 .c 需要重编。

【附: 为何 vmlinux 里能搜到 usb_unlimited 字符串】
  out/vmlinux = 724MB，CONFIG_DEBUG_INFO=y。
  这些字符串来自 DWARF 的 struct 成员名
  (mtk_charger_intf.h: int usb_unlimited_current / bool usb_unlimited)，
  被已编译的 mtk_switch_charging2.o 等引用，与 mtk_charger.c 无关。

【本机充电的真实执行者: OPLUS 栈，且已完整启用】
  drivers/power/Makefile:4    obj-$(CONFIG_OPLUS_CHARGER) += oplus/
  out/drivers/power/oplus/ 已编译: oplus_charger.o oplus_vooc.o oplus_pps.o
    oplus_adapter.o oplus_wireless.o oplus_gauge.o oplus_short.o
    oplus_configfs.o oplus_chg_ops_manager.o + vooc_ic/* + voocphy/* + charger_ic/*
  OPLUS 栈内不存在 VOOC/PPS 的 Kconfig 开关(全树无命中)
  -> 它们是无条件编译的，不存在"打开"一说。

【与原厂配置对比】
  充电相关行 diff: 还原后 = 0 处差异。
  => 我们的内核在充电方面与原厂完全一致，没有误关任何东西。

【顺带查明的"死符号"(有 Kconfig 定义、无任何代码使用)】
  CONFIG_MTK_DISABLE_TEMP_PROTECT    (仅 drivers/power/Kconfig:191)
  CONFIG_OPLUS_FAST2NORMAL_CHG       (仅 drivers/power/Kconfig:283)
  CONFIG_OPLUS_SMOOTH_SOC            (无命中)
  CONFIG_OPLUS_FEATURE_CHARGERPRESENT (无命中)
  CONFIG_OPLUS_CHG_VOOC              (无命中)
  CONFIG_OPLUS_SMART_CHARGER_SUPPORT  唯一使用点也在未编译的 mtk_charger.c:5631
  -> 以上开关全部无效。

【处置】
  - out/.config 已还原为原厂状态 (CONFIG_MTK_CHARGER_UNLIMITED is not set)
  - 还原前的 v10 配置副本: /tmp/out_config_v10_kept.txt
  - v10 镜像(18,357,718 B, 12:45)与 v9 功能等价(仅 init/version.o 时间戳差异)
    -> 无需刷入；设备继续运行 v9。
  - 补丁 0004-config-MTK_CHARGER_UNLIMITED.patch 标记为【无效，未采用】

============================================================
[v11] 补全 QEMU 8.2 所需的全部 ID 寄存器 (sys_regs.c)
============================================================
背景: v9 把 8 个 ID_AA64* 暴露给用户态后, QEMU 8.2 反而更早失败:
      "Failed to retrieve host CPU features"
      (v9 之前是更晚的 "Failed to put registers after init")

【QEMU 8.2.2 源码分析 (target/arm/kvm64.c)】
  err = read_sys_reg64(fd, &id_aa64pfr0, ARM64_SYS_REG(3,0,0,4,0));
  if (unlikely(err < 0)) {
      /* Before v4.15, the kernel only exposed a limited number of system
       * registers, not including any of the interesting AArch64 ID regs. */
      ahcf->isar.id_aa64pfr0 = 0x00000011;   /* 回退默认值 */
      err = 0;                               /* 直接成功, 后面全部跳过 */
  } else {
      err |= read_sys_reg64(... id_aa64pfr1/smfr0/dfr0/dfr1/isar0/isar1/isar2
                                    /mmfr0/mmfr1/mmfr2/zfr0 ...);
      err |= read_sys_reg32(... id_pfr0/pfr1/dfr0/mmfr0..3/isar0..5
                                    /mmfr4/isar6/mvfr0/1/2/pfr2/dfr1/mmfr5 ...);
  }
  if (err < 0) return false;   /* -> "Failed to retrieve host CPU features" */

  -> v9 之前: PFR0 读不到 => 走回退分支, 什么都不再读 => 特征获取"成功",
     一直走到 put registers 才因 -EINVAL 失败 (v9 的容忍写回就是为此)
  -> v9 之后: PFR0 能读了 => 进入严格分支, 撞上没暴露的 MVFR0/1/2 等 => 更早失败

【两个关键细节 (均已核对源码)】
  1) read_sys_reg32() 内部:
        assert((id & KVM_REG_SIZE_MASK) == KVM_REG_SIZE_U64);
     即 QEMU 读 32 位 ID 寄存器时用的也是 U64 请求,
     所以内核里 "KVM_REG_SIZE != sizeof(u64) -> -ENOENT" 那道检查不挡路。
  2) 回写集合: kvm_arm_init_cpreg_list() 用 KVM_GET_REG_LIST 向内核要清单,
     再逐个 write_kvmstate_to_list() 读回 —— 所以回写集合 = 内核表里有什么。
     => 只要表项齐了, 读写两侧都满足。

【v11 改动 (只动 arch/arm64/kvm/sys_regs.c, 不动 sysreg.h)】
  新增 12 个表项 (invariant_sys_regs 共 39 项, 严格升序):
    32-bit 族: ID_MMFR4(2,6) ID_ISAR6(2,7) MVFR0(3,0) MVFR1(3,1) MVFR2(3,2)
               ID_PFR2(3,4) ID_DFR1(3,5) ID_MMFR5(3,6)
    64-bit 族: ID_AA64ZFR0(4,4) ID_AA64SMFR0(4,5) ID_AA64DFR1(5,1)
               ID_AA64ISAR2(6,2)
  12 个全部使用"返回 0"的 getter (FUNCTION_INVARIANT_ZERO):
    - clang-11 汇编器不认识部分 mrs 寄存器名
      (构建报 "<inline asm>:1:10: error: expected readable system register")
    - 这些寄存器在 A55(Armv8.2) 上未必已分配, 对未分配编码 MRS 是 UNDEFINED
    - 取值 0 == "该 ID 字段未实现", 对纯 AArch64 guest 无影响
  QEMU 只要求这些寄存器"读得到", 不要求具体取值。

【安全性核对 (避免开机 BUG_ON 变砖)】
  kvm_sys_reg_table_init(): BUG_ON(check_sysreg_table(invariant_sys_regs,...))
  check_sysreg_table(): for (i=1;i<n;i++) if (cmp_sys_reg(&t[i-1],&t[i]) >= 0) return 1;
  cmp_sys_reg() 比较次序: Op0 -> Op1 -> CRn -> CRm -> Op2   (sys_regs.h:102)
  => 要求严格递增; 补丁脚本自带同样的升序自检, 39 项全部通过。
  => 另: kvm_sys_reg_table_init() 用 .reset(NULL, &entry) 填 ->val,
     我们的 getter 不使用 vcpu 参数, 传 NULL 安全。

【构建与刷入】
  BUILD_RC=0, 0 error; 日志含 CC arch/arm64/kvm/sys_regs.o + LTO vmlinux.o
  Image.gz = 18,357,912 B
  module_layout CRC = 0x409fffae (未变, 闭源 MTK 模块兼容)
  boot_kvm_v11.img = 19,916,800 B
  MD5 = aafb4e9437b887fa3a41ad10b68b200e
  已刷入 /dev/block/sdc44, 回读 MD5 与镜像逐字节一致
  补丁: kvmpatches/0005-KVM-arm64-ID-regs-complete.patch
  脚本: kvmpatches/0005-apply-kvm-idregs-complete.py

【待验证 (重启后)】
  bash /sdcard/Download/Operit/tmp/verify_v9.sh
  预期: QEMU 8.2.2 能起来并进入 guest
        (不再报 Failed to retrieve host CPU features /
                Failed to put registers after init)

【v9 实测记录 (重启后跑 verify_v9.sh 的结果)】
  ID_AA64PFR0/PFR1/DFR0/ISAR0/MMFR0: GET_OK 且 SET_OK  (v9 补丁生效)
  QEMU 8.2.2 -M virt,its=on -accel kvm -cpu host:
      qemu-system-aarch64: Failed to retrieve host CPU features
  => 这正是 v11 要修的问题

【回滚】
  dd if=/sdcard/Download/Operit/tmp/boot_kvm_v9.img of=/dev/block/sdc44 bs=4096 && sync

============================================================
[v11 实测 + v12] PMCR_EL0 —— 最后一块拼图
============================================================
【v11 重启后实测 (开机时间 13:14)】
  ID 寄存器: QEMU 需要的 33 个全部可读 (MISSING = 0)  -> v11 生效 ✓
  QEMU 8.2.2 仍报: qemu-system-aarch64: Failed to retrieve host CPU features
  => 说明该函数里还有别的读取失败

【定位过程】
  QEMU 8.2 的 kvm_arm_get_host_cpu_features() 在 ID 寄存器之后还有一段
  (target/arm/kvm64.c:397-401):

      if (pmu_supported) {
          /* PMCR_EL0 is only accessible if the vCPU has feature PMU_V3 */
          err |= read_sys_reg64(fdarray[2], &ahcf->isar.reset_pmcr_el0,
                                ARM64_SYS_REG(3, 3, 9, 12, 0));
      }

  实测:
    KVM_CAP_ARM_PMU_V3(126) = 1   -> pmu_supported = true -> QEMU 会去读 PMCR_EL0
    PMCR_EL0 (3,3,9,12,0): KVM_GET_ONE_REG -> -ENOENT (errno 2)   <-- 就是它
    (PMCCNTR/PMOVS 可读; PMCEID0 不可读, 但 QEMU 不读它)

  ※ 踩过的坑: 一开始用同一个 vCPU 连续做 INIT 矩阵测试,
    得出 "target=5 + PMU_V3 -> EINVAL" 的错误结论。
    实际上一个 vCPU 只能被 KVM_ARM_VCPU_INIT 成功初始化一次,
    后续调用无论 features 为何都返回 EINVAL。
    (kvmprobe.py 每次新建 vCPU, 它的结论才是对的: PMU_V3 -> OK)

【内核层根因】
  arch/arm64/kvm/sys_regs.c:985
      { SYS_DESC(SYS_PMCR_EL0), access_pmcr, reset_pmcr, },   <-- 缺 .reg
  邻居全都有 .reg (PMCNTENSET_EL0 / PMCCNTR_EL0 / PMUSERENR_EL0 ...)

  而 index_to_sys_reg_desc() 末尾:
      r = find_reg(&params, sys_reg_descs, ARRAY_SIZE(sys_reg_descs));
      /* Not saved in the sys_reg array? */
      if (r && !r->reg)
          r = NULL;        <-- 直接被置空 -> 落到 invariant 表 -> ENOENT

  但 PMCR_EL0 的状态确实存在 vcpu_sys_reg(vcpu, PMCR_EL0) 里:
      sys_regs.c:480  reset_pmcr(): vcpu_sys_reg(vcpu, PMCR_EL0) = val;
      sys_regs.c:527/530/534  access_pmcr() 读写它
  => 这是该 vendor 树的一处真实缺陷 (状态存了, 却不给 ONE_REG 索引)

【v12 改动 (只改 1 行)】
      { SYS_DESC(SYS_PMCR_EL0), access_pmcr, reset_pmcr, PMCR_EL0 },

  补上 .reg = PMCR_EL0 后:
    - index_to_sys_reg_desc() 能找到它 -> KVM_GET_ONE_REG 返回
      reset_pmcr() 算出的合法复位值
    - 它也随之进入 KVM_GET_REG_LIST (QEMU 的 cpreg list)

【构建与刷入】
  BUILD_RC=0, 0 error; CC arch/arm64/kvm/sys_regs.o + LTO + GZIP
  Image.gz = 18,357,475 B
  module_layout CRC = 0x409fffae (未变)
  boot_kvm_v12.img = 19,916,800 B
  MD5 = f5942fa56e750d781880abac7654d279
  已刷入 /dev/block/sdc44, 回读一致
  补丁: kvmpatches/0006-PMCR_EL0-add-reg.patch
  脚本: kvmpatches/0006-apply-pmcr-reg.py

【待验证 (重启后)】
  bash /sdcard/Download/Operit/tmp/verify_v9.sh

  预期至此 QEMU 8.2.2 能起来, 路径是:
    1. 读 ID_AA64PFR0 成功 -> 进入严格分支
    2. 33 个 ID 寄存器齐全 (v11)                  ✓
    3. PMCR_EL0 可读 (v12)                        ✓
    4. err = 0 -> 宿主 CPU 特征获取成功
    5. kvm_arm_init_cpreg_list(): KVM_GET_REG_LIST + 逐个读回 (表项齐全) ✓
    6. KVM_PUT_FULL_STATE 回写: set_invariant_sys_reg() 容忍写回 (v9)    ✓
    7. guest 启动

【回滚】
  dd if=/sdcard/Download/Operit/tmp/boot_kvm_v11.img of=/dev/block/sdc44 bs=4096 && sync

===============================================================================
【v13】修复 "Failed to put registers after init: Invalid argument"（偶发失败）
===============================================================================
日期: 2026-09-13

■ 现象
  v12 之后 QEMU 8.2.2 已经能通过"获取宿主 CPU 特征"那一步，但在
  KVM_PUT_FULL_STATE 写回寄存器时随机报:
      qemu-system-aarch64: Failed to put registers after init: Invalid argument
  同一条命令有时成功、有时失败（偶发）。

■ 根因定位（纯用户态复现，不需要编译器 / LD_PRELOAD）
  tools/probe_reglist.py 完整复现了 QEMU 的写回循环:
    1) KVM_GET_REG_LIST 拿内核自报清单（本机 n = 424）
    2) 过滤出 QEMU 会同步的项（只排除 KVM_REG_ARM_CORE, coproc=0x0010）-> 208 个
    3) 逐个"读出来 -> 原值写回"，哪个 SET 返回 EINVAL 就是它
  打补丁前的唯一失败者:
    FAIL id=0x6020000000110000 coproc=0x0011 U32 GET_OK(0x701fe01a) SET_ERR(22 Invalid argument)
  即 KVM_REG_ARM_DEMUX（c15 CCSIDR）—— 207/208 个寄存器里唯一的失败项。
  两次运行分别得到 FAILS=1 与 FAILS=0，与"偶发"完全吻合。

  内核 arch/arm64/kvm/sys_regs.c 的 demux_c15_set():
      case KVM_REG_ARM_DEMUX_ID_CCSIDR:
          ...
          if (newval != get_ccsidr(val))     <-- 要求写回值 == 当前物理核的 CCSIDR
              return -EINVAL;

  本机 MIDR = 0x414fd0b0 (Cortex-A76)，天玑700 = A76 + A55 大小核，
  两簇 cache 几何不同 -> get_ccsidr() 返回 0x701fe01a(大核) 或 0x201fe01a(小核)。
  QEMU 的 kvm_arm_reg_syncs_via_cpreg_list() 只排除 CORE / SVE，DEMUX 会被纳入同步；
  内核 kvm_arm_num_sys_reg_descs() 也把 num_demux_regs() 计入 REG_LIST。
  于是"读回来"与"写回去"两次 ioctl 一旦落在不同簇 -> 值不等 -> EINVAL -> QEMU 报错。
  这就是"同一命令时好时坏"的原因（取决于 vCPU 线程调度落在哪一簇）。

■ 修复（v13）
  arch/arm64/kvm/sys_regs.c : demux_c15_set() 删掉严格比较，改为接受写入并忽略其值:
      -		if (newval != get_ccsidr(val))
      -			return -EINVAL;
      +		/*
      +		 * CCSIDR 是只读的宿主缓存几何视图，内核本就无法"设置"它，
      +		 * get 永远返回真实值。而在大小核(big.LITTLE)系统上，
      +		 * 生成该值的读操作与本次写回可能落在不同簇，两簇 CCSIDR 不同，
      +		 * 于是严格比较会让 QEMU 的 KVM_PUT_FULL_STATE 失败并报
      +		 * "Failed to put registers after init: Invalid argument"
      +		 * (demux 寄存器会通过 KVM_GET_REG_LIST 暴露并被原值写回)。
      +		 * 因此接受写入并忽略其值。
      +		 */
      +		(void)newval;
      		return 0;
  理由: CCSIDR 只是宿主缓存几何的只读视图，放宽比较不影响客户机可见行为，
        却能让 QEMU 的 PUT_FULL_STATE 不再随机失败。

  补丁: kvmpatches/0007-KVM-arm64-demux-relax-ccsidr-writeback.patch  (773 B)
        自校验: `patch -p1 --dry-run` OK，且应用后与实测文件逐字节相同
  脚本: kvmpatches/0007-apply-demux-relax.py（原始打补丁脚本）
        kvmpatches/tools/mk_v13_patch.py（由注入块反向重建 before 并生成正式 diff）

■ 构建与刷入
  BUILD_RC = 0, 0 error
  Image.gz = 18,358,230 B；module_layout CRC 仍为 0x409fffae（闭源 MTK 模块兼容性未变）
  boot_kvm_v13.img = 19,916,800 B，MD5 = 19c834dec1a35bb1d724bd74b35d0009
  刷入: dd if=/sdcard/Download/Operit/tmp/boot_kvm_v13.img of=/dev/block/sdc44 bs=4096 && sync
  回读: dd if=/dev/block/sdc44 bs=512 count=38900 | md5sum -> 19c834de... 一致 ✓
  重启后 /proc/version = "#9 SMP PREEMPT Sun Sep 13 15:14:47 CST 2026" ✓

■ 实测结果（v13, 2026-09-13）
  [1] ID 寄存器 (v11)                    33/33 可读, MISSING=0               ✓
  [2] PMCR_EL0  (v12)                    GET OK 0x00000000410b302c          ✓
  [3] 写回循环全量探针 tools/probe_reglist.py 连跑 3 次
      208 个寄存器，FAILS = 0 / 0 / 0（v12 时为 1 / 0 随机）                  ✓
  [4] DEMUX 正向确认 tools/probe_demux.py
      demux regs in REG_LIST = 4，4/4 GET+SET OK                             ✓
        id=0x6020000000110000 U32 GET_OK(0x701fe01a) SET_OK
        id=0x6020000000110001 U32 GET_OK(0x201fe01a) SET_OK
        id=0x6020000000110002 U32 GET_OK(0x703fe03a) SET_OK
        id=0x6020000000110004 U32 GET_OK(0x707fe07a) SET_OK
      （0x701fe01a vs 0x201fe01a 正是大/小核两簇不同的 CCSIDR）
  [5] verify_v9.sh 端到端
      "===== GUEST INITRAMFS SHELL RUNNING ON KVM ====="，日志无任何 Failed to ✓
  [6] 回归压测 A 组（旧失败形态 -serial null）x6
      A_PASS = 6/6，stderr 全干净                                            ✓
  [7] 回归压测 B 组（-serial stdio x3）
      3/3 guest 都正常启动到 shell 提示符，无任何 Failed to                    ✓
      注: 管道一次性喂入的命令会丢（QEMU 非 tty stdin + pl011 无输入 FIFO），
          属测试方法问题，与内核无关
  [8] E2E 复测 tools/e2e_v13_fixed.sh（延迟 8s 再喂命令）x3
      E2E_FIXED_PASS = 3/3，rc=0，guest 交互正常:
        ~ # uname -m            -> aarch64        (guest: Alpine 6.6.134-0-virt)
        ~ # echo ---E2E_DONE--- -> ---E2E_DONE---
        QEMU 随 guest poweroff 正常退出                                       ✓

■ 结论
  QEMU 8.2.2 在本机（-M virt,its=on -accel kvm -cpu host）可**稳定**启动 guest
  虚拟机，不再出现:
    "Failed to retrieve host CPU features"
    "Failed to put registers after init: Invalid argument"
  v8/v9/v11/v12/v13 五处补丁共同构成完整修复链:
    v8  = vgic ITS CTRL_RESET
    v9  = 暴露 8 个 ID_AA64* 寄存器 + 容忍写回
    v11 = 补全 33 个 ID 寄存器（QEMU 8.2 严格分支全部需要）
    v12 = PMCR_EL0 补 .reg 索引（否则 KVM_GET_ONE_REG 返回 -ENOENT）
    v13 = 放宽 demux CCSIDR 写回（消除"偶发 Invalid argument"）

■ 本轮新增工具（kvmpatches/tools/）
  probe_reglist.py   复现 QEMU 写回循环，定位"哪一个寄存器写回失败"
  probe_demux.py     正向确认 DEMUX(coproc=0x0011) 的 GET/SET 是否成功
  stability_v13.sh   回归压测（-serial null x6 + -serial stdio x3）
  e2e_v13_fixed.sh   完整 E2E 复测（延迟喂命令，3 次）
  mk_v13_patch.py    由注入块反向重建 before，用 difflib 生成正式 unified diff

【回滚】
  v13 -> v12: dd if=/sdcard/Download/Operit/tmp/boot_kvm_v12.img of=/dev/block/sdc44 bs=4096 && sync
  v13 -> v11: dd if=/sdcard/Download/Operit/tmp/boot_kvm_v11.img of=/dev/block/sdc44 bs=4096 && sync
  更早: v9 / v8 / v7 同理
  原始可引导备份: /sdcard/Download/Operit/tmp/backup/boot_before_v7.img

================================================================
【归档位置说明】本记录中出现的 kvmpatches/xxx.patch 现对应归档:
  patches/xxx.patch         [内核补丁]
  tools/xxx-apply-*.py      [打补丁脚本]
  kvmpatches/tools/*.py  ->  tools/*.py
归档根目录: /sdcard/Download/Operit/kvm_mt6833/
镜像: images/boot_kvm_v13.img 当前 / v12 / v11 回滚
================================================================
