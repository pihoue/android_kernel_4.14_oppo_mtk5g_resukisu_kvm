#!/usr/bin/env python3
# 正向确认: 列出 REG_LIST 里的 KVM_REG_ARM_DEMUX(coproc=0x0011) 寄存器,
# 逐个 GET -> 原值 SET, 打印结果 (v13 之前这里必定 SET EINVAL)
import fcntl, os, ctypes, struct

KVM_CREATE_VM     = 0xAE01
KVM_CREATE_VCPU   = 0xAE41
KVM_ARM_VCPU_INIT = 0x4020AEAE
KVM_GET_ONE_REG   = 0x4010AEAB
KVM_SET_ONE_REG   = 0x4010AEAC
KVM_GET_REG_LIST  = 0xC008AEB0

SIZE_MASK   = 0x00f0000000000000
SIZE_U32    = 0x0020000000000000
SIZE_U64    = 0x0030000000000000
COPROC_MASK = 0xFFFF0000
DEMUX_COPROC = 0x0011 << 16


def size_s(rid):
    s = rid & SIZE_MASK
    if s == SIZE_U32:
        return "U32"
    if s == SIZE_U64:
        return "U64"
    return "sz%x" % (s >> 52)


fd = os.open("/dev/kvm", os.O_RDWR)
vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
vc = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)

b = ctypes.create_string_buffer(32)
struct.pack_into("<I", b, 0, 5)        # target = GENERIC_V8 (QEMU 用的)
struct.pack_into("<I", b, 4, 1 << 3)   # PMU_V3
try:
    fcntl.ioctl(vc, KVM_ARM_VCPU_INIT, b)
    print("INIT OK (target=5, PMU_V3)")
except OSError as e:
    print("INIT errno =", e.errno)

buf = ctypes.create_string_buffer(16)
try:
    fcntl.ioctl(vc, KVM_GET_REG_LIST, buf)
except OSError as e:
    print("first REG_LIST errno =", e.errno, "(expect 7 E2BIG)")
n = struct.unpack_from("<Q", buf, 0)[0]
print("n =", n)
big = ctypes.create_string_buffer(8 + 8 * n)
struct.pack_into("<Q", big, 0, n)
fcntl.ioctl(vc, KVM_GET_REG_LIST, big)
regs = [struct.unpack_from("<Q", big, 8 + 8 * i)[0] for i in range(n)]

demux = [r for r in regs if (r & COPROC_MASK) == DEMUX_COPROC]
print("demux regs in REG_LIST =", len(demux))
ok = 0
for rid in demux:
    val = ctypes.c_uint64(0)
    r1 = ctypes.create_string_buffer(16)
    struct.pack_into("<QQ", r1, 0, rid, ctypes.addressof(val))
    try:
        fcntl.ioctl(vc, KVM_GET_ONE_REG, r1)
        g = "GET_OK(0x%016x)" % val.value
        got = True
    except OSError as e:
        g = "GET_ERR(%d)" % e.errno
        got = False
    r2 = ctypes.create_string_buffer(16)
    struct.pack_into("<QQ", r2, 0, rid, ctypes.addressof(val))
    try:
        fcntl.ioctl(vc, KVM_SET_ONE_REG, r2)
        s = "SET_OK"
        ok += 1
    except OSError as e:
        s = "SET_ERR(%d %s)" % (e.errno, os.strerror(e.errno))
    print("  id=0x%016x %-5s %s  %s" % (rid, size_s(rid), g, s))

print("DEMUX_WRITEBACK_OK = %d / %d" % (ok, len(demux)))
print("PROBE_DEMUX_DONE")