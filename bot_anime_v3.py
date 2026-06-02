#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Anime V4 - Nuevo Anime
MEJORAS V4:
  1. Solo publica posts CON imagen válida de APIs (MAL/AniList/Kitsu)
  2. Imagen forzada a 1200x630px horizontal para Facebook
  3. Marca de agua "Nuevo Anime" con logo en esquina
  4. Metadatos EXIF en imágenes (SEO, copyright, keywords)
  5. Todo el contenido en español latino (traducción automática con IA)
  6. Filtro estricto: sin personas reales, deportes ni política
  7. Anti-duplicado persistente via GitHub Cache
  8. Hashtags y SEO optimizados por categoría
  9. Soporte 1-3 imágenes por post (carrusel Facebook)
  10. Fuentes: MAL (Jikan), AniList, Kitsu — sin NewsAPI
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import time
import struct
import zlib
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from urllib.parse import urlparse, quote
from collections import deque
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

FB_PAGE_ID        = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN   = os.getenv('FB_ACCESS_TOKEN')
GEMINI_API_KEY    = os.getenv('GEMINI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', os.path.join(BASE_DIR, 'data', 'historial_anime_v4.json'))
ESTADO_PATH    = os.getenv('ESTADO_PATH',    os.path.join(BASE_DIR, 'data', 'estado_bot_anime_v4.json'))
LOGO_PATH      = os.getenv('LOGO_PATH',      os.path.join(BASE_DIR, 'assets', 'nuevo_anime_logo.png'))

# Publicación
TIEMPO_ENTRE_PUBLICACIONES = 90   # minutos mínimos entre posts
MAX_PUBLICACIONES_DIA      = 12
UMBRAL_SIMILITUD_TITULO    = 0.85
MAX_CARACTERES_FB          = 1800

# Imagen
IMG_WIDTH  = 1200
IMG_HEIGHT = 630
IMG_RATIO  = IMG_WIDTH / IMG_HEIGHT   # 1.905

# Tipos y pesos
TIPOS_CONTENIDO = ["noticia", "personaje", "curiosidad", "databook", "estreno"]
PESOS_TIPO = {"noticia": 0.30, "personaje": 0.25, "curiosidad": 0.20, "databook": 0.15, "estreno": 0.10}

ANIME_POPULARES = [
    "One Piece", "Naruto", "Dragon Ball", "Attack on Titan", "Demon Slayer",
    "Jujutsu Kaisen", "My Hero Academia", "Spy x Family", "Chainsaw Man",
    "Bleach", "Hunter x Hunter", "Evangelion", "Death Note", "Fullmetal Alchemist",
    "One Punch Man", "Tokyo Ghoul", "Sword Art Online", "Steins;Gate",
    "Cowboy Bebop", "Code Geass", "Gintama", "Fairy Tail", "Black Clover",
    "Dr. Stone", "Fire Force", "Kaguya-sama", "Re:Zero", "Overlord",
    "Vinland Saga", "Frieren", "Oshi no Ko", "Blue Lock", "Haikyuu"
]

# Palabras que indican contenido NO anime (filtro de personas reales)
PALABRAS_BLOQUEADAS = [
    "tenis", "fútbol", "futbol", "baloncesto", "nba", "fifa", "liga",
    "presidente", "gobierno", "político", "elecciones", "congreso",
    "actor", "actriz", "cantante", "celebrity", "famoso",
    "receta", "cocina", "restaurante", "chef",
    "sinner", "messi", "ronaldo", "lebron", "djokovic",
    "covid", "pandemia", "vacuna", "hospital",
    "bolsa", "acciones", "crypto", "bitcoin", "dólar"
]

PALABRAS_CLAVE_ANIME = [
    "anime", "manga", "personaje", "shonen", "seinen", "shoujo", "otaku",
    "one piece", "naruto", "bleach", "dragon ball", "jujutsu", "demon slayer",
    "attack on titan", "my hero academia", "chainsaw", "evangelion", "death note",
    "fullmetal", "cowboy bebop", "hunter x hunter", "sword art", "re:zero",
    "temporada", "episodio", "opening", "ending", "seiyuu", "estudio",
    "shueisha", "mappa", "ufotable", "madhouse", "crunchyroll",
    "protagonista", "antagonista", "bankai", "jutsu", "quirk", "titan",
    "shinigami", "nakama", "akatsuki", "myanimelist", "anilist", "kitsu",
    "airing", "simulcast", "ova", "ova", "película anime", "light novel"
]

# Hashtags SEO por categoría
HASHTAGS = {
    "personaje": "#Anime #Personajes #OtakuLife #AnimeFan #MangaArt #Otaku #AnimeEspañol #NuevoAnime #AnimeLatino #Waifu",
    "databook":  "#Anime #Databook #OtakuFacts #AnimeData #MangaFacts #Otaku #AnimeEspañol #NuevoAnime #AnimeInfo",
    "curiosidad": "#Anime #Curiosidades #OtakuTrivia #AnimeFacts #MangaCuriosidades #Otaku #AnimeEspañol #NuevoAnime",
    "estreno":   "#Anime #Estreno #NuevoAnime #AnimeTemporal #MangaNuevo #Otaku #AnimeEspañol #AnimeLatino #Simulcast",
    "noticia":   "#Anime #Noticias #OtakuNews #AnimeNews #MangaNews #Otaku #AnimeEspañol #NuevoAnime #AnimeLatino"
}

RSS_FEEDS = {
    "noticia": [
        'https://somoskudasai.com/feed/',
        'https://www.animenewsnetwork.com/all/rss.xml',
        'https://myanimelist.net/rss/news.xml',
        'https://honeysanime.com/feed/',
        'https://animecorner.me/feed',
    ],
    "estreno": [
        'https://anitrendz.net/news/feed',
    ]
}

# =============================================================================
# INICIALIZAR IA
# =============================================================================

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
        client_gemini = genai.Client(api_key=GEMINI_API_KEY)
        test = client_gemini.models.generate_content(model="gemini-2.0-flash", contents="hola")
        AI_SERVICE = "gemini"
        print("✅ Gemini conectado")
    except Exception as e:
        print(f"⚠️ Gemini no disponible: {e}")

