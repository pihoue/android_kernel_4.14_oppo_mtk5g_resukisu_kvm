==============================================================================
 OPPO A55 5G (PFVM10 / MT6833) KVM 内核改造包 —— 刷入说明 (v13)
==============================================================================
设备: OPPO A55 5G  PFVM10 (OP522D)  天玑700 MT6833  Android 12
内核: 4.14.186+  分支 oppo/mtk_s_12.1  工具链 clang-r383902 (clang 11.0.1)
版本: v13  (#9 SMP PREEMPT Sun Sep 13 15:14:47 CST 2026)

------------------------------------------------------------------------------
一、包内容
------------------------------------------------------------------------------
  images/boot_kvm_v13.img      最终产物 · 可直接 dd 刷入的 boot 镜像 (19,916,800 B)
                               MD5 19c834dec1a35bb1d724bd74b35d0009
  images/Image.gz              最终产物 · 内核压缩镜像 (18,358,230 B)
  images/boot_kvm_v12.img      回滚镜像 (MD5 f5942fa56e750d781880abac7654d279)
  images/boot_kvm_v11.img      回滚镜像 (MD5 aafb4e9437b887fa3a41ad10b68b200e)
  flash.sh                     刷入脚本 (含自动回读校验/回滚模式)
  patches/                     内核补丁 0001~0007 (v8~v13 全部改动)
  tools/                       打补丁脚本 / 探针 / 压测 / 编译脚本 / 早期工具
  kernel-source/               已打好 v8~v13 全部补丁的内核源码 (不含 out/ 与 .git)
                               all-changes-vs-vendor.patch = 相对原厂的全部改动
                               BUILD-INFO.txt = 分支/commit/工具链/编译命令
  refs/                        QEMU 8.2.2 上游源码参考、补丁前原始文件、各版本 config
  logs/                        编译日志 + 设备侧验证原始日志
  gpt/                     ★★ 让 KVM 能运行的核心: 改好的分区表 + 原厂备份 + GZ 工具
                               pgpt4k_nogz.bin  (改好的, 要刷的) MD5 c3fdbe48…
                               pgpt4k_orig.bin  (原厂, 用于还原) MD5 5b4cffd9…
                               GPT-CHANGES.txt  原理 + 逐字节改动 + 刷入/还原/验证命令
                               tools/           patch_gz_gpt.py 等 GZ 相关工具
  flash-gpt.sh             GPT(分区表) 刷入脚本 (写前自动备份 / 写后回读比对 / --restore)
  magisk-module/               kvm_access Magisk 模块 (放开 /dev/kvm 访问, 含 zip)
  MANIFEST.txt                 归档清单 (含 SHA256/MD5)
  README.txt                   v8~v13 完整补丁记录 (根因/验证数据/回滚)

------------------------------------------------------------------------------
【重要】前置条件:必须先处理 GPT(分区表),否则刷了内核 KVM 也起不来
------------------------------------------------------------------------------
本机 MTK GenieZone(GZ) 运行在 EL2 并占住它,而 KVM 也需要 EL2。
必须先让 GZ 不加载(改 GPT 里的 gz1/gz2 分区 LBA),再刷内核镜像。
若设备尚未做过这一步:
      su -c "sh flash-gpt.sh"          # 详细原理/还原见本文件第七节与 gpt/GPT-CHANGES.txt
  确认:
      dd if=/dev/block/sdc bs=4096 count=64 | md5sum
      # 期望 c3fdbe48dccb5ceae2dfeebec1e87398  (= 已处理)
      # 原厂则为 5b4cffd99cf0d40e9038ba870024e985

------------------------------------------------------------------------------
二、刷入内核 (需要 root)
------------------------------------------------------------------------------
  方式 A · 用脚本 (推荐, 自带 MD5 校验与回读比对)
      cd <本包目录>
      su -c "sh flash.sh"                  # 刷 v13
      su -c "sh flash.sh --rollback"       # 回滚到 v12

  方式 B · 手动
      su
      dd if=images/boot_kvm_v13.img of=/dev/block/sdc44 bs=4096
      sync
      # 回读校验 (前 19,916,800 字节)
      dd if=/dev/block/sdc44 bs=512 count=38900 | md5sum
      # 期望: 19c834dec1a35bb1d724bd74b35d0009
      reboot

  说明: /dev/block/sdc44 是本机 boot 分区 (33,554,432 B)。
        boot 镜像只覆盖前 19,916,800 字节, 不做整分区擦写。

------------------------------------------------------------------------------
三、回滚 (任选一)
------------------------------------------------------------------------------
  1) su -c "sh flash.sh --rollback"                         -> v12
  2) dd if=images/boot_kvm_v12.img of=/dev/block/sdc44 bs=4096 && sync   -> v12
  3) dd if=images/boot_kvm_v11.img of=/dev/block/sdc44 bs=4096 && sync   -> v11
  4) 原始可引导备份 (完整 33 MB 分区镜像, 最保险)
     dd if=/sdcard/Download/Operit/tmp/backup/boot_before_v7.img of=/dev/block/sdc44 bs=4096 && sync
     MD5 = 917a1cd69d3d3f440281e5f321fc11aa

