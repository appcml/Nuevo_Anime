#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Anime V3 - Sistema Anti-Duplicado + Contenido Variado
FIXES:
  1. Imagen de personaje: se relajan los filtros de proporción para aceptar retratos MAL
  2. Anti-duplicado preventivo: se registra ANTES de publicar para evitar ejecuciones dobles
  3. Filtro de relevancia: se valida que el texto generado por IA contenga referencias a anime
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import time
from datetime import datetime
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
ESTADO_PATH = os.getenv('ESTADO_PATH', os.path.join(BASE_DIR, 'data', 'estado_bot_anime_v3.json'))

TIEMPO_ENTRE_PUBLICACIONES = 90
MAX_PUBLICACIONES_DIA = 12
UMBRAL_SIMILITUD_TITULO = 0.85
MAX_CARACTERES_FB = 1800

TIPOS_CONTENIDO = ["noticia", "personaje", "curiosidad", "databook", "estreno"]
PESOS_TIPO = {"noticia": 0.30, "personaje": 0.25, "curiosidad": 0.20, "databook": 0.15, "estreno": 0.10}

ANIME_POPULARES = [
    "One Piece", "Naruto", "Dragon Ball", "Attack on Titan", "Demon Slayer",
    "Jujutsu Kaisen", "My Hero Academia", "Spy x Family", "Chainsaw Man",
    "Bleach", "Hunter x Hunter", "Evangelion", "Death Note", "Fullmetal Alchemist",
    "One Punch Man", "Tokyo Ghoul", "Sword Art Online", "Steins;Gate",
    "Cowboy Bebop", "Code Geass", "Gintama", "Fairy Tail", "Black Clover",
    "Dr. Stone", "Fire Force", "Kaguya-sama", "Re:Zero", "Overlord"
]

# FIX 3: Palabras clave para validar que el texto generado sea sobre anime
PALABRAS_CLAVE_ANIME = [
    "anime", "manga", "personaje", "shonen", "seinen", "shoujo", "otaku",
    "one piece", "naruto", "bleach", "dragon ball", "jujutsu", "demon slayer",
    "attack on titan", "my hero academia", "chainsaw", "evangelion", "death note",
    "fullmetal", "cowboy bebop", "hunter x hunter", "sword art", "re:zero",
    "temporada", "episodio", "opening", "ending", "seiyuu", "estudio",
    "shueisha", "mappa", "ufotable", "madhouse", "crunchyroll", "funimation",
    "protagonista", "antagonista", "bankai", "jutsu", "quirk", "titan",
    "shinigami", "nakama", "senpai", "sensei", "dojo", "akatsuki",
    "mal_id", "myanimelist", "anilist", "airing", "kimono"
]

RSS_FEEDS = {
    "noticia": [
        'https://somoskudasai.com/feed/',
        'https://www.animenewsnetwork.com/all/rss.xml',
        'https://myanimelist.net/rss/news.xml',
        'https://otakumode.com/news/feed',
        'https://honeysanime.com/feed/',
        'https://animehunch.com/feed/',
        'https://animecorner.me/feed',
    ],
    "estreno": [
        'https://anitrendz.net/news/feed',
        'https://www.anime-planet.com/rss',
    ],
    "curiosidad": [
        'https://animemotivation.com/resources/',
        'https://otakuorbit.com/feed',
    ]
}

AI_SERVICE = None

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
# UTILIDADES
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

def extraer_dominio(url):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split('.')
        return '.'.join(parts[-2:]) if len(parts) > 2 else netloc
    except: return "anime"

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
# FIX 3: VALIDADOR DE RELEVANCIA ANIME
# =============================================================================

def texto_es_relevante_anime(texto):
    """
    Verifica que el texto generado contenga al menos 2 referencias a anime.
    Evita publicar contenido fuera de tema (noticias de famosos, recetas, etc.)
    """
    if not texto:
        return False
    texto_lower = texto.lower()
    coincidencias = sum(1 for palabra in PALABRAS_CLAVE_ANIME if palabra in texto_lower)
    if coincidencias < 2:
        log(f"⚠️ Texto rechazado por irrelevante (solo {coincidencias} coincidencias anime)", 'advertencia')
        return False
    return True

# =============================================================================
# SISTEMA ANTI-DUPLICADO
# =============================================================================

