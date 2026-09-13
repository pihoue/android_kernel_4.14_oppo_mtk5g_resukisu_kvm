import struct, sys

path = "/sdcard/Download/Operit/tmp/pgpt4k.bin"
data = open(path, "rb").read()

# GPT header at LBA1 (offset 0x1000 for 4K sectors)
sig = data[0x1000:0x1008]
print("sig:", sig)
if sig != b"EFI PART":
    sys.exit("bad gpt")

part_entries_lba = struct.unpack_from("<Q", data, 0x1000 + 72)[0]
num_entries = struct.unpack_from("<I", data, 0x1000 + 80)[0]
entry_size = struct.unpack_from("<I", data, 0x1000 + 84)[0]
print(f"entries_lba={part_entries_lba} num={num_entries} entry_size={entry_size}")

base = part_entries_lba * 4096  # sector size 4096
want = ("gz1", "gz2", "boot", "preloader_a", "preloader_b", "tee1", "tee2",
        "super", "vendor_boot", "userdata", "vbmeta", "scp1", "scp2",
        "sspm_1", "sspm_2", "mcupm_1", "mcupm_2", "lk", "lk2", "dtbo", "pgpt")
allnames = []
for i in range(num_entries):
    off = base + i * entry_size
    if off + 128 > len(data):
        break
    ent = data[off:off + 128]
    if ent == b"\x00" * 128:
        continue
    name = ent[56:128].decode("utf-16-le", errors="replace").rstrip("\x00")
    type_guid = ent[:16].hex()
    start = struct.unpack_from("<Q", ent, 32)[0]
    end = struct.unpack_from("<Q", ent, 40)[0]
    size = (end - start + 1) * 4096 / (1024 ** 3)
    allnames.append((name, start, size))
    if name in want or "preloader" in name or "gz" in name.lower():
        print(f"{name:22s} start_lba={start:<10d} size_GB={size:.2f} type={type_guid[:8]}")

print(f"--- total partitions: {len(allnames)} ---")
for n, s, sz in allnames:
    if n in ("gz1", "gz2", "boot", "super", "userdata", "vendor_boot", "preloader_a", "preloader_b", "pgpt"):
        print(n, s, f"{sz:.2f}G")
