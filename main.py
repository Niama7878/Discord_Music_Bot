import os
import re
import shutil
import discord
import subprocess
from pytubefix import YouTube
from discord.ext import commands
from pytubefix.cli import on_progress

# 设置Discord客户端和机器人命令前缀
intents = discord.Intents.all()
music_bot = commands.Bot(command_prefix = "/", intents = intents)

current_volume = 0.5 # 默认音量设置为50%

# 全局变量
music_queue = []  # 歌曲队列
current_music_index = 0  # 当前播放音乐的索引
voice_client = None  # 声音客户端（会在每次播放时更新）

# 检查语音频道状态
async def check_voice_channel(ctx, voice_client):
    # 如果用户不在语音频道
    if not ctx.author.voice:
        await ctx.send(f"```{ctx.author.name}, 你不在语音频道，请先进入语音频道再使用此命令!```")
        return False

    # 如果机器人不在语音频道
    if not voice_client:
        await ctx.send(f"```{ctx.author.name}, 我当前不在语音频道，请使用 /join 让我先加入语音频道!```")
        return False
    
    return True

def process_video(url, output_path, temp_suffix="_temp.mp3", final_suffix=".mp3"):
    """
    处理 YouTube 视频，下载音频流并生成文件路径
    :param url: YouTube 视频链接
    :param output_path: 音频保存路径
    :param temp_suffix: 临时文件后缀
    :param final_suffix: 最终文件后缀
    :return: 视频标题、临时文件路径、最终文件路径
    """
    video = YouTube(url, on_progress_callback=on_progress)
    stream = video.streams.filter(only_audio=True).first()
    filename = re.sub(r'[^\w\u4e00-\u9fa5]', '_', video.title).replace(' ', '')
    
    temp_output_file = f"{output_path}/{filename}{temp_suffix}"
    final_output_file = f"{output_path}/{filename}{final_suffix}"
    
    return filename, stream, temp_output_file, final_output_file

# 播放音乐的函数
async def play_audio(ctx):
    global current_music_index, music_queue, voice_client

    if len(music_queue) == 0:
        await ctx.send(f"```{ctx.author.name}, 没有更多的音乐可以播放!```")
        return

    # 获取当前音乐文件
    music = music_queue[current_music_index]
    source = discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=music)
    source = discord.PCMVolumeTransformer(source, volume=current_volume)
    
    # 播放音频，并设置播放完成后的回调
    voice_client.play(source, after=lambda e: on_song_end(ctx, e))

# 播放完成后的回调函数
async def on_song_end(ctx):
    global current_music_index, voice_client

    # 播放下一首歌曲
    if current_music_index < len(music_queue) - 1:
        current_music_index += 1  # 更新为下一首歌曲的索引
        await play_audio(ctx)
    else:
        # 如果播放完所有歌曲，重新从头播放
        current_music_index = 0
        await play_audio(ctx)
        await ctx.send(f"```{ctx.author.name}, 单曲播放已结束，正在重新从头播放!```")
        
# 加入语音频道命令
@music_bot.command(name="join")
async def join(ctx):
    # 如果用户不在语音频道
    if not ctx.author.voice:
        await ctx.send(f"```{ctx.author.name}, 你不在语音频道，请先进入语音频道再使用此命令!```")
        return

    channel = ctx.author.voice.channel
    voice_client = ctx.voice_client # 获取当前语音频道的客户端

    # 如果机器人已经在语音频道，移动到当前频道
    if voice_client and voice_client.is_connected():
        await voice_client.move_to(channel)
    else:
        voice_client = await channel.connect()

    await ctx.send(f"```{ctx.author.name}, 我已加入语音频道!```")
        
# 离开语音频道命令
@music_bot.command(name="leave")
async def leave(ctx):
    voice_client = ctx.voice_client # 获取当前语音频道的客户端

    # 检查机器人是否在语音频道
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send(f"```{ctx.author.name}, 我已离开语音频道。```")
    else:
        await ctx.send(f"```{ctx.author.name}, 我当前不在语音频道。```")
  
