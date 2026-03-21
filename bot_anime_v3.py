#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Anime V3.0 - Sistema Anti-Duplicado + Contenido Variado
- Verificación triple anti-duplicados (hash + URL + título similar)
- Contenido variado: Noticias, Personajes, Databooks, Curiosidades
- APIs: Jikan (MAL), AniList, NewsAPI
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from urllib.parse import urlparse, quote
from collections import deque

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', os.path.join(BASE_DIR, 'data', 'historial_anime_v3.json'))
ESTADO_PATH = os.getenv('ESTADO_PATH', os.path.join(BASE_DIR, 'data', 'estado_bot_v3.json'))

# Configuración de publicación
TIEMPO_ENTRE_PUBLICACIONES = 90  # Aumentado a 90 minutos
MAX_PUBLICACIONES_DIA = 12  # Reducido para mejor calidad
UMBRAL_SIMILITUD_TITULO = 0.85  # Aumentado para evitar duplicados similares
MAX_CARACTERES_FB = 1800

# Control de contenido - ROTACIÓN DE TIPOS
TIPOS_CONTENIDO = ["noticia", "personaje", "curiosidad", "databook", "estreno"]
PESOS_TIPO = {"noticia": 0.30, "personaje": 0.25, "curiosidad": 0.20, "databook": 0.15, "estreno": 0.10}

AI_SERVICE = None

# Inicializar IA (igual que antes)
if OPENROUTER_API_KEY:
    try:
        test_resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": "google/gemini-2.0-flash-exp:free", "messages": [{"role": "user", "content": "hola"}]},
            timeout=10
        )
        if test_resp.status_code == 200:
            AI_SERVICE = "openrouter"
            print("✅ OpenRouter conectado")
    except Exception as e:
        print(f"⚠️ OpenRouter no disponible: {e}")

if not AI_SERVICE and GEMINI_API_KEY:
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        test = client.models.generate_content(model="gemini-2.0-flash", contents="hola")
        AI_SERVICE = "gemini"
        print("✅ Gemini conectado")
    except Exception as e:
        print(f"⚠️ Gemini no disponible: {e}")

if not AI_SERVICE:
    print("⚠️ Sin servicio de IA - usando redacción manual")

# =============================================================================
# FUENTES RSS AMPLIADAS Y CATEGORIZADAS
# =============================================================================

RSS_FEEDS = {
    "noticia": [
        'https://somoskudasai.com/feed/',
        'https://www.animenewsnetwork.com/all/rss.xml',
        'https://myanimelist.net/rss/news.xml',
        'https://otakumode.com/news/feed',
        'https://honeysanime.com/feed/',
        'https://animehunch.com/feed/',
        'https://animecorner.me/feed',
        'https://www.crunchyroll.com/news/feed',
    ],
    "estreno": [
        'https://anitrendz.net/news/feed',
        'https://www.anime-planet.com/rss',
        'https://randomc.net/feed',
    ],
    "curiosidad": [
        'https://animemotivation.com/resources/',
        'https://otakuorbit.com/feed',
        'https://animemangastudies.com/feed',
    ]
}

# Anime populares para búsqueda de personajes/databooks
ANIME_POPULARES = [
    "One Piece", "Naruto", "Dragon Ball", "Attack on Titan", "Demon Slayer",
    "Jujutsu Kaisen", "My Hero Academia", "Spy x Family", "Chainsaw Man",
    "Bleach", "Hunter x Hunter", "Evangelion", "Death Note", "Fullmetal Alchemist",
    "One Punch Man", "Tokyo Ghoul", "Sword Art Online", "Steins;Gate",
    "Cowboy Bebop", "Code Geass", "Gintama", "Fairy Tail", "Black Clover",
    "Dr. Stone", "Fire Force", "Kaguya-sama", "Re:Zero", "Overlord"
]

# Palabras clave con pesos para scoring
PALABRAS_ANIME = {
    "attack on titan": 20, "demon slayer": 20, "kimetsu": 20, "jujutsu kaisen": 20,
    "my hero academia": 18, "one piece": 18, "spy x family": 18, "chainsaw man": 18,
    "dragon ball": 15, "naruto": 15, "bleach": 15, "hunter x hunter": 15,
    "evangelion": 15, "studio ghibli": 15, "temporada": 12, "estreno": 12,
    "trailer": 10, "nuevo anime": 10, "personaje": 8, "protagonista": 8,
    "databook": 12, "información": 8, "curiosidad": 8, "seiyuu": 10
}

# =============================================================================
# SISTEMA ANTI-DUPLICADO MEJORADO
# =============================================================================

