#!/usr/bin/env python3
# 全量枚举 KVM 暴露的 ARM64 sysreg（op0=3, op1=0），定位 QEMU 8.2 缺哪个 ID 寄存器
import fcntl, os, struct, ctypes

KVM_GET_ONE_REG = 0x4010AEAB
KVM_REG_ARM64       = 0x6000000000000000
KVM_REG_SIZE_U64    = 0x0030000000000000
KVM_REG_ARM64_SYSREG= 0x00130000

def enc(op0, op1, crn, crm, op2):
    return (KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM64_SYSREG |
            (op0 << 14) | (op1 << 11) | (crn << 7) | (crm << 3) | op2)

class OneReg(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint64), ("addr", ctypes.c_uint64)]

fd = os.open("/dev/kvm", os.O_RDWR)
vm = fcntl.ioctl(fd, 0xAE01, 0)
vcpu = fcntl.ioctl(vm, 0xAE41, 0)
_init = ctypes.create_string_buffer(32)          # struct kvm_vcpu_init = 32 bytes
struct.pack_into("<I", _init, 0, 5)              # target = KVM_ARM_TARGET_GENERIC_V8
fcntl.ioctl(vcpu, 0x4020AEAE, _init)

print("=== KVM 可读的 ID 区间 sysreg: (op0=3, op1=0, CRn=0..8) ===")
ok = 0
for crn in range(0, 9):
    for crm in range(0, 16):
        for op2 in range(0, 8):
            rid = enc(3, 0, crn, crm, op2)
            val = ctypes.c_uint64(0)
            r = OneReg(rid, ctypes.addressof(val))
            try:
                fcntl.ioctl(vcpu, KVM_GET_ONE_REG, bytes(r))
                print("  (3,0,%d,%d,%d) = 0x%016x" % (crn, crm, op2, val.value))
                ok += 1
            except OSError:
                pass
print("TOTAL_OK =", ok)
print("PROBE_ALL_DONE")