# 极暗亮度

Windows 亮度调节小工具：**Fn+F6 调暗、Fn+F7 调亮**，亮度可以低于系统原生最低档。

![Python](https://img.shields.io/badge/Python-3.12+-blue) ![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)

## 功能

- **两级调暗**：先把内屏背光降到硬件最低档；继续按 Fn+F6 时叠加全桌面软件暗化（基于 Windows Magnification API 的颜色矩阵），所有窗口一起变暗，鼠标点击穿透不受影响。
- **调亮**：Fn+F7 先撤销软件暗化，再逐级提高硬件背光，比系统自带滑块多一档亮度上限。
- **退出自动恢复**：关闭窗口或点"立即恢复"时，背光和屏幕颜色都回到启动时的状态。
- **多屏支持**：内屏走 WMI，外接屏尝试 DDC/CI；外屏不支持硬件调节时仍可软件暗化。
- **单实例**：重复启动不会开第二个程序。

## 按键说明

多数笔记本键盘上，F6/F7 默认执行系统功能（亮度、静音等），需要**按住 Fn 再按 F6/F7** 才会向 Windows 发送标准功能键。如果你的键盘开启了 FnLock（Fn+Esc 切换），直接按 F6/F7 即可。

## 运行

### 双击启动（源码）

1. 安装 [Python 3.12](https://www.python.org/downloads/)；
2. 双击 `start.cmd`——首次运行会自动创建虚拟环境并安装依赖（wmi、pywin32），之后直接启动。

### 打包成 exe

```cmd
pip install pyinstaller
pyinstaller --onefile --windowed --name 极暗亮度 screen_dim.py
```

生成 `dist\极暗亮度.exe`（约 11 MB），双击即可运行，无需安装 Python。

## 使用

| 操作 | 效果 |
|------|------|
| Fn+F6 | 调暗一级 |
| Fn+F7 | 调亮一级 |
| 立即恢复 | 回到启动时的亮度 |
| 退出 | 恢复亮度后关闭 |

窗口会显示每块屏幕的当前背光百分比和额外调暗幅度。热键被其他程序占用时会提示冲突，按钮仍然可用。

## 技术说明

- 内屏亮度：WMI `WmiMonitorBrightnessMethods`（需要支持 ACPI 亮度控制的内屏）。
- 外屏亮度：DXVA2 高层 API 或 DDC/CI VCP 0x10。
- 软件暗化：Magnification API 全屏颜色矩阵，效果作用于整个桌面合成层，不改变各窗口内容。
- 软件遮罩能压暗画面，但不能让背光熄灭；真省电请用硬件档。

## 限制

- 软件暗化在部分独占全屏游戏或系统安全桌面下可能不生效。
- 部分外接屏不支持 DDC/CI，只能软件暗化。
- 需要管理员权限的场景（如 UAC 提示框）热键可能被拦截。
