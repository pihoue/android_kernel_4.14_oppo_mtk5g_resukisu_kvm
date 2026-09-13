/* kvmvm.c - minimal arm64 KVM test: actually EXECUTE guest code in hardware
 * virtualization and prove it by catching an MMIO exit.
 * Freestanding (no libc, raw syscalls).
 */
typedef long l;
typedef unsigned long ul;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef unsigned char u8;

static inline l sys1(l n, l a) {
    register l x0 asm("x0") = a;
    register l x8 asm("x8") = n;
    asm volatile("svc #0" : "+r"(x0) : "r"(x8) : "memory", "cc");
    return x0;
}
static inline l sys3(l n, l a, l b, l c) {
    register l x0 asm("x0") = a;
    register l x1 asm("x1") = b;
    register l x2 asm("x2") = c;
    register l x8 asm("x8") = n;
    asm volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2) : "memory", "cc");
    return x0;
}
static inline l sys4(l n, l a, l b, l c, l d) {
    register l x0 asm("x0") = a;
    register l x1 asm("x1") = b;
    register l x2 asm("x2") = c;
    register l x3 asm("x3") = d;
    register l x8 asm("x8") = n;
    asm volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory", "cc");
    return x0;
}
static inline l sys6(l n, l a, l b, l c, l d, l e, l f) {
    register l x0 asm("x0") = a;
    register l x1 asm("x1") = b;
    register l x2 asm("x2") = c;
    register l x3 asm("x3") = d;
    register l x4 asm("x4") = e;
    register l x5 asm("x5") = f;
    register l x8 asm("x8") = n;
    asm volatile("svc #0" : "+r"(x0)
                 : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5)
                 : "memory", "cc");
    return x0;
}

#define SYS_ioctl  29
#define SYS_openat 56
#define SYS_write  64
#define SYS_exit   93
#define SYS_mmap   222

#define O_RDWR     2
#define AT_FDCWD   (-100)
#define PROT_RW    (1 | 2)
#define MAP_SHARED 0x01
#define MAP_ANON   0x20
#define MAP_PRIV   0x02

#define KVM_GET_API_VERSION        0xAE00
#define KVM_CREATE_VM              0xAE01
#define KVM_GET_VCPU_MMAP_SIZE     0xAE04
#define KVM_CREATE_VCPU            0xAE41
#define KVM_RUN                    0xAE80
#define KVM_ARM_VCPU_INIT          0x4020AEAE   /* _IOW(0xae,0xae,32) */
#define KVM_SET_USER_MEMORY_REGION 0x4020AE46   /* _IOW(0xae,0x46,32) */
#define KVM_SET_ONE_REG            0x4010AEAC   /* _IOW(0xae,0xac,16) */

#define KVM_REG_ARM64      0x6000000000000000ULL
#define KVM_REG_SIZE_U64   0x0030000000000000ULL
#define KVM_REG_ARM_CORE   0x100000ULL          /* 0x0010 << 16 */

/* offsets inside struct kvm_regs, in units of __u32 (that is the ABI) */
#define KREG_X1     2     /* regs.regs[1]  :  8/4  */
#define KREG_PC     64    /* regs.pc       : 256/4 */
#define KREG_PSTATE 66    /* regs.pstate   : 264/4 */

static ul slen(const char *s) { ul n = 0; while (s[n]) n++; return n; }
static void puts_(const char *s) { sys3(SYS_write, 1, (l)s, (l)slen(s)); }

static void putnum(l v) {
    char b[24]; int i = 0;
    if (v < 0) { puts_("-"); v = -v; }
    if (v == 0) b[i++] = '0';
    while (v) { b[i++] = (char)('0' + (v % 10)); v /= 10; }
    while (i--) { char c = b[i]; sys3(SYS_write, 1, (l)&c, 1); }
}
static void puthex(u64 v, int ndig) {
    const char *h = "0123456789abcdef";
    char b[16]; int i;
    for (i = 0; i < ndig; i++) { b[i] = h[v & 15]; v >>= 4; }
    for (i = ndig - 1; i >= 0; i--) { char c = b[i]; sys3(SYS_write, 1, (l)&c, 1); }
}
static void puthex64(u64 v) { puthex(v, 16); }
static void puthex8(u64 v) { puthex(v, 2); }

static u64 corereg(u32 off) {
    return KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM_CORE | (u64)off;
}

static int set_reg(l vcpu, u64 id, u64 val) {
    u64 v = val;
    u64 arg[2];
    arg[0] = id;
    arg[1] = (u64)(ul)&v;
    return (int)sys3(SYS_ioctl, vcpu, KVM_SET_ONE_REG, (l)arg);
}