class AntiDuplicado:
    def __init__(self, historial):
        self.cache_hashes = set(historial.get('hashes_titulos', []))
        self.cache_urls = set(historial.get('urls_normalizadas', []))
        self.cache_titulos = deque(historial.get('titulos', [])[-50:], maxlen=50)
        self.cache_fingerprints = set(historial.get('fingerprints', []))

    def generar_fingerprint(self, titulo, contenido):
        texto = f"{titulo} {contenido}".lower()
        texto = re.sub(r'[^\w\s]', '', texto)
        palabras = sorted(set(texto.split()))
        return hashlib.sha256(' '.join(palabras[:20]).encode()).hexdigest()[:16]

    def es_duplicado(self, titulo, url, contenido=""):
        url_norm = normalizar_url(url)
        if url_norm in self.cache_urls:
            log(f"🔴 Duplicado por URL: {url_norm[:60]}...", 'debug')
            return True

        hash_titulo = generar_hash(titulo)
        if hash_titulo in self.cache_hashes:
            log(f"🔴 Duplicado por hash exacto", 'debug')
            return True

        if contenido:
            fp = self.generar_fingerprint(titulo, contenido)
            if fp in self.cache_fingerprints:
                log(f"🔴 Duplicado por fingerprint", 'debug')
                return True

        for titulo_previo in self.cache_titulos:
            similitud = calcular_similitud(titulo, titulo_previo)
            if similitud >= UMBRAL_SIMILITUD_TITULO:
                log(f"🔴 Duplicado por similitud ({similitud:.2f})", 'debug')
                return True

        return False

    def registrar(self, titulo, url, contenido=""):
        self.cache_hashes.add(generar_hash(titulo))
        self.cache_urls.add(normalizar_url(url))
        self.cache_titulos.append(titulo)
        if contenido:
            self.cache_fingerprints.add(self.generar_fingerprint(titulo, contenido))

# =============================================================================
# OBTENCIÓN DE CONTENIDO
# =============================================================================

