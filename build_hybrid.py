"""Build a hybrid 1.07 + 1.10 firmware package for P1S.

Base: 1.07 (no telemetry/cloud-lock)
MC + TH + language from: 1.10 (performance updates, noise calibration)
AP stays: 1.07 (no spyware)
"""
import hashlib, json, os, shutil, struct, zipfile

BASE = r'C:\Users\Administrator\Desktop\bambu-fw'
V107 = os.path.join(BASE, 'v107')
V110 = os.path.join(BASE, 'v110')
OUT  = os.path.join(BASE, 'hybrid')

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def sha256f(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def extract_manifest_json(path):
    with open(path, 'rb') as f:
        data = f.read()
    hdr_size = struct.unpack_from('<I', data, 0x20)[0]
    payload = data[hdr_size:]
    js = payload[payload.find(b'{'):payload.rfind(b'}') + 1]
    return json.loads(js)


# Layout of the pre_json metadata block that sits between the BIMH header and
# the JSON body (verified against the stock 1.07 files):
#   [0x00 .. 0x3F]  inner filename, null-terminated + padding (64 bytes)
#   [0x40]          u32  algo/type id (== 4)
#   [0x44]          u32  length of the JSON body                <-- update me
#   [0x48]          u32  metadata size (== 0x210)
#   [0x4C]          u32  reserved (== 0)
#   [0x50 .. 0x6F]  SHA-256 digest of the JSON body            <-- update me
OFF_JSON_LEN = 0x44
OFF_DIGEST = 0x50


def build_bimh(src_path, json_dict, out_name):
    """Re-wrap `json_dict` using the BIMH header + pre_json block from
    `src_path`, recomputing every size and self-check field so the result
    validates:
      - BIMH total_size (0x08) and payload_size (0x28)
      - BIMH outer filename (0x30)
      - pre_json inner filename (0x00), JSON length (0x44) and SHA-256 (0x50)
    Returns the finished bytes.
    """
    with open(src_path, 'rb') as f:
        data = f.read()
    hdr_size = struct.unpack_from('<I', data, 0x20)[0]
    hdr = bytearray(data[:hdr_size])
    payload = data[hdr_size:]
    pre = bytearray(payload[:payload.find(b'{')])

    js = json.dumps(json_dict, indent=2).encode('utf-8')

    # inner filename (outer name without the trailing ".sig")
    inner = out_name[:-4] if out_name.endswith('.sig') else out_name
    ib = inner.encode('ascii')
    if len(ib) > 64:
        raise ValueError(f"inner filename too long ({len(ib)} > 64): {inner}")
    pre[0:64] = b'\x00' * 64
    pre[0:len(ib)] = ib
    # embedded json length + digest
    if len(pre) >= OFF_DIGEST + 32:
        struct.pack_into('<I', pre, OFF_JSON_LEN, len(js))
        pre[OFF_DIGEST:OFF_DIGEST + 32] = hashlib.sha256(js).digest()

    new_payload = bytes(pre) + js
    struct.pack_into('<Q', hdr, 8, hdr_size + len(new_payload))       # total_size
    struct.pack_into('<Q', hdr, 0x28, len(new_payload))              # payload_size
    nb = out_name.encode('ascii')
    if len(nb) > 128:
        raise ValueError(f"filename too long for BIMH header ({len(nb)} > 128): {out_name}")
    hdr[0x30:0x30 + 128] = b'\x00' * 128
    hdr[0x30:0x30 + len(nb)] = nb
    return bytes(hdr) + new_payload


# 1. Copy all 1.07 files as the base
print("1. Copying 1.07 base...")
for f in os.listdir(V107):
    shutil.copy2(os.path.join(V107, f), os.path.join(OUT, f))

# 2. Replace MC, TH, language with 1.10 versions
replacements = {
    'mc': ('mc_rev7-firmware-v00.00.29.75-20241114122921_product.bin.sig',
           'mc_rev7-firmware-v00.01.33.24-20260312181138_product.bin.sig'),
    'th': ('th_rev9-firmware-v00.00.09.95-20240229141237_product.bin.sig',
           'th_rev9-firmware-v00.02.09.98-20260312152150_product.bin.sig'),
    'lang': ('ota-language_v00.00.00.03-20230606143801_product.pack.sig',
             'ota-language_v00.00.00.05-20251204220216_product.pack.sig'),
}

for key, (old_name, new_name) in replacements.items():
    old_path = os.path.join(OUT, old_name)
    new_src = os.path.join(V110, new_name)
    if os.path.exists(old_path):
        os.remove(old_path)
    shutil.copy2(new_src, os.path.join(OUT, new_name))
    print(f"   {key}: replaced with 1.10 -> {new_name}")

# 3. Build new manifest
print("\n2. Building hybrid manifest...")
manifest = extract_manifest_json(
    os.path.join(V107, 'ota-p003_v01.07.00.00-20241210145014.json.sig'))

mc_new = 'mc_rev7-firmware-v00.01.33.24-20260312181138_product.bin.sig'
manifest['mc07']['sig'] = md5(os.path.join(OUT, mc_new))
manifest['mc07']['url'] = f"http://127.0.0.1/{mc_new}"
manifest['mc07']['version'] = "00.01.33.24"

th_new = 'th_rev9-firmware-v00.02.09.98-20260312152150_product.bin.sig'
manifest['th09']['sig'] = md5(os.path.join(OUT, th_new))
manifest['th09']['url'] = f"http://127.0.0.1/{th_new}"
manifest['th09']['version'] = "00.02.09.98"

# bump the version slightly so it's distinct from stock 1.07
manifest['version'] = "01.07.01.00"

print(json.dumps(manifest, indent=2))

# 4. Rebuild the manifest .json.sig (BIMH wrapper)
print("\n3. Rebuilding manifest BIMH...")
src_manifest = os.path.join(V107, 'ota-p003_v01.07.00.00-20241210145014.json.sig')
new_manifest_name = 'ota-p003_v01.07.01.00-hybrid.json.sig'

# remove old manifest(s) FIRST so the package-list rebuild below sees only the
# final file set (avoids hashing a manifest we are about to delete)
for f in os.listdir(OUT):
    if f.startswith('ota-p003') and f.endswith('.json.sig'):
        os.remove(os.path.join(OUT, f))

manifest_path = os.path.join(OUT, new_manifest_name)
with open(manifest_path, 'wb') as f:
    f.write(build_bimh(src_manifest, manifest, new_manifest_name))
print(f"   manifest: {new_manifest_name}")

# 5. Rebuild the package-list so its SHA-256 hashes + manifest reference match
#    the actual hybrid file set (stale 1.07 entries removed, new files added).
print("\n4. Rebuilding package-list...")
src_pkg_list = os.path.join(V107, 'ota-package-list.json.sig')
pkg_json = extract_manifest_json(src_pkg_list)

# rebuild the packages array from the files actually on disk.  Match stock
# behaviour: the package-list lists the manifest but NOT itself.
packages = []
for f in sorted(os.listdir(OUT)):
    if f == 'ota-package-list.json.sig':
        continue
    fp = os.path.join(OUT, f)
    if os.path.isfile(fp):
        packages.append({"file": f, "hash": sha256f(fp)})
pkg_json['packages'] = packages
if 'ota_ver' in pkg_json:
    pkg_json['ota_ver'] = manifest['version']

with open(os.path.join(OUT, 'ota-package-list.json.sig'), 'wb') as f:
    f.write(build_bimh(src_pkg_list, pkg_json, 'ota-package-list.json.sig'))
print(f"   {len(packages)} files hashed")

# 6. Create the final zip
print("\n5. Creating final zip...")
zip_name = 'offline-ota-p003_v01.07.01.00-hybrid-notelemetry.zip'
zip_path = os.path.join(BASE, zip_name)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(OUT)):
        zf.write(os.path.join(OUT, f), f)

zip_size = os.path.getsize(zip_path)
print(f"\n{'=' * 60}")
print(f"  HYBRID FIRMWARE BUILT")
print(f"{'=' * 60}")
print(f"  file: {zip_path}")
print(f"  size: {zip_size / 1024 / 1024:.1f} MB")
print()
print(f"  AP (main SoC):     1.07  v01.11.32.89  (NO telemetry)")
print(f"  MC (motion ctrl):  1.10  v00.01.33.24  (noise cal, vibration comp)")
print(f"  TH (toolhead):     1.10  v00.02.09.98  (extrusion improvements)")
print(f"  AMS:               1.07  v00.00.06.49  (matches AP)")
print(f"  Language:           1.10  v00.00.00.05  (updated translations)")
print(f"  EXT:               1.07  v01.00.00.03  (unchanged)")
print(f"{'=' * 60}")
print(f"\nFlash via USB: copy zip to SD card -> printer menu -> update")
print(f"Or via network: copy to printer /tmp/ and trigger update")
