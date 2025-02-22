# Discord 音乐机器人

这是一个 Discord 音乐机器人，使用 Python 和 `discord.py` 库实现，支持在 Discord 语音频道播放音乐，管理播放列表和音乐文件。

## 功能

- **播放音乐**：通过 `/play YouTubeLink` 播放单曲。
- **播放播放列表**：通过 `/play_playlist playlistname` 播放指定播放列表中的所有音乐。
- **管理播放列表**：
  - 创建并添加音乐到播放列表。
  - 删除播放列表和播放列表中的音乐。
  - 查看所有播放列表和音乐。
- **音乐控制**：
  - 播放上一首 `/previous`。
  - 播放下一首 `/next`。
  - 暂停和恢复音乐 `/pause`, `/resume`。
  - 停止当前播放 `/stop`。
- **音量控制**：通过 `/volume 0-100` 设置音乐音量。

## 安装

1. 需要安装的库：

   ```bash
   pip install discord.py pynacl yt-dlp

## 使用教程

[YouTube](https://youtu.be/kra8P4W97So) [Bilibili](https://www.bilibili.com/video/BV1EfkDY9EgL)