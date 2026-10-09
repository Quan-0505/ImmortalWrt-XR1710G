# XR1710G 文档索引

> 本目录是 XR1710G（Gemtek / Brightspeed，Airoha AN7581GT）这台设备的实战记录：
> 根因分析（RCA）、部署记录、刷机指南与仓库修复说明。均为实测所得，含证据与「已排除的假设」，
> 便于后来者不重走弯路。

| 文档 | 内容 |
|---|---|
| [GITHUB-UPDATE.md](GITHUB-UPDATE.md) | 项目长期 brief：现存缺陷清单、优先级、验证方法与当前设备状态 |
| [RCA-lan2-10g-flapping.md](RCA-lan2-10g-flapping.md) | lan2 万兆抖动根因（phy5 的 reset-before-id-read）与修复后实机验证 |
| [RCA-daed-multicore-saturation.md](RCA-daed-multicore-saturation.md) | daed 单核吃满：网卡中断集中 CPU0 + RPS 设错队列，含修复 |
| [RCA-proxy-throughput-instability.md](RCA-proxy-throughput-instability.md) | 代理吞吐不稳：内核 netdev_budget 默认为 1，含 A/B 实测 |
| [RCA-proxy-1000M-ceiling.md](RCA-proxy-1000M-ceiling.md) | 代理吞吐 ~550 Mbps 上限的算力账本与测量口径速查 |
| [kixdns-deployment.md](kixdns-deployment.md) | kixdns 部署记录：配置来源、端口选择、接入方式与实测 |
| [FLASH-GUIDE-20261009.md](FLASH-GUIDE-20261009.md) | 刷机指南（release 20261009-bcdc0b3e）：选文件、校验、试运行、刷后判据 |
| [HANDOFF-lan2-10g-fix.md](HANDOFF-lan2-10g-fix.md) | lan2 修复的交接文档（含 UBI 布局刷机注意事项） |
| [repo-fixes-tc-dep-and-feed-publish.md](repo-fixes-tc-dep-and-feed-publish.md) | 仓库两项修复（tc 依赖、自定义 feed 发布）与三条结论纠正 |
| [FIX-lan2-10g-reset-before-id-read.patch](FIX-lan2-10g-reset-before-id-read.patch) | lan2 修复的一行补丁（可 git apply） |

---

固件与发布：<https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases>
仓库说明与构建方式见仓库根目录 [README.md](../README.md)。
