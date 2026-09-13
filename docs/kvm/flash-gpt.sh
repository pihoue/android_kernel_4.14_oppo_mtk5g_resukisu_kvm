#!/system/bin/sh
# ============================================================================
#  OPPO A55 5G (PFVM10 / MT6833)  GPT(分区表) 刷入脚本  —— 让 KVM 能运行的核心
#  作用: 把 gz1/gz2 两个 GenieZone 分区的 LBA 改为越界 → LK 加载 GZ 失败
#        → EL2 空出来给 KVM。不改分区名/其它分区, 只写 eMMC 前 256 KB。
#
#  用法:  su -c "sh flash-gpt.sh"            刷入 改好的 NoGZ GPT
#         su -c "sh flash-gpt.sh --restore"  还原 原厂 GPT
#         su -c "sh flash-gpt.sh --check"    只查看当前状态
# ============================================================================
DEV=/dev/block/sdc                 # eMMC 用户区 (GPT 在其 0 偏移)
DIR=$(dirname "$0")
PATCHED="$DIR/gpt/pgpt4k_nogz.bin"
ORIG="$DIR/gpt/pgpt4k_orig.bin"
MD5_PATCHED=c3fdbe48dccb5ceae2dfeebec1e87398
MD5_ORIG=5b4cffd99cf0d40e9038ba870024e985

cur_md5() { dd if=$DEV bs=4096 count=64 2>/dev/null | md5sum | awk '{print $1}'; }

CUR=$(cur_md5)
echo "== 当前 GPT MD5 : $CUR"
echo "   NoGZ 版本    : $MD5_PATCHED   $([ "$CUR" = "$MD5_PATCHED" ] && echo '<== 当前已是' || echo '')"
echo "   原厂 版本    : $MD5_ORIG    $([ "$CUR" = "$MD5_ORIG" ] && echo '<== 当前是原厂' || echo '')"

[ "$1" = "--check" ] && exit 0

if [ "$1" = "--restore" ]; then
    IMG="$ORIG"; EXP=$MD5_ORIG; LOOKUP="原厂"
    echo "== 还原模式: 写回原厂 GPT (GZ 将重新加载, KVM 会再次不可用)"
else
    IMG="$PATCHED"; EXP=$MD5_PATCHED; LOOKUP="NoGZ"
    echo "== 刷入模式: 写入 NoGZ GPT (EL2 让给 KVM)"
fi

[ -f "$IMG" ] || { echo "!! 找不到 $IMG  中止"; exit 1; }

# 写前自动备份当前 GPT 到 sdcard
SAFE=/sdcard/gpt_backup_$(date +%Y%m%d_%H%M%S)_$CUR.bin
dd if=$DEV of="$SAFE" bs=4096 count=64 2>/dev/null && echo "== 已备份当前 GPT: $SAFE"

echo "== 写入 $LOOKUP GPT ..."
dd if="$IMG" of=$DEV bs=4096 count=64 || { echo "!! dd 失败, 中止"; exit 1; }
sync

NEW=$(cur_md5)
echo "== 回读 MD5 : $NEW"
echo "== 期望 MD5 : $EXP"
if [ "$NEW" = "$EXP" ]; then
    echo "== [OK] GPT 写入成功, 重启生效: reboot"
else
    echo "== [FAIL] 回读不一致! 立即还原:"
    echo "          dd if=$SAFE of=$DEV bs=4096 count=64 && sync && reboot"
fi