class AntiDuplicado:
    """Sistema triple capa: Hash MD5 + URL normalizada + Similitud de título"""

    def __init__(self, historial):
        self.historial = historial
        self.cache_hashes = set(historial.get('hashes_titulos', []))
        self.cache_urls = set(historial.get('urls_normalizadas', []))
        self.cache_titulos = deque(historial.get('titulos', [])[-50:], maxlen=50)  # Últimos 50
        self.cache_fingerprints = set(historial.get('fingerprints', []))  # Nuevo: fingerprint de contenido

    def generar_fingerprint(self, titulo, contenido):
        """Genera fingerprint único combinando título + contenido"""
        texto = f"{titulo} {contenido}".lower()
        # Eliminar stopwords y caracteres especiales
        texto = re.sub(r'[^\w\s]', '', texto)
        palabras = sorted(set(texto.split()))
        return hashlib.sha256(' '.join(palabras[:20]).encode()).hexdigest()[:16]

    def es_duplicado(self, titulo, url, contenido=""):
        """Verificación triple"""
        # 1. Verificar URL
        url_norm = normalizar_url(url)
        if url_norm in self.cache_urls:
            log(f"🔴 Duplicado por URL: {url_norm[:60]}...", 'debug')
            return True

        # 2. Verificar hash exacto del título
        hash_titulo = generar_hash(titulo)
        if hash_titulo in self.cache_hashes:
            log(f"🔴 Duplicado por hash exacto", 'debug')
            return True

        # 3. Verificar fingerprint de contenido
        if contenido:
            fp = self.generar_fingerprint(titulo, contenido)
            if fp in self.cache_fingerprints:
                log(f"🔴 Duplicado por fingerprint", 'debug')
                return True

        # 4. Verificar similitud con títulos recientes (últimos 50)
        for titulo_previo in self.cache_titulos:
            similitud = calcular_similitud(titulo, titulo_previo)
            if similitud >= UMBRAL_SIMILITUD_TITULO:
                log(f"🔴 Duplicado por similitud ({similitud:.2f}): '{titulo[:50]}...' vs '{titulo_previo[:50]}...'", 'debug')
                return True

        return False

    def registrar(self, titulo, url, contenido=""):
        """Registra en todas las capas"""
        self.cache_hashes.add(generar_hash(titulo))
        self.cache_urls.add(normalizar_url(url))
        self.cache_titulos.append(titulo)
        if contenido:
            self.cache_fingerprints.add(self.generar_fingerprint(titulo, contenido))

# =============================================================================
# OBTENCIÓN DE CONTENIDO VARIADO (APIs)
# =============================================================================

def obtener_personaje_jikan():
    """Obtiene información de un personaje aleatorio popular usando Jikan API (MAL)"""
    try:
        # Seleccionar anime popular aleatorio
        anime = random.choice(ANIME_POPULARES)

        # Buscar anime
        search_url = f"https://api.jikan.moe/v4/anime?q={quote(anime)}&limit=1"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data.get('data'):
            return None

        anime_id = data['data'][0]['mal_id']
        anime_title = data['data'][0]['title']

        # Obtener personajes del anime
        chars_url = f"https://api.jikan.moe/v4/anime/{anime_id}/characters"
        resp = requests.get(chars_url, timeout=10)
        if resp.status_code != 200:
            return None

        chars_data = resp.json()
        if not chars_data.get('data'):
            return None

        # Seleccionar personaje principal o importante
        personajes = [c for c in chars_data['data'] if c.get('role') in ['Main', 'Supporting']]
        if not personajes:
            personajes = chars_data['data']

        personaje = random.choice(personajes[:10])  # Entre los 10 primeros
        char_info = personaje['character']

        # Obtener detalles del personaje
        char_id = char_info['mal_id']
        detail_url = f"https://api.jikan.moe/v4/characters/{char_id}/full"
        resp = requests.get(detail_url, timeout=10)

        bio = ""
        if resp.status_code == 200:
            detail_data = resp.json()
            bio = detail_data.get('data', {}).get('about', '')[:500]

        return {
            'titulo': f"{char_info['name']} de {anime_title}",
            'descripcion': bio or f"Personaje de {anime_title}",
            'url': char_info.get('url', f"https://myanimelist.net/character/{char_id}"),
            'imagen': char_info.get('images', {}).get('jpg', {}).get('image_url'),
            'fuente': 'MyAnimeList (Jikan)',
            'tipo': 'personaje',
            'puntaje': 85,
            'metadata': {
                'anime': anime_title,
                'rol': personaje.get('role', 'Desconocido'),
                'favoritos': char_info.get('favorites', 0)
            }
        }
    except Exception as e:
        log(f"Error Jikan: {e}", 'debug')
        return None

