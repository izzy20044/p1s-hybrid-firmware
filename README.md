# P1S Hybrid Firmware — 1.07 Privacy + 1.10 Performance

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

## Downloads

- **`offline-ota-p003_v01.07.01.00-hybrid-notelemetry.zip`** — Try this one first
- **`offline-ota-p003_v01.07.01.00-hybrid-spoofed.zip`** — Backup variant with fully recomputed checksums (BIMH header sizes, manifest MD5s, package-list SHA-256s, embedded SHA-256 digests, inner/outer filenames)

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

## Technical Details

The hybrid is built by:
1. Extracting both stock firmware ZIPs (1.07 and 1.10)
2. Using 1.07 as the base
3. Swapping in 1.10's MC, TH, and language pack binaries (these are untouched, Bambu-signed originals)
4. Rebuilding the OTA manifest with correct MD5 hashes
5. Rebuilding the package-list with correct SHA-256 hashes
6. Recomputing all BIMH header sizes, embedded JSON lengths, and embedded SHA-256 digests

The build scripts (`build_hybrid.py` and `build_hybrid_spoofed.py`) are included so you can verify or rebuild the package yourself.

### What We Don't Touch

- The AP (main SoC) firmware is **AES-XTS-256 encrypted with RSA-2048 signatures and Secure Boot** (keys fused into the chip's eFuse). It cannot be decrypted, diffed, or binary-patched without the vendor's private key.
- Each component `.bin.sig` file is an untouched Bambu-signed original — only the manifest and package-list wrappers are rebuilt.

## Compatibility

- **Printer:** Bambu Lab P1S only (model code C11 / P003)
- **AMS:** Works with the original AMS. Do NOT use with AMS 2 Pro (that requires 1.10's AMS firmware)
- **Starting firmware:** Any P1S firmware version (the offline flash overwrites all components)

## Known Limitations

- If the printer's bootloader validates an RSA signature on the OTA manifest itself (not just the individual component signatures), the flash will be rejected. This is unlikely on pre-1.08 firmware with SD-card offline flashing, but can only be confirmed by trying.
- The 1.07 AP does not include UI improvements or bug fixes from 1.08–1.10 that are specific to the AP layer. Motion and extrusion improvements are covered by the MC/TH swap.

## Disclaimer

Use at your own risk. This is an unofficial modification. Keep a backup of your current firmware. The authors are not responsible for bricked printers, failed prints, or voided warranties.

## Credits

Built with analysis assistance from multiple AI models for firmware structure reverse-engineering, BIMH format parsing, and checksum verification.

## License

The firmware binaries are property of Bambu Lab. The build scripts and this documentation are released under MIT License.
