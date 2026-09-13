import sys, shutil
q = chr(34)
p = "/home/moao/resukisu_kernel/drivers/misc/mediatek/imgsensor/src/common/v1_1/imgsensor_hw.c"
s = open(p).read()
ins = open("/tmp/ins.txt").read()
if q + "afvdd" + q + "," in s:
    print("ALREADY PATCHED")
    sys.exit(2)
if q + "vcamio" + q + "," not in s:
    print("NOTFOUND")
    sys.exit(1)
shutil.copy(p, p + ".bak")
s = s.replace(q + "vcamio" + q + ",", q + "vcamio" + q + "," + chr(10) + ins, 1)
open(p, "w").write(s)
print("PATCHED OK")