if not AI_SERVICE:
    print("⚠️ Sin servicio de IA")

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
        log(f"Error guardando JSON: {e}", 'error')
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

def truncar_texto(texto, max_chars=MAX_CARACTERES_FB):
    if len(texto) <= max_chars: return texto
    return texto[:max_chars].rsplit(' ', 1)[0] + "..."

def extraer_dominio(url):
    try:
        parsed = urlparse(url)
        parts = parsed.netloc.lower().split('.')
        return '.'.join(parts[-2:]) if len(parts) > 2 else parsed.netloc.lower()
    except: return "anime"

# =============================================================================
# FILTROS DE CONTENIDO
# =============================================================================

def contiene_persona_real(titulo, descripcion=""):
    texto = f"{titulo} {descripcion}".lower()
    return any(palabra in texto for palabra in PALABRAS_BLOQUEADAS)

def es_contenido_anime(titulo, descripcion=""):
    texto = f"{titulo} {descripcion}".lower()
    if contiene_persona_real(titulo, descripcion):
        log(f"🚫 Bloqueado (persona real/off-topic): {titulo[:60]}", 'debug')
        return False
    coincidencias = sum(1 for p in PALABRAS_CLAVE_ANIME if p in texto)
    if coincidencias < 1:
        log(f"🚫 Bloqueado (no anime, solo {coincidencias} coincidencias): {titulo[:60]}", 'debug')
        return False
    return True

# =============================================================================
# TRADUCCIÓN Y ADAPTACIÓN AL ESPAÑOL
# =============================================================================

def detectar_idioma(texto):
    """Retorna True si el texto está en inglés."""
    palabras_ingles = ['the ', 'and ', ' for ', ' with ', ' has ', ' have ', ' are ', ' was ', ' were ', ' this ', ' that ', ' from ', ' been ', ' will ', ' they ', ' their ']
    texto_lower = f" {texto.lower()} "
    hits = sum(1 for p in palabras_ingles if p in texto_lower)
    return hits >= 3

def traducir_y_adaptar(titulo, contenido, tipo="noticia"):
    """
    Detecta idioma y traduce al español latino con IA.
    Retorna (None, None) si el texto está en inglés y no hay IA disponible
    para forzar el descarte del contenido.
    """
    if not detectar_idioma(f"{titulo} {contenido}"):
        return titulo, contenido  # Ya está en español

    log("🌐 Contenido en inglés — traduciendo...", 'info')

    if not AI_SERVICE:
        log("⛔ Sin IA disponible — descartando contenido en inglés", 'advertencia')
        return None, None  # Señal de descarte

    prompt = f"""Traduce y adapta este contenido de anime al ESPAÑOL LATINO natural (tú, no vos ni usted).
Mantén nombres propios de anime/personajes en su forma original (ej: "My Hero Academia", "Deku", "Bakugo").
Devuelve SOLO un JSON con este formato exacto, sin backticks ni texto extra:
{{"titulo": "...", "contenido": "..."}}

TÍTULO: {titulo}
CONTENIDO: {contenido[:800]}"""

    resultado = llamar_ia(prompt, max_tokens=700)
    if resultado:
        try:
            limpio = re.sub(r'```json|```', '', resultado).strip()
            # Buscar el JSON aunque haya texto antes/después
            match = re.search(r'\{{.*\}}', limpio, re.DOTALL)
            if match:
                data = json.loads(match.group())
                t = data.get('titulo', '').strip()
                c = data.get('contenido', '').strip()
                if t and c and len(c) > 30:
                    log(f"✅ Traducido: {t[:60]}", 'debug')
                    return t, c
        except Exception as e:
            log(f"Error parseando traducción: {e}", 'debug')

    log("⚠️ Fallo en traducción — descartando contenido en inglés", 'advertencia')
    return None, None  # Descartar si no se pudo traducir

def llamar_ia(prompt, max_tokens=500):
    """Llama a la IA disponible y devuelve el texto generado."""
    if AI_SERVICE == "openrouter":
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com",
                    "X-Title": "Nuevo Anime Bot"
                },
                json={
                    "model": "google/gemini-2.0-flash-exp:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('choices'):
                    return data['choices'][0]['message']['content'].strip()
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
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=max_tokens)
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            log(f"Error Gemini: {e}", 'debug')

    return None

# =============================================================================
# ANTI-DUPLICADO
# =============================================================================

class AntiDuplicado:
    def __init__(self, historial):
        self.cache_hashes = set(historial.get('hashes_titulos', []))
        self.cache_urls   = set(historial.get('urls_normalizadas', []))
        self.cache_titulos = deque(historial.get('titulos', [])[-50:], maxlen=50)
        self.cache_fingerprints = set(historial.get('fingerprints', []))

    def generar_fingerprint(self, titulo, contenido):
        texto = f"{titulo} {contenido}".lower()
        texto = re.sub(r'[^\w\s]', '', texto)
        palabras = sorted(set(texto.split()))
        return hashlib.sha256(' '.join(palabras[:20]).encode()).hexdigest()[:16]

    def es_duplicado(self, titulo, url, contenido=""):
        url_norm = normalizar_url(url)
        if url_norm and url_norm in self.cache_urls:
            log(f"🔴 Duplicado por URL", 'debug')
            return True
        hash_titulo = generar_hash(titulo)
        if hash_titulo in self.cache_hashes:
            log(f"🔴 Duplicado por hash", 'debug')
            return True
        if contenido:
            fp = self.generar_fingerprint(titulo, contenido)
            if fp in self.cache_fingerprints:
                log(f"🔴 Duplicado por fingerprint", 'debug')
                return True
        for titulo_previo in self.cache_titulos:
            if calcular_similitud(titulo, titulo_previo) >= UMBRAL_SIMILITUD_TITULO:
                log(f"🔴 Duplicado por similitud", 'debug')
                return True
        return False

    def registrar(self, titulo, url, contenido=""):
        self.cache_hashes.add(generar_hash(titulo))
        if url: self.cache_urls.add(normalizar_url(url))
        self.cache_titulos.append(titulo)
        if contenido:
            self.cache_fingerprints.add(self.generar_fingerprint(titulo, contenido))

