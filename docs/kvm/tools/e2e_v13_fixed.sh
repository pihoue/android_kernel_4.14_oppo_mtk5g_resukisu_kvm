#!/bin/bash
# v13 E2E 复测(修正输入时序): guest 起串口后再喂命令
set -u
K=/root/kvmtest
Q=/usr/bin/qemu-system-aarch64
COMMON="-M virt,its=on -accel kvm -cpu host -m 1024 -display none -no-reboot -nic none"

pass=0
for i in 1 2 3; do
    rm -f /tmp/e2efix_$i.log
    { sleep 8; printf 'echo E2E_MARK_%s\nuname -m\necho ---E2E_DONE---\npoweroff -f\n' "$i"; } \
      | timeout 120 $Q $COMMON -serial stdio -kernel $K/Image -initrd $K/initrd.gz \
          -append "console=ttyAMA0 rdinit=/init" > /tmp/e2efix_$i.log 2>&1
    rc=$?
    if grep -q "E2E_MARK_$i" /tmp/e2efix_$i.log && grep -q -- "---E2E_DONE---" /tmp/e2efix_$i.log; then
        if grep -qi "Failed to" /tmp/e2efix_$i.log; then
            echo "  run $i: FAIL-GUESTTALEN? (rc=$rc) 有 Failed to"
        else
            echo "  run $i: PASS (rc=$rc) guest 交互正常, KVM 无错误"
            pass=$((pass+1))
        fi
    else
        echo "  run $i: FAIL (rc=$rc)"
        grep -i "Failed to" /tmp/e2efix_$i.log | head -3
        tail -5 /tmp/e2efix_$i.log
    fi
done
echo "E2E_FIXED_PASS=$pass/3"
echo "E2E_FIXED_DONE"