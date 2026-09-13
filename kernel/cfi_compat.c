/*
 * Compatibility shim for MTK vendor modules.
 *
 * The stock kernel for this device is built with clang + CONFIG_CFI_CLANG, and
 * the closed-source modules in /vendor/lib/modules were linked against the CFI
 * runtime helpers.  When the kernel is rebuilt without CFI (e.g. with GCC), the
 * module loader rejects every vendor module with:
 *
 *     wmt_drv: Unknown symbol __cfi_slowpath (err 0)
 *
 * Provide the symbol so those modules can be resolved and loaded.  When the
 * kernel really is built with CFI the real implementation in kernel/cfi.c is
 * used instead (see the #ifndef below), so this stays inert for CFI builds.
 */
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/export.h>
#include <linux/types.h>

#ifndef CONFIG_CFI_CLANG
void __cfi_slowpath(uint64_t id, void *ptr, void *diag)
{
	/* No CFI shadow in this build - the vendor modules only need the
	 * symbol to resolve, so this is intentionally a no-op. */
	(void)id;
	(void)ptr;
	(void)diag;
}
EXPORT_SYMBOL(__cfi_slowpath);
#endif