# =============================================================================
# OBTENCIÓN DE IMÁGENES
# =============================================================================

def deduplicar_imagenes(urls):
    """Elimina URLs de imagen duplicadas o muy similares."""
    vistas = set()
    resultado = []
    for url in urls:
        if not url: continue
        # Normalizar URL para comparar (quitar parámetros de tamaño)
        url_norm = re.sub(r'[?&](width|height|w|h|size|quality|q)=\d+', '', url.lower().strip())
        url_norm = re.sub(r'/(small|medium|large|original|thumb)/', '/X/', url_norm)
        if url_norm not in vistas:
            vistas.add(url_norm)
            resultado.append(url)
    return resultado

def descargar_imagen_url(url):
    """Descarga una imagen desde URL y retorna objeto PIL o None."""
    if not url: return None
    # Bloquear dominios no deseados
    for bad in ['google.com', 'gstatic.com', 'facebook.com', 'twitter.com', 'logo', 'favicon', 'icon']:
        if bad in url.lower(): return None
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20, stream=True)
        content_type = r.headers.get('content-type', '')
        if 'image' not in content_type: return None
        img = Image.open(BytesIO(r.content))
        w, h = img.size
        # Rechazar imágenes muy pequeñas
        if w < 200 or h < 200:
            log(f"🖼️ Imagen muy pequeña ({w}x{h}), descartando", 'debug')
            return None
        # Rechazar proporciones extremas
        if w / h > 5 or h / w > 5:
            log(f"🖼️ Proporción extrema ({w}x{h}), descartando", 'debug')
            return None
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        log(f"🖼️ Imagen descargada: {w}x{h}", 'debug')
        return img
    except Exception as e:
        log(f"Error descargando imagen: {e}", 'debug')
        return None

def preparar_imagen_facebook(img_pil, titulo="", tipo="noticia", keywords=None):
    """
    Convierte cualquier imagen PIL a 1200x630px con:
    - Recorte inteligente centrado
    - Marca de agua "Nuevo Anime" con logo
    - Metadatos EXIF/PNG
    Retorna path del archivo temporal.
    """
    if img_pil is None: return None

    w, h = img_pil.size
    ratio_actual = w / h
    ratio_target = IMG_WIDTH / IMG_HEIGHT  # 1.905

    # --- Recorte inteligente a 1200x630 ---
    if ratio_actual > ratio_target:
        # Imagen muy ancha → recortar lados
        new_w = int(h * ratio_target)
        left = (w - new_w) // 2
        img_pil = img_pil.crop((left, 0, left + new_w, h))
    elif ratio_actual < ratio_target:
        # Imagen muy alta (retrato) → fondo difuminado + imagen centrada
        canvas = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), (15, 15, 30))
        # Fondo: imagen estirada y muy difuminada
        bg = img_pil.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
        # Oscurecer fondo
        overlay = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), (0, 0, 0))
        bg = Image.blend(bg, overlay, alpha=0.5)
        canvas.paste(bg, (0, 0))
        # Imagen original centrada, ajustada al alto
        factor = IMG_HEIGHT / h
        new_w_img = int(w * factor)
        new_h_img = IMG_HEIGHT
        img_resized = img_pil.resize((new_w_img, new_h_img), Image.LANCZOS)
        x_offset = (IMG_WIDTH - new_w_img) // 2
        canvas.paste(img_resized, (x_offset, 0))
        img_pil = canvas
    
    # Resize final exacto
    img_pil = img_pil.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)

    # --- Marca de agua ---
    img_pil = agregar_marca_agua(img_pil)

    # --- Guardar con metadatos ---
    path = f'/tmp/nuevo_anime_{generar_hash(titulo)[:8]}.jpg'
    
    # Metadatos EXIF via comentario JPEG (compatible universalmente)
    keywords_str = ", ".join(keywords) if keywords else "anime, manga, otaku, nuevo anime"
    
    from PIL import PngImagePlugin
    img_pil.save(path, 'JPEG', quality=90, optimize=True,
                 comment=f"Nuevo Anime | {titulo} | {keywords_str}".encode())

    log(f"🖼️ Imagen preparada: {IMG_WIDTH}x{IMG_HEIGHT} → {path}", 'debug')
    return path

