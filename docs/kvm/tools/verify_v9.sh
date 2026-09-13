#!/bin/bash
# ---------------------------------------------------------------
# v9 内核验证：QEMU 8.x + ITS reset 是否修好
# 在 Operit 的 Ubuntu(proot) 终端里执行：bash /sdcard/Download/Operit/tmp/verify_v9.sh
# ---------------------------------------------------------------
set -u
K=/root/kvmtest
D=/sdcard/Download/Operit/kvm_mt6833/tools
Q=/usr/bin/qemu-system-aarch64

echo "############ 0. 内核版本 ############"
cat /proc/version

echo
echo "############ 1. KVM 状态 ############"
dmesg 2>/dev/null | grep -i "kvm \[" | head -5
ls -l /dev/kvm

echo
echo "############ 2. ID_AA64* 寄存器探针（v8 之前应全部 ENOENT） ############"
if [ -f "$D/kvmprobe.py" ]; then
    python3 "$D/kvmprobe.py" 2>&1 | head -40
else
    python3 - <<'PYEOF'
import fcntl, os, struct
KVM_GET_ONE_REG = 0x4010AEAB
KVM_SET_ONE_REG = 0x4010AEAC
KVM_REG_ARM64 = 0x6000000000000000
KVM_REG_SIZE_U64 = 0x0030000000000000
KVM_REG_ARM64_SYSREG = 0x00130000
def enc(op0, op1, crn, crm, op2):
    return KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM64_SYSREG | \
           (op0 << 14) | (op1 << 11) | (crn << 7) | (crm << 3) | op2
regs = {
    "MIDR_EL1":        enc(3, 0, 0, 0, 0),
    "ID_AA64PFR0_EL1": enc(3, 0, 0, 4, 0),
    "ID_AA64PFR1_EL1": enc(3, 0, 0, 4, 1),
    "ID_AA64DFR0_EL1": enc(3, 0, 0, 5, 0),
    "ID_AA64ISAR0_EL1":enc(3, 0, 0, 6, 0),
    "ID_AA64ISAR1_EL1":enc(3, 0, 0, 6, 1),
    "ID_AA64MMFR0_EL1":enc(3, 0, 0, 7, 0),
    "ID_AA64MMFR1_EL1":enc(3, 0, 0, 7, 1),
    "ID_AA64MMFR2_EL1":enc(3, 0, 0, 7, 2),
}
fd = os.open("/dev/kvm", os.O_RDWR)
kvmfd = fd
print("open(/dev/kvm) =", fd)
print("api_version =", fcntl.ioctl(kvmfd, 0xAE00, 0))
vm = fcntl.ioctl(kvmfd, 0xAE01, 0)
print("vm_fd =", vm)
# KVM_ARM_VCPU_INIT: guest type = 5 (GENERIC_V8)
init_blob = struct.pack("=IIII", 5, 0, 0, 0)
vcpu = fcntl.ioctl(vm, 0xAE41, 0)
print("vcpu_fd =", vcpu)
fcntl.ioctl(vcpu, 0x4020AEAE, init_blob)
ok = 0
for name, rid in regs.items():
    buf = bytearray(8)
    try:
        fcntl.ioctl(vcpu, KVM_GET_ONE_REG, struct.pack("=QQ", rid, 0))
        # ioctl via fcntl needs the data pointer; use os.ioctl-style trick below
    except Exception:
        pass
    try:
        # proper way: pass id in a struct and receive value
        import ctypes
        class OneReg(ctypes.Structure):
            _fields_ = [("id", ctypes.c_uint64), ("addr", ctypes.c_uint64)]
        val = ctypes.c_uint64(0)
        r = OneReg(rid, ctypes.addressof(val))
        fcntl.ioctl(vcpu, KVM_GET_ONE_REG, bytes(r))
        print("  %-18s GET_OK  = 0x%016x" % (name, val.value))
        ok += 1
    except OSError as e:
        print("  %-18s GET_ERR(%d %s)" % (name, e.errno, os.strerror(e.errno)))
print("ID_REGS_OK =", ok, "/", len(regs))
print("KVM_IDREG_TEST_DONE")
PYEOF
fi

echo
echo "############ 3. QEMU 版本 ############"
$Q --version 2>&1 | head -2

echo
echo "############ 4. QEMU 8.x + -cpu host + ITS 启动 guest（v8 会死在 put registers） ############"
printf 'echo GUEST_ALIVE_V9\nuname -a\ncat /proc/version\necho ---CPUINFO---\nhead -8 /proc/cpuinfo\necho ---GUEST_DONE---\npoweroff -f\n' \
 | timeout 150 $Q -M virt,its=on -accel kvm -cpu host -m 1024 \
     -display none -no-reboot -nic none -serial stdio \
     -kernel $K/Image -initrd $K/initrd.gz \
     -append "console=ttyAMA0 rdinit=/init" 2>&1 | tail -60

echo
echo "############ 5. 关键字检查 ############"
echo "（上面的输出里应能看到 GUEST_ALIVE_V9 与 ---GUEST_DONE---；"
echo "  且不应有 'Failed to put registers after init' / 'full reset is not supported'）"