# XR1710G 的 Go KDAE 与 LuCI 入口

固件将 Rust daed 替换为 [daed-kdae v2.2.4-kdae](https://github.com/Quan-0505/daed-kdae/releases/tag/v2.2.4-kdae)，使用静态 AArch64 二进制，界面内嵌。原来的旧 Web 覆盖层已移除。

## 管理入口

两个 XR1710G 配置种子均预装 `luci-app-daed`。点击 **LuCI → 服务 → daed**，直接跳转到当前路由器上的面板。端口读取 `/etc/config/daed` 的 `main.listen`（默认 `0.0.0.0:2023`），无需输入 IP 和端口。IPv6 主机地址保留方括号；从 HTTPS LuCI 进行顶层跳转，避免 HTTP iframe 被浏览器拦截。返回键会回到先前的 LuCI 页面。

## 数据目录与迁移

- Go 数据目录：`/etc/daed-kdae/`，数据库 `wing.db`。
- 原 Rust 数据目录：`/etc/daed/`，数据库 `daed.db`，保留用于迁移或恢复。
- 原 UCI 的 `enabled`、`listen`、`respawn` 继续使用；Rust 的 `state`、`web_root` 和 `http_profile` 不作为 Go 参数传入。
- `/lib/upgrade/keep.d/daed` 登记两个数据目录和 UCI 文件。刷写前仍须核对备份内容，不能只依赖保留配置选项。

Rust 数据库不能直接当作 Go 数据库。带旧数据升级前，停止 Rust 后生成一致的数据库备份，在有 Python 3 的电脑/构建机使用 KDAE 仓库的 `backend/migrate-rust-state.py`，配合空 Go 数据库模板转换到独立的 `wing.db`。原账号 ID、JWT secret 与资源绑定保留；原 Argon2 密码首次验证成功后自动转为 Go 哈希。将迁移好的库放入 Go 数据目录，再启动 Go；没有迁移库时会进入新账户/配置初始化。

完整迁移步骤与验证边界见 [KDAE 后端说明](https://github.com/Quan-0505/daed-kdae/blob/main/backend/README.md)。程序、原数据库、服务配置和 geodata 均应备份；失败时恢复对应的旧程序与服务配置，不覆盖原 Rust 数据库。

固件源码和安装包不包含设备数据库、订阅、节点、密码、令牌或私有备份。

## 构建验证

`PATCH/daed-pkg/payload.json` 固定公开归档与二进制 SHA256。下载器只提取程序、Geoip 和 Geosite，并核对静态 ELF64 AArch64。LuCI 与 daed 均替换实际 feed 定义，避免 `package/new/` 被遮蔽。

构建后检查：两种布局的 manifest 中为 `daed - 2.2.4-r1` 与 `luci-app-daed - 2.2.4-r1`；真实固件根目录中的程序哈希、执行权限、启动参数、备份目录、LuCI 菜单/ACL/跳转行为，以及内核 BTF/BPF/veth/clsact/Netkit 支持。

镜像构建与内容校验通过后按仓库规则发布，两套分区布局不能互刷。此接入不自动刷写正在运行的路由器。