def obtener_curiosidad_anilist():
    """Obtiene curiosidad de anime usando AniList GraphQL API"""
    try:
        query = """
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                media(type: ANIME, sort: POPULARITY_DESC, isAdult: false) {
                    id
                    title { romaji english native }
                    description
                    popularity
                    averageScore
                    episodes
                    status
                    season
                    seasonYear
                    studios { nodes { name } }
                    coverImage { large }
                }
            }
        }
        """

        variables = {"page": random.randint(1, 10), "perPage": 10}

        resp = requests.post(
            "https://graphql.anilist.co",
            json={"query": query, "variables": variables},
            timeout=10
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        medias = data.get('data', {}).get('Page', {}).get('media', [])
        if not medias:
            return None

        anime = random.choice(medias)
        titulo = anime['title']['romaji'] or anime['title']['english'] or anime['title']['native']

        # Crear curiosidad basada en datos
        desc = anime.get('description', '')[:400]
        studio = anime.get('studios', {}).get('nodes', [{}])[0].get('name', 'Estudio desconocido')

        curiosidad = f"{titulo} - {desc} Este anime tiene una puntuación de {anime.get('averageScore', 'N/A')}/100 y fue producido por {studio}."

        return {
            'titulo': f"Curiosidad: {titulo}",
            'descripcion': curiosidad,
            'url': f"https://anilist.co/anime/{anime['id']}",
            'imagen': anime.get('coverImage', {}).get('large'),
            'fuente': 'AniList',
            'tipo': 'curiosidad',
            'puntaje': min(anime.get('popularity', 0) / 1000, 100),
            'metadata': {
                'score': anime.get('averageScore'),
                'episodios': anime.get('episodes'),
                'estado': anime.get('status'),
                'temporada': f"{anime.get('season')} {anime.get('seasonYear')}"
            }
        }
    except Exception as e:
        log(f"Error AniList: {e}", 'debug')
        return None

def obtener_databook_info():
    """Genera contenido tipo databook usando información de APIs"""
    try:
        # Usar Jikan para obtener anime con muchos datos
        anime = random.choice(["One Piece", "Naruto", "Bleach", "Fairy Tail", "Gintama"])

        search_url = f"https://api.jikan.moe/v4/anime?q={quote(anime)}&limit=1"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data.get('data'):
            return None

        anime_data = data['data'][0]
        anime_id = anime_data['mal_id']

        # Obtener estadísticas
        stats_url = f"https://api.jikan.moe/v4/anime/{anime_id}/statistics"
        resp = requests.get(stats_url, timeout=10)
        stats = {}
        if resp.status_code == 200:
            stats_data = resp.json().get('data', {})
            stats = {
                'completado': stats_data.get('completed', 0),
                'viendo': stats_data.get('watching', 0),
                'puntuacion': stats_data.get('score', 0)
            }

        # Obtener staff
        staff_url = f"https://api.jikan.moe/v4/anime/{anime_id}/staff"
        resp = requests.get(staff_url, timeout=10)
        staff_names = []
        if resp.status_code == 200:
            staff_data = resp.json().get('data', [])
            staff_names = [s['person']['name'] for s in staff_data[:3]]

        titulo = anime_data['title']
        sinopsis = anime_data.get('synopsis', '')[:300]

        descripcion = f"Databook de {titulo}. {sinopsis} "
        if stats:
            descripcion += f"Estadísticas MAL: {stats.get('completado', 0):,} usuarios completaron la serie. "
        if staff_names:
            descripcion += f"Staff clave: {', '.join(staff_names)}."

        return {
            'titulo': f"📚 Databook: {titulo}",
            'descripcion': descripcion,
            'url': anime_data.get('url'),
            'imagen': anime_data.get('images', {}).get('jpg', {}).get('large_image_url'),
            'fuente': 'MyAnimeList Databook',
            'tipo': 'databook',
            'puntaje': 90,
            'metadata': {
                'episodios': anime_data.get('episodes'),
                'duracion': anime_data.get('duration'),
                'rating': anime_data.get('rating'),
                'score_mal': anime_data.get('score')
            }
        }
    except Exception as e:
        log(f"Error Databook: {e}", 'debug')
        return None

def obtener_noticias_newsapi():
    """Obtiene noticias de NewsAPI como fuente adicional"""
    if not NEWS_API_KEY:
        return []

    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': 'anime OR manga OR "japanese animation"',
            'language': 'es',
            'sortBy': 'publishedAt',
            'pageSize': 10,
            'apiKey': NEWS_API_KEY
        }

        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return []

        data = resp.json()
        articulos = data.get('articles', [])

        noticias = []
        for art in articulos:
            titulo = art.get('title', '').strip()
            if not titulo or '[Removed]' in titulo:
                continue

            noticias.append({
                'titulo': limpiar_texto(titulo),
                'descripcion': limpiar_texto(art.get('description', '')),
                'url': art.get('url'),
                'imagen': art.get('urlToImage'),
                'fuente': extraer_dominio(art.get('url', '')),
                'tipo': 'noticia',
                'puntaje': calcular_puntaje(titulo, art.get('description', '')),
                'fecha': art.get('publishedAt')
            })

        return noticias
    except Exception as e:
        log(f"Error NewsAPI: {e}", 'debug')
        return []

def obtener_noticias_rss(tipo="noticia"):
    """Obtiene noticias de RSS feeds categorizados"""
    feeds = RSS_FEEDS.get(tipo, RSS_FEEDS["noticia"])
    noticias = []

    for feed_url in feeds:
        try:
            log(f"📡 RSS [{tipo}]: {feed_url[:45]}...", 'debug')
            feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
            if not feed or not feed.entries:
                continue

            for entry in feed.entries[:3]:
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo:
                    continue

                link = entry.get('link', '')
                if not link:
                    continue

                desc = limpiar_texto(entry.get('summary', '') or entry.get('description', ''))

                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for l in entry.links:
                        if l.get('type', '').startswith('image/'):
                            imagen = l.get('href')
                            break

                tipo_detectado = detectar_tipo(titulo, desc)
                if tipo == "estreno" or tipo_detectado == "estreno":
                    tipo_final = "estreno"
                else:
                    tipo_final = tipo

                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': desc,
                    'url': link,
                    'imagen': imagen,
                    'fuente': extraer_dominio(link),
                    'tipo': tipo_final,
                    'puntaje': calcular_puntaje(titulo, desc)
                })
        except Exception as e:
            log(f"Error RSS: {e}", 'debug')
            continue

    return noticias

# =============================================================================
# REDACCIÓN MEJORADA POR TIPO
# =============================================================================

def truncar_texto(texto, max_chars=MAX_CARACTERES_FB):
    """Trunca texto respetando palabras y estructura"""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars].rsplit(' ', 1)[0] + "..."

