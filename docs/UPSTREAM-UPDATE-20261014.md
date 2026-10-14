# XR1710G upstream refresh — 2026-10-14

Merged naoki66/ImmortalWrt-for-Gemtek-brightspeed master through 04cc62e8928308598cf2e88bddee37ede658b814, including ImmortalWrt da63f7d6ac4207e534c9b92ba3d2b555a8edce8d.

- Linux 6.18.55 (previous image: 6.18.54); mt76 2026-10-08 and wireless management updates.
- Keep upstream rollback of forced MT7996 WED and antenna overrides. BBR returns to upstream BBRv1.
- Keep the two XR1710G profiles distinct, both PHY5 fixes, 1.3 GHz CPU ceiling, NETKIT and the persistent Footstrap navigation fix.
- Align built-in board/firmware and fitblk selections in both seeds. Follow upstream removal of the Glass feed; Footstrap remains selected. Update custom feed export for ONU and pushbot feed names.
- Package Go KDAE 2.2.4-r2 with the DNS listener handoff binary from ba1e98402460c165e3269d5458d16aa171daa9f4, successful Backend CI 38321321823. This fixes staged geodata reload failing to bind native DNS port 5355. Public release asset and full binary SHA256 are pinned in payload.json; only public geodata is extracted from the existing verified APK archive.

Existing user subscriptions, rules, CA certificates and IPv4-only runtime configuration must be backed up and preserved when upgrading. Firmware production does not constitute a new on-device validation. Neither partition layout may be flashed over the other.
