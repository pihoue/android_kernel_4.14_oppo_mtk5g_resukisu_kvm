#!/usr/bin/env python3
# v11 后综合诊断：定位 QEMU 8.2 到底卡在哪一步
import fcntl, os, ctypes, struct

KVM_GET_API_VERSION   = 0xAE00
KVM_CREATE_VM         = 0xAE01
KVM_CHECK_EXTENSION   = 0xAE03
KVM_CREATE_VCPU       = 0xAE41
KVM_ARM_VCPU_INIT     = 0x4020AEAE
KVM_ARM_PREFERRED_TARGET = 0x8020AEAF
KVM_GET_ONE_REG       = 0x4010AEAB

KVM_REG_ARM64        = 0x6000000000000000
KVM_REG_SIZE_U64     = 0x0030000000000000
KVM_REG_ARM64_SYSREG = 0x00130000


def enc(o0, o1, crn, crm, o2):
    return (KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM64_SYSREG |
            (o0 << 14) | (o1 << 11) | (crn << 7) | (crm << 3) | o2)


class OneReg(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint64), ("addr", ctypes.c_uint64)]


fd = os.open("/dev/kvm", os.O_RDWR)
print("api_version =", fcntl.ioctl(fd, KVM_GET_API_VERSION, 0))

for cap, nm in [(126, "KVM_CAP_ARM_PMU_V3"), (165, "KVM_CAP_ARM_VM_IPA_SIZE")]:
    try:
        print("EXT %-24s(%d) = %d" % (nm, cap, fcntl.ioctl(fd, KVM_CHECK_EXTENSION, cap)))
    except OSError as e:
        print("EXT %-24s ERR %d" % (nm, e.errno))

vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
print("vm_fd =", vm)

buf = ctypes.create_string_buffer(32)
try:
    fcntl.ioctl(vm, KVM_ARM_PREFERRED_TARGET, buf)
    print("PREFERRED_TARGET: target=%d features[0]=0x%x"
          % (struct.unpack_from("<I", buf, 0)[0], struct.unpack_from("<I", buf, 4)[0]))
except OSError as e:
    print("PREFERRED_TARGET ERR %d (%s)" % (e.errno, os.strerror(e.errno)))

vc = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)
print("vcpu_fd =", vc)

print("--- KVM_ARM_VCPU_INIT matrix (target x features) ---")
for tgt in range(0, 8):
    row = []
    for feats, fn in [(0, "none"), (1 << 3, "PMU_V3")]:
        b = ctypes.create_string_buffer(32)
        struct.pack_into("<I", b, 0, tgt)
        struct.pack_into("<I", b, 4, feats)
        try:
            fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, b)
            row.append("%s=OK" % fn)
        except OSError as e:
            row.append("%s=ERR%d" % (fn, e.errno))
    print("  target=%d  %s" % (tgt, "  ".join(row)))

b = ctypes.create_string_buffer(32)
struct.pack_into("<I", b, 0, 5)
try:
    fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, b)
    print("clean INIT(target=5) OK")
except OSError as e:
    print("clean INIT(target=5) ERR", e.errno)

REQ = [
    ("ID_AA64PFR0", (3, 0, 0, 4, 0)), ("ID_AA64PFR1", (3, 0, 0, 4, 1)),
    ("ID_AA64ZFR0", (3, 0, 0, 4, 4)), ("ID_AA64SMFR0", (3, 0, 0, 4, 5)),
    ("ID_AA64DFR0", (3, 0, 0, 5, 0)), ("ID_AA64DFR1", (3, 0, 0, 5, 1)),
    ("ID_AA64ISAR0", (3, 0, 0, 6, 0)), ("ID_AA64ISAR1", (3, 0, 0, 6, 1)),
    ("ID_AA64ISAR2", (3, 0, 0, 6, 2)),
    ("ID_AA64MMFR0", (3, 0, 0, 7, 0)), ("ID_AA64MMFR1", (3, 0, 0, 7, 1)),
    ("ID_AA64MMFR2", (3, 0, 0, 7, 2)),
    ("ID_PFR0", (3, 0, 0, 1, 0)), ("ID_PFR1", (3, 0, 0, 1, 1)),
    ("ID_DFR0", (3, 0, 0, 1, 2)),
    ("ID_MMFR0", (3, 0, 0, 1, 4)), ("ID_MMFR1", (3, 0, 0, 1, 5)),
    ("ID_MMFR2", (3, 0, 0, 1, 6)), ("ID_MMFR3", (3, 0, 0, 1, 7)),
    ("ID_ISAR0", (3, 0, 0, 2, 0)), ("ID_ISAR1", (3, 0, 0, 2, 1)),
    ("ID_ISAR2", (3, 0, 0, 2, 2)), ("ID_ISAR3", (3, 0, 0, 2, 3)),
    ("ID_ISAR4", (3, 0, 0, 2, 4)), ("ID_ISAR5", (3, 0, 0, 2, 5)),
    ("ID_MMFR4", (3, 0, 0, 2, 6)), ("ID_ISAR6", (3, 0, 0, 2, 7)),
    ("MVFR0", (3, 0, 0, 3, 0)), ("MVFR1", (3, 0, 0, 3, 1)), ("MVFR2", (3, 0, 0, 3, 2)),
    ("ID_PFR2", (3, 0, 0, 3, 4)), ("ID_DFR1", (3, 0, 0, 3, 5)), ("ID_MMFR5", (3, 0, 0, 3, 6)),
]

print("--- QEMU 8.2 required ID regs (U64 读取) ---")
miss = 0
for nm, (o0, o1, crn, crm, o2) in REQ:
    val = ctypes.c_uint64(0)
    r = OneReg(enc(o0, o1, crn, crm, o2), ctypes.addressof(val))
    try:
        fcntl.ioctl(vc, KVM_GET_ONE_REG, bytes(r))
        print("  %-14s OK   0x%016x" % (nm, val.value))
    except OSError as e:
        print("  %-14s MISS errno=%d" % (nm, e.errno))
        miss += 1
print("MISSING =", miss)
print("PROBE_DIAG_DONE")