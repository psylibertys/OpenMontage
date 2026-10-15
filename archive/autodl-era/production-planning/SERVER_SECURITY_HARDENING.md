# duolaiduo 家庭服务器 SSH 与防火墙加固方案

> 状态：已完成只读审计；尚未修改服务器配置、用户、密钥、防火墙、Docker、路由器或服务状态
> 审计日期：2026-07-22（Asia/Shanghai）
> 目标：降低公网 SSH 暴力扫描和非必要端口暴露，同时不锁死现有管理通道，并保持 AutoDL 使用 `model-sync` 只读 SFTP 的能力。

## 1. 结论

当前应按“高优先级加固”处理，但尚未发现成功入侵的直接证据。最重要的事实是：公网机器人持续碰撞的 SSH 服务仍允许普通账号密码认证；主机数据面防火墙实际未启用；多个服务监听所有网卡；Docker 发布端口需要单独处理，不能只依赖 UFW。

推荐目标形态：

1. 管理账号 `psynaut` 和只读模型账号 `model-sync` 均只允许 SSH 公钥；彻底禁止 root SSH 登录。
2. 仅保留一个 SSH 端口。优先让管理访问走 Tailscale；如果 AutoDL 暂时不能加入 Tailnet，则公网保留 TCP 2222，但必须是公钥认证，并配合限速和 Fail2ban。
3. 主机默认拒绝入站，只放行经过确认的公网、局域网和 Tailscale 流量。
4. 反向代理后的应用只绑定 `127.0.0.1`；Samba、Jellyfin 发现和代理端口仅允许局域网；Docker 发布端口通过绑定回环或 `DOCKER-USER` 单独收口。
5. 先修复自动安全更新因电源判断停止的问题，再补齐积压的安全更新。

## 2. 只读审计证据

### 2.1 SSH

`sshd -t` 通过。有效配置与监听状态如下：

| 项目 | 当前值 | 判断 |
|---|---|---|
| SSH 监听 | TCP 22、2222；IPv4/IPv6 所有地址 | 两个入口扩大扫描面 |
| `PasswordAuthentication` | `yes` | 高风险；机器人可持续尝试密码 |
| `PermitRootLogin` | `without-password` | root 密码被禁止，但仍允许 root 公钥登录 |
| `PubkeyAuthentication` | `yes` | 可作为禁用密码前的迁移基础 |
| `MaxAuthTries` | 6 | 可收紧到 3 |
| `LoginGraceTime` | 120 秒 | 可收紧到 30 秒 |
| `MaxStartups` | `10:30:100` | 面对大量并发扫描偏宽松 |
| `X11Forwarding` | `yes` | 当前用途不需要，建议关闭 |
| `AllowTcpForwarding` | `yes` | 当前用途不需要，建议默认关闭 |
| Fail2ban / sshguard | 未安装 | 没有自动延时/封禁层 |

配置来源包括：

- `/etc/ssh/sshd_config`：同时声明 `Port 22` 与 `Port 2222`；
- `/etc/ssh/sshd_config.d/50-cloud-init.conf`：明确设置 `PasswordAuthentication yes`，并重复声明两个端口；
- `/etc/ssh/sshd_config.d/60-model-sync.conf`：为 `model-sync` 配置只读 SFTP、禁用密码/TTY/转发，设计正确。

过去 24 小时的 SSH 日志统计：

| 事件 | 次数 |
|---|---:|
| `Failed password` | 32,232 |
| `Invalid user` | 8,778 |
| PAM `authentication failure` | 32,237 |
| `Connection closed by invalid user` | 8,506 |
| `Accepted password` | 23/24（采集窗口临界点造成 1 次差异） |
| `Accepted publickey` | 74 |

成功认证按账号/方式汇总为：`psynaut` 公钥 70 次、密码 24 次，`model-sync` 公钥 4 次。它说明密码登录仍在实际使用，不能在没有验证公钥管理通道前直接关闭。审计未发现 root 成功登录记录，但这不等于完成了入侵排查。

密钥与权限：