def agregar_marca_agua(img):
    """Agrega marca de agua 'Nuevo Anime' con logo en esquina inferior derecha."""
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Cargar fuente
    font_wm = None
    fonts_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    font_size_wm = max(22, w // 42)
    for fp in fonts_paths:
        try:
            if os.path.exists(fp):
                font_wm = ImageFont.truetype(fp, font_size_wm)
                break
        except: continue
    if not font_wm:
        font_wm = ImageFont.load_default()

    texto_wm = "Nuevo Anime"

    # Calcular posición (esquina inferior derecha)
    bbox = draw.textbbox((0, 0), texto_wm, font=font_wm)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    logo_size = int(font_size_wm * 1.8)
    padding = 12
    total_w = logo_size + 8 + tw + padding * 2
    total_h = max(logo_size, th) + padding * 2

    x = w - total_w - 12
    y = h - total_h - 12

    # Fondo semitransparente
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [x - 4, y - 4, x + total_w + 4, y + total_h + 4],
        radius=8,
        fill=(0, 0, 0, 160)
    )
    img = img.convert('RGBA')
    img = Image.alpha_composite(img, overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

    # Logo pequeño
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert('RGBA')
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            # Hacer circular
            mask = Image.new('L', (logo_size, logo_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, logo_size, logo_size), fill=255)
            logo_rgb = logo.convert('RGB')
            logo_rgb.putalpha(mask)
            img.paste(logo_rgb, (x + padding, y + padding + (total_h - logo_size) // 2), mask)
        except Exception as e:
            log(f"Error logo: {e}", 'debug')

    # Texto "Nuevo Anime"
    text_x = x + padding + logo_size + 8
    text_y = y + padding + (total_h - padding * 2 - th) // 2
    # Sombra
    draw.text((text_x + 1, text_y + 1), texto_wm, font=font_wm, fill=(0, 0, 0, 200))
    # Texto blanco
    draw.text((text_x, text_y), texto_wm, font=font_wm, fill=(255, 255, 255))

    return img

# =============================================================================
# FUENTES DE CONTENIDO — SOLO APIs DE ANIME CON IMAGEN
# =============================================================================

def obtener_personaje_jikan():
    """Obtiene personaje de MyAnimeList via Jikan API con imagen garantizada."""
    try:
        anime = random.choice(ANIME_POPULARES)
        log(f"🎭 Jikan: buscando personaje de {anime}", 'debug')

        search_url = f"https://api.jikan.moe/v4/anime?q={quote(anime)}&limit=1"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200: return None

        data = resp.json()
        if not data.get('data'): return None

        anime_id    = data['data'][0]['mal_id']
        anime_title = data['data'][0]['title']

        time.sleep(0.5)  # Rate limit Jikan
        chars_url = f"https://api.jikan.moe/v4/anime/{anime_id}/characters"
        resp = requests.get(chars_url, timeout=10)
        if resp.status_code != 200: return None

        chars_data = resp.json()
        if not chars_data.get('data'): return None

        # Filtrar personajes con imagen
        personajes_con_img = []
        for c in chars_data['data'][:15]:
            img_url = c['character'].get('images', {}).get('jpg', {}).get('large_image_url') or \
                      c['character'].get('images', {}).get('jpg', {}).get('image_url')
            if img_url and 'questionmark' not in img_url:
                personajes_con_img.append(c)

        if not personajes_con_img: return None

        personaje   = random.choice(personajes_con_img[:8])
        char_info   = personaje['character']
        char_id     = char_info['mal_id']
        imagen_url  = char_info.get('images', {}).get('jpg', {}).get('large_image_url') or \
                      char_info.get('images', {}).get('jpg', {}).get('image_url')

        time.sleep(0.5)
        detail_url = f"https://api.jikan.moe/v4/characters/{char_id}/full"
        resp = requests.get(detail_url, timeout=10)
        bio = ""
        if resp.status_code == 200:
            detail_data = resp.json().get('data', {})
            bio = detail_data.get('about', '')[:600]
            large = detail_data.get('images', {}).get('jpg', {}).get('large_image_url')
            if large and 'questionmark' not in large:
                imagen_url = large

        titulo = f"{char_info['name']} de {anime_title}"
        desc   = bio or f"Personaje de {anime_title} en MyAnimeList."

        # Traducir si está en inglés
        titulo, desc = traducir_y_adaptar(titulo, desc, "personaje")
        if titulo is None:
            log("⛔ Jikan personaje descartado (inglés sin IA)", "debug")
            return None

        return {
            'titulo': titulo,
            'descripcion': desc,
            'url': char_info.get('url', f"https://myanimelist.net/character/{char_id}"),
            'imagen': imagen_url,
            'imagenes': [imagen_url] if imagen_url else [],
            'fuente': 'MyAnimeList',
            'tipo': 'personaje',
            'puntaje': 85,
            'keywords': ['anime', char_info['name'], anime_title, 'personaje', 'otaku', 'manga'],
            'metadata': {
                'anime': anime_title,
                'rol': personaje.get('role', 'Desconocido'),
                'favoritos': char_info.get('favorites', 0)
            }
        }
    except Exception as e:
        log(f"Error Jikan personaje: {e}", 'debug')
        return None

def obtener_anime_jikan():
    """Obtiene info de un anime de MAL con imagen de portada."""
    try:
        anime = random.choice(ANIME_POPULARES)
        log(f"📺 Jikan: buscando anime {anime}", 'debug')

        search_url = f"https://api.jikan.moe/v4/anime?q={quote(anime)}&limit=3"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200: return None

        data = resp.json()
        if not data.get('data'): return None

        # Elegir uno al azar de los resultados
        anime_data = random.choice(data['data'])
        imagen_url = anime_data.get('images', {}).get('jpg', {}).get('large_image_url') or \
                     anime_data.get('images', {}).get('jpg', {}).get('image_url')

        if not imagen_url or 'questionmark' in imagen_url: return None

        titulo = anime_data.get('title_spanish') or anime_data.get('title') or ""
        sinopsis = anime_data.get('synopsis', '')[:600]
        score = anime_data.get('score', 'N/A')
        episodios = anime_data.get('episodes', 'N/A')

        titulo, sinopsis = traducir_y_adaptar(titulo, sinopsis, "databook")
        if titulo is None:
            log("⛔ Jikan databook descartado (inglés sin IA)", "debug")
            return None

        desc = f"{sinopsis} Puntuación: {score}/10. Episodios: {episodios}."

        # Imágenes adicionales del mismo anime (personajes)
        imagenes_extra = []
        time.sleep(0.5)
        chars_url = f"https://api.jikan.moe/v4/anime/{anime_data['mal_id']}/characters"
        resp2 = requests.get(chars_url, timeout=10)
        if resp2.status_code == 200:
            chars = resp2.json().get('data', [])
            for c in chars[:8]:
                img = c['character'].get('images', {}).get('jpg', {}).get('large_image_url')
                if img and 'questionmark' not in img:
                    imagenes_extra.append(img)
                if len(imagenes_extra) >= 2: break
        imagenes = deduplicar_imagenes([imagen_url] + imagenes_extra)[:3]

        return {
            'titulo': f"📊 {titulo}",
            'descripcion': desc,
            'url': anime_data.get('url', ''),
            'imagen': imagen_url,
            'imagenes': imagenes[:3],
            'fuente': 'MyAnimeList',
            'tipo': 'databook',
            'puntaje': 90,
            'keywords': ['anime', titulo, 'databook', 'myanimelist', 'otaku', str(score)],
            'metadata': {
                'score': score,
                'episodios': episodios,
                'rating': anime_data.get('rating', ''),
                'studio': (anime_data.get('studios') or [{}])[0].get('name', '') if anime_data.get('studios') else ''
            }
        }
    except Exception as e:
        log(f"Error Jikan anime: {e}", 'debug')
        return None

def obtener_curiosidad_anilist():
    """Obtiene anime con imagen de AniList."""
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
                    coverImage { large extraLarge }
                    bannerImage
                }
            }
        }
        """
        variables = {"page": random.randint(1, 15), "perPage": 10}
        resp = requests.post("https://graphql.anilist.co",
                             json={"query": query, "variables": variables}, timeout=10)
        if resp.status_code != 200: return None

        medias = resp.json().get('data', {}).get('Page', {}).get('media', [])
        if not medias: return None

        # Filtrar los que tienen imagen
        con_imagen = [m for m in medias if m.get('coverImage', {}).get('extraLarge') or m.get('coverImage', {}).get('large')]
        if not con_imagen: return None

        anime = random.choice(con_imagen)
        titulo = anime['title'].get('english') or anime['title'].get('romaji') or anime['title'].get('native', '')
        imagen_url = anime.get('coverImage', {}).get('extraLarge') or anime.get('coverImage', {}).get('large')
        banner_url = anime.get('bannerImage')

        desc = limpiar_texto(anime.get('description', ''))[:500]
        studio = (anime.get('studios', {}).get('nodes') or [{}])[0].get('name', 'Estudio desconocido')

        titulo, desc = traducir_y_adaptar(titulo, desc, "curiosidad")
        if titulo is None:
            log("⛔ AniList descartado (inglés sin IA)", "debug")
            return None

        imagenes_raw = [imagen_url, banner_url]
        imagenes = deduplicar_imagenes([i for i in imagenes_raw if i])[:2]

        return {
            'titulo': f"✨ Curiosidad: {titulo}",
            'descripcion': f"{desc} Producido por {studio}. Puntuación: {anime.get('averageScore', 'N/A')}/100.",
            'url': f"https://anilist.co/anime/{anime['id']}",
            'imagen': imagen_url,
            'imagenes': imagenes[:2],
            'fuente': 'AniList',
            'tipo': 'curiosidad',
            'puntaje': min(anime.get('popularity', 0) / 1000, 100),
            'keywords': ['anime', titulo, 'curiosidad', 'anilist', 'otaku', studio],
            'metadata': {
                'score': anime.get('averageScore'),
                'episodios': anime.get('episodes'),
                'temporada': f"{anime.get('season', '')} {anime.get('seasonYear', '')}"
            }
        }
    except Exception as e:
        log(f"Error AniList: {e}", 'debug')
        return None

def obtener_anime_kitsu():
    """Obtiene anime trending de Kitsu con imagen HD."""
    try:
        log("🦊 Kitsu: buscando anime trending", 'debug')
        # Trending anime
        offset = random.randint(0, 40)
        url = f"https://kitsu.io/api/edge/trending/anime?page[limit]=10&page[offset]={offset}"
        headers = {'Accept': 'application/vnd.api+json'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            # Fallback: anime populares
            url = "https://kitsu.io/api/edge/anime?sort=-popularityRank&page[limit]=10"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200: return None

        data = resp.json().get('data', [])
        if not data: return None

        # Filtrar los que tienen imagen
        con_imagen = []
        for item in data:
            attrs = item.get('attributes', {})
            img = attrs.get('posterImage', {}).get('large') or attrs.get('posterImage', {}).get('medium')
            if img:
                con_imagen.append((item, img))

        if not con_imagen: return None

        item, imagen_url = random.choice(con_imagen)
        attrs = item.get('attributes', {})

        titulo = attrs.get('titles', {}).get('en') or \
                 attrs.get('titles', {}).get('en_jp') or \
                 attrs.get('canonicalTitle', '')

        sinopsis = attrs.get('synopsis', '')[:500]
        rating = attrs.get('averageRating', 'N/A')
        episodios = attrs.get('episodeCount', 'N/A')

        titulo, sinopsis = traducir_y_adaptar(titulo, sinopsis, "noticia")
        if titulo is None:
            log("⛔ Kitsu descartado (inglés sin IA)", "debug")
            return None

        cover = attrs.get('coverImage', {}) or {}
        imagenes_raw = [imagen_url, cover.get('original'), cover.get('large'), cover.get('small')]
        imagenes = deduplicar_imagenes([i for i in imagenes_raw if i])[:2]

        return {
            'titulo': f"🦊 {titulo}",
            'descripcion': f"{sinopsis} Rating: {rating}/100. Episodios: {episodios}.",
            'url': f"https://kitsu.io/anime/{item.get('id', '')}",
            'imagen': imagen_url,
            'imagenes': imagenes[:2],
            'fuente': 'Kitsu',
            'tipo': 'noticia',
            'puntaje': 75,
            'keywords': ['anime', titulo, 'kitsu', 'otaku', 'trending', 'manga'],
            'metadata': {
                'rating': rating,
                'episodios': episodios,
                'estado': attrs.get('status', '')
            }
        }
    except Exception as e:
        log(f"Error Kitsu: {e}", 'debug')
        return None

def obtener_noticias_rss(tipo="noticia"):
    """Obtiene noticias de RSS feeds. Requiere que tengan imagen."""
    feeds = RSS_FEEDS.get(tipo, RSS_FEEDS["noticia"])
    noticias = []

    for feed_url in feeds:
        try:
            log(f"📡 RSS: {feed_url[:50]}", 'debug')
            feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
            if not feed or not feed.entries: continue

            for entry in feed.entries[:4]:
                titulo = entry.get('title', '').strip()
                if not titulo: continue

                link = entry.get('link', '')
                if not link: continue

                desc = limpiar_texto(entry.get('summary', '') or entry.get('description', ''))

                # Filtrar personas reales y contenido off-topic
                if not es_contenido_anime(titulo, desc): continue

                # Buscar imagen en la entrada RSS
                imagen = None
                if hasattr(entry, 'media_content') and entry.media_content:
                    imagen = entry.media_content[0].get('url')
                if not imagen and hasattr(entry, 'links'):
                    for l in entry.links:
                        if l.get('type', '').startswith('image/'):
                            imagen = l.get('href')
                            break
                # Buscar en enclosures
                if not imagen and hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if 'image' in enc.get('type', ''):
                            imagen = enc.get('href') or enc.get('url')
                            break
                # Buscar en tags media
                if not imagen:
                    content = entry.get('content', [{}])
                    if content:
                        soup = BeautifulSoup(content[0].get('value', ''), 'html.parser')
                        img_tag = soup.find('img')
                        if img_tag:
                            imagen = img_tag.get('src')

                # Si no hay imagen, intentar extraer de la web
                if not imagen:
                    try:
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        r = requests.get(link, headers=headers, timeout=8)
                        soup = BeautifulSoup(r.content, 'html.parser')
                        for meta in ['og:image', 'twitter:image']:
                            tag = soup.find('meta', property=meta) or soup.find('meta', attrs={'name': meta})
                            if tag and tag.get('content'):
                                imagen = tag['content'].strip()
                                break
                    except: pass

                # Sin imagen → descartar
                if not imagen:
                    log(f"🚫 RSS sin imagen, descartando: {titulo[:50]}", 'debug')
                    continue

                titulo, desc = traducir_y_adaptar(titulo, desc, tipo)
                if titulo is None:
                    log(f"⛔ RSS descartado (inglés sin IA)", "debug")
                    continue

                noticias.append({
                    'titulo': titulo,
                    'descripcion': desc,
                    'url': link,
                    'imagen': imagen,
                    'imagenes': [imagen],
                    'fuente': extraer_dominio(link),
                    'tipo': tipo,
                    'puntaje': 60,
                    'keywords': ['anime', 'manga', 'otaku', 'noticias anime'],
                    'metadata': {}
                })

        except Exception as e:
            log(f"Error RSS {feed_url[:40]}: {e}", 'debug')
            continue

    return noticias

# =============================================================================
# REDACCIÓN CON IA
# =============================================================================

def redactar_post(titulo, contenido, tipo, metadata=None):
    """Genera texto del post en español latino optimizado para Facebook."""

    hooks = {
        "personaje": ["🎭 ¡Personaje épico!", "✨ ¡Conoce a este personaje!", "🔥 ¡Icono del anime!"],
        "databook":  ["📊 ¡Datos oficiales!", "📚 ¡Info confirmada!", "🔍 ¡Detalles revelados!"],
        "curiosidad": ["💡 ¿Sabías que...?", "🤯 ¡Dato curioso!", "🎯 ¡Curiosidad otaku!"],
        "estreno":   ["🚨 ¡Estreno confirmado!", "🎉 ¡Llega pronto!", "✨ ¡Anuncio oficial!"],
        "noticia":   ["📢 ¡Última hora!", "🔥 ¡Breaking news anime!", "🎌 ¡Anuncio oficial!"]
    }

    ctas = {
        "personaje": "¿Es tu personaje favorito? ¡Déjalo en los comentarios! 👇",
        "databook":  "¿Qué dato te sorprendió más? 👇",
        "curiosidad": "¿Lo sabías? ¡Cuéntame! 👇",
        "estreno":   "¿Lo vas a ver? 👇",
        "noticia":   "¿Qué opinás de esto? 👇"
    }

    prompt = f"""Eres el community manager de "Nuevo Anime", página de Facebook para otakus hispanohablantes.