def obtener_personaje_jikan():
    try:
        anime = random.choice(ANIME_POPULARES)
        search_url = f"https://api.jikan.moe/v4/anime?q={quote(anime)}&limit=1"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200: return None

        data = resp.json()
        if not data.get('data'): return None

        anime_id = data['data'][0]['mal_id']
        anime_title = data['data'][0]['title']

        chars_url = f"https://api.jikan.moe/v4/anime/{anime_id}/characters"
        resp = requests.get(chars_url, timeout=10)
        if resp.status_code != 200: return None

        chars_data = resp.json()
        if not chars_data.get('data'): return None

        personajes = [c for c in chars_data['data'] if c.get('role') in ['Main', 'Supporting']]
        if not personajes: personajes = chars_data['data']

        personaje = random.choice(personajes[:10])
        char_info = personaje['character']

        char_id = char_info['mal_id']
        detail_url = f"https://api.jikan.moe/v4/characters/{char_id}/full"
        resp = requests.get(detail_url, timeout=10)

        bio = ""
        imagen_url = char_info.get('images', {}).get('jpg', {}).get('image_url')

        if resp.status_code == 200:
            detail_data = resp.json().get('data', {})
            bio = detail_data.get('about', '')[:500]
            # FIX 1: Preferir imagen de mayor resolución si está disponible
            large_img = detail_data.get('images', {}).get('jpg', {}).get('large_image_url')
            if large_img:
                imagen_url = large_img

        return {
            'titulo': f"{char_info['name']} de {anime_title}",
            'descripcion': bio or f"Personaje de {anime_title}",
            'url': char_info.get('url', f"https://myanimelist.net/character/{char_id}"),
            'imagen': imagen_url,
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

        if resp.status_code != 200: return None

        data = resp.json()
        medias = data.get('data', {}).get('Page', {}).get('media', [])
        if not medias: return None

        anime = random.choice(medias)
        titulo = anime['title']['romaji'] or anime['title']['english'] or anime['title']['native']

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
    try:
        anime = random.choice(["One Piece", "Naruto", "Bleach", "Fairy Tail", "Gintama"])

        search_url = f"https://api.jikan.moe/v4/anime?q={quote(anime)}&limit=1"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200: return None

        data = resp.json()
        if not data.get('data'): return None

        anime_data = data['data'][0]
        anime_id = anime_data['mal_id']

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
    if not NEWS_API_KEY: return []

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
        if resp.status_code != 200: return []

        data = resp.json()
        articulos = data.get('articles', [])

        noticias = []
        for art in articulos:
            titulo = art.get('title', '').strip()
            if not titulo or '[Removed]' in titulo: continue

            # FIX 3: Filtrar noticias que no sean sobre anime
            titulo_lower = titulo.lower()
            desc_lower = (art.get('description', '') or '').lower()
            if not any(p in titulo_lower or p in desc_lower for p in ['anime', 'manga', 'otaku', 'animation', 'animación']):
                log(f"🚫 Noticia descartada (no anime): {titulo[:50]}", 'debug')
                continue

            noticias.append({
                'titulo': limpiar_texto(titulo),
                'descripcion': limpiar_texto(art.get('description', '')),
                'url': art.get('url'),
                'imagen': art.get('urlToImage'),
                'fuente': extraer_dominio(art.get('url', '')),
                'tipo': 'noticia',
                'puntaje': 50,
                'metadata': {}
            })

        return noticias
    except Exception as e:
        log(f"Error NewsAPI: {e}", 'debug')
        return []

def obtener_noticias_rss(tipo="noticia"):
    feeds = RSS_FEEDS.get(tipo, RSS_FEEDS["noticia"])
    noticias = []

    for feed_url in feeds:
        try:
            log(f"📡 RSS [{tipo}]: {feed_url[:45]}...", 'debug')
            feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
            if not feed or not feed.entries: continue

            for entry in feed.entries[:3]:
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo: continue

                link = entry.get('link', '')
                if not link: continue

                desc = limpiar_texto(entry.get('summary', '') or entry.get('description', ''))

                # FIX 3: Filtrar entradas RSS que no sean sobre anime
                texto_combinado = f"{titulo} {desc}".lower()
                if not any(p in texto_combinado for p in ['anime', 'manga', 'otaku', 'animation', 'animación', 'japanese']):
                    log(f"🚫 RSS descartado (no anime): {titulo[:50]}", 'debug')
                    continue

                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for l in entry.links:
                        if l.get('type', '').startswith('image/'):
                            imagen = l.get('href')
                            break

                tipo_detectado = detectar_tipo(titulo, desc)
                tipo_final = tipo if (tipo == "estreno" or tipo_detectado == "estreno") else tipo

                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': desc,
                    'url': link,
                    'imagen': imagen,
                    'fuente': extraer_dominio(link),
                    'tipo': tipo_final,
                    'puntaje': 50 if any(p in titulo.lower() for p in ['attack on titan', 'demon slayer', 'jujutsu kaisen', 'one piece']) else 30,
                    'metadata': {}
                })
        except Exception as e:
            log(f"Error RSS: {e}", 'debug')
            continue

    return noticias

# =============================================================================
# REDACCIÓN
# =============================================================================

def truncar_texto(texto, max_chars=MAX_CARACTERES_FB):
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars].rsplit(' ', 1)[0] + "..."

def redactar_manual(titulo, contenido, tipo="noticia", fuente="", metadata=None):
    hooks = {
        "personaje": ["🎭 ¡Personaje destacado!", "✨ ¡Conoce a...!", "🔥 ¡Protagonista épico!"],
        "databook": ["📚 ¡Datos oficiales!", "📖 ¡Información confirmada!", "🔍 ¡Detalles revelados!"],
        "curiosidad": ["💡 ¿Sabías que...?", "🤯 ¡Dato curioso!", "🎯 ¡Información secreta!"],
        "estreno": ["🚨 ¡Fechas confirmadas!", "🎉 ¡Estreno anunciado!", "✨ ¡Llega pronto!"],
        "noticia": ["📢 ¡Última hora!", "🔥 ¡Noticia bomba!", "🎌 ¡Anuncio oficial!"]
    }

    ctas = {
        "personaje": ["¿Su personaje favorito? ¡Opinen! 👇", "¿Qué les parece? 👇"],
        "databook": ["¿Qué dato les sorprendió? 👇", "¿Ya sabían esto? 👇"],
        "curiosidad": ["¿Lo sabían? ¡Cuéntenme! 👇", "¿Más curiosidades? 👇"],
        "estreno": ["¿Lo esperan? 👇", "¿Emocionados? 👇"],
        "noticia": ["¿Qué opinan? 👇", "¿Impactados? 👇"]
    }

    hook = random.choice(hooks.get(tipo, hooks["noticia"]))
    cta = random.choice(ctas.get(tipo, ctas["noticia"]))

    oraciones = [s.strip() for s in re.split(r'[.!?]+', contenido) if len(s.strip()) > 20][:4]
    resumen = ". ".join(oraciones) + "." if oraciones else contenido[:250] + "..."

    extra_info = ""
    if metadata:
        if tipo == "personaje" and metadata.get('rol'):
            extra_info = f" Rol: {metadata['rol']}."
        elif tipo == "databook" and metadata.get('episodios'):
            extra_info = f" Episodios: {metadata['episodios']}."
        elif tipo == "curiosidad" and metadata.get('score'):
            extra_info = f" Puntuación: {metadata['score']}/100."

    titulo_limpio = titulo[:70] if len(titulo) > 70 else titulo

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
        f"📰 {resumen}{extra_info}",
        "",
        f"💬 {cta}",
        "",
        hashtags
    ]

    return truncar_texto("\n".join(lineas), MAX_CARACTERES_FB)

