import os
from os import path
import discord
import asyncio
import random
from random import shuffle
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord.utils import get
from youtube_dl import YoutubeDL

class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""

client = commands.Bot(command_prefix='!')
class ytdl():
    youtube_dl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
    }
    ydl=YoutubeDL(youtube_dl_opts)
    def __init__(self,*,data:dict):
        self.data=data
        self.title=data.get('title')
        self.url=data.get('url')
        self.weburl=data.get('webpage_url')
        self.duration=self.parse_duration(int(data.get('duration')))
    @classmethod
    def create_source(cls,info):
        try:
            s=cls.ydl.extract_info(info,download=False)
            return cls(data=s)
        except TypeError:
            ctx.send("enter a valid url")
    @staticmethod
    def parse_duration(duration:int):
        try:
            minutes,seconds=divmod(duration,60)
            hours,minutes=divmod(minutes,60)
            duration=[]
            if hours>0:
                duration.append(f'{hours_02d}')
            if minutes>0:
                duration.append(f'{minutes:02d}')
            if seconds>0:
                duration.append(f'{seconds:02d}')
            return ':'.join(duration)
        except TypeError:
            print("enter a valid url")

@client.event
async def on_ready():
    print('client ready')

@client.event
async def on_guild_join(guild):
    general = guild.text_channels[0]
    em=discord.Embed(title="Thanks for adding me to your server! :blush: ",description="To get started, join a voice channel and use '!play' a song.Feel the music in the AIR",colour=0x7289da)
    if general and general.permissions_for(guild.me).send_messages:
        await general.send(embed=em)

class Voicestate:
    def __init__(self,ctx):
        self.client=client
        self.channel=ctx.channel
        self.guild=ctx.guild
        self.current=None
        self.queue = asyncio.Queue()
        self.play_next_song = asyncio.Event()
        client.loop.create_task(self.audio_player_task())
    async def audio_player_task(self):
            while True:
                self.play_next_song.clear()
                self.current = await self.queue.get()
                song=discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.current.url,before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                options='-vn',))
                self.guild.voice_client.play(song,after=self.toggle_next)
                em=discord.Embed(title='Now Playing :',description=f'[{self.current.title}]({self.current.weburl})',colour=0x7289da)
                await self.channel.send(embed=em)
                await self.play_next_song.wait()


    def toggle_next(self,error):
            try:
                client.loop.call_soon_threadsafe(self.play_next_song.set)
            except Exception as e:
                print(e)


class Music(commands.Cog):
    def __init__(self,client):
        self.client=client
        self.players = {}

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = Voicestate(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error,commands.CommandNotFound):
            await ctx.send("```css\nInvalid Command. Please use '!help' for valid commands!\n```")
        elif isinstance(error,commands.MissingRequiredArgument):
            if error.param.name == 'url':
                await ctx.send("```css\nPlease provide url or youtube link!\n```")
        elif isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
            except:
                pass
        elif isinstance(error,commands.ArgumentParsingError):
            await ctx.send("```css\nPlease provide a valid object!\n```")

    @commands.command(aliases=['connect'],help="Joins the users channel")
    async def join(self,ctx, channel: discord.VoiceChannel=None):
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel('```css\nNo channel to join. Please either specify a valid channel or join one.\n```')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'```css\nMoving to channel: <{channel}> timed out.\n```')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'```css\nConnecting to channel: <{channel}> timed out.\n```')

        await ctx.send(f'```css\nConnected to: {channel}\n```', delete_after=20)

    @commands.command(help="Leaves the channel")
    async def leave(self,ctx):
        vc=ctx.voice_client
        await ctx.voice_client.disconnect()

    @commands.command(aliases=['p'],help="Add a song to the queue(youtube link).")
    async def play(self,ctx, url):
        await ctx.trigger_typing()
        vc = ctx.voice_client
        if not vc:
            await ctx.invoke(self.join)
        player=self.get_player(ctx)
        source = ytdl.create_source(url)
        if int(source.duration[0:2])>15:
                await ctx.send("```css\nCant add this song to the queue. The maximum duration of a song is 15:00. Please try to add a shorter video\n```")
        else:
            await player.queue.put(source)
            em=discord.Embed(description=f'Queued : [{source.title}]({source.weburl})',colour=0x95a5a6)
            await ctx.send(embed=em)

    @commands.command(aliases=['pa'],help="Pauses the song.")
    async def pause(self,ctx):
        vc=ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send('```css\nNo song currently playing\n```', delete_after=20)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send("```css\nSong paused\n```")

    @commands.command(aliases=['res'],help="Resumes the song.")
    async def resume(self,ctx):
        vc=ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("```css\nResumed song\n```",delete_after=20)
        else:
            await ctx.send("```css\nSong not paused resume failed\n```",delete_after=20)

    @commands.command(aliases=['sk'],help="Skips the current song.")
    async def skip(self,ctx):
        vc=ctx.voice_client
        player=self.get_player(ctx)
        if (vc and vc.is_playing()):
            if player.queue.qsize()>0:
                vc.stop()
                await ctx.send("```css\nSong skipped\n```",delete_after=20)
            elif player.queue.qsize() ==0:
                await ctx.send("```css\nNo song in the queue to skip.\n```",delete_after=20)
        else:
            await ctx.send("```css\nMusic not playing failed skip\n```",delete_after=20)

    @commands.command(aliases=['st'],help="Stops the music and clears the queue")
    async def stop(self,ctx):
        vc=ctx.voice_client
        player=self.get_player(ctx)
        if not (vc and vc.is_playing()):
            await ctx.send('```css\nSong not playing failed stop\n```',delete_after=20)
        else:
            player.queue._queue.clear()
            vc.stop()
            await ctx.send('```css\nSong stopped\n```')

    @commands.command(aliases=['q','queue'],help="Shows the current queue.")
    async def queues(self,ctx):
        vc=ctx.voice_client
        player=self.get_player(ctx)
        if not vc or not vc.is_connected():
            return await ctx.send('```css\nI am not currently connected to voice!\n```', delete_after=20)
        if (vc and vc.is_playing()) or vc.is_paused():
            em = discord.Embed(title=player.current.title,
                               colour=0x87CEEB)
            em.set_author(name="Playing now:")
            q_list = ""
            if len(player.queue._queue) > 0:
                for index, song in enumerate(player.queue._queue,start=1):
                    if index > 0:
                        q_list += str(index) + ". " + f"{(song.title[:32]+'...') if len(song.title)>35 else (song.title.ljust(35))} {song.duration}\n"
                    if index >10:
                        if len(player.queue._queue) > 10:
                            q_list += "*[" + str(len(player.queue._queue) - 10) + " more songs...]*"
                        break
                em.add_field(name="Queued:", value=q_list, inline=False)
            else:
                em.add_field(name="Queued:", value=" - ", inline=False)
            await ctx.send(embed=em)
        else:
            await ctx.send("```css\nNo song playing nor queued\n```")
    @commands.command(aliases=['sh','random'],help="Shuffles the song.")
    async def shuffle(self,ctx):
        player=self.get_player(ctx)
        if player.queue.empty():
            await ctx.send("```css\nQueue Empty\n```",delete_after=20)
        else:
            random.shuffle(player.queue._queue)
            await ctx.send("```css\nSongs shuffled\n```",delete_after=20)

client.add_cog(Music(client))

client.run("token")