def redactar_con_ia(titulo, contenido, tipo="noticia", metadata=None):
    """Genera publicación adaptada al tipo de contenido"""

    emojis_tipo = {
        "personaje": "🎭",
        "databook": "📚", 
        "historia": "📖",
        "estreno": "🚨",
        "noticia": "📢",
        "curiosidad": "💡"
    }

    emoji_header = emojis_tipo.get(tipo, "📢")

    # Prompts específicos por tipo
    prompts_especificos = {
        "personaje": f"""Enfócate en el personaje: quién es, su rol en la historia, por qué es importante.
Datos clave: Rol: {metadata.get('rol', 'Desconocido')}, Favoritos MAL: {metadata.get('favoritos', 'N/A')}""",

        "databook": f"""Enfócate en datos técnicos y estadísticas del anime/manga.
Datos: Episodios: {metadata.get('episodios', 'N/A')}, Puntuación: {metadata.get('score_mal', 'N/A')}, Rating: {metadata.get('rating', 'N/A')}""",

        "curiosidad": f"""Enfócate en datos interesantes, rarezas o información poco conocida.
Datos: Puntuación: {metadata.get('score', 'N/A')}, Temporada: {metadata.get('temporada', 'N/A')}""",

        "estreno": "Enfócate en fechas, trailers, y qué esperar de este estreno.",

        "noticia": "Enfócate en la noticia actual, impacto en la comunidad anime, y detalles relevantes."
    }

    prompt_especifico = prompts_especificos.get(tipo, "")

    prompt = f"""Crea una publicación de Facebook sobre anime en ESPAÑOL LATINO.

TÍTULO ORIGINAL: {titulo}
CONTENIDO: {contenido[:800]}
TIPO: {tipo}

INSTRUCCIONES ESPECÍFICAS PARA {tipo.upper()}:
{prompt_especifico}

REGLAS GENERALES:
1. ESPAÑOL LATINO (tú, no usted)
2. Estructura OBLIGATORIA:

   {emoji_header} [HOOK llamativo específico para {tipo}]

   🎌 [Título traducido/resumido - máx 70 chars]

   📰 [Contenido adaptado al tipo - 3-4 oraciones con datos concretos]

   💬 [CTA que invite a interactuar según el tipo]

   [3-4 hashtags relevantes al anime/tema]

3. Máximo 1600 caracteres
4. Incluir información concreta: nombres, números, fechas
5. No uses emojis en exceso

EJEMPLO PARA {tipo.upper()}:
{obtener_ejemplo_tipo(tipo)}"""

    if AI_SERVICE == "openrouter":
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com",
                    "X-Title": "Anime Bot"
                },
                json={
                    "model": "google/gemini-2.0-flash-exp:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return truncar_texto(data['choices'][0]['message']['content'].strip(), 1600)
        except Exception as e:
            log(f"⚠️ Error OpenRouter: {e}", 'debug')

    if AI_SERVICE == "gemini":
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=GEMINI_API_KEY)

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=500)
            )
            if response and response.text:
                return truncar_texto(response.text.strip(), 1600)
        except Exception as e:
            log(f"⚠️ Error Gemini: {e}", 'debug')

    return None

def obtener_ejemplo_tipo(tipo):
    """Retorna ejemplo según el tipo"""
    ejemplos = {
        "personaje": """🎭 ¡El cerebro detrás de todo!

🎌 L Lawliet de Death Note

📰 L es el detective más brillante del mundo, conocido por sentarse raro y comer dulces mientras resuelve casos imposibles. Su rivalidad intelectual con Light Yagami es legendaria. Creado por Tsugumi Ohba, es uno de los personajes más populares de MAL con más de 50,000 favoritos.

¿Team L o Team Light? ¡Defiendan su favorito! 👇

#DeathNote #L #Anime""",

        "databook": """📚 Datos oficiales revelados

🎌 One Piece Databook Vol. 1

📰 El databook confirma que Luffy nació el 5 de mayo (Día del Niño en Japón). Sanji originalmente se llamaba Naruto. La fruta Gomu Gomu cambió de nombre 3 veces durante la creación. Eiichiro Oda reveló que el final ya está planeado desde 2002.

¿Qué dato les sorprendió más? 👇

#OnePiece #Databook #EiichiroOda""",

        "curiosidad": """💡 ¿Lo sabías?

🎌 Evangelion y su presupuesto

📰 Neon Genesis Evangelion tuvo tantos problemas de presupuesto en sus últimos episodios que usaron grabaciones de voz sobre fotografías estáticas. El episodio 25 y 26 fueron controversiales por su abstracto final. Años después, Gainax lanzó "The End of Evangelion" para dar cierre "real".

¿Prefieren el final original o EoE? 👇

#Evangelion #Curiosidad #Anime90s""",

        "estreno": """🚨 ¡Fecha confirmada!

🎌 Jujutsu Kaisen Season 3

📰 Mappa confirmó que la temporada adaptará el arco del "Incidente de Shibuya" en octubre 2025. El director será nuevamente Shōta Goshozono. Se espera que tenga 23 episodios y animación de nivel cinematográfico.

¿Listos para el trauma de Shibuya? 👇

#JujutsuKaisen #Estreno #MAPPA"""
    }
    return ejemplos.get(tipo, "")

