#!/usr/bin/env python3
# 验证 PMCR_EL0 等 PMU 寄存器是否暴露给用户态
import fcntl, os, ctypes, struct

KVM_CREATE_VM   = 0xAE01
KVM_CREATE_VCPU = 0xAE41
KVM_ARM_VCPU_INIT = 0x4020AEAE
KVM_GET_ONE_REG = 0x4010AEAB

KVM_REG_ARM64        = 0x6000000000000000
KVM_REG_SIZE_U64     = 0x0030000000000000
KVM_REG_ARM64_SYSREG = 0x00130000


def enc(o0, o1, crn, crm, o2):
    return (KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM64_SYSREG |
            (o0 << 14) | (o1 << 11) | (crn << 7) | (crm << 3) | o2)


class OneReg(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint64), ("addr", ctypes.c_uint64)]


fd = os.open("/dev/kvm", os.O_RDWR)
vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
vc = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)

# 用 QEMU 的方式初始化：target=5, features[0] = 1<<3 (PMU_V3)
b = ctypes.create_string_buffer(32)
struct.pack_into("<I", b, 0, 5)
struct.pack_into("<I", b, 4, 1 << 3)
try:
    fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, b)
    print("INIT(target=5, PMU_V3) OK  <-- 与 QEMU scratch vcpu 相同")
except OSError as e:
    print("INIT(target=5, PMU_V3) ERR", e.errno)

CAND = [
    ("PMCR_EL0  (3,3,9,12,0)", (3, 3, 9, 12, 0)),
    ("PMCCNTR   (3,3,9,13,0)", (3, 3, 9, 13, 0)),
    ("PMCEID0   (3,3,9,12,6)", (3, 3, 9, 12, 6)),
    ("PMOVS     (3,3,9,14,0)", (3, 3, 9, 14, 0)),
    ("PMINTEN   (3,3,9,14,1)", (3, 3, 9, 14, 1)),
    ("ID_AA64ZFR0(3,0,0,4,4)", (3, 0, 0, 4, 4)),
    ("MIDR_EL1  (3,0,0,0,0)", (3, 0, 0, 0, 0)),
]
print("--- PMU / misc registers ---")
for nm, (o0, o1, crn, crm, o2) in CAND:
    val = ctypes.c_uint64(0)
    r = OneReg(enc(o0, o1, crn, crm, o2), ctypes.addressof(val))
    try:
        fcntl.ioctl(vc, KVM_GET_ONE_REG, bytes(r))
        print("  %-24s OK   0x%016x" % (nm, val.value))
    except OSError as e:
        print("  %-24s MISS errno=%d (%s)" % (nm, e.errno, os.strerror(e.errno)))

print("--- 枚举 op1=3, CRn=9 (PMU 区间) ---")
n = 0
for crm in range(0, 16):
    for op2 in range(0, 8):
        val = ctypes.c_uint64(0)
        r = OneReg(enc(3, 3, 9, crm, op2), ctypes.addressof(val))
        try:
            fcntl.ioctl(vc, KVM_GET_ONE_REG, bytes(r))
            print("  (3,3,9,%d,%d) = 0x%016x" % (crm, op2, val.value))
            n += 1
        except OSError:
            pass
print("PMU range readable =", n)
print("PROBE_PMCR_DONE")