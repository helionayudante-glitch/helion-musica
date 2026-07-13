# ============================================================
#  RADIO HELION — Sistema de música para el bot @helion
#  De Javi "Lobito" para Rafalillo, con el sello de la casa:
#  todo local, sin nubes, sin terceros, sin cuotas.
#
#  "Lo que crees, creas. Nunca te rindas: lo imposible solo
#   tarda un poco más. Y si arriesgas, ganas siempre."
# ============================================================
#  Cómo engancharlo a tu bot (ver README_MUSICA.md):
#    await bot.load_extension("musica")
#  Requiere: discord.py[voice], yt-dlp, FFmpeg instalado.
# ============================================================

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections import deque

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

# ---------- configuración ----------
COLOR_HELION = 0x00E5FF          # cian Helion para los embeds
COLOR_FORJA = 0xFFB300           # ámbar de la forja
MAX_COLA = 50                    # canciones máximas en cola
VOTOS_SKIP = 2                   # votos necesarios para saltar (si hay >2 oyentes)

# Piper (voz de DJ) — OPCIONAL. Si no está instalado, la radio funciona
# igual pero anuncia por texto. Configúralo en .env:
#   PIPER_CMD=piper --model /ruta/a/es_ES-voz.onnx --output_file {out}
PIPER_CMD = os.getenv("PIPER_CMD", "")

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


class Cancion:
    """Una canción en la cola de la Forja."""

    def __init__(self, datos, pedida_por):
        self.titulo = datos.get("title", "Desconocida")
        self.url_stream = datos.get("url")
        self.url_web = datos.get("webpage_url", "")
        self.duracion = int(datos.get("duration") or 0)
        self.miniatura = datos.get("thumbnail", "")
        self.pedida_por = pedida_por

    @property
    def duracion_txt(self):
        if not self.duracion:
            return "—"
        m, s = divmod(self.duracion, 60)
        return f"{m}:{s:02d}"


class EstadoServidor:
    """Estado de la radio en un servidor concreto."""

    def __init__(self):
        self.cola = deque()
        self.actual = None
        self.bucle = False
        self.dj = True          # modo DJ (anuncios de Helion) activado
        self.votos_skip = set()
        self.canal_texto = None