# 设置音量命令
@music_bot.command(name="volume")
async def volume(ctx, new_volume):
    global current_volume

    voice_client = ctx.guild.voice_client # 获取当前语音频道的客户端

    if not await check_voice_channel(ctx, voice_client):
        return
    
    # 检查是否正在播放音乐
    if not voice_client.is_paused() and not voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 我没有在播放音乐，请使用 /play 命令开始播放!```")
        return
    
    try:
        # 设置音量，确保在有效范围内
        if 0 <= int(new_volume) <= 100:
            current_volume = int(new_volume) / 100 
            voice_client.source.volume = current_volume 
            await ctx.send(f"```音量已设置为 {new_volume}%```")

        else:
            await ctx.send(f"```{ctx.author.name}, 音量无效, 请输入一个0到100之间的值。```")

    except:
        await ctx.send(f"```{ctx.author.name}, 请确保输入的是有效的数字!```")

# 播放YouTube视频音频命令
@music_bot.command(name="play")
async def play(ctx, url):
    global current_music_index, music_queue, voice_client
    voice_client = ctx.guild.voice_client # 获取当前语音频道的客户端

    if not await check_voice_channel(ctx, voice_client):
        return
    
    # 如果音乐在播放或暂停
    if voice_client.is_paused() or voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 命令停止当前音乐后再使用此命令!```")
        return

    await ctx.send(f"```{ctx.author.name}, 请稍等片刻...```")

    try:
        output_path = "music"
        filename, stream, temp_output_file, final_output_file = process_video(url, output_path)

        # 检查文件是否已经存在
        if os.path.exists(final_output_file):
            await ctx.send(f"```{ctx.author.name}, {filename} 已存在!```")
            
        else:
            # 下载视频并转换为音频文件
            stream.download(output_path=output_path, filename=os.path.basename(temp_output_file))

            ffmpeg_command = [
                'ffmpeg',
                '-y', 
                '-i', temp_output_file,
                '-acodec', 'libmp3lame',
                '-q:a', '2',
                final_output_file
            ]

            subprocess.run(ffmpeg_command, check=True)
            os.remove(temp_output_file)

        music_queue.append(final_output_file)
        current_music_index = len(music_queue) - 1  # 更新当前播放的音乐索引

    except:
        await ctx.send(f"```{ctx.author.name}, 请确保输入的是有效的YouTube视频链接!```")
        return

    # 开始播放音乐
    if not voice_client.is_playing():
        await play_audio(ctx)

    await ctx.send(f"```{ctx.author.name}, 正在播放: {filename}```")

