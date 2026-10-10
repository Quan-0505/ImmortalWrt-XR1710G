# XR1710G 文档索引

> 本目录是 XR1710G（Gemtek / Brightspeed，Airoha AN7581GT）这台设备的实战记录：
> 根因分析（RCA）、部署记录、刷机指南与仓库修复说明。均为实测所得，含证据链与「已排除的假设」，
> 便于后来者不重走弯路。

| 文档 | 内容 |
|---|---|
| [CI-verification-20261010.md](CI-verification-20261010.md) | 6.18.54 同步、CI 配置定位修复、run#24 产物验证与正式双布局发布要求 |
| [FIX-lan2-10g-reset-before-id-read.patch](FIX-lan2-10g-reset-before-id-read.patch) | lan2 修复的一行补丁（可 git apply） |
| [FLASH-GUIDE-20261009.md](FLASH-GUIDE-20261009.md) | 刷机指南（release 20261009-bcdc0b3e）：选文件、校验、试运行、刷后判据 |
| [GITHUB-UPDATE.md](GITHUB-UPDATE.md) | 项目长期 brief：缺陷清单、优先级、验证方法与当前设备状态 |
| [HANDOFF-lan2-10g-fix.md](HANDOFF-lan2-10g-fix.md) | lan2 修复的交接文档（含 UBI 布局刷机注意事项） |
| [RCA-daed-multicore-saturation.md](RCA-daed-multicore-saturation.md) | daed 单核吃满：网卡中断集中 CPU0 + RPS 设错队列，含修复 |
| [RCA-lan2-10g-flapping.md](RCA-lan2-10g-flapping.md) | lan2 万兆抖动根因（phy5 的 reset-before-id-read）与修复后实机验证 |
| [RCA-npu-crypto-capability.md](RCA-npu-crypto-capability.md) | NPU 加解密能力实测：NPU（PPE）无密码学单元、EIP93 有硬件无驱动、CPU 无 AES 扩展，而代理流量全走 ChaCha20 故加密非瓶颈 |
| [RCA-proxy-1000M-ceiling.md](RCA-proxy-1000M-ceiling.md) | 代理吞吐 ~550 Mbps 上限的算力账本与测量口径速查 |
| [RCA-proxy-throughput-instability.md](RCA-proxy-throughput-instability.md) | 代理吞吐不稳：内核 netdev_budget 默认为 1，含 A/B 实测 |
| [airoha-bridge-flowtable-offload.md](airoha-bridge-flowtable-offload.md) | Airoha 透明桥 flowtable 本地适配 |
| [kixdns-deployment.md](kixdns-deployment.md) | kixdns 部署记录：配置来源、端口选择、接入方式与实测 |
| [repo-fixes-tc-dep-and-feed-publish.md](repo-fixes-tc-dep-and-feed-publish.md) | 仓库两项修复（tc 依赖、自定义 feed 发布）与三条结论纠正 |
| [xg2010g-voice-debug.md](xg2010g-voice-debug.md) | XG2010G voice debug |

> 本索引按 `docs/` 实际内容生成，新增文档后请同步补一行（未登记的文件会自动取标题）。

---

固件与发布：<https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases>
仓库说明与构建方式见仓库根目录 [README.md](../README.md)。