def redactar_manual_mejorado(titulo, contenido, tipo="noticia", fuente="", metadata=None):
    """Redacción manual específica por tipo"""

    hooks = {
        "personaje": ["🎭 ¡Personaje destacado!", "✨ ¡Conoce a...!", "🔥 ¡Protagonista épico!", "💎 ¡Personaje icónico!"],
        "databook": ["📚 ¡Datos oficiales!", "📖 ¡Información confirmada!", "🔍 ¡Detalles revelados!", "📊 ¡Estadísticas!"],
        "curiosidad": ["💡 ¿Sabías que...?", "🤯 ¡Dato curioso!", "🎯 ¡Información secreta!", "🔮 ¡Misterio resuelto!"],
        "estreno": ["🚨 ¡Fechas confirmadas!", "🎉 ¡Estreno anunciado!", "✨ ¡Llega pronto!", "📅 ¡Calendario anime!"],
        "noticia": ["📢 ¡Última hora!", "🔥 ¡Noticia bomba!", "🎌 ¡Anuncio oficial!", "⚡ ¡Actualización!"]
    }

    ctas = {
        "personaje": ["¿Su personaje favorito? ¡Opinen! 👇", "¿Qué les parece este personaje? 👇", "¿Team protagonista o antagonista? 👇"],
        "databook": ["¿Qué dato les sorprendió más? 👇", "¿Ya sabían esto? 👇", "¿Más databooks de este anime? 👇"],
        "curiosidad": ["¿Lo sabían? ¡Cuéntenme! 👇", "¿Más curiosidades así? 👇", "¿Verdad o mito? 👇"],
        "estreno": ["¿Lo esperan con ansias? 👇", "¿Emocionados por el estreno? 👇", "¿Marcando el calendario? 👇"],
        "noticia": ["¿Qué les parece esta noticia? 👇", "¿Impactados? ¡Reaccionen! 👇", "¿Opiniones? ¡Al comentario! 👇"]
    }

    hook = random.choice(hooks.get(tipo, hooks["noticia"]))
    cta = random.choice(ctas.get(tipo, ctas["noticia"]))

    # Procesar contenido según tipo
    oraciones = re.split(r'[.!?]+', contenido)
    oraciones = [s.strip() for s in oraciones if len(s.strip()) > 20]

    resumen_parts = []
    chars_count = 0
    max_chars_resumen = 400 if tipo in ["databook", "curiosidad"] else 350

    for oracion in oraciones[:6]:
        if chars_count + len(oracion) < max_chars_resumen and len(oracion) > 30:
            oracion_limpia = re.sub(r'\s+', ' ', oracion).strip()
            if oracion_limpia:
                resumen_parts.append(oracion_limpia)
                chars_count += len(oracion_limpia) + 2

    if resumen_parts:
        resumen = ". ".join(resumen_parts) + "."
    else:
        resumen = contenido[:300].rsplit(' ', 1)[0] + "..."

    # Añadir metadata si existe
    if metadata and tipo == "personaje":
        resumen += f" Rol: {metadata.get('rol', 'Desconocido')}."
    elif metadata and tipo == "databook":
        if metadata.get('episodios'):
            resumen += f" Episodios: {metadata['episodios']}."
        if metadata.get('score_mal'):
            resumen += f" Puntuación MAL: {metadata['score_mal']}/10."
    elif metadata and tipo == "curiosidad":
        if metadata.get('score'):
            resumen += f" Puntuación media: {metadata['score']}/100."

    titulo_limpio = re.sub(r'\s+', ' ', titulo).strip()[:75]

    # Hashtags específicos por tipo
    hashtags_map = {
        "personaje": "#Anime #Personajes #OtakuLife",
        "databook": "#Anime #Databook #OtakuFacts",
        "curiosidad": "#Anime #Curiosidades #OtakuTrivia",
        "estreno": "#Anime #Estreno #NuevoAnime",
        "noticia": "#Anime #Noticias #Otaku"
    }
    hashtags = hashtags_map.get(tipo, "#Anime #Noticias #Otaku")

    lineas = [
        hook,
        "",
        f"🎌 {titulo_limpio}",
        "",
        f"📰 {resumen}",
        "",
        f"💬 {cta}",
        "",
        hashtags
    ]

    return truncar_texto("\n".join(lineas), MAX_CARACTERES_FB)

def verificar_espanol(texto):
    palabras = ["el", "la", "de", "que", "y", "en", "un", "es", "se", "no", "lo", "su", "con", "por", "para", "del", "al"]
    texto_lower = texto.lower()
    return sum(1 for p in palabras if f" {p} " in f" {texto_lower} ") >= 3

def detectar_tipo(titulo, desc):
    texto = f"{titulo} {desc}".lower()
    if any(p in texto for p in ["personaje", "protagonista", "seiyuu", "diseño", "character"]):
        return "personaje"
    if any(p in texto for p in ["databook", "guía oficial", "data book", "fanbook"]):
        return "databook"
    if any(p in texto for p in ["curiosidad", "sabías", "dato", "misterio", "teoría", "secretos"]):
        return "curiosidad"
    if any(p in texto for p in ["estreno", "trailer", "temporada", "fecha", "anunciado", "próximo"]):
        return "estreno"
    return "noticia"

# =============================================================================
# UTILIDADES (mantenidas del original)
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None: default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else default.copy()
        except: pass
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

def generar_hash(texto):
    if not texto: return ""
    t = re.sub(r'[^\w\s]', '', texto.lower().strip())
    return hashlib.md5(re.sub(r'\s+', ' ', t).encode()).hexdigest()

def normalizar_url(url):
    if not url: return ""
    try:
        parsed = urlparse(url)
        netloc = re.sub(r'^(www\.|m\.)', '', parsed.netloc.lower())
        path = re.sub(r'/index\.html?$', '/', parsed.path.lower().rstrip('/'))
        # Eliminar parámetros de tracking
        path = re.sub(r'[?&](utm_|ref|source|campaign).*', '', path)
        return f"{netloc}{path}"
    except: return url.lower().strip()

def calcular_similitud(t1, t2):
    if not t1 or not t2: return 0.0
    def n(t): return re.sub(r'[^\w\s]', '', t.lower().strip())
    return SequenceMatcher(None, n(t1), n(t2)).ratio()

def limpiar_texto(texto):
    if not texto: return ""
    import html
    t = html.unescape(texto)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def calcular_puntaje(titulo, desc):
    txt = f"{titulo} {desc}".lower()
    p = sum(puntos for palabra, puntos in PALABRAS_ANIME.items() if palabra in txt)
    return min(p + 5, 100) if 20 <= len(titulo) <= 120 else min(p, 100)

def extraer_dominio(url):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split('.')
        return '.'.join(parts[-2:]) if len(parts) > 2 else netloc
    except: return "anime"

# =============================================================================
# EXTRACCIÓN WEB Y PROCESAMIENTO DE IMÁGENES (mantenido)
# =============================================================================

