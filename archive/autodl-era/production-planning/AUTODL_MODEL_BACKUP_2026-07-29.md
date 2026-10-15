# AutoDL ComfyUI 模型备份报告

日期：2026-07-29（Asia/Shanghai）

## 结果

- 状态：成功；
- AutoDL 源目录：`/root/autodl-tmp/comfyui-models/`；
- duolaiduo 目标目录：`/media/data/ai-models/comfyui/models/`；
- 源文件：153 个，181,569,648,075 字节；
- 目标文件：153 个，181,569,648,075 字节；
- 软链接：1 个，两端路径和目标一致；
- 路径与逐文件大小：完全一致；
- SHA-256：153/153 完全一致；
- AutoDL 模型删除数：0；
- duolaiduo 备份后模型目录：约 170GiB；
- duolaiduo 数据盘：约 13TiB，总占用约 176GiB，剩余约 12TiB。

## 增量传输

- duolaiduo 原有备份：38 个文件，55,016,694,235 字节；
- 本次新增或大小变化：115 个文件，126,552,953,840 字节；
- `rsync` 状态码：0；
- 删除文件：0；
- 传输耗时：约 43 分 44 秒；
- 平均有效吞吐：约 46MB/s；
- 使用 `--partial --append-verify`，支持中断续传。

## 校验与审计文件

duolaiduo：

- SHA-256 清单：`/media/data/ai-models/comfyui/checksums/autodl-models-sha256-20260729.tsv`；
- 路径与大小清单：`/media/data/ai-models/comfyui/manifests/autodl-model-files-20260729.tsv`；
- 传输日志：`/media/data/ai-models/comfyui/manifests/autodl-backup-20260729.log`；
- 状态码：`/media/data/ai-models/comfyui/manifests/autodl-backup-20260729.status`。

## 安全处理

- 未把Mac或家庭服务器长期私钥复制到AutoDL；
- 在duolaiduo生成一次性拉取密钥，只把受限公钥临时加入AutoDL；
- 完成双端SHA-256校验后，已从AutoDL撤销临时公钥；
- 已从duolaiduo删除一次性私钥及公钥；
- 撤销后确认临时标记数量为0，日常AutoDL SSH仍可使用；
- 未删除或移动AutoDL模型；
- 未自动关闭AutoDL实例。