def redactar_con_ia(titulo, contenido, tipo="noticia", metadata=None):
    # FIX 3: Prompt más estricto que obliga a mencionar anime/manga explícitamente
    prompt = f"""Crea una publicación de Facebook sobre anime en ESPAÑOL LATINO (tú, no usted).
IMPORTANTE: El tema es EXCLUSIVAMENTE anime/manga. NO menciones celebridades, comida, noticias generales ni ningún tema fuera del mundo del anime.

TÍTULO DEL ANIME/PERSONAJE: {titulo}
CONTENIDO: {contenido[:600]}
TIPO DE POST: {tipo} (personaje de anime / noticia de anime / curiosidad de anime)

Estructura OBLIGATORIA:
{random.choice(["📢", "🔥", "🎌", "✨"])} [Hook llamativo sobre anime]

🎌 [Título corto]

📰 [Resumen 2-3 oraciones con datos concretos del anime/personaje]

💬 [Pregunta para fans de anime]

[3 hashtags de anime]

Máximo 1500 caracteres. El texto DEBE mencionar anime, personaje, o el título específico."""

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
                    texto = data['choices'][0]['message']['content'].strip()
                    # FIX 3: Validar relevancia del texto generado
                    if texto_es_relevante_anime(texto) and len(texto) > 100:
                        return truncar_texto(texto, 1600)
                    elif len(texto) > 100:
                        log("⚠️ Texto IA descartado: no es sobre anime", 'advertencia')
        except Exception as e:
            log(f"Error OpenRouter: {e}", 'debug')

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
                texto = response.text.strip()
                # FIX 3: Validar relevancia del texto generado
                if texto_es_relevante_anime(texto) and len(texto) > 100:
                    return truncar_texto(texto, 1600)
                elif len(texto) > 100:
                    log("⚠️ Texto IA descartado: no es sobre anime", 'advertencia')
        except Exception as e:
            log(f"Error Gemini: {e}", 'debug')

    return None

# =============================================================================
# PROCESAMIENTO DE IMÁGENES
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
        log(f"Error extrayendo web: {e}", 'debug')
        return None, None