# 暂停播放音乐命令
@music_bot.command(name="pause")
async def pause(ctx):
    voice_client = ctx.guild.voice_client # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    # 如果音乐正在播放
    if voice_client and voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 正在暂停音乐，你可以使用 /resume 命令恢复!```")
        voice_client.pause()
    else:
        await ctx.send(f"```{ctx.author.name}, 请确保我在语音频道并且正在播放音乐!```")
  
# 恢复播放音乐命令  
@music_bot.command(name="resume")
async def resume(ctx):
    voice_client = ctx.guild.voice_client # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    # 如果音乐已暂停
    if voice_client and voice_client.is_paused():
        await ctx.send(f"```{ctx.author.name}, 正在恢复音乐播放!```")
        voice_client.resume()
    else:
        await ctx.send(f"```{ctx.author.name}, 请确保我在语音频道并且音乐是暂停状态!```")

# 停止播放音乐命令
@music_bot.command(name="stop")
async def stop(ctx):
    global music_queue, current_music_index
    voice_client = ctx.guild.voice_client # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    # 如果音乐在播放或已暂停
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        await ctx.send(f"```{ctx.author.name}, 正在停止音乐，你可以使用 /play 或 /play_playlist 命令播放新音乐!```")
        await voice_client.disconnect()
        await ctx.author.voice.channel.connect()

        # 清空音乐队列并重置索引
        music_queue = []
        current_music_index = 0
    else:
        await ctx.send(f"```{ctx.author.name}, 请确保我在语音频道并且音乐是播放或暂停状态!```")

# 创建播放列表命令
@music_bot.command(name="playlist")
async def playlist(ctx, foldername, *url_list):
    if os.path.exists(f"music/{foldername}") and os.path.isdir(f"music/{foldername}"):
        await ctx.send(f"```{ctx.author.name}, {foldername} 播放列表已经存在。```")
    else:
        os.mkdir(f"music/{foldername}")
        await ctx.send(f"```{ctx.author.name}, {foldername} 播放列表创建成功!```")

    foldername = f"music/{foldername}"
    
    # 遍历url_list并下载每个视频
    for url in url_list:
        try:
            filename, stream, temp_output_file, final_output_file = process_video(url, foldername)

            if os.path.exists(final_output_file):
                await ctx.send(f"```{ctx.author.name}, {filename} 已在 {foldername} 播放列表中！```")
            
            else:
                stream.download(output_path=foldername, filename=os.path.basename(temp_output_file))

                ffmpeg_command = [
                    'ffmpeg',
                    '-y', 
                    '-i', temp_output_file,
                    '-acodec', 'libmp3lame',
                    '-q:a', '2',
                    final_output_file
                ]

                subprocess.run(ffmpeg_command, check=True)
                os.remove(temp_output_file)

                await ctx.send(f"```{ctx.author.name}, {filename} 已添加到 {foldername} 播放列表！```")

        except:
            await ctx.send(f"```{ctx.author.name}, 处理 {url} 时发生错误，请检查链接是否有效。```")

# 播放列表命令
@music_bot.command(name="play_playlist")
async def play_playlist(ctx, playlist):
    global current_music_index, music_queue, voice_client
    # 检查播放列表是否存在
    if os.path.exists(f"music/{playlist}") and os.path.isdir(f"music/{playlist}"):
        music_list = os.listdir(f"music/{playlist}")
        music_queue.extend([f"music/{playlist}/{music}" for music in music_list])  # 添加所有音乐到队列
        current_music_index = 0  # 从列表的第一首开始播放

        voice_client = ctx.guild.voice_client

        if not await check_voice_channel(ctx, voice_client):
            return

        if voice_client.is_paused() or voice_client.is_playing():
            await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 停止音乐，然后再使用此命令!```")
            return

        music_queue.clear()  # 清空音乐队列
        for music in music_list:
            music_queue.append(f"music/{playlist}/{music}")  # 添加播放列表中的音乐文件到队列

        current_music_index = 0  # 设置为播放列表的第一首音乐

        # 开始播放音乐
        if not voice_client.is_playing():
            await play_audio(ctx)

        current_music = music_queue[current_music_index].split('/')[-1]  # 获取音乐文件名

        await ctx.send(f"```{ctx.author.name}, 正在播放播放列表: {playlist}, {current_music}```")

    else:
        await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表不存在!```")

# 上一首命令
@music_bot.command(name="previous")
async def previous(ctx):
    global current_music_index

    voice_client = ctx.guild.voice_client # 获取当前语音频道的客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    if voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /pause 暂停音乐，然后再使用此命令!```")
        return

    if current_music_index > 0:
        current_music_index -= 1
        current_music = music_queue[current_music_index].split('/')[-1]  # 获取音乐文件名
        await ctx.send(f"```{ctx.author.name}, 正在播放上一首歌曲 : {current_music}```")
        await play_audio(ctx)
    else:
        await ctx.send(f"```{ctx.author.name}, 当前已经是第一首歌曲了!```")

# 下一首命令
@music_bot.command(name="next")
async def next(ctx):
    global current_music_index

    voice_client = ctx.guild.voice_client # 获取当前语音频道的客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    if voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /pause 暂停音乐，然后再使用此命令!```")
        return

    if current_music_index < len(music_queue) - 1:
        current_music_index += 1
        current_music = music_queue[current_music_index].split('/')[-1]  # 获取音乐文件名
        await ctx.send(f"```{ctx.author.name}, 正在播放下一首歌曲: {current_music}```")
        await play_audio(ctx)
    else:
        await ctx.send(f"```{ctx.author.name}, 当前已经是最后一首歌曲了!```")

