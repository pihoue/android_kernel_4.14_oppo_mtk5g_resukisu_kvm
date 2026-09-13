#!/usr/bin/env python3
# Diagnose which arm64 KVM operations our 4.14 kernel supports.
import os
import fcntl
import ctypes
import struct

KVM_GET_API_VERSION = 0xAE00
KVM_CREATE_VM = 0xAE01
KVM_CREATE_VCPU = 0xAE41
KVM_ARM_VCPU_INIT = 0x4020AEAE          # _IOW(KVMIO, 0xae, struct kvm_vcpu_init) = 32 bytes
KVM_GET_ONE_REG = 0x4010AEAB            # _IOW(KVMIO, 0xab, struct kvm_one_reg)   = 16 bytes
KVM_SET_ONE_REG = 0x4010AEAC            # _IOW(KVMIO, 0xac, struct kvm_one_reg)

KVM_REG_ARM64 = 0x6000000000000000
KVM_REG_SIZE_U64 = 0x0030000000000000
# from arch/arm64/include/uapi/asm/kvm.h:
#   #define KVM_REG_ARM_COPROC_SHIFT 16
#   #define KVM_REG_ARM64_SYSREG (0x0013 << KVM_REG_ARM_COPROC_SHIFT)  -> 0x130000
KVM_REG_ARM64_SYSREG = 0x130000
KVM_REG_ARM_CORE = 0x100000


def sysreg(op0, op1, crn, crm, op2):
    return (KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM64_SYSREG
            | (op0 << 14) | (op1 << 11) | (crn << 7) | (crm << 3) | op2)


def corereg(off_u32):
    return KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM_CORE | off_u32


REGS = [
    ('MIDR_EL1',         (3, 0, 0, 0, 0)),
    ('MPIDR_EL1',        (3, 0, 0, 0, 5)),
    ('ID_AA64PFR0_EL1',  (3, 0, 0, 4, 0)),
    ('ID_AA64PFR1_EL1',  (3, 0, 0, 4, 1)),
    ('ID_AA64DFR0_EL1',  (3, 0, 0, 5, 0)),
    ('ID_AA64ISAR0_EL1', (3, 0, 0, 6, 0)),
    ('ID_AA64MMFR0_EL1', (3, 0, 0, 7, 0)),
    ('CLIDR_EL1',        (3, 1, 0, 0, 1)),
    ('CTR_EL0',          (3, 3, 0, 0, 1)),
]

fd = os.open('/dev/kvm', os.O_RDWR)
print('KVM_GET_API_VERSION =', fcntl.ioctl(fd, KVM_GET_API_VERSION, 0))

print()
print('--- KVM_ARM_VCPU_INIT feature-bit probe (target=5 GENERIC_V8) ---')
for feats, desc in [(0, 'none'), (1 << 1, 'PSCI_0_2'), (1 << 3, 'PMU_V3'),
                    (1 << 4, 'SVE'), (1 << 5, 'PTRAUTH_ADDR'), (1 << 6, 'PTRAUTH_GEN')]:
    vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
    vc = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)
    buf = ctypes.create_string_buffer(32)
    struct.pack_into('<I', buf, 0, 5)
    struct.pack_into('<I', buf, 4, feats)      # features[0]
    try:
        fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, buf)
        r = 'OK'
    except OSError as e:
        r = 'ERR %d (%s)' % (e.errno, e.strerror)
    print('  features=%-14s -> %s' % (desc, r))
    os.close(vc)
    os.close(vm)

print()
print('--- register GET/SET probe (after clean INIT) ---')
vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
vc = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)
buf = ctypes.create_string_buffer(32)
struct.pack_into('<I', buf, 0, 5)
fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, buf)

for name, (o0, o1, crn, crm, op2) in REGS:
    rid = sysreg(o0, o1, crn, crm, op2)
    val = ctypes.c_uint64(0)
    arg = ctypes.create_string_buffer(struct.pack('<QQ', rid, ctypes.addressof(val)))
    try:
        fcntl.ioctl(vc, KVM_GET_ONE_REG, arg)
        g = 'GET_OK(%016x)' % val.value
    except OSError as e:
        g = 'GET_ERR(%d)' % e.errno
    try:
        fcntl.ioctl(vc, KVM_SET_ONE_REG, arg)   # write back the same value
        s = 'SET_OK'
    except OSError as e:
        s = 'SET_ERR(%d %s)' % (e.errno, e.strerror)
    print('  %-18s %-24s %s' % (name, g, s))