Redacta una publicación COMPLETA en ESPAÑOL LATINO (tú, nunca vos ni usted).

TEMA: {titulo}
CONTENIDO BASE: {contenido[:1000]}
TIPO: {tipo}

ESTRUCTURA:
[emoji] [Hook llamativo — 1 línea que genere curiosidad]

🎌 [Título del post — máximo 80 caracteres]

📰 [3-4 oraciones completas con datos concretos. NO cortes las oraciones a la mitad. Cada oración debe terminar con punto, signo de exclamación o interrogación.]

💬 [{ctas.get(tipo, "¿Qué opinás? 👇")}]

REGLAS ESTRICTAS:
- Todas las oraciones deben estar COMPLETAS, nunca cortadas
- Lenguaje casual y apasionado, nada de texto formal
- NUNCA menciones personas reales (deportistas, políticos, actores reales)
- Solo anime y manga
- NO incluyas hashtags (los agrego yo)
- NO incluyas URLs"""

    # Usar más tokens para que la IA no corte el texto
    texto = llamar_ia(prompt, max_tokens=900)

    if texto and es_contenido_anime(texto) and len(texto) > 80:
        # NO truncar — dejar el texto completo que generó la IA
        return texto.strip()

    # Fallback manual — oraciones completas sin truncar
    hook = random.choice(hooks.get(tipo, hooks["noticia"]))
    # Dividir en oraciones completas
    oraciones_raw = re.split(r'(?<=[.!?])\s+', contenido.strip())
    oraciones = [o.strip() for o in oraciones_raw if len(o.strip()) > 15][:4]
    resumen = " ".join(oraciones) if oraciones else contenido[:500]

    return f"{hook}\n\n🎌 {titulo[:80]}\n\n📰 {resumen}\n\n💬 {ctas.get(tipo, '¿Qué opinás? 👇')}"

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {
        'urls': [], 'urls_normalizadas': [], 'hashes_titulos': [],
        'fingerprints': [], 'titulos': [], 'timestamps': [],
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
    historial['urls_normalizadas'] = list(anti_dup.cache_urls)[-300:]
    historial['hashes_titulos']    = list(anti_dup.cache_hashes)[-300:]
    historial['fingerprints']      = list(anti_dup.cache_fingerprints)[-300:]
    historial['titulos']           = list(anti_dup.cache_titulos)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['timestamps'] = historial['timestamps'][-300:]
    historial['tipos_publicados'][tipo] = historial['tipos_publicados'].get(tipo, 0) + 1
    historial['estadisticas']['total'] += 1
    historial['estadisticas']['hoy']   += 1
    historial['estadisticas']['fecha']  = datetime.now().strftime('%Y-%m-%d')
    guardar_json(HISTORIAL_PATH, historial)
    return historial

def verificar_limite():
    estado = cargar_json(ESTADO_PATH, {'ultima': None, 'hoy': 0, 'fecha': None})
    hoy = datetime.now().strftime('%Y-%m-%d')
    if estado.get('fecha') != hoy:
        estado = {'ultima': None, 'hoy': 0, 'fecha': hoy}
    if estado['hoy'] >= MAX_PUBLICACIONES_DIA:
        log(f"🚫 Límite diario alcanzado ({MAX_PUBLICACIONES_DIA})", 'advertencia')
        return False, estado
    if estado.get('ultima'):
        try:
            minutos = (datetime.now() - datetime.fromisoformat(estado['ultima'])).total_seconds() / 60
            if minutos < TIEMPO_ENTRE_PUBLICACIONES:
                log(f"⏱️ Esperando {TIEMPO_ENTRE_PUBLICACIONES - minutos:.0f} min más", 'info')
                return False, estado
        except: pass
    return True, estado

def seleccionar_tipo(historial):
    tipos_count = historial.get('tipos_publicados', {})
    total = sum(tipos_count.values()) if tipos_count else 0
    if total == 0: return random.choice(TIPOS_CONTENIDO)
    scores = {t: total * PESOS_TIPO.get(t, 0.2) - tipos_count.get(t, 0) for t in TIPOS_CONTENIDO}
    return max(scores, key=scores.get) if random.random() < 0.7 else random.choice(TIPOS_CONTENIDO)

# =============================================================================
# FACEBOOK
# =============================================================================

def publicar_facebook_foto_unica(mensaje, imagen_path):
    """Publica post con una sola imagen."""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"
        with open(imagen_path, 'rb') as img:
            resp = requests.post(url, files={'file': ('anime.jpg', img, 'image/jpeg')},
                                 data={'message': mensaje, 'access_token': FB_ACCESS_TOKEN, 'published': 'true'},
                                 timeout=60)
        result = resp.json()
        if 'id' in result or 'post_id' in result:
            log(f"✅ Publicado (1 imagen): {result.get('post_id', result.get('id'))}", 'exito')
            return True
        error = result.get('error', {})
        log(f"❌ Error FB ({error.get('code')}): {error.get('message', 'Unknown')}", 'error')
        return False
    except Exception as e:
        log(f"❌ Excepción FB: {e}", 'error')
        return False

def publicar_facebook_carrusel(mensaje, imagenes_paths):
    """Publica post con múltiples imágenes (carrusel)."""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False
    if len(imagenes_paths) == 1:
        return publicar_facebook_foto_unica(mensaje, imagenes_paths[0])
    try:
        # Subir cada imagen sin publicar
        media_ids = []
        for img_path in imagenes_paths:
            url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"
            with open(img_path, 'rb') as img:
                resp = requests.post(url,
                                     files={'file': ('anime.jpg', img, 'image/jpeg')},
                                     data={'access_token': FB_ACCESS_TOKEN, 'published': 'false'},
                                     timeout=60)
            result = resp.json()
            if 'id' in result:
                media_ids.append(result['id'])
                log(f"🖼️ Imagen subida: {result['id']}", 'debug')
            else:
                log(f"⚠️ Error subiendo imagen: {result}", 'debug')

        if not media_ids:
            log("❌ No se pudieron subir imágenes", 'error')
            return False

        # Publicar post con todas las imágenes
        post_url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed"
        attached = [{"media_fbid": mid} for mid in media_ids]
        post_data = {
            'message': mensaje,
            'access_token': FB_ACCESS_TOKEN,
            'attached_media': json.dumps(attached)
        }
        resp = requests.post(post_url, data=post_data, timeout=60)
        result = resp.json()

        if 'id' in result:
            log(f"✅ Publicado ({len(media_ids)} imágenes): {result['id']}", 'exito')
            return True

        error = result.get('error', {})
        log(f"❌ Error FB carrusel ({error.get('code')}): {error.get('message', 'Unknown')}", 'error')
        # Fallback: publicar solo primera imagen
        log("⚠️ Fallback: publicando solo primera imagen", 'advertencia')
        return publicar_facebook_foto_unica(mensaje, imagenes_paths[0])

    except Exception as e:
        log(f"❌ Excepción carrusel: {e}", 'error')
        return False

# =============================================================================
# OBTENCIÓN DE CONTENIDO POR TIPO
# =============================================================================

def obtener_contenido_por_tipo(tipo, historial):
    anti_dup = AntiDuplicado(historial)
    candidatos = []

    log(f"🔍 Buscando contenido tipo: {tipo}", 'info')

    if tipo == "personaje":
        for _ in range(4):
            data = obtener_personaje_jikan()
            time.sleep(0.8)
            if data and not anti_dup.es_duplicado(data['titulo'], data['url'], data['descripcion']):
                candidatos.append(data)
                if len(candidatos) >= 2: break

    elif tipo == "curiosidad":
        # AniList + Kitsu
        data = obtener_curiosidad_anilist()
        if data and not anti_dup.es_duplicado(data['titulo'], data['url'], data['descripcion']):
            candidatos.append(data)
        data2 = obtener_anime_kitsu()
        if data2 and not anti_dup.es_duplicado(data2['titulo'], data2['url'], data2['descripcion']):
            candidatos.append(data2)

    elif tipo == "databook":
        for _ in range(3):
            data = obtener_anime_jikan()
            time.sleep(0.8)
            if data and not anti_dup.es_duplicado(data['titulo'], data['url'], data['descripcion']):
                candidatos.append(data)
                break

    elif tipo in ["noticia", "estreno"]:
        noticias = obtener_noticias_rss(tipo)
        kitsu = obtener_anime_kitsu()
        if kitsu: noticias.append(kitsu)
        for n in noticias:
            if not anti_dup.es_duplicado(n['titulo'], n['url'], n['descripcion']):
                candidatos.append(n)
        candidatos.sort(key=lambda x: x['puntaje'], reverse=True)

    return candidatos[:5]

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("🎌 BOT NUEVO ANIME V4 — Solo APIs Oficiales + Español + SEO")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 IA: {AI_SERVICE or 'No disponible'} | FB: {'✅' if FB_ACCESS_TOKEN else '❌'}")
    print("="*70)

    puede, estado = verificar_limite()
    if not puede: return False

    historial = cargar_historial()
    log(f"📊 Publicados hoy: {estado.get('hoy', 0)}/{MAX_PUBLICACIONES_DIA}", 'info')

    tipos_count = historial.get('tipos_publicados', {})
    if tipos_count:
        dist = " | ".join([f"{k}:{v}" for k, v in sorted(tipos_count.items())])
        log(f"📈 Distribución total: {dist}", 'info')

    tipo_objetivo = seleccionar_tipo(historial)
    log(f"🎯 Tipo seleccionado: {tipo_objetivo}", 'info')

    candidatos = obtener_contenido_por_tipo(tipo_objetivo, historial)

    if not candidatos:
        log(f"⚠️ Sin candidatos para {tipo_objetivo}, probando alternativas...", 'advertencia')
        for alt in [t for t in TIPOS_CONTENIDO if t != tipo_objetivo]:
            candidatos = obtener_contenido_por_tipo(alt, historial)
            if candidatos:
                tipo_objetivo = alt
                log(f"✅ Usando tipo alternativo: {tipo_objetivo}", 'info')
                break

    if not candidatos:
        log("❌ Sin contenido disponible con imagen válida", 'error')
        return False

    # Procesar candidatos hasta encontrar uno con imagen válida
    seleccionada = None
    mensaje_final = None
    imagenes_paths = []

    for candidato in candidatos:
        if contiene_persona_real(candidato['titulo'], candidato['descripcion']):
            log(f"🚫 Candidato rechazado (persona real): {candidato['titulo'][:50]}", 'advertencia')
            continue

        # Verificar y descargar imágenes — sin duplicados por contenido real
        imgs_validas = []
        hashes_vistos = set()
        urls_imagenes = deduplicar_imagenes(candidato.get('imagenes', []))
        if candidato.get('imagen') and candidato['imagen'] not in urls_imagenes:
            urls_imagenes.insert(0, candidato['imagen'])
        urls_imagenes = deduplicar_imagenes(urls_imagenes)  # segunda pasada

        for img_url in urls_imagenes[:3]:
            img_pil = descargar_imagen_url(img_url)
            if img_pil:
                # Hash visual: comparar thumbnail 8x8 para detectar imágenes idénticas
                thumb = img_pil.resize((8, 8)).convert('L')
                import struct
                pixel_hash = hashlib.md5(thumb.tobytes()).hexdigest()[:12]
                if pixel_hash in hashes_vistos:
                    log(f"🖼️ Imagen duplicada (mismo contenido visual) — descartando", "debug")
                    time.sleep(0.2)
                    continue
                hashes_vistos.add(pixel_hash)

                path = preparar_imagen_facebook(
                    img_pil,
                    titulo=candidato['titulo'],
                    tipo=candidato['tipo'],
                    keywords=candidato.get('keywords', [])
                )
                if path:
                    imgs_validas.append(path)
            time.sleep(0.3)

        if not imgs_validas:
            log(f"⚠️ Sin imagen válida para: {candidato['titulo'][:50]}", 'advertencia')
            continue

        # Generar texto
        log(f"✍️ Generando texto para: {candidato['titulo'][:50]}", 'info')
        texto = redactar_post(
            candidato['titulo'],
            candidato['descripcion'],
            candidato['tipo'],
            candidato.get('metadata')
        )

        if not texto or len(texto) < 50:
            for p in imgs_validas:
                try: os.remove(p)
                except: pass
            continue

        # Agregar hashtags SEO — sin truncar, Facebook acepta hasta 63.000 chars
        hashtags = HASHTAGS.get(candidato['tipo'], HASHTAGS['noticia'])
        mensaje_final = f"{texto.strip()}\n\n{hashtags}"

        seleccionada = candidato
        imagenes_paths = imgs_validas
        break

    if not seleccionada or not mensaje_final or not imagenes_paths:
        log("❌ No se pudo generar contenido válido con imagen", 'error')
        return False

    # Preview
    print(f"\n{'='*60}")
    print(f"📱 PREVIEW ({seleccionada['tipo'].upper()}) — {len(imagenes_paths)} imagen(es):")
    print(f"{'='*60}")
    print(mensaje_final)
    print(f"{'='*60}")
    print(f"📊 {len(mensaje_final)} chars | Fuente: {seleccionada['fuente']} | Imágenes: {len(imagenes_paths)}")

    # Registrar ANTES de publicar (anti-duplicado)
    historial = guardar_historial(
        historial, seleccionada['url'], seleccionada['titulo'],
        seleccionada['tipo'], seleccionada['descripcion']
    )
    estado['ultima'] = datetime.now().isoformat()
    estado['hoy']    = estado.get('hoy', 0) + 1
    guardar_json(ESTADO_PATH, estado)

    # Publicar
    exito = publicar_facebook_carrusel(mensaje_final, imagenes_paths)

    # Limpiar archivos temporales
    for p in imagenes_paths:
        try:
            if os.path.exists(p): os.remove(p)
        except: pass

    if exito:
        log(f"✅ Total histórico: {historial['estadisticas']['total']}", 'exito')
    else:
        log("❌ Falló publicación en Facebook", 'error')

    return exito

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except KeyboardInterrupt:
        log("🛑 Interrumpido", 'advertencia')
        exit(0)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