def descargar_imagen(url):
    """
    FIX 1: Se relajan los filtros de proporción para aceptar retratos verticales de MAL.
    Las imágenes de personajes de MyAnimeList son típicamente retratos (más altas que anchas),
    el filtro original h/w > 3 las rechazaba. Ahora se acepta hasta 4:1 de alto.
    """
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

        # FIX 1: Antes era w < 400 or h < 300 or w/h > 3 or h/w > 3
        # Las imágenes de MAL son ~225x350px (retratos pequeños). Se relaja el mínimo
        # y se amplía la tolerancia de proporción vertical a 5:1
        if w < 200 or h < 200:
            log(f"🖼️ Imagen demasiado pequeña ({w}x{h}), descartando", 'debug')
            return None
        if w / h > 4:
            log(f"🖼️ Imagen demasiado ancha ({w}x{h}), descartando", 'debug')
            return None
        # Permitir retratos verticales (h/w hasta 5:1) — típico en MAL
        if h / w > 5:
            log(f"🖼️ Imagen demasiado alta ({w}x{h}), descartando", 'debug')
            return None

        if img.mode in ('RGBA', 'P'): img = img.convert('RGB')

        # FIX 1: Para retratos pequeños de MAL, ampliar en lugar de reducir
        # Asegurar que la imagen publicada tenga al menos 600px en el lado mayor
        min_dimension = 600
        if max(w, h) < min_dimension:
            factor = min_dimension / max(w, h)
            new_w = int(w * factor)
            new_h = int(h * factor)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            log(f"🖼️ Imagen ampliada de {w}x{h} a {new_w}x{new_h}", 'debug')

        img.thumbnail((1200, 1200))

        path = f'/tmp/anime_{generar_hash(url)[:8]}.jpg'
        img.save(path, 'JPEG', quality=85)

        if os.path.getsize(path) < 5000:  # FIX 1: Reducido de 10KB a 5KB para imágenes pequeñas
            os.remove(path)
            return None
        return path
    except Exception as e:
        log(f"Error descargando imagen: {e}", 'debug')
        return None

