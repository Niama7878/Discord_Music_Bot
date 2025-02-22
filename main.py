import os
import re
import shutil
import discord
import yt_dlp
from discord.ext import commands
import asyncio

# 设置Discord客户端和机器人命令前缀
intents = discord.Intents.all()
music_bot = commands.Bot(command_prefix = "/", intents = intents)

current_volume = 0.5 # 默认音量设置为50%

# 全局变量
music_queue = []  # 歌曲队列
current_music_index = 0  # 当前播放音乐的索引
voice_client = None  # 声音客户端（会在每次播放时更新）
music_stopped = False  # 用于检查音乐是否已停止

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

def process_video(url, output_path):
    try:
        # 处理URL，提取视频ID
        def clean_url(url):
            # 如果URL包含'='，提取视频ID
            if '=' in url:
                video_id = url.split('=')[-1].split('&')[0]  # 处理可能的额外参数
                return f"https://youtu.be/{video_id}"
            # 如果URL不包含'='，可能是短链接格式，直接移除查询参数
            return url.split('?')[0]
        
        cleaned_url = clean_url(url)
        
        # 先用临时选项获取视频信息
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(cleaned_url, download=False)
            if not info:
                raise ValueError("无法获取视频信息")
            
            # 获取标题并处理文件名
            title = info.get('title', '')
            if not title:
                raise ValueError("无法获取视频标题")
                
            filename = re.sub(r'[^\w\u4e00-\u9fa5]', '_', title).replace(' ', '')
            final_output_file = f"{output_path}/{filename}.mp3"
            
            # 检查文件是否已存在
            if os.path.exists(final_output_file):
                return filename, final_output_file, "exists"
            
            # 如果文件不存在，设置下载选项
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
                'outtmpl': final_output_file[:-4],  # 移除.mp3后缀，yt-dlp会自动添加
            }
            
            # 下载文件
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([cleaned_url])
            
            return filename, final_output_file, "downloaded"
            
    except Exception as e:
        print(f"下载出错: {str(e)}")
        raise

# 确保使用 bot 的事件循环
def get_bot_event_loop(ctx):
    try:
        return ctx.bot.loop  # 优先使用 bot 的主循环
    except AttributeError:
        return asyncio.get_event_loop()

# 播放音乐函数
async def play_audio(ctx):
    global current_music_index, music_queue, voice_client, music_stopped

    if not music_queue:
        await ctx.send(f"```{ctx.author.name}, 没有更多的音乐可以播放!```")
        return

    # 获取当前音乐文件
    music = music_queue[current_music_index]
    source = discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=music)
    source = discord.PCMVolumeTransformer(source, volume=current_volume)

    # 确保 after 只传递 error 参数
    voice_client.play(source, after=lambda error: sync_on_song_end(ctx, error))

    # 恢复自动播放功能
    music_stopped = False  # 播放音乐后，允许自动播放下一首

# 同步函数调用协程
def sync_on_song_end(ctx, error):
    loop = get_bot_event_loop(ctx)

    if loop.is_running():
        asyncio.run_coroutine_threadsafe(on_song_end(ctx, error), loop)
    else:
        loop.run_until_complete(on_song_end(ctx, error))