- `/home/psynaut/.ssh` 为 `0700`，`authorized_keys` 为 `0600`，符合要求；检测到 2 个 Ed25519 公钥指纹。
- `/etc/ssh/authorized_keys/model-sync` 为 root 所有、普通只读，检测到预期的独立 Ed25519 公钥。
- `/root/.ssh/authorized_keys` 存在且权限为 `0600`，但 `ssh-keygen -lf` 无法解析为公钥文件。禁止 root 登录前需人工只看结构和用途，避免误删云初始化标记或未知内容；文档不记录其内容。

### 2.2 防火墙与端口

资产清单记录的 UFW `inactive` 与本次有效检查一致：`ufw status verbose` 和 `ufw status numbered` 均为 `inactive`。虽然 systemd 的 `ufw.service` 显示 enabled/active，但这不代表过滤规则已启用。

当前 IPv4/IPv6 `INPUT` 策略均为 `ACCEPT`。除 80/443 外，下列服务监听所有网卡，是否暴露到公网仍取决于路由器 NAT、IPv6 和上游策略：

- SSH：22、2222/TCP；
- Samba：139、445/TCP，137、138/UDP；
- New API：3000/TCP；
- Douyin/TikTok API：6080/TCP；
- VCPToolBox：6005、6006/TCP；
- API 反代：7444/TCP；
- Jellyfin：8096/TCP、7359/UDP；
- Mihomo：7890、7891、7892/TCP/UDP。

Docker 证据：

- `new-api` 明确发布为 `0.0.0.0:3000` 和 `[::]:3000`；
- `douyin_tiktok_download_api`、`jellyfin` 使用 host 网络；
- `DOCKER-USER` 链为空；
- Docker 已为 3000 创建独立转发和放行规则。

因此，仅启用 UFW 不足以保证 Docker 发布端口被挡住。应优先把只供 Nginx 使用的容器端口绑定到 `127.0.0.1`，并把 `DOCKER-USER` 当成额外防线。

### 2.3 安全更新

- `unattended-upgrades` 已启用且服务 active；APT 周期更新和自动升级配置均为 `1`。
- 登录提示显示 190 个可更新包，其中 138 个标准安全更新；本地 APT 缓存复核约为 182/130，差异来自缓存与提示生成时间。
- `unattended-upgrade --dry-run --debug` 返回 `System is on battery power, stopping`，`on_ac_power` 返回非零。也就是说服务“启用”不等于安全更新实际执行。

这项需要优先调查 UPS、电源检测或 APT 电池策略，不能在未理解原因时简单绕过。

## 3. 风险分级

| 级别 | 风险 | 建议时限 |
|---|---|---|
| P0 | 密码认证开启且 24 小时约 3.2 万次密码失败 | 公钥验证完成后立即关闭密码认证 |
| P0 | UFW 实际 inactive、INPUT 默认 ACCEPT，多项服务全网卡监听 | 在端口用途和 NAT 盘点后尽快启用默认拒绝 |
| P1 | Docker 3000 直接发布、`DOCKER-USER` 为空；UFW 可能被 Docker 绕过 | 与防火墙同一变更窗口处理 |
| P1 | 大量安全更新积压，自动更新因“电池供电”判断停止 | 先排查电源判断，再分批补丁 |
| P1 | 22/2222 双端口、root 公钥登录仍允许、无 Fail2ban | SSH 第一阶段处理 |
| P2 | X11 和 TCP 转发全局开启；认证时限与重试偏宽 | SSH 加固时一并收紧 |
| 待验证 | 路由器 NAT、IPv6 公网可达性、上游 ACL、成功登录是否均为本人 | 变更前完成 |

## 4. 分阶段实施方案

以下各阶段都涉及服务器或网络状态变更，必须单独获得用户批准后执行。本次只完成审计和方案。

### 阶段 0：先建立基线，不改配置

1. 核对路由器 NAT/端口转发，尤其是公网 22、2222、7443 及各应用端口。
2. 从局域网、移动网络和 Tailnet 三个视角做端口探测，区分“主机监听”和“真实公网暴露”。
3. 核对过去 7 天所有成功登录的时间、账号、方式和来源，确认均为本人、AutoDL 或既有自动化。
4. 记录 SSH 主机指纹、当前有效配置、UFW/iptables/nftables 和 Docker 端口基线。
5. 确认本地至少有一个可用的 `psynaut` 私钥，并做离线备份。

### 阶段 1：验证公钥管理通道

