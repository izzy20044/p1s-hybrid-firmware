"""Build the 'spoofed' variant of the hybrid firmware.

Same components as the first hybrid, but EVERY checksum, hash, filename
reference, and package-list entry is recomputed to match the actual files
on disk.  The goal is to pass every validation the printer might run:
  - BIMH header sizes match file sizes
  - manifest sig (MD5) fields match the component .bin.sig files
  - ota-package-list SHA-256 hashes match every file in the zip
  - manifest filename in its own BIMH header matches the actual filename
"""
import hashlib, json, os, shutil, struct, zipfile

BASE   = r'C:\Users\Administrator\Desktop\bambu-fw'
V107   = os.path.join(BASE, 'v107')
V110   = os.path.join(BASE, 'v110')
OUT    = os.path.join(BASE, 'hybrid-spoofed')

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)


def md5f(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def sha256f(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


# Layout of the pre_json metadata block that precedes the JSON body in the
# payload (verified against the stock 1.07 files):
#   [0x00 .. 0x3F]  inner filename, null-terminated + null padding (64 bytes)
#   [0x40]          u32  algo/type id (== 4)
#   [0x44]          u32  length of the JSON body in bytes   <-- must be updated
#   [0x48]          u32  metadata size (== 0x210 == 528)
#   [0x4C]          u32  reserved (== 0)
#   [0x50 .. 0x6F]  SHA-256 digest of the JSON body         <-- must be updated
# The pre_json block is exactly 112 (0x70) bytes long.
PRE_JSON_LEN = 0x70
OFF_JSON_LEN = 0x44   # u32 json-body length inside pre_json
OFF_DIGEST   = 0x50   # 32-byte SHA-256 of the json body inside pre_json


def extract_bimh(path):
    """Return (header_bytes, pre_json_bytes, json_dict) from a BIMH-wrapped JSON."""
    with open(path, 'rb') as f:
        data = f.read()
    hdr_size = struct.unpack_from('<I', data, 0x20)[0]
    hdr = data[:hdr_size]
    payload = data[hdr_size:]
    js_start = payload.find(b'{')
    pre = payload[:js_start]
    js_end = payload.rfind(b'}') + 1
    return bytearray(hdr), pre, json.loads(payload[js_start:js_end])


def write_bimh(path, hdr, pre_json, json_dict, filename_override=None):
    """Write a BIMH-wrapped JSON file with correct sizes AND a valid pre_json
    block (embedded JSON length + SHA-256 digest of the JSON body).

    The stock files embed a SHA-256 of the JSON payload inside pre_json; if the
    JSON changes and pre_json is copied verbatim, both the embedded length field
    and the digest go stale and the printer rejects the file.  We recompute both
    here so the file self-validates.
    """
    js = json.dumps(json_dict, indent=2).encode('utf-8')

    pre = bytearray(pre_json)
    # Keep the inner filename (first 64 bytes of pre_json) in sync with the
    # outer BIMH filename.  The inner name is the outer name minus the trailing
    # ".sig" (that is how the stock files are laid out).
    if filename_override and len(pre) >= 64:
        inner = filename_override
        if inner.endswith('.sig'):
            inner = inner[:-4]
        ib = inner.encode('ascii')
        if len(ib) > 64:
            raise ValueError(f"inner filename too long for pre_json ({len(ib)} > 64): {inner}")
        pre[0:64] = b'\x00' * 64
        pre[0:len(ib)] = ib
    # Patch the embedded JSON-body length and SHA-256 digest so they match `js`.
    if len(pre) >= OFF_DIGEST + 32:
        struct.pack_into('<I', pre, OFF_JSON_LEN, len(js))
        pre[OFF_DIGEST:OFF_DIGEST + 32] = hashlib.sha256(js).digest()

    payload = bytes(pre) + js
    hdr = bytearray(hdr)
    hdr_size = struct.unpack_from('<I', hdr, 0x20)[0]
    total = hdr_size + len(payload)
    struct.pack_into('<Q', hdr, 8, total)        # total_size
    struct.pack_into('<Q', hdr, 0x28, len(payload))  # payload_size
    if filename_override:
        nb = filename_override.encode('ascii')
        if len(nb) > 128:
            raise ValueError(f"filename too long for BIMH header ({len(nb)} > 128): {filename_override}")
        hdr[0x30:0x30 + 128] = b'\x00' * 128
        hdr[0x30:0x30 + len(nb)] = nb
    with open(path, 'wb') as f:
        f.write(bytes(hdr) + payload)


# ---- 1. Copy 1.07 base, replace MC/TH/language with 1.10 --------------------
print("1. Building file set...")
for f in os.listdir(V107):
    shutil.copy2(os.path.join(V107, f), os.path.join(OUT, f))

swaps = [
    ('mc_rev7-firmware-v00.00.29.75-20241114122921_product.bin.sig',
     'mc_rev7-firmware-v00.01.33.24-20260312181138_product.bin.sig'),
    ('th_rev9-firmware-v00.00.09.95-20240229141237_product.bin.sig',
     'th_rev9-firmware-v00.02.09.98-20260312152150_product.bin.sig'),
    ('ota-language_v00.00.00.03-20230606143801_product.pack.sig',
     'ota-language_v00.00.00.05-20251204220216_product.pack.sig'),
]
for old, new in swaps:
    p = os.path.join(OUT, old)
    if os.path.exists(p):
        os.remove(p)
    shutil.copy2(os.path.join(V110, new), os.path.join(OUT, new))
    print(f"   swapped {old.split('-')[0]} -> {new}")

# remove old manifest + package-list (we rebuild both)
for f in list(os.listdir(OUT)):
    if f.startswith('ota-p003') and f.endswith('.json.sig'):
        os.remove(os.path.join(OUT, f))
    if f == 'ota-package-list.json.sig':
        os.remove(os.path.join(OUT, f))

# also remove old language OTA json if present
for f in list(os.listdir(OUT)):
    if 'ota-language' in f and f.endswith('.json.sig'):
        os.remove(os.path.join(OUT, f))
# copy 1.10 language ota json if it exists
for f in os.listdir(V110):
    if f.startswith('ota-language') and f.endswith('.json.sig') and 'pack' not in f:
        pass  # skip — not needed for offline


# ---- 2. Build spoofed manifest ----------------------------------------------
print("\n2. Building manifest with correct MD5s...")
hdr, pre, manifest = extract_bimh(
    os.path.join(V107, 'ota-p003_v01.07.00.00-20241210145014.json.sig'))

mc_file = 'mc_rev7-firmware-v00.01.33.24-20260312181138_product.bin.sig'
th_file = 'th_rev9-firmware-v00.02.09.98-20260312152150_product.bin.sig'
ap_file = 'ap-es3_rev4-v01.11.32.89-20241203204535_product.bin.sig'

manifest['ap04']['sig'] = md5f(os.path.join(OUT, ap_file))
manifest['ap04']['url'] = f"http://127.0.0.1/{ap_file}"

manifest['mc07']['sig'] = md5f(os.path.join(OUT, mc_file))
manifest['mc07']['url'] = f"http://127.0.0.1/{mc_file}"
manifest['mc07']['version'] = "00.01.33.24"

manifest['th09']['sig'] = md5f(os.path.join(OUT, th_file))
manifest['th09']['url'] = f"http://127.0.0.1/{th_file}"
manifest['th09']['version'] = "00.02.09.98"

manifest['version'] = "01.07.01.00"

print(json.dumps(manifest, indent=2))

manifest_name = 'ota-p003_v01.07.01.00-20241210145014.json.sig'
write_bimh(os.path.join(OUT, manifest_name), hdr, pre, manifest, manifest_name)
print(f"   -> {manifest_name}")


# ---- 3. Build spoofed package-list -------------------------------------------
print("\n3. Building package-list with correct SHA-256s...")
pkg_hdr, pkg_pre, pkg_json = extract_bimh(
    os.path.join(V107, 'ota-package-list.json.sig'))

# rebuild the packages array from the actual files on disk
packages = []
for f in sorted(os.listdir(OUT)):
    if f == 'ota-package-list.json.sig':
        continue
    fp = os.path.join(OUT, f)
    if os.path.isfile(fp):
        packages.append({
            "file": f,
            "hash": sha256f(fp),
        })

pkg_json['packages'] = packages
# keep the package-list's advertised OTA version in step with the manifest
if 'ota_ver' in pkg_json:
    pkg_json['ota_ver'] = manifest['version']
# some firmwares carry an explicit manifest-name reference; update it if present
if 'ota_json' in pkg_json:
    pkg_json['ota_json'] = manifest_name

write_bimh(os.path.join(OUT, 'ota-package-list.json.sig'),
           pkg_hdr, pkg_pre, pkg_json, 'ota-package-list.json.sig')
print(f"   {len(packages)} files hashed")


# ---- 4. Now re-hash the package-list itself into packages --------------------
# (the package-list references itself in some firmwares — re-generate if needed)


# ---- 5. Create the final zip -------------------------------------------------
print("\n4. Creating final zip...")
zip_name = 'offline-ota-p003_v01.07.01.00-hybrid-spoofed.zip'
zip_path = os.path.join(BASE, zip_name)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(OUT)):
        zf.write(os.path.join(OUT, f), f)

zip_size = os.path.getsize(zip_path)
print(f"\n{'=' * 60}")
print(f"  HYBRID FIRMWARE (SPOOFED) BUILT")
print(f"{'=' * 60}")
print(f"  file: {zip_path}")
print(f"  size: {zip_size / 1024 / 1024:.1f} MB")
print()
print(f"  AP (main SoC):     1.07  v01.11.32.89  (NO telemetry)")
print(f"  MC (motion ctrl):  1.10  v00.01.33.24  (noise cal)")
print(f"  TH (toolhead):     1.10  v00.02.09.98  (extrusion)")
print(f"  AMS:               1.07  v00.00.06.49")
print(f"  Language:           1.10  v00.00.00.05")
print()
print(f"  Manifest MD5s:     RECOMPUTED to match actual files")
print(f"  Package-list SHA256: RECOMPUTED for every file in zip")
print(f"  BIMH header sizes: RECOMPUTED")
print(f"{'=' * 60}")

# ---- 6. Verify everything matches -------------------------------------------
print("\n5. Verification...")
ok = True
# verify manifest MD5s
for key, fname_key in [('ap04', ap_file), ('mc07', mc_file), ('th09', th_file)]:
    expected = manifest[key]['sig']
    actual = md5f(os.path.join(OUT, fname_key))
    match = expected == actual
    print(f"   {key} MD5: {'OK' if match else 'MISMATCH'}")
    if not match:
        ok = False

# verify package-list SHA256s
for pkg in packages:
    fp = os.path.join(OUT, pkg['file'])
    actual = sha256f(fp)
    match = pkg['hash'] == actual
    if not match:
        print(f"   {pkg['file']} SHA256: MISMATCH")
        ok = False

print(f"\n   {'ALL CHECKSUMS VERIFIED' if ok else 'SOME MISMATCHES — CHECK ABOVE'}")
