#!/bin/bash
# v13 稳定性压测
#  A) 用之前"必失败"的 -serial null 形态跑 6 次: 判断 stderr 里有没有
#     "Failed to put registers after init" / "Failed to retrieve host CPU features"
#  B) 用 -serial stdio + 管道命令跑 3 次完整 E2E: 判断 guest 标记是否出现
set -u
K=/root/kvmtest
Q=/usr/bin/qemu-system-aarch64
COMMON="-M virt,its=on -accel kvm -cpu host -m 1024 -display none -no-reboot -nic none"

echo "===== A) -serial null x6 (旧失败形态) ====="
apass=0
for i in 1 2 3 4 5 6; do
    rm -f /tmp/sn_err_$i.log
    printf 'echo HI\npoweroff -f\n' \
      | timeout 20 $Q $COMMON -serial null -kernel $K/Image -initrd $K/initrd.gz \
          -append "console=ttyAMA0 rdinit=/init" > /tmp/sn_err_$i.log 2>&1
    rc=$?
    if grep -qi "Failed to" /tmp/sn_err_$i.log; then
        echo "  run $i: FAIL (rc=$rc)"; sed -n '1,4p' /tmp/sn_err_$i.log
    else
        echo "  run $i: OK   (rc=$rc, stderr clean)"
        apass=$((apass+1))
    fi
done
echo "A_PASS=$apass/6"

echo
echo "===== B) -serial stdio x3 (完整 E2E) ====="
bpass=0
for i in 1 2 3; do
    rm -f /tmp/e2e_out_$i.log
    printf 'echo E2E_MARK_%s\nuname -m\necho ---E2E_DONE---\npoweroff -f\n' "$i" \
      | timeout 150 $Q $COMMON -serial stdio -kernel $K/Image -initrd $K/initrd.gz \
          -append "console=ttyAMA0 rdinit=/init" > /tmp/e2e_out_$i.log 2>&1
    rc=$?
    if grep -q "E2E_MARK_$i" /tmp/e2e_out_$i.log && grep -q -- "---E2E_DONE---" /tmp/e2e_out_$i.log \
       && ! grep -qi "Failed to" /tmp/e2e_out_$i.log; then
        echo "  run $i: PASS (rc=$rc)"
        bpass=$((bpass+1))
    else
        echo "  run $i: FAIL (rc=$rc)"
        grep -i "Failed to" /tmp/e2e_out_$i.log | head -3
        tail -6 /tmp/e2e_out_$i.log
    fi
done
echo "B_PASS=$bpass/3"
echo "STABILITY_DONE"
