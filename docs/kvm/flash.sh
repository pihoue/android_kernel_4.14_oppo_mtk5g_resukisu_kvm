#!/system/bin/sh
# ============================================================================
#  OPPO A55 5G (PFVM10 / MT6833)  KVM 内核镜像刷入脚本   —— v13
#  用法:  su -c "sh flash.sh"                 (刷同目录 images/boot_kvm_v13.img)
#         su -c "sh flash.sh <镜像路径>"       (刷指定镜像)
#         su -c "sh flash.sh --rollback"       (回滚到 v12)
# ============================================================================
BOOT=/dev/block/sdc44            # boot 分区 (33,554,432 B)
DIR=$(dirname "$0")
IMG_DEFAULT="$DIR/images/boot_kvm_v13.img"
IMG_ROLLBACK="$DIR/images/boot_kvm_v12.img"
EXPECT_MD5=19c834dec1a35bb1d724bd74b35d0009     # boot_kvm_v13.img (v13)

if [ "$1" = "--rollback" ]; then
    IMG="$IMG_ROLLBACK"
    EXPECT_MD5=f5942fa56e750d781880abac7654d279
    echo "== 回滚模式: v13 -> v12"
else
    IMG=${1:-$IMG_DEFAULT}
fi

echo "== 目标分区 : $BOOT"
echo "== 镜像     : $IMG"
[ -f "$IMG" ] || { echo "!! 镜像不存在, 中止"; exit 1; }

M=$(md5sum "$IMG" | awk '{print $1}')
echo "== 镜像 MD5 : $M"
echo "== 期望 MD5 : $EXPECT_MD5"
[ "$M" = "$EXPECT_MD5" ] || echo "!! 警告: MD5 与发行记录不一致, 请先确认镜像来源"

echo "== 写入中..."
dd if="$IMG" of=$BOOT bs=4096 || { echo "!! dd 失败, 中止"; exit 1; }
sync

echo "== 回读校验中..."
R=$(dd if=$BOOT bs=512 count=38900 2>/dev/null | md5sum | awk '{print $1}')
echo "== 回读 MD5 : $R"
if [ "$R" = "$M" ]; then
    echo "== [OK] 写入成功且校验一致, 执行 reboot 生效"
else
    echo "== [FAIL] 回读不一致! 不要重启, 立即用整分区备份重刷:"
    echo "          dd if=/sdcard/Download/Operit/tmp/backup/boot_before_v7.img of=$BOOT bs=4096 && sync"
fi