# 📡 RADIO HELION — Sistema de música para el bot @helion

**De Javi "Lobito" para Rafalillo.** La máquina también pincha: cola de canciones,
votación para saltar, modo bucle, y el toque que no tiene nadie — **DJ Helion**,
que presenta cada canción con su propia voz (100% local con Piper, sin nubes ni cuotas).

> *"Lo que crees, creas. Nunca te rindas: lo imposible solo tarda un poco más.
> Y si arriesgas, ganas siempre."*

---

## 🚨 ANTES DE NADA: el token

1. **Regenera el token YA** en el [Discord Developer Portal](https://discord.com/developers/applications)
   → tu aplicación → *Bot* → **Reset Token**. El anterior ha circulado por chats
   y hay que darlo por quemado.
2. El token **NUNCA** se escribe en el código ni se sube a GitHub. GitHub escanea
   los repositorios y Discord **revoca automáticamente** cualquier token que
   encuentre publicado: subirlo = matar el bot al instante.
3. El token vive solo en tu fichero `.env` local (ver paso 3), y `.env` está
   en el `.gitignore` de este paquete. Así de simple y así de seguro.

---

## Instalación (15 minutos)

### 1. FFmpeg (el motor de audio)
- **Windows:** descarga el build "release essentials" desde gyan.dev o ffmpeg.org,
  descomprime y añade la carpeta `bin` al PATH. Comprueba con `ffmpeg -version`.
- **Linux:** `sudo apt install ffmpeg`

### 2. Dependencias de Python (dentro de tu venv de siempre)
```
pip install -U "discord.py[voice]" yt-dlp python-dotenv
```

### 3. El fichero `.env` (junto a tu bot)
Copia `.env.example` a `.env` y rellena:
```
DISCORD_TOKEN=tu_token_nuevo_aqui
# OPCIONAL — voz de DJ Helion con Piper (ver sección DJ):
# PIPER_CMD=piper --model /ruta/es_ES-davefx-medium.onnx --output_file {out}
```

### 4. Engancharlo a tu bot
`musica.py` va en la misma carpeta que tu bot. Tu bot debe ser un
`commands.Bot` (si ahora usas `discord.Client`, es un cambio de 3 líneas):

```python
import os, discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.load_extension("musica")   # ← RADIO HELION
    await bot.tree.sync()                # publica los comandos /
    print(f"{bot.user} en antena.")

bot.run(os.getenv("DISCORD_TOKEN"))
```

> Si tu bot ya carga extensiones en otro sitio, solo añade
> `await bot.load_extension("musica")` y el `tree.sync()`.

### 5. Permisos del bot en Discord
Al invitarlo (o en los ajustes del servidor): *Ver canales, Enviar mensajes,
Insertar enlaces, Conectar, Hablar*. Nada de administrador "por si acaso".

---

## Comandos

| Comando | Qué hace |
|---|---|
| `/play <nombre o URL>` | Busca en YouTube y la pone o la encola (máx. 50) |
| `/cola` | Muestra lo que suena y lo que viene |
| `/skip` | Vota para saltar (con 3+ oyentes hacen falta 2 votos) |
| `/pausa` | Pausa / reanuda |
| `/bucle` | Repite la canción actual |
| `/dj` | Activa/desactiva los anuncios de DJ Helion |
| `/fuera` | Vacía la cola y desconecta |

Extras que ya vienen puestos: se **desconecta solo** si se queda sin oyentes
un minuto (no gasta recursos), embeds con la estética Helion, y votación de
skip para que nadie sea el dictador de la música.

---

## 🎙️ DJ HELION — el toque que no tiene nadie

Con Piper (texto-a-voz **local y gratuito**), Helion presenta cada canción con
su propia voz antes de que suene: *"Suena Bohemian Rhapsody, pedida por Rafa.
Sube el volumen."*

1. Descarga Piper y una voz en español (por ejemplo `es_ES-davefx-medium`)
   desde el repositorio oficial de Piper en GitHub (rhasspy/piper).
2. En el `.env`: `PIPER_CMD=piper --model /ruta/a/la/voz.onnx --output_file {out}`
   (deja `{out}` tal cual: el sistema lo sustituye por el fichero temporal).
3. `/dj` para encenderlo o apagarlo. Sin Piper configurado, la radio funciona
   igual — solo que sin voz.

Cuando tengáis definida "la voz oficial" de Helion, usad ese mismo modelo aquí:
la coherencia entre el robot real y el bot es lo que hace que la gente flipe.

---

## Avisos honestos

- La reproducción usa **yt-dlp**: para un bot privado de comunidad en un PC de
  casa funciona bien, pero YouTube cambia cosas de vez en cuando — si un día
  `/play` falla, casi siempre se arregla con `pip install -U yt-dlp`.
- El audio consume ancho de banda de subida del PC donde corre el bot
  (~128 kbps por servidor). Para un servidor de amigos, ni se nota.

## Estructura del paquete

```
radio_helion/
├── musica.py           ← el sistema completo (cog)
├── README_MUSICA.md    ← esto
├── requirements.txt    ← dependencias
├── .env.example        ← plantilla (cópiala a .env)
└── .gitignore          ← protege tu .env y tu base de datos
```

Dale caña, forjador. 🔧⚡
