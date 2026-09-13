#!/system/bin/sh
# customize.sh - executed by the module manager at install time
if ! command -v ui_print >/dev/null 2>&1; then
  ui_print() { echo "$1"; }
fi
ui_print "*******************************"
ui_print " KVM access (SELinux policy)"
ui_print " Allows apps/shell to use /dev/kvm"
ui_print " Policy is patched at every boot."
ui_print "*******************************"