def crear_imagen_default(titulo, tipo="noticia"):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        colores = {
            "personaje": ("#1a1a2e", "#e94560"),
            "databook": ("#16213e", "#e94560"),
            "curiosidad": ("#0f0f23", "#ff006e"),
            "estreno": ("#1a1a2e", "#f39c12"),
            "noticia": ("#0f0f23", "#ff006e")
        }

        bg_color, accent = colores.get(tipo, colores["noticia"])

        img = Image.new('RGB', (1200, 630), color=bg_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (1200, 8)], fill=accent)
        draw.rectangle([(0, 622), (1200, 630)], fill=accent)

        emojis = {"personaje": "🎭", "databook": "📚", "curiosidad": "💡", "estreno": "🚨", "noticia": "📢"}
        emoji = emojis.get(tipo, "🎌")

        fonts_to_try = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
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

        draw.text((60, 550), f"{emoji} {tipo.upper()} | Anime Inteligente", font=font_sub, fill=accent)
        draw.text((60, 590), "🎌 Contenido variado para otakus", font=font_sub, fill='#a0a0a0')

        path = f'/tmp/anime_{tipo}_{generar_hash(titulo)[:8]}.jpg'
        img.save(path, 'JPEG', quality=90)
        return path
    except Exception as e:
        log(f"Error creando imagen: {e}", 'error')
        return None

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {
        'urls': [],
        'urls_normalizadas': [],
        'hashes_titulos': [],
        'fingerprints': [],
        'titulos': [],
        'timestamps': [],
        'tipos_publicados': {},
        'estadisticas': {'total': 0, 'hoy': 0, 'fecha': None}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h: h[k] = default[k]
    return h

def guardar_historial(historial, url, titulo, tipo, contenido=""):
    anti_dup = AntiDuplicado(historial)
    anti_dup.registrar(titulo, url, contenido)

    historial['urls'] = list(anti_dup.cache_urls)[-200:]
    historial['urls_normalizadas'] = list(anti_dup.cache_urls)[-200:]
    historial['hashes_titulos'] = list(anti_dup.cache_hashes)[-200:]
    historial['fingerprints'] = list(anti_dup.cache_fingerprints)[-200:]
    historial['titulos'] = list(anti_dup.cache_titulos)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['timestamps'] = historial['timestamps'][-200:]

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
    tipos_count = historial.get('tipos_publicados', {})
    total = sum(tipos_count.values()) if tipos_count else 0

    if total == 0:
        return random.choice(TIPOS_CONTENIDO)

    scores = {}
    for tipo in TIPOS_CONTENIDO:
        actual = tipos_count.get(tipo, 0)
        esperado = total * PESOS_TIPO.get(tipo, 0.2)
        scores[tipo] = esperado - actual

    if random.random() < 0.7:
        return max(scores, key=scores.get)
    else:
        return random.choice(TIPOS_CONTENIDO)

# =============================================================================
# FACEBOOK
# =============================================================================

def publicar_facebook(mensaje, imagen_path):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False

    mensaje_seguro = truncar_texto(mensaje, MAX_CARACTERES_FB)
    log(f"📝 Caracteres: {len(mensaje_seguro)}/{MAX_CARACTERES_FB}", 'info')

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
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }

            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()

        if 'id' in result or 'post_id' in result:
            post_id = result.get('post_id', result.get('id'))
            log(f"✅ Publicado: {post_id}", 'exito')
            return True

        error = result.get('error', {})
        log(f"❌ Error FB ({error.get('code')}): {error.get('message', 'Unknown')}", 'error')
        return False

    except Exception as e:
        log(f"❌ Excepción: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def obtener_contenido_por_tipo(tipo, historial):
    anti_dup = AntiDuplicado(historial)
    candidatos = []

    log(f"🔍 Buscando contenido tipo: {tipo}", 'info')

    if tipo == "personaje":
        for _ in range(3):
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
        noticias = obtener_noticias_rss(tipo)
        noticias.extend(obtener_noticias_newsapi())

        for n in noticias:
            if not anti_dup.es_duplicado(n['titulo'], n['url'], n['descripcion']):
                candidatos.append(n)

        candidatos.sort(key=lambda x: x['puntaje'], reverse=True)

    return candidatos[:5]

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

    tipos_count = historial.get('tipos_publicados', {})
    if tipos_count:
        distribucion = " | ".join([f"{k}:{v}" for k, v in sorted(tipos_count.items())])
        log(f"📈 Distribución: {distribucion}", 'info')

    tipo_objetivo = seleccionar_tipo(historial)
    log(f"🎯 Tipo seleccionado: {tipo_objetivo}", 'info')

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

    seleccionada = None
    mensaje_final = None

    for candidato in candidatos:
        log(f"✍️ Generando texto ({AI_SERVICE or 'manual'})...", 'info')

        contenido_extra = candidato['descripcion']
        if candidato.get('url') and candidato['fuente'] not in ['MyAnimeList (Jikan)', 'AniList', 'MyAnimeList Databook']:
            web_content, _ = extraer_web(candidato['url'])
            if web_content and len(web_content) > 50:
                contenido_extra = web_content

        texto_ia = redactar_con_ia(candidato['titulo'], contenido_extra, candidato['tipo'], candidato.get('metadata'))

        if texto_ia:
            mensaje_final = texto_ia
            log("✅ Texto IA generado", 'exito')
        else:
            mensaje_final = redactar_manual(
                candidato['titulo'],
                contenido_extra,
                candidato['tipo'],
                candidato['fuente'],
                candidato.get('metadata')
            )
            log("✅ Texto manual generado", 'info')

        # FIX 3: Validar relevancia del texto manual también
        if not texto_es_relevante_anime(mensaje_final):
            log("⚠️ Texto irrelevante, probando siguiente candidato", 'advertencia')
            continue

        if mensaje_final and len(mensaje_final) > 50:
            seleccionada = candidato
            break
        else:
            log("⚠️ Texto inválido, probando siguiente candidato", 'advertencia')

    if not seleccionada or not mensaje_final:
        log("❌ No se pudo generar contenido válido", 'error')
        return False

    mensaje_final = truncar_texto(mensaje_final, MAX_CARACTERES_FB)

    print(f"\n{'='*60}")
    print(f"📱 PREVIEW ({seleccionada['tipo'].upper()}):")
    print(f"{'='*60}")
    print(mensaje_final)
    print(f"{'='*60}")
    print(f"📊 {len(mensaje_final)} chars | Fuente: {seleccionada['fuente']}")

    log("🖼️ Procesando imagen...", 'info')
    img_path = descargar_imagen(seleccionada.get('imagen')) if seleccionada.get('imagen') else None
    if not img_path:
        log("⚠️ Imagen original no válida, usando imagen default", 'advertencia')
        img_path = crear_imagen_default(seleccionada['titulo'], seleccionada['tipo'])

    if not img_path:
        log("❌ No se pudo crear imagen", 'error')
        return False

    # FIX 2: Registrar en historial ANTES de publicar para evitar duplicados
    # si el bot se interrumpe y se vuelve a ejecutar inmediatamente
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

    exito = publicar_facebook(mensaje_final, img_path)

    try:
        if os.path.exists(img_path): os.remove(img_path)
    except: pass

    if exito:
        log(f"✅ Total histórico: {historial['estadisticas']['total']}", 'exito')
        return True
    else:
        log("❌ Falló publicación en Facebook (contenido ya registrado en historial)", 'error')
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