# 播放完成后的回调函数
async def on_song_end(ctx, error):
    global current_music_index, voice_client, music_stopped

    if error:
        await ctx.send(f"```播放过程中发生错误: {error}```")
        return

    # 只有当 music_stopped 为 False 时，才会自动播放下一首
    if music_stopped:  
        return  # 如果音乐被停止，则不自动播放

    # 自动播放下一首
    if current_music_index < len(music_queue) - 1:
        current_music_index += 1  # 更新索引
        await ctx.send(f"```{ctx.author.name}, 正在播放下一首音乐 : {music_queue[current_music_index].split('/')[-1]}```")
    else:
        # 播放完列表，重新开始
        current_music_index = 0
        await ctx.send(f"```{ctx.author.name}, 播放列表已结束，正在重新播放!```")

    await play_audio(ctx)

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
    voice_client = ctx.guild.voice_client

    if not await check_voice_channel(ctx, voice_client):
        return
    
    if voice_client.is_paused() or voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 命令停止当前音乐后再使用此命令!```")
        return

    await ctx.send(f"```{ctx.author.name}, 请稍等片刻...```")

    try:
        output_path = "music"
        filename, final_output_file, status = process_video(url, output_path)
        
        music_queue.append(final_output_file)
        current_music_index = len(music_queue) - 1

        if status == "exists":
            await ctx.send(f"```{ctx.author.name}, 音乐文件已存在，无需重新下载```")
        else:
            await ctx.send(f"```{ctx.author.name}, 下载完成```")

    except Exception as e:
        await ctx.send(f"```{ctx.author.name}, 下载失败: {str(e)}```")
        return

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
    global music_queue, current_music_index, music_stopped
    voice_client = ctx.guild.voice_client  # 获取语音客户端

    if not await check_voice_channel(ctx, voice_client):
        return

    if voice_client.is_playing() or voice_client.is_paused():
        await ctx.send(f"```{ctx.author.name}, 正在停止音乐，你可以使用 /play 或 /play_playlist 命令播放新音乐!```")

        music_stopped = True  # 防止触发 on_song_end 误触发
        voice_client.stop()   # 停止音乐，但不离开语音频道

        # 清空音乐队列并重置索引
        music_queue = []
        current_music_index = 0

        # 此时不重置 music_stopped，保持 True 直到播放重新开始
    else:
        await ctx.send(f"```{ctx.author.name}, 目前没有播放中的音乐!```")

# 创建播放列表命令
@music_bot.command(name="playlist")
async def playlist(ctx, foldername, *url_list):
    if os.path.exists(f"music/{foldername}") and os.path.isdir(f"music/{foldername}"):
        await ctx.send(f"```{ctx.author.name}, {foldername} 播放列表已经存在。```")
    else:
        os.mkdir(f"music/{foldername}")
        await ctx.send(f"```{ctx.author.name}, {foldername} 播放列表创建成功!```")

    foldername = f"music/{foldername}"
    
    for url in url_list:
        try:
            filename, final_output_file, status = process_video(url, foldername)
            if status == "exists":
                await ctx.send(f"```{ctx.author.name}, {filename} 已存在于 {foldername} 播放列表中```")
            else:
                await ctx.send(f"```{ctx.author.name}, {filename} 已添加到 {foldername} 播放列表！```")
        except Exception as e:
            await ctx.send(f"```{ctx.author.name}, 处理 {url} 时发生错误: {str(e)}```")

# 播放列表命令
@music_bot.command(name="play_playlist")
async def play_playlist(ctx, playlist):
    global current_music_index, music_queue, voice_client
    
    # 检查播放列表是否存在
    if not (os.path.exists(f"music/{playlist}") and os.path.isdir(f"music/{playlist}")):
        await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表不存在!```")
        return

    voice_client = ctx.guild.voice_client
    if not await check_voice_channel(ctx, voice_client):
        return

    if voice_client.is_paused() or voice_client.is_playing():
        await ctx.send(f"```{ctx.author.name}, 请先使用 /stop 停止音乐，然后再使用此命令!```")
        return

    # 获取播放列表中的所有音乐
    music_list = os.listdir(f"music/{playlist}")
    
    # 清空并重新添加音乐队列
    music_queue.clear()
    music_queue.extend([f"music/{playlist}/{music}" for music in music_list])
    
    # 设置为播放列表的第一首音乐
    current_music_index = 0

    # 开始播放音乐
    if not voice_client.is_playing():
        await play_audio(ctx)

    current_music = music_queue[current_music_index].split('/')[-1]
    await ctx.send(f"```{ctx.author.name}, 正在播放播放列表: {playlist}, {current_music}```")

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
    async def list_files_and_folders(path, indent=""):
        items = os.listdir(path)
        
        if len(items) == 0:
            await ctx.send(f"```{ctx.author.name}, 音乐和播放列表为空!```")
            return
        
        # 分离文件夹和文件
        folders = []
        files = []
        for item in items:
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                folders.append(item)
            else:
                files.append(item)
                
        # 先处理播放列表（文件夹）
        for folder in folders:
            folder_path = os.path.join(path, folder)
            await ctx.send(f"```{folder} 播放列表:```")
            # 递归处理播放列表内的文件，增加缩进
            folder_items = os.listdir(folder_path)
            for item in folder_items:
                if item.endswith('.mp3'):
                    music_name = re.sub(r'\.mp3$', '', item)
                    await ctx.send(f"```  {music_name}```")
        
        # 再处理非播放列表的音乐文件
        if files and path == "music":  # 只在根目录显示"单曲:"
            await ctx.send("```单曲:```")
            for file in files:
                if file.endswith('.mp3'):
                    music_name = re.sub(r'\.mp3$', '', file)
                    await ctx.send(f"```{music_name}```")

    # 从根目录开始列出所有音乐和播放列表
    await list_files_and_folders("music")