def extraer_web(url):
    if not url: return None, None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')

        for elem in soup(['script', 'style', 'nav', 'header', 'footer']): elem.decompose()

        content = None
        for selector in ['article', '.entry-content', '.post-content', 'main', '.content']:
            elem = soup.select_one(selector)
            if elem:
                paragraphs = elem.find_all('p')
                text = ' '.join([limpiar_texto(p.get_text()) for p in paragraphs if len(p.get_text()) > 25])
                if len(text) > 100:
                    content = text[:1200]
                    break

        imagen = None
        for meta in ['og:image', 'twitter:image']:
            tag = soup.find('meta', property=meta) or soup.find('meta', attrs={'name': meta})
            if tag and tag.get('content'):
                imagen = tag['content'].strip()
                break

        return content, imagen
    except Exception as e:
        log(f"Error extrayendo: {e}", 'debug')
        return None, None

def descargar_imagen(url):
    if not url: return None
    for bad in ['google.com', 'gstatic.com', 'facebook.com', 'logo', 'icon', 'favicon']:
        if bad in url.lower(): return None

    try:
        from PIL import Image
        from io import BytesIO

        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20, stream=True)
        if 'image' not in r.headers.get('content-type', ''): return None

        img = Image.open(BytesIO(r.content))
        w, h = img.size
        if w < 400 or h < 300 or w/h > 3 or h/w > 3: return None

        if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
        img.thumbnail((1200, 1200))

        path = f'/tmp/anime_{generar_hash(url)[:8]}.jpg'
        img.save(path, 'JPEG', quality=85)

        if os.path.getsize(path) < 10000:
            os.remove(path)
            return None
        return path
    except Exception as e:
        log(f"Error imagen: {e}", 'debug')
        return None