class Musica(commands.Cog):
    """RADIO HELION — la máquina también pincha."""

    def __init__(self, bot):
        self.bot = bot
        self.estados = {}  # guild_id -> EstadoServidor

    # ---------- utilidades ----------
    def estado(self, guild_id):
        if guild_id not in self.estados:
            self.estados[guild_id] = EstadoServidor()
        return self.estados[guild_id]

    async def buscar(self, consulta):
        """Busca en YouTube (o resuelve URL) sin bloquear el bot."""
        loop = asyncio.get_running_loop()
        datos = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(consulta, download=False)
        )
        if "entries" in datos:
            datos = datos["entries"][0]
        return datos

    def _generar_anuncio_wav(self, texto):
        """Genera un wav con la voz de Helion vía Piper. None si no hay Piper."""
        if not PIPER_CMD:
            return None
        try:
            out = os.path.join(tempfile.gettempdir(), "helion_dj.wav")
            cmd = PIPER_CMD.replace("{out}", out)
            subprocess.run(
                cmd, input=texto.encode("utf-8"), shell=True,
                timeout=20, check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return out if os.path.exists(out) else None
        except Exception:
            return None

    async def _reproducir_wav(self, vc, ruta):
        """Reproduce un wav y espera a que termine."""
        fin = asyncio.Event()
        loop = asyncio.get_running_loop()
        vc.play(
            discord.FFmpegPCMAudio(ruta),
            after=lambda e: loop.call_soon_threadsafe(fin.set),
        )
        await fin.wait()

    # ---------- motor de reproducción ----------
    async def sonar_siguiente(self, guild):
        est = self.estado(guild.id)
        vc = guild.voice_client
        if vc is None:
            return

        # bucle: la actual vuelve a la cola
        if est.bucle and est.actual:
            est.cola.appendleft(est.actual)

        if not est.cola:
            est.actual = None
            if est.canal_texto:
                await est.canal_texto.send(
                    embed=discord.Embed(
                        description="🔧 La Forja se queda en silencio. "
                        "Ponme algo con **/play** cuando quieras.",
                        color=COLOR_FORJA,
                    )
                )
            return

        est.actual = est.cola.popleft()
        est.votos_skip.clear()

        # DJ Helion: anuncio con su voz (si hay Piper) antes de la canción
        if est.dj:
            anuncio = (
                f"Suena {est.actual.titulo}, "
                f"pedida por {est.actual.pedida_por}. Sube el volumen."
            )
            wav = await asyncio.get_running_loop().run_in_executor(
                None, self._generar_anuncio_wav, anuncio
            )
            if wav:
                try:
                    await self._reproducir_wav(vc, wav)
                except Exception:
                    pass

        loop = asyncio.get_running_loop()

        def despues(_error):
            asyncio.run_coroutine_threadsafe(self.sonar_siguiente(guild), loop)

        vc.play(
            discord.FFmpegPCMAudio(est.actual.url_stream, **FFMPEG_OPTS),
            after=despues,
        )

        if est.canal_texto:
            e = discord.Embed(
                title="📡 RADIO HELION — sonando ahora",
                description=f"**[{est.actual.titulo}]({est.actual.url_web})**",
                color=COLOR_HELION,
            )
            e.add_field(name="Duración", value=est.actual.duracion_txt)
            e.add_field(name="La pidió", value=est.actual.pedida_por)
            if est.actual.miniatura:
                e.set_thumbnail(url=est.actual.miniatura)
            e.set_footer(text="La Forja también tiene banda sonora.")
            await est.canal_texto.send(embed=e)

    # ---------- comandos ----------
    @app_commands.command(name="play", description="Pide una canción (nombre o URL de YouTube)")
    async def play(self, interaction: discord.Interaction, cancion: str):
        est = self.estado(interaction.guild_id)
        est.canal_texto = interaction.channel

        if interaction.user.voice is None:
            await interaction.response.send_message(
                "Entra primero a un canal de voz y te sigo hasta allí. 🔊",
                ephemeral=True,
            )
            return

        if len(est.cola) >= MAX_COLA:
            await interaction.response.send_message(
                f"La cola está a tope ({MAX_COLA}). La Forja tiene un límite. 😅",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            datos = await self.buscar(cancion)
        except Exception:
            await interaction.followup.send(
                "No he podido encontrar eso. Prueba con otro nombre o pega la URL."
            )
            return

        nueva = Cancion(datos, interaction.user.display_name)
        est.cola.append(nueva)

        vc = interaction.guild.voice_client
        if vc is None:
            vc = await interaction.user.voice.channel.connect()

        if not vc.is_playing() and not vc.is_paused() and est.actual is None:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"⚡ Encendiendo la radio con **{nueva.titulo}**...",
                    color=COLOR_HELION,
                )
            )
            await self.sonar_siguiente(interaction.guild)
        else:
            e = discord.Embed(
                description=f"➕ **{nueva.titulo}** a la cola "
                f"(posición {len(est.cola)}).",
                color=COLOR_HELION,
            )
            await interaction.followup.send(embed=e)

    @app_commands.command(name="skip", description="Vota para saltar la canción actual")
    async def skip(self, interaction: discord.Interaction):
        est = self.estado(interaction.guild_id)
        vc = interaction.guild.voice_client
        if vc is None or est.actual is None:
            await interaction.response.send_message("No suena nada ahora mismo.", ephemeral=True)
            return

        oyentes = [m for m in vc.channel.members if not m.bot]
        est.votos_skip.add(interaction.user.id)

        if len(oyentes) <= 2 or len(est.votos_skip) >= VOTOS_SKIP:
            await interaction.response.send_message("⏭️ Saltando. La Forja decide.")
            vc.stop()  # dispara sonar_siguiente por el callback
        else:
            faltan = VOTOS_SKIP - len(est.votos_skip)
            await interaction.response.send_message(
                f"🗳️ Voto registrado. Falta {faltan} voto más para saltar."
            )

    @app_commands.command(name="cola", description="Muestra la cola de la radio")
    async def cola(self, interaction: discord.Interaction):
        est = self.estado(interaction.guild_id)
        if est.actual is None and not est.cola:
            await interaction.response.send_message("La cola está vacía. Estrénala con /play.")
            return
        e = discord.Embed(title="📻 Cola de RADIO HELION", color=COLOR_HELION)
        if est.actual:
            e.add_field(
                name="▶️ Sonando",
                value=f"{est.actual.titulo} · {est.actual.duracion_txt}",
                inline=False,
            )
        if est.cola:
            lineas = [
                f"`{i+1}.` {c.titulo} · {c.duracion_txt} — {c.pedida_por}"
                for i, c in enumerate(list(est.cola)[:10])
            ]
            extra = f"\n... y {len(est.cola) - 10} más" if len(est.cola) > 10 else ""
            e.add_field(name="⏭️ Siguientes", value="\n".join(lineas) + extra, inline=False)
        if est.bucle:
            e.set_footer(text="🔁 Modo bucle activado")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="pausa", description="Pausa o reanuda la música")
    async def pausa(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.send_message("No estoy en ningún canal de voz.", ephemeral=True)
            return
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Pausado. La Forja contiene la respiración.")
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Seguimos. ¡Arriba!")
        else:
            await interaction.response.send_message("No hay nada que pausar.", ephemeral=True)

    @app_commands.command(name="bucle", description="Activa o desactiva el bucle de la canción actual")
    async def bucle(self, interaction: discord.Interaction):
        est = self.estado(interaction.guild_id)
        est.bucle = not est.bucle
        await interaction.response.send_message(
            "🔁 Bucle **activado**: esta se queda en repetición."
            if est.bucle else "➡️ Bucle **desactivado**."
        )

    @app_commands.command(name="dj", description="Activa o desactiva los anuncios de DJ Helion")
    async def dj(self, interaction: discord.Interaction):
        est = self.estado(interaction.guild_id)
        est.dj = not est.dj
        if est.dj and not PIPER_CMD:
            await interaction.response.send_message(
                "🎙️ Modo DJ activado (sin voz: configura PIPER_CMD en el .env "
                "para que Helion presente las canciones con SU voz)."
            )
        else:
            await interaction.response.send_message(
                "🎙️ Modo DJ **activado**: Helion presenta las canciones."
                if est.dj else "🔇 Modo DJ desactivado."
            )

    @app_commands.command(name="fuera", description="Vacía la cola y saca a Helion del canal de voz")
    async def fuera(self, interaction: discord.Interaction):
        est = self.estado(interaction.guild_id)
        est.cola.clear()
        est.actual = None
        est.bucle = False
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        await interaction.response.send_message(
            "👋 Radio apagada. Volveré cuando la Forja me llame."
        )

    # ---------- auto-desconexión si se queda solo ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        vc = member.guild.voice_client
        if vc and len([m for m in vc.channel.members if not m.bot]) == 0:
            await asyncio.sleep(60)
            if vc.is_connected() and len(
                [m for m in vc.channel.members if not m.bot]
            ) == 0:
                est = self.estado(member.guild.id)
                est.cola.clear()
                est.actual = None
                await vc.disconnect()


async def setup(bot):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg no está instalado o no está en el PATH. "
            "Ver README_MUSICA.md, paso 1."
        )
    await bot.add_cog(Musica(bot))
