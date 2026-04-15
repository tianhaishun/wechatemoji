# WeChat Emoji Extractor

从微信客户端提取自定义表情包，支持解密导出为 PNG/GIF 格式。

## 功能

- 自动检测本机微信账号和表情数据库
- 解密微信加密的表情文件（V1MMWX 格式）
- 支持 AES 解密 CustomEmotion 目录下的表情
- 导出为标准 PNG/GIF 格式
- 提供图形界面 (GUI) 和命令行 (CLI) 两种使用方式
- 可选：通过浏览器自动化导入飞书（实验性功能）

## 安装

```bash
pip install -r requirements.txt
```

如需使用飞书导入功能，还需安装 Playwright：

```bash
pip install playwright
python -m playwright install chromium
```

## 使用

### 图形界面（推荐）

```bash
python main.py
```

### 命令行

```bash
# 提取微信表情
python main.py --cli extract

# 提取指定微信账号的表情
python main.py --cli extract --wxid <wxid>

# 审计环境
python main.py --cli audit
```

### 导出位置

表情默认导出到 `output/emojis/` 目录。

## 项目结构

```
├── main.py              # 主入口
├── gui.py               # GUI 界面 (PyWebView)
├── config.py            # 配置文件
├── wechat_extractor.py  # 微信表情提取核心模块
├── key_extractor.py     # 微信数据库密钥提取
├── feishu_uploader.py   # 飞书上传模块（实验性）
├── web/
│   └── index.html       # GUI 前端页面
└── requirements.txt     # Python 依赖
```

## 技术原理

1. 定位微信数据目录下的 `emoticon.db`（SQLite 数据库）
2. 通过微信进程内存提取数据库解密密钥
3. 使用 SQLCipher 解密数据库，读取表情记录
4. 对于 V1MMWX 加密格式，使用 AES-CBC 解密
5. 将解密后的二进制数据转换为 PNG/GIF 图片

## 注意事项

- 需要在 Windows 系统上运行
- 提取表情时需要微信客户端正在运行（用于获取解密密钥）
- 本工具仅用于个人数据备份，请勿用于其他用途

## License

MIT