# 删除播放列表命令
@music_bot.command(name="delete_playlist")
async def delete_playlist(ctx, playlist):
    global voice_client, music_queue, current_music_index
    
    # 检查播放列表是否存在
    if not (os.path.exists(f"music/{playlist}") and os.path.isdir(f"music/{playlist}")):
        await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表不存在!```")
        return

    # 如果正在播放，先停止
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        music_queue.clear()
        current_music_index = 0
        await ctx.send(f"```{ctx.author.name}, 已停止当前播放的音乐```")

    try:
        # 删除播放列表文件夹及其内容
        shutil.rmtree(f"music/{playlist}")
        await ctx.send(f"```{ctx.author.name}, {playlist} 播放列表已删除!```")
    except Exception as e:
        await ctx.send(f"```{ctx.author.name}, 删除 {playlist} 播放列表时发生错误: {str(e)}```")

@music_bot.command(name="delete_playlist_music")
async def delete_playlist_music(ctx, playlist, music_name):
    global voice_client, music_queue, current_music_index
    
    # 检查播放列表和音乐文件是否存在
    music_path = f"music/{playlist}/{music_name}.mp3"
    if not os.path.exists(music_path):
        await ctx.send(f"```{ctx.author.name}, 在 {playlist} 播放列表中未找到 {music_name}!```")
        return

    # 如果正在播放这首歌，先停止
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        current_music = music_queue[current_music_index]
        if current_music == music_path:
            voice_client.stop()
            music_queue.clear()
            current_music_index = 0
            await ctx.send(f"```{ctx.author.name}, 已停止当前播放的音乐```")

    try:
        # 删除音乐文件
        os.remove(music_path)
        await ctx.send(f"```{ctx.author.name}, 已从 {playlist} 播放列表中删除 {music_name}!```")
    except Exception as e:
        await ctx.send(f"```{ctx.author.name}, 删除音乐文件时发生错误: {str(e)}```")

@music_bot.command(name="delete_music")
async def delete_music(ctx, music_name):
    global voice_client, music_queue, current_music_index
    
    # 检查音乐文件是否存在
    music_path = f"music/{music_name}.mp3"
    if not os.path.exists(music_path):
        await ctx.send(f"```{ctx.author.name}, 未找到 {music_name}!```")
        return

    # 如果正在播放这首歌，先停止
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        current_music = music_queue[current_music_index]
        if current_music == music_path:
            voice_client.stop()
            music_queue.clear()
            current_music_index = 0
            await ctx.send(f"```{ctx.author.name}, 已停止当前播放的音乐```")

    try:
        # 删除音乐文件
        os.remove(music_path)
        await ctx.send(f"```{ctx.author.name}, 已删除 {music_name}!```")
    except Exception as e:
        await ctx.send(f"```{ctx.author.name}, 删除音乐文件时发生错误: {str(e)}```")

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
music_bot.run("TOKEN")