1. 保持当前会话不断开，另开第二个终端。
2. 使用公钥从公网 TCP 2222 登录 `psynaut`；再从 Tailscale 地址登录一次。
3. 验证 `sudo -v`、SFTP 下载和关键运维命令。
4. 使用 AutoDL 侧私钥验证 `model-sync`：能读取 `/models`，不能写入、不能获得 shell、不能端口转发。
5. 只有上述验证全部通过，才进入阶段 2。

### 阶段 2：SSH 配置收紧

推荐最终有效策略：

```text
Port 2222
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
MaxAuthTries 3
LoginGraceTime 30
MaxStartups 10:30:30
X11Forwarding no
AllowTcpForwarding no
PermitTunnel no
AllowUsers psynaut model-sync
ClientAliveInterval 300
ClientAliveCountMax 2
```

注意 OpenSSH 使用“首次取得的值”。当前 `50-cloud-init.conf` 先设置了 `PasswordAuthentication yes`，所以简单新增 `90-hardening.conf` 未必能覆盖它；并且 `60-model-sync.conf` 进入 `Match User model-sync` 后，后续文件若没有 `Match all` 可能继续落在该 Match 上下文。实施时应：

- 优先创建更早加载的全局文件，例如 `01-hardening.conf`；
- 或在保留备份的前提下修改 cloud-init drop-in；
- 每次都以 `sshd -T` 和 `sshd -T -C user=model-sync,...` 验证最终值，而不是只看文件文本。

`model-sync` 的现有 Match 块继续保留：`ForceCommand internal-sftp -R`、Chroot、禁止密码、TTY、agent/TCP/X11/tunnel 转发。全局 `AllowUsers` 必须包含它。

端口从 22/2222 改为只保留 2222 时，还要同步 systemd socket activation。需要 `daemon-reload` 和重启 `ssh.socket`，这比单纯 reload `ssh.service` 风险更高，应最后单独做，并先确认路由器和客户端均使用 2222。

### 阶段 3：Fail2ban 与 SSH 限速

建议安装 Fail2ban，使用 systemd 日志后端，并在过渡期监控 `22,2222`，移除 22 后只监控 2222。起始参数建议：

```text
enabled  = true
backend  = systemd
port     = 22,2222
maxretry = 3
findtime = 10m
bantime  = 1h
```

稳定后可启用递增封禁。使用 nftables/iptables 兼容的 banaction，并验证重启后仍生效。不要永久白名单宽泛公网网段；如需白名单，仅使用确认过的 Tailnet/管理出口。Fail2ban 是降噪和抑制层，不能替代公钥认证和防火墙。

### 阶段 4：主机防火墙与端口收口

推荐 UFW 初始策略：默认拒绝入站、允许出站、启用 IPv6。必须先添加 allow 规则，再启用 UFW。

建议流量分类：

| 服务 | 建议来源 |
|---|---|
| 80/443 | 公网（确有公开站点需求） |
| SSH 2222 | 优先 Tailscale；AutoDL 未入 Tailnet时可暂时公网开放，但仅公钥、限速、Fail2ban |
| SSH 22 | 迁移期仅 LAN/Tailscale；验证后删除 |
| Samba 137/138/139/445 | 仅 `192.168.50.0/24` |
| Jellyfin 8096/7359 | 仅 LAN/Tailscale；公网需求走认证完善的反代 |
| Mihomo 7890/7891/7892 | 仅 LAN，最好绑定内网地址，不得公网开放 |
| 3000、6005、6006、6080、7444 | 优先绑定 `127.0.0.1`，只由 Nginx 访问 |
| Tailscale | 允许 `tailscale0`，保留其 UDP 穿透端口 |

Docker 处理顺序：

1. 把 New API 端口改为 `127.0.0.1:3000:3000`；
2. 评估 host 网络容器是否可以改 bridge + 显式回环绑定；
3. 对无法改绑定的端口，在 `DOCKER-USER` 中先允许 established/related、LAN/Tailscale 和必要公网端口，再拒绝 WAN 入站；
4. 从外部网络实测，不能只看 `ufw status`。

### 阶段 5：路由器与 Tailscale 收口