def crear_imagen_default(titulo, tipo="noticia"):
    """Crea imagen según el tipo de contenido"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        # Colores según tipo
        colores = {
            "personaje": ("#1a1a2e", "#e94560", "#0f3460"),
            "databook": ("#16213e", "#e94560", "#0f3460"),
            "curiosidad": ("#0f0f23", "#ff006e", "#3a0ca3"),
            "estreno": ("#1a1a2e", "#f39c12", "#e74c3c"),
            "noticia": ("#0f0f23", "#ff006e", "#3a0ca3")
        }

        bg_color, accent1, accent2 = colores.get(tipo, colores["noticia"])

        img = Image.new('RGB', (1200, 630), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Bordes decorativos
        draw.rectangle([(0, 0), (1200, 8)], fill=accent1)
        draw.rectangle([(0, 622), (1200, 630)], fill=accent2)

        # Emoji según tipo
        emojis = {"personaje": "🎭", "databook": "📚", "curiosidad": "💡", "estreno": "🚨", "noticia": "📢"}
        emoji = emojis.get(tipo, "🎌")

        fonts_to_try = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf"
        ]

        font_title = font_sub = None
        for font_path in fonts_to_try:
            try:
                if os.path.exists(font_path):
                    font_title = ImageFont.truetype(font_path, 46)
                    font_sub = ImageFont.truetype(font_path, 26)
                    break
            except: continue

        if not font_title:
            font_title = font_sub = ImageFont.load_default()

        wrapped = textwrap.fill(titulo[:70], width=30)
        lines = wrapped.split('\n')
        y_start = (630 - len(lines) * 55) // 2 - 10

        for i, line in enumerate(lines):
            draw.text((60, y_start + i * 55), line, font=font_title, fill='#ffffff')

        draw.text((60, 550), f"{emoji} {tipo.upper()} | Anime Inteligente", font=font_sub, fill=accent1)
        draw.text((60, 590), "🎌 Contenido variado para otakus", font=font_sub, fill='#a0a0a0')

        path = f'/tmp/anime_{tipo}_{generar_hash(titulo)[:8]}.jpg'
        img.save(path, 'JPEG', quality=90)
        return path
    except Exception as e:
        log(f"Error imagen default: {e}", 'error')
        return None

# =============================================================================
# HISTORIAL Y ESTADO MEJORADOS
# =============================================================================

def cargar_historial():
    default = {
        'urls': [],
        'urls_normalizadas': [],
        'hashes_titulos': [],
        'fingerprints': [],
        'titulos': [],
        'timestamps': [],
        'tipos_publicados': {},  # Contador por tipo
        'estadisticas': {'total': 0, 'hoy': 0, 'fecha': None}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h: h[k] = default[k]
    return h

def guardar_historial(historial, url, titulo, tipo, contenido=""):
    """Guarda con sistema anti-duplicado mejorado"""
    anti_dup = AntiDuplicado(historial)
    anti_dup.registrar(titulo, url, contenido)

    historial['urls'] = list(anti_dup.cache_urls)[-200:]
    historial['urls_normalizadas'] = list(anti_dup.cache_urls)[-200:]
    historial['hashes_titulos'] = list(anti_dup.cache_hashes)[-200:]
    historial['fingerprints'] = list(anti_dup.cache_fingerprints)[-200:]
    historial['titulos'] = list(anti_dup.cache_titulos)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['timestamps'] = historial['timestamps'][-200:]

    # Contador por tipo
    if tipo not in historial['tipos_publicados']:
        historial['tipos_publicados'][tipo] = 0
    historial['tipos_publicados'][tipo] += 1

    historial['estadisticas']['total'] += 1
    historial['estadisticas']['hoy'] += 1
    historial['estadisticas']['fecha'] = datetime.now().strftime('%Y-%m-%d')

    guardar_json(HISTORIAL_PATH, historial)
    return historial

def verificar_limite():
    estado = cargar_json(ESTADO_PATH, {'ultima': None, 'hoy': 0, 'fecha': None, 'tipo_ultimo': None})
    hoy = datetime.now().strftime('%Y-%m-%d')

    if estado.get('fecha') != hoy:
        estado = {'ultima': None, 'hoy': 0, 'fecha': hoy, 'tipo_ultimo': None}

    if estado['hoy'] >= MAX_PUBLICACIONES_DIA:
        log(f"🚫 Límite diario alcanzado ({MAX_PUBLICACIONES_DIA})", 'advertencia')
        return False, estado

    ultima = estado.get('ultima')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            minutos = (datetime.now() - ultima_dt).total_seconds() / 60
            if minutos < TIEMPO_ENTRE_PUBLICACIONES:
                log(f"⏱️ Esperando {TIEMPO_ENTRE_PUBLICACIONES - minutos:.0f}min más", 'info')
                return False, estado
        except: pass

    return True, estado

def seleccionar_tipo(historial):
    """Selecciona tipo de contenido basado en rotación y frecuencia"""
    tipos_count = historial.get('tipos_publicados', {})
    total = sum(tipos_count.values()) if tipos_count else 0

    if total == 0:
        return random.choice(TIPOS_CONTENIDO)

    # Encontrar el tipo menos publicado proporcionalmente
    scores = {}
    for tipo in TIPOS_CONTENIDO:
        actual = tipos_count.get(tipo, 0)
        esperado = total * PESOS_TIPO.get(tipo, 0.2)
        scores[tipo] = esperado - actual  # Negativo = necesita más

    # 70% probabilidad de elegir el que más falta, 30% aleatorio
    if random.random() < 0.7:
        return max(scores, key=scores.get)
    else:
        return random.choice(TIPOS_CONTENIDO)

# =============================================================================
# FACEBOOK (mantenido con mejoras)
# =============================================================================

def publicar_facebook(mensaje, imagen_path):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False

    mensaje_seguro = truncar_texto(mensaje, MAX_CARACTERES_FB)
    log(f"📝 Caracteres: {len(mensaje_seguro)}/{MAX_CARACTERES_FB}", 'info')

    try:
        debug_url = "https://graph.facebook.com/v22.0/debug_token"
        debug_params = {'input_token': FB_ACCESS_TOKEN, 'access_token': FB_ACCESS_TOKEN}

        resp = requests.get(debug_url, params=debug_params, timeout=10)
        debug_info = resp.json()

        if 'data' in debug_info:
            data = debug_info['data']
            scopes = data.get('scopes', [])
            if 'pages_manage_posts' not in scopes:
                log("❌ FALTA PERMISO: pages_manage_posts", 'error')
                return False

            profile_id = data.get('profile_id')
            if profile_id and profile_id != FB_PAGE_ID:
                page_token = obtener_page_token(FB_ACCESS_TOKEN, FB_PAGE_ID)
                if page_token:
                    return publicar_con_token(mensaje_seguro, imagen_path, page_token)
                return False
    except Exception as e:
        log(f"⚠️ Error verificando token: {e}", 'advertencia')

    return publicar_con_token(mensaje_seguro, imagen_path, FB_ACCESS_TOKEN)

def obtener_page_token(user_token, page_id):
    try:
        url = f"https://graph.facebook.com/v22.0/{page_id}"
        params = {'fields': 'access_token', 'access_token': user_token}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        return data.get('access_token')
    except Exception as e:
        log(f"❌ Error obteniendo Page Token: {e}", 'error')
        return None

def publicar_con_token(mensaje, imagen_path, token):
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"

        if os.path.getsize(imagen_path) > 10 * 1024 * 1024:
            from PIL import Image
            img = Image.open(imagen_path)
            img.thumbnail((800, 800))
            img.save(imagen_path, 'JPEG', quality=70, optimize=True)

        with open(imagen_path, 'rb') as img:
            files = {'file': ('anime.jpg', img, 'image/jpeg')}
            data = {
                'message': mensaje[:MAX_CARACTERES_FB],
                'access_token': token,
                'published': 'true'
            }

            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()

        if 'id' in result or 'post_id' in result:
            post_id = result.get('post_id', result.get('id'))
            log(f"✅ Publicado: {post_id}", 'exito')
            return True

        error = result.get('error', {})
        code = error.get('code')
        msg = error.get('message', 'Unknown')
        log(f"❌ Error FB ({code}): {msg}", 'error')

        if code in [1, 200]:
            return publicar_solo_texto(mensaje, token)
        return False

    except Exception as e:
        log(f"❌ Excepción: {e}", 'error')
        return False

def publicar_solo_texto(mensaje, token):
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed"
        data = {
            'message': mensaje[:MAX_CARACTERES_FB],
            'access_token': token,
            'link': 'https://anime.news'
        }

        resp = requests.post(url, data=data, timeout=30)
        result = resp.json()

        if 'id' in result:
            log(f"✅ Publicado (texto): {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {})
            log(f"❌ Error texto: {error.get('message', 'Unknown')}", 'error')
            return False
    except Exception as e:
        log(f"❌ Error texto: {e}", 'error')
        return False

# =============================================================================
# MAIN MEJORADO
# =============================================================================

def obtener_contenido_por_tipo(tipo, historial):
    """Obtiene contenido según el tipo seleccionado"""
    anti_dup = AntiDuplicado(historial)
    candidatos = []

    log(f"🔍 Buscando contenido tipo: {tipo}", 'info')

    if tipo == "personaje":
        # Intentar obtener personaje de Jikan
        for _ in range(3):  # 3 intentos
            data = obtener_personaje_jikan()
            if data and not anti_dup.es_duplicado(data['titulo'], data['url'], data['descripcion']):
                candidatos.append(data)
                break
            time.sleep(1)

    elif tipo == "curiosidad":
        data = obtener_curiosidad_anilist()
        if data and not anti_dup.es_duplicado(data['titulo'], data['url'], data['descripcion']):
            candidatos.append(data)

    elif tipo == "databook":
        data = obtener_databook_info()
        if data and not anti_dup.es_duplicado(data['titulo'], data['url'], data['descripcion']):
            candidatos.append(data)

    elif tipo in ["noticia", "estreno"]:
        # RSS + NewsAPI
        noticias = obtener_noticias_rss(tipo)
        noticias.extend(obtener_noticias_newsapi())

        for n in noticias:
            if not anti_dup.es_duplicado(n['titulo'], n['url'], n['descripcion']):
                candidatos.append(n)

        candidatos.sort(key=lambda x: x['puntaje'], reverse=True)

    return candidatos[:5]  # Top 5 candidatos

def main():
    print("\n" + "="*70)
    print("🇯🇵 BOT ANIME V3.0 - Anti-Duplicado + Contenido Variado")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 IA: {AI_SERVICE or 'Manual'} | FB: {'✅' if FB_ACCESS_TOKEN else '❌'}")
    print("="*70)

    puede, estado = verificar_limite()
    if not puede:
        return False

    historial = cargar_historial()
    log(f"📊 Hoy: {estado.get('hoy', 0)}/{MAX_PUBLICACIONES_DIA}", 'info')

    # Mostrar distribución de tipos
    tipos_count = historial.get('tipos_publicados', {})
    if tipos_count:
        distribucion = " | ".join([f"{k}:{v}" for k, v in sorted(tipos_count.items())])
        log(f"📈 Distribución histórica: {distribucion}", 'info')

    # Seleccionar tipo de contenido
    tipo_objetivo = seleccionar_tipo(historial)
    log(f"🎯 Tipo seleccionado: {tipo_objetivo}", 'info')

    # Obtener candidatos
    candidatos = obtener_contenido_por_tipo(tipo_objetivo, historial)

    if not candidatos:
        log(f"⚠️ Sin candidatos para {tipo_objetivo}, probando otros tipos...", 'advertencia')
        for alt_tipo in [t for t in TIPOS_CONTENIDO if t != tipo_objetivo]:
            candidatos = obtener_contenido_por_tipo(alt_tipo, historial)
            if candidatos:
                tipo_objetivo = alt_tipo
                log(f"✅ Usando tipo alternativo: {tipo_objetivo}", 'info')
                break

    if not candidatos:
        log("❌ Sin contenido disponible", 'error')
        return False

    # Seleccionar el mejor candidato
    seleccionada = None
    mensaje_final = None

    for candidato in candidatos:
        log(f"✍️ Generando texto ({AI_SERVICE or 'manual'})...", 'info')

        # Extraer más contenido si es RSS
        contenido_extra = candidato['descripcion']
        if candidato.get('url') and candidato['fuente'] not in ['MyAnimeList (Jikan)', 'AniList', 'MyAnimeList Databook']:
            web_content, _ = extraer_web(candidato['url'])
            if web_content and len(web_content) > 50:
                contenido_extra = web_content

        # Generar texto
        texto_ia = redactar_con_ia(
            candidato['titulo'], 
            contenido_extra, 
            candidato['tipo'],
            candidato.get('metadata', {})
        )

        if texto_ia and verificar_espanol(texto_ia):
            mensaje_final = texto_ia
            log("✅ Texto IA en español", 'exito')
        else:
            mensaje_final = redactar_manual_mejorado(
                candidato['titulo'],
                contenido_extra,
                candidato['tipo'],
                candidato['fuente'],
                candidato.get('metadata', {})
            )
            log("✅ Texto manual generado", 'info')

        if mensaje_final and verificar_espanol(mensaje_final):
            seleccionada = candidato
            break

    if not seleccionada or not mensaje_final:
        log("❌ No se pudo generar contenido válido", 'error')
        return False

    mensaje_final = truncar_texto(mensaje_final, MAX_CARACTERES_FB)

    # Preview
    print(f"\n{'='*60}")
    print(f"📱 PREVIEW ({seleccionada['tipo'].upper()}):")
    print(f"{'='*60}")
    print(mensaje_final)
    print(f"{'='*60}")
    print(f"📊 {len(mensaje_final)} chars | Fuente: {seleccionada['fuente']}")

    # Procesar imagen
    log("🖼️ Procesando imagen...", 'info')
    img_path = None
    if seleccionada.get('imagen'):
        img_path = descargar_imagen(seleccionada['imagen'])
    if not img_path:
        img_path = crear_imagen_default(seleccionada['titulo'], seleccionada['tipo'])

    # Publicar
    if not img_path:
        log("❌ Sin imagen, intentando texto solo...", 'error')
        exito = publicar_solo_texto(mensaje_final, FB_ACCESS_TOKEN)
    else:
        exito = publicar_facebook(mensaje_final, img_path)
        try:
            if os.path.exists(img_path): os.remove(img_path)
        except: pass

    if exito:
        historial = guardar_historial(
            historial, 
            seleccionada['url'], 
            seleccionada['titulo'],
            seleccionada['tipo'],
            seleccionada['descripcion']
        )
        estado['ultima'] = datetime.now().isoformat()
        estado['hoy'] = estado.get('hoy', 0) + 1
        estado['tipo_ultimo'] = seleccionada['tipo']
        guardar_json(ESTADO_PATH, estado)
        log(f"✅ Total histórico: {historial['estadisticas']['total']}", 'exito')
        return True
    else:
        log("❌ Falló publicación", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except KeyboardInterrupt:
        log("🛑 Interrumpido", 'advertencia')
        exit(0)
    except Exception as e:
        log(f"💥 Crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