void _start(void) {
    int i;
    l fd, vm, vcpu, rc;
    u32 init[8];
    u32 slot[8];
    u8 *krun;
    u32 *guest;
    l mmap_sz;
    u64 addr, reason;

    puts_("[kvmvm] === minimal arm64 KVM guest execution test ===\n");

    fd = sys4(SYS_openat, AT_FDCWD, (l)"/dev/kvm", O_RDWR, 0);
    puts_("[kvmvm] open(/dev/kvm) = "); putnum(fd); puts_("\n");
    if (fd < 0) { puts_("KVM_OPEN_FAILED\n"); sys1(SYS_exit, 1); }

    puts_("[kvmvm] KVM_GET_API_VERSION = ");
    putnum(sys3(SYS_ioctl, fd, KVM_GET_API_VERSION, 0)); puts_("\n");

    vm = sys3(SYS_ioctl, fd, KVM_CREATE_VM, 0);
    puts_("[kvmvm] KVM_CREATE_VM = "); putnum(vm); puts_("\n");

    vcpu = sys3(SYS_ioctl, vm, KVM_CREATE_VCPU, 0);
    puts_("[kvmvm] KVM_CREATE_VCPU = "); putnum(vcpu); puts_("\n");

    for (i = 0; i < 8; i++) init[i] = 0;
    init[0] = 5;                                  /* KVM_ARM_TARGET_GENERIC_V8 */
    rc = sys3(SYS_ioctl, vcpu, KVM_ARM_VCPU_INIT, (l)init);
    puts_("[kvmvm] KVM_ARM_VCPU_INIT = "); putnum(rc); puts_("\n");

    mmap_sz = sys3(SYS_ioctl, fd, KVM_GET_VCPU_MMAP_SIZE, 0);
    krun = (u8 *)sys6(SYS_mmap, 0, mmap_sz, PROT_RW, MAP_SHARED, vcpu, 0);
    puts_("[kvmvm] kvm_run @ "); puthex64((u64)(ul)krun); puts_("\n");

    /* one page of guest RAM */
    guest = (u32 *)sys6(SYS_mmap, 0, 0x1000, PROT_RW, MAP_PRIV | MAP_ANON, -1, 0);
    puts_("[kvmvm] guest ram @ "); puthex64((u64)(ul)guest); puts_("\n");

    for (i = 0; i < 8; i++) slot[i] = 0;
    slot[0] = 0;                     /* slot id   */
    slot[1] = 0;                     /* flags     */
    ((u64 *)slot)[1] = 0;            /* guest_phys_addr  */
    ((u64 *)slot)[2] = 0x1000;       /* memory_size      */
    ((u64 *)slot)[3] = (u64)(ul)guest; /* userspace_addr */
    rc = sys3(SYS_ioctl, vm, KVM_SET_USER_MEMORY_REGION, (l)slot);
    puts_("[kvmvm] KVM_SET_USER_MEMORY_REGION = "); putnum(rc); puts_("\n");
    if (rc < 0) { puts_("KVM_MEMSLOT_FAILED\n"); sys1(SYS_exit, 2); }

    /* guest program (PA 0x10000000 has no memory slot -> must trap) :
     *   mov  x1, #0x1000, lsl #16     ; x1 = 0x10000000
     *   ldr  w0, [x1]                 ; data abort -> KVM_EXIT_MMIO
     */
    guest[0] = 0xD2A20001u;
    guest[1] = 0xB9400020u;
    puts_("[kvmvm] guest code: "); puthex8((u64)0); puthex8((u64)0); puthex8((u64)0); puthex8((u64)0);
    puts_(" ... patched\n");

    set_reg(vcpu, corereg(KREG_X1), 0x10000000ULL);
    set_reg(vcpu, corereg(KREG_PC), 0);
    set_reg(vcpu, corereg(KREG_PSTATE), 0x3c5ULL);   /* EL1h, DAIF masked */

    puts_("[kvmvm] >>> KVM_RUN (this executes the guest on real vCPU) <<<\n");
    rc = sys3(SYS_ioctl, vcpu, KVM_RUN, 0);
    puts_("[kvmvm] KVM_RUN returned "); putnum(rc); puts_("\n");

    reason = 0;
    for (i = 0; i < 4; i++) reason |= (u64)krun[8 + i] << (8 * i);
    puts_("[kvmvm] exit_reason = "); putnum((l)reason);
    puts_("  (6=MMIO, 24=ARM_NISV, 0=UNKNOWN)\n");

    puts_("[kvmvm] kvm_run dump:");
    for (i = 0; i < 40; i++) {
        if (i % 8 == 0) puts_(" ");
        puthex8((u64)krun[i]);
    }
    puts_("\n");

    /* scan the run struct for the expected faulting address 0x10000000 */
    addr = 0;
    for (i = 0; i + 8 <= 128; i++) {
        u64 v = 0;
        int j;
        for (j = 0; j < 8; j++) v |= (u64)krun[i + j] << (8 * j);
        if (v == 0x10000000ULL) { addr = v; break; }
    }
    puts_("[kvmvm] faulting GPA found in kvm_run: ");
    if (addr == 0x10000000ULL) {
        puts_("0x10000000  ==> GUEST REALLY EXECUTED\n");
        puts_("KVM_GUEST_EXECUTION_OK\n");
    } else {
        puts_("NOT FOUND\n");
        puts_("KVM_GUEST_EXECUTION_UNKNOWN\n");
    }
    sys1(SYS_exit, 0);
}