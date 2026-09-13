#!/usr/bin/env python3
# 复现 QEMU 的 write_list_to_kvmstate()：找出哪个寄存器的"写回"失败
import fcntl, os, ctypes, struct

KVM_CREATE_VM      = 0xAE01
KVM_CREATE_VCPU    = 0xAE41
KVM_ARM_VCPU_INIT  = 0x4020AEAE
KVM_GET_ONE_REG    = 0x4010AEAB
KVM_SET_ONE_REG    = 0x4010AEAC
KVM_GET_REG_LIST   = 0xC008AEB0   # _IOWR(KVMIO,0xb0,struct kvm_reg_list)=sizeof 8 (reg[0])

SIZE_MASK   = 0x00f0000000000000
SIZE_U32    = 0x0020000000000000
SIZE_U64    = 0x0030000000000000
COPROC_MASK = 0xFFFF0000          # coproc 字段在 bit16 以上


class OneReg(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint64), ("addr", ctypes.c_uint64)]


def size_s(rid):
    s = rid & SIZE_MASK
    if s == SIZE_U32:
        return "U32"
    if s == SIZE_U64:
        return "U64"
    return "sz%x" % (s >> 52)


def desc(rid):
    cop = (rid & COPROC_MASK)
    if cop == (0x0013 << 16):
        o0 = (rid >> 14) & 0x3
        o1 = (rid >> 11) & 0x7
        crn = (rid >> 7) & 0xf
        crm = (rid >> 3) & 0xf
        o2 = rid & 0x7
        return "SYSREG(3,%d,%d,%d,%d)" % (o1, crn, crm, o2)
    return "coproc=0x%04x" % (cop >> 16)


fd = os.open("/dev/kvm", os.O_RDWR)
vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
vc = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)

b = ctypes.create_string_buffer(32)
struct.pack_into("<I", b, 0, 5)          # target = GENERIC_V8
struct.pack_into("<I", b, 4, 1 << 3)     # PMU_V3 (与 QEMU 的 scratch vcpu 一致)
fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, b)

buf = ctypes.create_string_buffer(16)
try:
    fcntl.ioctl(vc, KVM_GET_REG_LIST, buf)
except OSError as e:
    print("first KVM_GET_REG_LIST errno =", e.errno, "(expect 7 E2BIG)")
n = struct.unpack_from("<Q", buf, 0)[0]
print("kernel reports n =", n)

big = ctypes.create_string_buffer(8 + 8 * n)
struct.pack_into("<Q", big, 0, n)
fcntl.ioctl(vc, KVM_GET_REG_LIST, big)
regs = [struct.unpack_from("<Q", big, 8 + 8 * i)[0] for i in range(n)]
print("fetched", len(regs), "reg ids")

sync = [r for r in regs if (r & COPROC_MASK) != (0x0010 << 16)]
print("regs to test (excl. CORE only, FW included) =", len(sync))
print("--- 逐个 读->原值写回 ---")

nfail = 0
for rid in sync:
    val = ctypes.c_uint64(0)
    r1 = OneReg(rid, ctypes.addressof(val))
    try:
        fcntl.ioctl(vc, KVM_GET_ONE_REG, bytes(r1))
        g = "GET_OK(0x%016x)" % val.value
        got = True
    except OSError as e:
        g = "GET_ERR(%d)" % e.errno
        got = False
    r2 = OneReg(rid, ctypes.addressof(val))
    try:
        fcntl.ioctl(vc, KVM_SET_ONE_REG, bytes(r2))
        s = "SET_OK"
        sok = True
    except OSError as e:
        s = "SET_ERR(%d %s)" % (e.errno, os.strerror(e.errno))
        sok = False
    if not got or not sok:
        nfail += 1
        print("  FAIL id=0x%016x %-22s %-6s %s  %s"
              % (rid, desc(rid), size_s(rid), g, s))

print("FAILS =", nfail)
print("PROBE_REGLIST_DONE")