# 查看所有文件命令
@music_bot.command(name="view_all")
async def view_all(ctx):
    # 列出所有文件和文件夹的函数
    async def list_files_and_folders(path):
        items = os.listdir(path) # 获取目录中的所有项目
        
        # 如果目录为空
        if len(items) == 0:
            await ctx.send(f"```{ctx.author.name}, 音乐和播放列表为空!```")
            return
        
        else:
            for item in items:
                item_path = os.path.join(path, item)

                # 如果是目录，则显示播放列表内容
                if os.path.isdir(item_path):
                    await ctx.send(f"```{item} 播放列表:```")
                    await list_files_and_folders(item_path)
                    
                else:
                    # 如果是音乐文件，显示音乐名称
                    folder_content = re.sub(r'\.mp3$', '', item)
                    await ctx.send(f"```{folder_content}```")

    # 从根目录开始列出所有音乐和播放列表
    await list_files_and_folders("music")

# 删除播放列表命令
@music_bot.command(name="delete_playlist")
async def delete_playlist(ctx, *playlist_list):
    voice_client = ctx.guild.voice_client # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    # 如果正在播放或暂停播放，要求先停止音乐
    if voice_client.is_paused() or voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 停止音乐，然后再使用此命令!```")
        return
    
    # 删除指定的播放列表
    for playlist in playlist_list:
        if os.path.exists(f"music/{playlist}") and os.path.isdir(f"music/{playlist}"):
            shutil.rmtree(f"music/{playlist}") # 删除目录
            await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表删除成功!```")

        else:
            await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表不存在!```")

# 删除播放列表音乐命令
@music_bot.command(name="delete_playlist_music")
async def delete_playlist_music(ctx, playlist, *music_list):
    voice_client = ctx.guild.voice_client # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return
    
    # 如果正在播放或暂停播放，要求先停止音乐
    if voice_client.is_paused() or voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 停止音乐，然后再使用此命令!```")
        return
    
    # 删除指定播放列表中的音乐
    if os.path.exists(f"music/{playlist}") and os.path.isdir(f"music/{playlist}"):
        for music in music_list:
            if os.path.exists(f"music/{playlist}/{music}.mp3"):
                os.remove(f"music/{playlist}/{music}.mp3") # 删除指定的音乐文件
                await ctx.send(f"```{ctx.author.name}, {music} 已成功从 {playlist} 播放列表中删除!```")

            else:
                await ctx.send(f"```{ctx.author.name}, {music} 在 {playlist} 播放列表中不存在!```")
       
    else:
        await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表不存在!```")

# 删除音乐命令
@music_bot.command(name="delete_music")
async def delete_music(ctx, *music_list):
    voice_client = ctx.guild.voice_client # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    # 如果正在播放或暂停播放，要求先停止音乐
    if voice_client.is_paused() or voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 停止音乐，然后再使用此命令!```")
        return
    
    # 删除指定的音乐文件
    for music in music_list:
        if os.path.exists(f"music/{music}.mp3") and not os.path.isdir(f"music/{music}.mp3"):
            os.remove(f"music/{music}.mp3") # 删除音乐文件
            await ctx.send(f"```{ctx.author.name}, {music} 已成功删除!```")

        else:
            await ctx.send(f"```{ctx.author.name}, {music} 不存在!```")

# 帮助命令
@music_bot.tree.command(name="help", description="显示所有指令")
async def help(user):
    help_message = """```
我的命令：
- /join (让我加入语音频道)
- /play YouTubeLink (播放音乐)
- /playlist playlistname YouTubeLink... (创建并添加音乐到播放列表)
- /play_playlist playlistname (播放播放列表中的音乐)
- /view_all (查看所有播放列表和音乐)
- /volume 0-100 (控制音乐音量)
- /pause (暂停音乐)
- /resume (恢复音乐)
- /stop (停止音乐，之后可以使用 /play 或 /play_playlist 命令播放新音乐)
- /leave (让我离开语音频道)
- /delete_playlist playlistname... (删除播放列表)
- /delete_playlist_music playlistname music... (从播放列表中删除音乐)
- /delete_music music... (删除单独的音乐曲目)
- /previous (播放上一首音乐*需先暂停音乐)
- /next (播放下一首音乐*需先暂停音乐)
```"""
    await user.response.send_message(help_message)

# 启动机器人
@music_bot.event
async def on_ready():
    print(f'已经成功连接到 Discord! 登录为 {music_bot.user}')
    await music_bot.tree.sync()

# 运行机器人
music_bot.run("")