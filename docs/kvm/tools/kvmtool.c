/* OPERIT KVM functional test - freestanding, no libc */
typedef long l;
typedef unsigned long ul;

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

#define SYS_write  64
#define SYS_openat 56
#define SYS_ioctl  29
#define SYS_exit   93

static ul slen(const char *s) { ul n = 0; while (s[n]) n++; return n; }
static void puts_(const char *s) { sys3(SYS_write, 1, (l)s, (l)slen(s)); }
static void putnum(l v) {
    char b[24]; int i = 0;
    if (v < 0) { puts_("-"); v = -v; }
    if (v == 0) b[i++] = '0';
    while (v) { b[i++] = (char)('0' + (v % 10)); v /= 10; }
    while (i--) { char c = b[i]; sys3(SYS_write, 1, (l)&c, 1); }
}

void _start(void) {
    l fd = sys4(SYS_openat, -100, (l)"/dev/kvm", 2, 0);
    puts_("[kvmtest] open(/dev/kvm) = "); putnum(fd); puts_("\n");
    if (fd < 0) { puts_("KVM_OPEN_FAILED\n"); sys1(SYS_exit, 1); }

    l api = sys3(SYS_ioctl, fd, 0xAE00, 0);          /* KVM_GET_API_VERSION  */
    puts_("[kvmtest] KVM_GET_API_VERSION = "); putnum(api); puts_(" (expect 12)\n");

    l ms = sys3(SYS_ioctl, fd, 0xAE04, 0);           /* KVM_GET_VCPU_MMAP_SIZE */
    puts_("[kvmtest] KVM_GET_VCPU_MMAP_SIZE = "); putnum(ms); puts_("\n");

    l vm = sys3(SYS_ioctl, fd, 0xAE01, 0);           /* KVM_CREATE_VM */
    puts_("[kvmtest] KVM_CREATE_VM = "); putnum(vm); puts_("\n");
    if (vm < 0) { puts_("KVM_CREATE_VM_FAILED\n"); sys1(SYS_exit, 2); }

    l vcpu = sys3(SYS_ioctl, vm, 0xAE41, 0);         /* KVM_CREATE_VCPU */
    puts_("[kvmtest] KVM_CREATE_VCPU = "); putnum(vcpu); puts_("\n");
    if (vcpu < 0) { puts_("KVM_CREATE_VCPU_FAILED\n"); sys1(SYS_exit, 3); }

    l cap = sys3(SYS_ioctl, fd, 0xAE03, 0);          /* KVM_CHECK_EXTENSION(0) */
    puts_("[kvmtest] KVM_CHECK_EXTENSION(0) = "); putnum(cap); puts_("\n");

    puts_("KVM_FUNCTIONAL_TEST_OK\n");
    sys1(SYS_exit, 0);
}
