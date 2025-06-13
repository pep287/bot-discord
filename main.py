# Bibliotecas
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import time
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Configuração do bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

# Variáveis globais
music_queues = {}
current_tracks = {}
# classe da Queue
class QueuePaginator(discord.ui.View):
    def __init__(self, ctx, queue, per_page=10):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.queue = queue
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = (len(queue) - 1) // per_page + 1

    def get_page_content(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.queue[start:end]
        description = ""
        for i, (_, title) in enumerate(page_items, start=start + 1):
            description += f"**{i}.** {title}\n"
        return description

    async def update_message(self, interaction):
        embed = discord.Embed(
            title=f"Fila de reprodução — Página {self.current_page + 1}/{self.total_pages}",
            description=self.get_page_content(),
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Apenas quem pediu pode usar os botões!", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Apenas quem pediu pode usar os botões!", ephemeral=True)
            return
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

# Funções auxiliares
def get_queue(ctx):
    return music_queues.setdefault(ctx.guild.id, [])

def set_current_track(ctx, title):
    current_tracks[ctx.guild.id] = title

def clear_current_track(ctx):
    current_tracks.pop(ctx.guild.id, None)

def get_current_track(ctx):
    return current_tracks.get(ctx.guild.id)

# Eventos
@bot.event
async def on_ready():
    print(f"✅ {bot.user} está online!")

# Comandos
@bot.command()
async def ping(ctx):
    start = time.perf_counter()
    message = await ctx.send("Pinging...")
    end = time.perf_counter()
    ms = (end - start) * 1000
    await message.edit(
        content=f"🏓 Pong! Latência: {int(ms)}ms | API: {round(bot.latency * 1000)}ms"
    )

@bot.command()
async def play(ctx, *, url=None):
    if url is None:
        await ctx.send("❌ Você precisa fornecer uma URL do YouTube.")
        return

    queue = get_queue(ctx)

    ydl_opts = {
        'format': 'bestaudio',
        'quiet': True,
        'extract_flat': True,  # Importante para extrair playlists rapidamente sem baixar
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            await ctx.send(f"❌ Erro ao tentar extrair info: {e}")
            return

    # Se for playlist, info terá 'entries'
    if 'entries' in info:
        count = 0
        for entry in info['entries']:
            if entry is None:
                continue
            # Pode ser necessário obter URL completo para alguns vídeos
            video_url = entry.get('url')
            title = entry.get('title', 'Música sem título')
            # URLs podem ser relativas; montar o link completo se precisar
            # Mas o ytdlp geralmente já traz o url certo na 'url'
            queue.append((video_url, title))
            count += 1
        await ctx.send(f"🎶 Playlist adicionada com {count} músicas à fila!")
    else:
        title = info.get('title', 'Música')
        queue.append((url, title))
        await ctx.send(f"🎶 Adicionado à fila: **{title}**")

    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("❌ Você precisa estar em um canal de voz.")
            return

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Pulando para a próxima música...")
    else:
        await ctx.send("❌ Não estou tocando nada no momento.")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Música pausada.")
    else:
        await ctx.send("❌ Não há música tocando para pausar.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Música retomada.")
    else:
        await ctx.send("❌ A música não está pausada.")

@bot.command()
async def queue(ctx):
    queue = get_queue(ctx)
    if not queue:
        await ctx.send("📭 A fila de reprodução está vazia.")
        return

    paginator = QueuePaginator(ctx, queue)
    embed = discord.Embed(
        title=f"Fila de reprodução — Página 1/{paginator.total_pages}",
        description=paginator.get_page_content(),
        color=discord.Color.blurple()
    )
    message = await ctx.send(embed=embed, view=paginator)
    paginator.message = message


@bot.command()
async def now(ctx):
    current = get_current_track(ctx)
    if current:
        await ctx.send(f"🎧 **Tocando agora:** {current}")
    else:
        await ctx.send("❌ Nenhuma música está tocando no momento.")

@bot.command()
async def clear(ctx):
    music_queues.pop(ctx.guild.id, None)
    await ctx.send("🗑️ Fila de reprodução limpa.")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Saí do canal de voz.")
        music_queues.pop(ctx.guild.id, None)
        clear_current_track(ctx)
    else:
        await ctx.send("❌ Não estou em um canal de voz.")

# Função principal de reprodução
async def play_next(ctx):
    queue = get_queue(ctx)
    if queue:
        url, title = queue.pop(0)
        set_current_track(ctx, title)

        ydl_opts = {'format': 'bestaudio', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)

        def after_playing(error):
            if error:
                print(f"⚠️ Erro: {error}")
            fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"⚠️ Erro no after_playing: {e}")

        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"🎧 **Tocando agora:** {title}")
    else:
        clear_current_track(ctx)
        await ctx.voice_client.disconnect()
        await ctx.send("📭 Fila vazia. Saindo do canal de voz.")

bot.run("TOKEN")
