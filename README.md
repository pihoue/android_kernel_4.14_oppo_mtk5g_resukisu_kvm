# OPPO A55 5G (MT6833) — KVM 化内核 · 分支 `oppo/mtk_12.1_kvm`

> 机型 **OPPO A55 5G PFVM10 (OP522D)** · 天玑700 **MT6833** · Android 12
> 内核 **4.14.186+** · 工具链 **clang-r383902 (clang 11.0.1)**
> 当前版本 **v13**（内核串 `#9 SMP PREEMPT Sun Sep 13 15:14:47 CST 2026`）
> 基线仓库 [AkinaHaruka/android_kernel_4.14_oppo_mtk5g_resukisu](https://github.com/AkinaHaruka/android_kernel_4.14_oppo_mtk5g_resukisu)（已集成 Re-SukiSU）

本分支是上述 4.14 厂商内核的 **KVM 改造版**：让 **QEMU 8.x** 能在真机上以

```bash
qemu-system-aarch64 -M virt,its=on -accel kvm -cpu host ...
```

**稳定**启动 guest 虚拟机。

实测 guest：Alpine Linux `6.6.134-0-virt`（aarch64），端到端复测 **3/3 通过**，日志中不再出现：

```
Failed to retrieve host CPU features
Failed to put registers after init: Invalid argument
```

---

## 1. 前置条件：必须先处理 GPT（否则刷了内核 KVM 也起不来）

MTK 的 **GenieZone（GZ）** 安全虚拟化层运行在 **EL2**，而 KVM 也需要 EL2。本机 GPT 中有两个专用分区被 preloader / LK 用来加载 GZ：

| 分区 | LBA 范围 | 大小 |
|---|---|---|
| `#39 gz1` | `0x43900 – 0x458ff` | 32 MB |
| `#40 gz2` | `0x45900 – 0x478ff` | 32 MB |

**做法**：把 gz1/gz2 的 First/Last LBA 改成越界地址，LK 读取时 I/O 失败 → GZ 不加载 → EL2 空出来给 KVM。

- 改动文件与原厂逐字节比对**仅 22 字节不同**（GPT 头 CRC32 + 分区表 CRC32 + gz1/gz2 的 LBA 字段），其余 51 个分区、分区名与类型 GUID 完全未动。
- GPT 位于 `/dev/block/sdc`（整块 eMMC 用户区）开头，只写前 `64 × 4096 = 256 KB`，不触碰任何分区数据。

```bash
# 当前是否已处理
dd if=/dev/block/sdc bs=4096 count=64 | md5sum
# 已处理(NoGZ): c3fdbe48dccb5ceae2dfeebec1e87398
# 原厂(GZ 生效): 5b4cffd99cf0d40e9038ba870024e985
```

刷入 / 还原脚本（`flash-gpt.sh`）与两个 GPT 镜像随发布包提供，详见 `docs/kvm/README-FLASH.txt` 第七节。

---

## 2. 补丁链 v8 → v13

五处内核补丁共同构成完整修复链，全部集中在 `arch/arm64/kvm/`、`virt/kvm/arm/`：

| 版本 | 改动 | 解决的问题 |
|---|---|---|
| **v8** | `vgic-its` 增加 `CTRL_RESET`（含 uapi `KVM_DEV_ARM_ITS_CTRL_RESET`） | 允许 `-M virt,its=on`；消除 `full reset is not supported by the host kernel` |
| **v9** | 暴露 8 个 `ID_AA64*` 寄存器 + `set_invariant_sys_reg()` 容忍写回 | QEMU 8.x 不再卡在 `PUT_FULL_STATE` 的 `-EINVAL` |
| **v11** | 补全 33 个 ID 寄存器（`invariant_sys_regs[]` 共 39 项，严格升序） | 消除 `Failed to retrieve host CPU features` |
| **v12** | `PMCR_EL0` 表项补 `.reg` 索引（1 行） | `KVM_GET_ONE_REG` 由 `-ENOENT` 变为可读 |
| **v13** | 放宽 `demux_c15_set()` 的 CCSIDR 写回校验 | 消除大小核之间偶发的 `Failed to put registers after init: Invalid argument` |

要点摘录：

- **v11**：该表有 `BUG_ON(check_sysreg_table(...))` 严格升序检查，补丁按 `Op0→Op1→CRn→CRm→Op2` 编码升序插入；12 个新增项使用「返回 0」getter（clang-11 汇编器不认识部分 `mrs` 寄存器名，且未分配编码的 MRS 是 UNDEFINED，取值 0 == 该 ID 字段未实现，对纯 AArch64 guest 无影响）。
- **v12**：`sys_reg_descs[]` 中 `PMCR_EL0` 缺 `.reg`，导致 `index_to_sys_reg_desc()` 把它置空并回退到 invariant 表 → `KVM_GET_ONE_REG` 返回 `-ENOENT`；而 `reset_pmcr()` / `access_pmcr()` 其实一直在读写 `vcpu_sys_reg(vcpu, PMCR_EL0)`，属该 vendor 树的真实缺陷。PMU_V3 可用时 QEMU 一定会读它。
- **v13**：`tools/probe_reglist.py` 纯用户态复现了 QEMU 的写回循环 —— `KVM_GET_REG_LIST` 得到 424 项，过滤出 QEMU 会同步的 208 项后逐个「读出来 → 原值写回」。修复前唯一失败项是 `KVM_REG_ARM_DEMUX`（c15 CSSIDR）；A76+A55 大小核两簇 `CCSIDR` 不同（`0x701fe01a` / `0x201fe01a`），读与写两次 ioctl 落在不同簇时严格比较即 `-EINVAL`。CCSIDR 本身只是宿主缓存几何的只读视图，故接受写入并忽略其值。

> `v10`（`CONFIG_MTK_CHARGER_UNLIMITED` 快充开关）经排查证实为**死开关**（`mtk_charger.c` 在本机配置下根本不参与编译，本机充电由 OPLUS 栈无条件执行），已还原，补丁 0004 仅作留档，**未采用**。

---

## 3. 编译

源码即本分支（已含全部补丁），产物为 `out/arch/arm64/boot/Image.gz`。

```bash
export PATH=$PWD/toolchains/clang/bin:$PWD/toolchains/gcc64/bin:$PATH
export ARCH=arm64
export CLANG_PREBUILT_BIN=$PWD/toolchains/clang/bin
export LINUX_GCC_CROSS_COMPILE_PREBUILTS_BIN=$PWD/toolchains/gcc64/bin
export KCFLAGS="-fno-builtin-stpcpy -Wno-error=pointer-to-int-cast -Wno-pointer-to-int-cast -Wno-strict-prototypes -Wno-error=strict-prototypes"

MAKEARGS="O=out ARCH=arm64 CC=clang LD=ld.lld \
  LD_LIBRARY_PATH=$PWD/toolchains/clang/lib64 AR=llvm-ar NM=llvm-nm \
  OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip \
  CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-androidkernel-"

make -j32 $MAKEARGS olddefconfig
make -j32 $MAKEARGS Image.gz
```

完整脚本见发布包 `tools/build_v11.sh`（v11/v12/v13 共用），编译信息另见仓库内 `BUILD-INFO.txt` 与 `BUILD-CONFIG.txt`。

打包 boot：

```bash
python3 mkbootimg.py --kernel Image.gz --ramdisk unpacked/ramdisk --dtb unpacked/dtb \
  --cmdline "bootopt=64S3,32N2,64N2 buildvariant=user" \
  --base 0x40000000 --kernel_offset 0x00080000 --ramdisk_offset 0x11100000 \
  --tags_offset 0x07c80000 --dtb_offset 0x07c80000 \
  --os_version 12.0.0 --os_patch_level 2025-03 \
  --pagesize 2048 --header_version 2 -o boot_kvm_v13.img
```

> `module_layout` CRC 全程保持 `0x409fffae` 不变，闭源 MTK 模块兼容性未受影响。

---

## 4. 刷入 / 回滚

boot 分区为 **`/dev/block/sdc44`（33,554,432 B）**，镜像只覆盖前 **19,916,800** 字节，不做整分区擦写。

```bash
# 刷入 v13（推荐用脚本，自带 MD5 校验 + 回读比对 + --rollback）
su -c "sh flash.sh"

# 手动
su -c "dd if=images/boot_kvm_v13.img of=/dev/block/sdc44 bs=4096 && sync"
su -c "dd if=/dev/block/sdc44 bs=512 count=38900 | md5sum"   # 期望 19c834de…

# 回滚
su -c "sh flash.sh --rollback"                                # -> v12
```

| 镜像 | 大小 | MD5 |
|---|---|---|
| `boot_kvm_v13.img`（当前） | 19,916,800 B | `19c834dec1a35bb1d724bd74b35d0009` |
| `boot_kvm_v12.img` | 19,916,800 B | `f5942fa56e750d781880abac7654d279` |
| `boot_kvm_v11.img` | 19,916,800 B | `aafb4e9437b887fa3a41ad10b68b200e` |

---

## 5. 验证

```bash
cat /proc/version                     # #9 SMP PREEMPT Sun Sep 13 15:14:47 CST 2026
ls -l /dev/kvm                        # crw-rw-rw- root root 10,232
python3 tools/probe_reglist.py        # 208 regs, FAILS = 0
python3 tools/probe_demux.py          # demux 4/4 GET+SET OK
bash    tools/verify_v9.sh            # ===== GUEST INITRAMFS SHELL RUNNING ON KVM =====
```

v13 实测结果（2026-09-13）：

| 项 | 结果 |
|---|---|
| ID 寄存器（v11） | 33/33 可读，MISSING = 0 ✓ |
| PMCR_EL0（v12） | GET OK `0x00000000410b302c` ✓ |
| 写回循环探针（v13） | 连跑 3 次，FAILS = 0 / 0 / 0（v12 时随机 1 / 0） ✓ |
| DEMUX 正向确认 | REG_LIST 中 4 个，4/4 GET+SET OK ✓ |
| E2E 端到端 | 3/3 通过，guest 内 `uname -m` = `aarch64` ✓ |
| 回归压测 | `-serial null` ×6 全过；`-serial stdio` ×3 全过 ✓ |

> 另注：普通 App 域访问 `/dev/kvm` 需要 SELinux 策略放行。发布包提供 KernelSU/Magisk 模块 **`kvm_access`**（经 `sepolicy.rule` 于开机注入策略，不改只读分区）。App 域已实测可 `open` `/dev/kvm`、拿到 api_version 12、创建 vm/vcpu 并 `mmap` vCPU 成功。

---

## 6. 仓库内文档

| 路径 | 内容 |
|---|---|
| `BUILD-INFO.txt` | 分支 / 基线 commit / 版本 / 编译脚本 |
| `BUILD-CONFIG.txt` | 编译所用的完整 `.config` |
| `docs/kvm/README-KVM.txt` | v8~v13 完整技术记录（根因、验证数据、回滚） |
| `docs/kvm/README-FLASH.txt` | 刷入 / 回滚 / 验证 / GPT 处理的完整说明 |
| `docs/kvm/MANIFEST.txt` | 发布归档清单（含各镜像 SHA256/MD5） |
| `docs/kvm/RELEASE-INFO.txt` | 发布压缩包结构与解压/使用说明 |
| `docs/kvm/README-upstream-resukisu.md` | 上游（Re-SukiSU）原 README 备份 |
| `drivers/kernelsu` → `../KernelSU/kernel` | Re-SukiSU 内核侧集成软链（`KernelSU/` 目录按 `.gitignore` 不入库） |
| `kernel/cfi_compat.c` | 为兼容闭源 MTK 模块而加的 CFI 兼容层 |

## 7. 未包含在本分支的发布物料

`boot` 镜像、内核补丁文件、GPT 分区表、Magisk 模块、探针/压测脚本、编译与设备日志、QEMU 参考源码等，均打包在发布归档 **`kvm_mt6833_v13_full.tar.xz`** 中：

```
kvm_mt6833_v13_20260913/
├── images/     boot_kvm_v13.img / Image.gz / v12 / v11
├── gpt/        pgpt4k_nogz.bin · pgpt4k_orig.bin · GPT-CHANGES.txt · tools/
├── patches/    0001~0007（v8/v9/v10 留档/v11/v12/v13）
├── tools/      打补丁脚本 · 探针 · 压测 · 编译脚本
├── magisk-module/ kvm_access（源码 + 可刷 zip）
├── refs/ logs/ flash.sh flash-gpt.sh README*.txt MANIFEST.txt
```

（本分支的 `.gitignore` 忽略 `*.patch`，故补丁文件未入库；如需一并纳管请告知。）

---

## 8. 上游说明（保留）

- **SUSFS 不可用**：与 ReSukiSU 所用版本存在重大 API 差异，回移风险过高，当前不可用；仅 Re-SukiSU 可正常工作。
- **稳定性与安全的取舍**：为强制兼容 MTK 闭源内核模块，`MODULE_SIG`、`MODVERSION`、`CLANG CFI` 实际上被绕过/失效（CFI 钩子已物理中和，内核对所有间接跳转放行）。使用本内核即表示接受可能的安全风险与不可预测的内核崩溃，**风险自负**。
- 上游原文完整保留在 `docs/kvm/README-upstream-resukisu.md`。
- 使用 SukiSU 时请避免把 Hybrid Mount 作为元模块，可能导致无法开机；若已循环启动，可连按音量上+下（Vol-）≥3 次进入安全模式。

## 9. 许可

沿用上游：**禁止在修改后闭源，禁止用于商业用途**；**禁止用于任何在线竞技游戏的作弊**。