------------------------------------------------------------------------------
四、刷完怎么验证
------------------------------------------------------------------------------
  1) 内核版本
       cat /proc/version        # 应看到 "#9 SMP PREEMPT Sun Sep 13 15:14:47 CST 2026"
  2) KVM 设备
       ls -l /dev/kvm           # crw-rw-rw- root root 10,232
  3) 寄存器探针 (在设备上的 Ubuntu/proot 终端里, 需要 python3)
       python3 tools/probe_reglist.py    # 期望: 208 regs, FAILS = 0
       python3 tools/probe_demux.py      # 期望: demux 4/4 GET+SET OK
  4) 端到端启动 guest (需要 qemu-system-aarch64 8.x 与 guest 内核/initrd)
       bash tools/verify_v9.sh
       # 期望看到: ===== GUEST INITRAMFS SHELL RUNNING ON KVM =====
       # 且日志中不应出现:
       #   Failed to retrieve host CPU features
       #   Failed to put registers after init: Invalid argument

------------------------------------------------------------------------------
五、这套补丁解决了什么 (概览, 详见 README.txt)
------------------------------------------------------------------------------
  v8  vgic ITS CTRL_RESET                 -> 允许 -M virt,its=on
  v9  暴露 8 个 ID_AA64* 寄存器 + 容忍写回  -> 让 QEMU 8.x 进入严格特征分支
  v11 补全 33 个 ID 寄存器                 -> "Failed to retrieve host CPU features" 消失
  v12 PMCR_EL0 补 .reg 索引                -> QEMU 8.2 首次成功启动 guest
  v13 放宽 demux CCSIDR 写回               -> "Failed to put registers after init" 彻底消除
  结论: QEMU 8.2.2 (-M virt,its=on -accel kvm -cpu host) 可稳定启动 guest
        (实测 guest: Alpine Linux 6.6.134-0-virt aarch64; E2E 3/3 通过)

  v10 的 "内核快充" (CONFIG_MTK_CHARGER_UNLIMITED) 经证明在本机是死开关,
      已回滚, 补丁 0004 仅作留档 (标记未采用)。

------------------------------------------------------------------------------
六、重新编译 (在 Linux 编译主机上)
------------------------------------------------------------------------------
  源码: kernel-source/ (已含全部补丁)   产物输出: out/arch/arm64/boot/Image.gz
  1) 依赖 clang-r383902 (clang 11.0.1) 与 GNU 工具链
  2) bash tools/build_v11.sh            # 脚本内含完整 CC/LD/CLANG_TRIPLE 参数
  3) 打包成 boot 镜像 (工作目录内需要 ramdisk/ 与 dtb/ unpacked 结构):
     python3 mkbootimg.py --kernel Image.gz --ramdisk unpacked/ramdisk --dtb unpacked/dtb \
        --cmdline "bootopt=64S3,32N2,64N2 buildvariant=user" \
        --base 0x40000000 --kernel_offset 0x00080000 --ramdisk_offset 0x11100000 \
        --tags_offset 0x07c80000 --dtb_offset 0x07c80000 \
        --os_version 12.0.0 --os_patch_level 2025-03 \
        --pagesize 2048 --header_version 2 -o boot_kvm_vXX.img
==============================================================================------------------------------------------------------------------------------
七、GPT(分区表) —— 让 KVM 能运行的核心步骤
------------------------------------------------------------------------------
  原理:
    MTK 的 GenieZone(GZ) 安全虚拟化层运行在 EL2,本机 GPT 中有两个专用分区:
        #39  gz1   LBA 0x43900 - 0x458ff   (32 MB)
        #40  gz2   LBA 0x45900 - 0x478ff   (32 MB)
    preloader / LK 启动时按分区名查到它们并加载 GZ 镜像 → GZ 占住 EL2 →
    KVM 无法运行(只刷内核补丁 v8~v13 也起不来)。
    改法: 把 gz1/gz2 的 First/Last LBA 改成越界地址, LK 读取时 I/O 失败 →
    GZ 不加载 → EL2 空出来给 KVM。

  改的文件(与原厂逐字节比对, 仅 22 字节不同):
        gpt/pgpt4k_nogz.bin   (= 设备当前 GPT, MD5 c3fdbe48dccb5ceae2dfeebec1e87398)
        gpt/pgpt4k_orig.bin   (= 原厂备份,      MD5 5b4cffd99cf0d40e9038ba870024e985)
        差异 = GPT 头 CRC32 + 分区表 CRC32 重算 + gz1/gz2 的 LBA 字段;
        分区名/类型 GUID/其它 51 个分区完全未动。

  刷入 / 还原 / 检查:
        su -c "sh flash-gpt.sh"             # 刷入 NoGZ GPT (写前自动备份当前 GPT)
        su -c "sh flash-gpt.sh --restore"   # 还原原厂 GPT (GZ 回归, KVM 将不可用)
        su -c "sh flash-gpt.sh --check"     # 只查看当前是哪一版

  手动:
        dd if=gpt/pgpt4k_nogz.bin of=/dev/block/sdc bs=4096 count=64 && sync
        dd if=/dev/block/sdc bs=4096 count=64 | md5sum   # 期望 c3fdbe48…

  说明:  /dev/block/sdc 为整块 eMMC 用户区; 只写前 64×4096 = 256 KB
         (GPT 头 + 128 条分区表项), 不触碰任何分区数据。
         本机实测当前回读 MD5 = c3fdbe48dccb5ceae2dfeebec1e87398 ✓

  完整细节(含 22 字节差异位置、上游工具说明)见: gpt/GPT-CHANGES.txt
  相关工具: gpt/tools/  (patch_gz_gpt.py / detect_gz_bypass.py / detect_lk_gz.py /
                        patch_tee_vcp.py / patch_vendor_boot.py / README.md)
==============================================================================