1. 删除没有业务依据的公网端口转发。
2. 管理面优先迁移到 Tailscale，Funnel 保持关闭。
3. 如果 AutoDL 可安装 Tailscale，则让 `model-sync` 也走 Tailnet，并关闭公网 SSH 转发；这是最终推荐形态。
4. 如果 AutoDL 实例短期、动态且不适合加入 Tailnet，则保留公网 2222 的公钥 SFTP，配合 Fail2ban/限速；不要为了 allowlist 随意放行云厂商大网段。

### 阶段 6：补丁与持续维护

1. 查明 `on_ac_power=1` 的原因，确认是否为 UPS/虚拟电池误判或 APT 策略。
2. 先做数据和关键配置备份，再分批安装积压的安全更新。
3. 如更新包含内核、OpenSSH、Docker 或网络组件，安排维护窗口和重启验证。
4. 每月复核 SSH 成功登录、封禁统计、开放端口、Docker 映射、补丁状态和磁盘备份。

## 5. 防锁死、回滚与验证流程

### 5.1 SSH 变更

1. 备份所有 SSH 主配置、drop-in 和 systemd socket 配置，记录时间戳与校验值。
2. 保持第一条已登录的管理员会话不退出。
3. 预设 5–10 分钟自动回滚任务；验证成功后再取消。该任务本身也是变更，需批准。
4. 修改后先运行 `sshd -t`；失败则不 reload。
5. 用 `sshd -T` 验证全局策略，再用 `sshd -T -C user=model-sync,...` 验证 Match 策略。
6. 仅涉及认证项时先 reload；涉及 Port/systemd socket 时，在第二维护窗口处理。
7. 从第二终端分别验证：`psynaut` 公钥登录与 sudo、错误密码被拒绝、root 被拒绝、`model-sync` 只读 SFTP。
8. 若失败，使用第一条会话恢复备份并 reload；若会话已断，等待预设回滚任务执行。

### 5.2 防火墙变更

1. 备份 UFW、iptables/nftables 和 Docker 规则；保存路由器 NAT 截图。
2. 先加入 SSH/Tailscale/LAN/80/443 的必要 allow，再设置默认拒绝。
3. 启用后保持现有会话，使用第二终端和外部网络逐端口验证。
4. Docker 端口必须单独实测；若管理通道异常，立即 `ufw disable` 并恢复备份规则。

### 5.3 通过标准

- `sshd -T` 显示：仅 2222、root no、password no、publickey yes；
- `psynaut` 公钥登录和 sudo 正常，密码登录失败；
- root 使用密码和公钥均失败；
- `model-sync` 可下载、不可上传、不可 shell、不可转发；
- 互联网只能访问明确批准的公网端口；LAN/Tailscale 服务仍正常；
- `ufw status verbose` 为 active，但还必须确认 Docker 端口外部不可达；
- Fail2ban jail active，测试失败登录会计数，正常 AutoDL 同步不会误封；
- 自动安全更新不再因电源检测跳过，补丁积压得到处理。

## 6. 需要单独批准的实际操作

本次均未执行。未来以下动作必须逐项获批：

- 新增/修改 SSH drop-in、cloud-init SSH 配置、systemd `ssh.socket`；
- 禁用密码/root 登录、删除 22 端口、reload/restart SSH；
- 安装和配置 Fail2ban；
- 启用或修改 UFW、nftables、iptables、`DOCKER-USER`；
- 修改 Docker Compose/端口绑定或重建容器；
- 修改路由器 NAT、IPv6 防火墙或 Tailscale ACL；
- 修改 APT 电源策略、安装更新或重启服务器；
- 删除/替换任何账号、authorized_keys 或密钥。

## 7. 待验证项

- 路由器实际公网 NAT/端口转发清单，以及公网 7443 到本机 443 的映射；
- 主机是否拥有可路由公网 IPv6，IPv6 入站是否有上游防火墙；
- 24 小时内 24 次 `psynaut` 密码成功登录是否全部为本次人工操作；
- `/root/.ssh/authorized_keys` 的结构和来源；
- Mihomo、Samba、Jellyfin、VCP、Douyin API 各端口真实需要的访问范围；
- Fail2ban 应使用的 nftables/iptables banaction；
- 自动更新的“电池供电”判断来源及安全修复方式；
- 备份与恢复演练是否覆盖 SSH、UFW、Docker、Nginx 和应用数据。
