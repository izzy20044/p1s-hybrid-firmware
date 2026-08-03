# P1S Hybrid Firmware — 1.07 Privacy + 1.10 Performance

> **CURRENTLY DOES NOT WORK — STAY TUNED.** Bambu's firmware uses RSA-2048 signatures on every component and the OTA manifest. The printer rejects modified packages. We're investigating alternative flashing methods (MQTT component push, UART, etc.). The build scripts and research are here for the community to build on.

Custom hybrid firmware for the **Bambu Lab P1S** that keeps the privacy and offline freedom of firmware 1.07 while pulling in the performance improvements from 1.10.

## Why?

Firmware versions after 1.07 introduced:
- Mandatory cloud connectivity / authorization control system (1.08+)
- Telemetry and usage data collection
- Restrictions on LAN-only and third-party control
- Gating of basic printer functions behind cloud accounts

If you run your P1S **offline** and want to keep full control of your printer without phoning home, 1.07 is the last firmware that respects that. But 1.07 misses out on real performance improvements in the motion controller and toolhead firmware.

This hybrid gives you both.

## What's Inside

| Component | Version | Source | What You Get |
|---|---|---|---|
| **AP (Main SoC)** | v01.11.32.89 | **1.07** | No telemetry, no cloud-lock, full offline control |
| **MC (Motion Controller)** | v00.01.33.24 | **1.10** | Noise calibration improvements, vibration compensation, motor tuning |
| **TH (Toolhead)** | v00.02.09.98 | **1.10** | Updated extrusion and retraction control |
| **AMS** | v00.00.06.49 | **1.07** | Matched to AP version (1.10 AMS is for AMS 2 Pro hardware) |
| **Language Pack** | v00.00.00.05 | **1.10** | Updated translations |
| **AHB / EXT** | Unchanged | Identical across both versions |

All checksums (BIMH header sizes, manifest MD5s, package-list SHA-256s, embedded SHA-256 digests, inner/outer filenames) are fully recomputed to match the actual file contents.

## Download

Grab the latest from the [Releases page](https://github.com/izzy20044/p1s-hybrid-firmware/releases).

## How to Flash (Offline, No Internet Required)

1. Copy the zip file to a **MicroSD card** (FAT32)
2. Insert into the P1S
3. Go to **Settings > Firmware > Update** on the printer's touchscreen
4. Select the firmware file
5. Wait for the update to complete (~5 minutes)

## After Flashing

**Important:** Re-run these calibrations since the motion controller and toolhead firmware changed:

1. **Motor Noise Cancellation** — Control > Calibration > Motor Noise Cancellation (~10 min)
2. **Vibration Compensation / Resonance** — Control > Calibration > Vibration Compensation
3. **Pressure Advance** — Run PA calibration from OrcaSlicer (per-filament)

## Recommended Settings

- **Enable LAN-Only Mode** — Settings > Network > LAN Only Mode
- **Enable Developer Mode** — Settings > Network > Developer Mode (opens local MQTT, FTP, and video stream with zero cloud dependency)
- **Tune in OrcaSlicer** — Acceleration, jerk, input shaping, fan curves, and PA are all controllable from the slicer without any firmware changes

## Build It Yourself

If you'd rather not trust a pre-built zip, you can build the hybrid from stock Bambu firmware yourself.

### Requirements
- Python 3.10+
- Stock firmware ZIPs:
  - `offline-ota-p003_v01.07.00.00-*.zip` (1.07)
  - `offline-ota-p003_v01.10.00.00-*.zip` (1.10)

You can get these from [bambu.pages.dev](https://bambu.pages.dev) or from the [user-bambulab-firmware](https://github.com/search?q=user-bambulab-firmware) community repos.

### Steps

```bash
# 1. Create a working directory and extract both firmwares
mkdir bambu-fw && cd bambu-fw
mkdir v107 v110
cd v107 && unzip /path/to/offline-ota-p003_v01.07*.zip && cd ..
cd v110 && unzip /path/to/offline-ota-p003_v01.10*.zip && cd ..

# 2. Place the build script in the same directory
# (download build_hybrid.py from this repo)

# 3. Edit the BASE path in build_hybrid.py to point to your bambu-fw directory

# 4. Run it
python build_hybrid.py

# 5. Your hybrid zip will be in the bambu-fw directory
```

The script:
1. Copies all 1.07 files as the base
2. Swaps in 1.10's MC, TH, and language pack (untouched Bambu-signed binaries)
3. Rebuilds the OTA manifest with correct MD5 hashes
4. Rebuilds the package-list with correct SHA-256 hashes for every file
5. Recomputes all BIMH header sizes, embedded JSON lengths, and embedded SHA-256 digests
6. Packs everything into a flashable zip

You can inspect and verify every step — it's ~190 lines of Python with no dependencies.

## Technical Details

### What We Change
- The OTA manifest JSON is rebuilt with updated component references (MD5 hashes, version strings, filenames)
- The package-list JSON is rebuilt with SHA-256 hashes of every file in the package
- Both JSON files are re-wrapped in BIMH headers with correct sizes and embedded digests

### What We Don't Touch
- The AP (main SoC) firmware is **AES-XTS-256 encrypted with RSA-2048 signatures and Secure Boot** (keys fused into the chip's eFuse). It cannot be decrypted, diffed, or binary-patched without the vendor's private key.
- Each component `.bin.sig` file is an **untouched, Bambu-signed original** — only the manifest and package-list wrappers are rebuilt.

### Why Not Use 1.10's AMS Firmware?
The 1.10 AMS firmware (`v01.00.06.83`) has a major version bump (`00` → `01`) corresponding to the AMS 2 Pro generation and the post-1.08 authorization protocol rework. Pairing it with the 1.07 AP risks communication errors. The original AMS firmware (`v00.00.06.49`) is correctly matched to the 1.07 AP.

### Why Not Use the Full 1.10 AP?
The 1.10 AP firmware (`v01.16.38.70`) includes the Authorization Control System introduced in 1.08 — mandatory cloud auth, telemetry, and third-party control restrictions. The AP firmware is encrypted and signed; the telemetry cannot be stripped out. Keeping the 1.07 AP is the only way to maintain full offline control.

## Compatibility

- **Printer:** Bambu Lab P1S (model code C11 / P003)
- **AMS:** Works with the original AMS. Do NOT use with AMS 2 Pro (that requires 1.10's AMS firmware)
- **Starting firmware:** Any P1S firmware version

## Known Limitations

- If the printer's bootloader validates an RSA signature on the OTA manifest (not just the individual component signatures), the flash will be rejected. This is unlikely on pre-1.08 firmware with SD-card offline flashing, but can only be confirmed by trying.
- The 1.07 AP does not include AP-layer UI improvements or bug fixes from 1.08–1.10. Motion and extrusion improvements are covered by the MC/TH swap.

## Disclaimer

Use at your own risk. This is an unofficial modification. Keep a backup of your current firmware. Not responsible for bricked printers, failed prints, or voided warranties.

## License

The firmware binaries are property of Bambu Lab. The build scripts and documentation are released under MIT License.
