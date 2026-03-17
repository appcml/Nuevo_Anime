#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Anime para Facebook - V2.0 (CON GEMINI AI)
Mejorado con redacción inteligente, emojis automáticos y búsqueda de personajes/historias
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# APIs y Tokens (desde variables de entorno)
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # NUEVO: API Key de Gemini

# Rutas de archivos - Usando las carpetas existentes
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', os.path.join(BASE_DIR, 'data', 'historial_anime.json'))
ESTADO_PATH = os.getenv('ESTADO_PATH', os.path.join(BASE_DIR, 'data', 'estado_bot_anime.json'))
PERSONAJES_PATH = os.path.join(BASE_DIR, 'data', 'personajes_cache.json')

# Configuración de publicación
TIEMPO_ENTRE_PUBLICACIONES = 60  # 60 minutos entre publicaciones
MAX_PUBLICACIONES_DIA = 24  # Máximo 24 publicaciones al día (una por hora)
UMBRAL_SIMILITUD_TITULO = 0.80
UMBRAL_SIMILITUD_CONTENIDO = 0.70

# Inicializar Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None
    print("⚠️ No se encontró GEMINI_API_KEY - Se usará redacción básica")

# =============================================================================
# FUENTES RSS DE ANIME OPTIMIZADAS
# =============================================================================

RSS_FEEDS = [
    # Español - Fuentes principales y confiables
    'https://somoskudasai.com/noticias/feed/',
    'https://www.crunchyroll.com/es/news/rss',
    'https://www.crunchyroll.com/es-es/news/rss',
    'https://feeds.feedburner.com/crunchyroll/animenews',
    'https://www.animenewsnetwork.com/all/rss.xml',
    'https://myanimelist.net/rss/news.xml',
    'https://otakumode.com/news/feed',
    'https://honeysanime.com/feed/',
    'https://anitrendz.net/news/feed/',
    'https://randomc.net/feed/',
    'https://theanimedaily.com/feed/',
    'https://animehunch.com/feed/',
    # Fuentes de personajes e historias
    'https://www.animecharactersdatabase.com/rss',
    'https://www.anime-planet.com/rss',
    'https://www.animefillerlist.com/rss',
]

# =============================================================================
# PALABRAS CLAVE PARA CLASIFICACIÓN
# =============================================================================

PALABRAS_ANIME_POPULAR = [
    "attack on titan", "shingeki no kyojin", "demon slayer", "kimetsu no yaiba",
    "jujutsu kaisen", "my hero academia", "boku no hero", "one piece", "naruto",
    "dragon ball", "spy x family", "chainsaw man", "bleach", "hunter x hunter",
    "evangelion", "studio ghibli", "makoto shinkai", "hayao miyazaki",
    "suzume", "your name", "weathering with you", "el juego del calamar", 
    "squid game", "death note", "fullmetal alchemist", "sword art online",
    "tokyo ghoul", "attack on titan", "shingeki", "demon slayer", "kimetsu"
]

PALABRAS_PERSONAJES = [
    "personaje", "protagonista", "seiyuu", "voice actor", "doblaje",
    "tanjiro", "nezuko", "zenitsu", "inosuke", "eren", "mikasa", "levi",
    "goku", "vegeta", "luffy", "zoro", "naruto", "sasuke", "gojo", "itadori",
    "megumi", "nobara", "denji", "power", "makima", "anya", "loid", "yor",
    "asta", "yuno", "deku", "bakugo", "todoroki", "spiderman", "batman"
]

PALABRAS_HISTORIA = [
    "historia", "trama", "argumento", "sinopsis", "resumen", "recap",
    "final", "conclusión", "desenlace", "spoiler", "teoría", "predicción",
    "arco", "saga", "temporada", "capítulo", "episodio", "manga"
]

PALABRAS_ESTRENO = [
    "nuevo anime", "temporada", "estreno", "tráiler", "trailer", "revelado", "anunciado",
    "adaptación", "secuela", "precuela", "spin-off", "ova", "película", "movie",
    "netflix anime", "crunchyroll", "funimation", "hidive", "prime video"
]

# =============================================================================
# FUNCIONES DE REDACCIÓN CON GEMINI AI
# =============================================================================

def redactar_con_gemini(titulo, contenido, tipo="noticia"):
    """
    Usa Gemini AI para redactar una publicación atractiva con emojis
    """
    if not model:
        return None
    
    try:
        # Crear prompt según el tipo de contenido
        if tipo == "personaje":
            prompt = f"""Eres un redactor experto en anime y manga. Crea una publicación atractiva para Facebook sobre este personaje de anime.

TÍTULO ORIGINAL: {titulo}
CONTENIDO: {contenido[:500]}

INSTRUCCIONES:
1. Escribe en español de forma natural y entusiasta
2. Usa MUCHOS emojis relevantes (🎌🔥✨🌟💫🎭🎨🗡️🛡️⚡💥🌸🍜🎵)
3. Incluye hashtags relevantes al final (#Anime #Personajes #Otaku)
4. Máximo 1500 caracteres
5. Termina con una pregunta para generar engagement
6. Destaca datos interesantes del personaje

FORMATO:
🇯🇵 [Título atractivo]

[Contenido con emojis]

📎 Fuente: [mención]

[Hashtags]

¿Tú qué opinas? 🤔"""

        elif tipo == "historia":
            prompt = f"""Eres un redactor experto en anime. Crea una publicación sobre la historia/trama de este anime.

TÍTULO: {titulo}
CONTENIDO: {contenido[:500]}

INSTRUCCIONES:
1. Escribe en español, evitando spoilers importantes
2. Usa emojis narrativos (📖✨🎭🔮🌟⚔️🛡️💫🎪🎬)
3. Genera intriga sin spoilear
4. Máximo 1500 caracteres
5. Incluye hashtags (#Anime #Historia #SpoilerAlert si aplica)
6. Pregunta a los fans qué les parece la trama

FORMATO:
📖 [Título intrigante]

[Resumen con emojis]

⚠️ Sin spoilers importantes

📎 Fuente: [mención]

[Hashtags]"""

        else:  # noticia general
            prompt = f"""Eres un redactor experto en noticias de anime. Crea una publicación viral para Facebook.

TÍTULO: {titulo}
CONTENIDO: {contenido[:500]}

INSTRUCCIONES:
1. Escribe en español, estilo periodístico pero divertido
2. Usa MUCHOS emojis relevantes (🎌🔥✨📢🚨🎉🎊🌟💥⚡🎭🎨🎪)
3. Destaca lo más importante en la primera línea
4. Máximo 1500 caracteres
5. Incluye hashtags populares (#Anime #NoticiasAnime #Otaku #NuevoAnime)
6. Termina con pregunta para comentarios

FORMATO:
🚨 [Título llamativo con emojis]

[Cuerpo de la noticia con emojis]

📎 Fuente: [mención]

[Hashtags]

¿Qué te parece esta noticia? 👇"""

        # Configurar generación
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=800,
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        if response.text:
            return response.text.strip()
        return None
        
    except Exception as e:
        print(f"⚠️ Error con Gemini: {e}")
        return None

def detectar_tipo_contenido(titulo, descripcion):
    """Detecta si es noticia de personaje, historia o estreno"""
    texto = f"{titulo} {descripcion}".lower()
    
    puntaje_personaje = sum(1 for p in PALABRAS_PERSONAJES if p in texto)
    puntaje_historia = sum(1 for p in PALABRAS_HISTORIA if p in texto)
    puntaje_estreno = sum(1 for p in PALABRAS_ESTRENO if p in texto)
    
    if puntaje_personaje >= 2:
        return "personaje"
    elif puntaje_historia >= 2:
        return "historia"
    elif puntaje_estreno >= 2:
        return "estreno"
    else:
        return "noticia"

def generar_texto_manual(titulo, contenido, tipo="noticia", fuente=""):
    """Genera texto básico si Gemini no está disponible"""
    emojis_base = ["🎌", "✨", "🔥", "💫", "🌟", "🎭", "🎨", "📢", "🚨", "🎉"]
    emoji_titulo = random.choice(emojis_base)
    
    if tipo == "personaje":
        intro = f"{emoji_titulo} ¡Descubre todo sobre este increíble personaje! ✨"
        cuerpo = f"\n\n🎭 {titulo}\n\n{contenido[:400]}..."
        cierre = "\n\n💬 ¿Cuál es tu personaje favorito? ¡Cuéntanos! 👇"
        hashtags = "\n\n#Anime #Personajes #Otaku #Manga #Seiyuu"
    elif tipo == "historia":
        intro = f"{emoji_titulo} ¡La historia que todos están comentando! 📖"
        cuerpo = f"\n\n✨ {titulo}\n\n{contenido[:400]}..."
        cierre = "\n\n🔮 ¿Ya viste este anime? ¡Sin spoilers! 🤫"
        hashtags = "\n\n#Anime #Historia #Spoilers #Otaku #AnimeLatam"
    else:
        intro = f"{emoji_titulo} ¡Últimas noticias del mundo anime! 🚨"
        cuerpo = f"\n\n📢 {titulo}\n\n{contenido[:400]}..."
        cierre = "\n\n🤔 ¿Qué opinas de esta noticia? ¡Comenta! 👇"
        hashtags = "\n\n#Anime #NoticiasAnime #Otaku #NuevoAnime #Manga"
    
    return f"{intro}{cuerpo}{cierre}\n\n📎 Fuente: {fuente}{hashtags}\n\n— Nuevo Anime 🎌"

# =============================================================================
# FUNCIONES UTILITARIAS (MANTENIDAS Y MEJORADAS)
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None: 
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else default.copy()
        except Exception as e:
            log(f"Error cargando JSON {ruta}: {e}", 'error')
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temp_path = f"{ruta}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, ruta)
        return True
    except Exception as e:
        log(f"Error guardando JSON: {e}", 'error')
        return False

def generar_hash(texto):
    if not texto: 
        return ""
    t = re.sub(r'[^\w\s]', '', texto.lower().strip())
    t = re.sub(r'\s+', ' ', t)
    return hashlib.md5(t.encode()).hexdigest()

def normalizar_url(url):
    if not url: 
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        netloc = re.sub(r'^(www\.|m\.|mobile\.|amp\.)', '', netloc)
        path = re.sub(r'/index\.(html|php|htm|asp)$', '/', path)
        path = path.rstrip('/')
        path = re.sub(r'\.html?$', '', path)
        url_base = f"{netloc}{path}"
        return url_base
    except:
        return url.lower().strip()

def calcular_similitud(t1, t2):
    if not t1 or not t2: 
        return 0.0
    def n(t):
        t = re.sub(r'[^\w\s]', '', t.lower().strip())
        t = re.sub(r'\s+', ' ', t)
        return t.strip()
    return SequenceMatcher(None, n(t1), n(t2)).ratio()

def limpiar_texto(texto):
    if not texto: 
        return ""
    import html
    t = html.unescape(texto)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'https?://\S*', '', t)
    t = t.strip()
    return t

def calcular_puntaje(titulo, desc):
    txt = f"{titulo} {desc}".lower()
    p = 0
    
    # Palabras de alto impacto
    for f in PALABRAS_ANIME_POPULAR:
        if f in txt: 
            p += 15
    for f in PALABRAS_ESTRENO:
        if f in txt: 
            p += 12
    for f in PALABRAS_PERSONAJES:
        if f in txt: 
            p += 10
    for f in PALABRAS_HISTORIA:
        if f in txt: 
            p += 8
    
    # Longitud óptima
    if 20 <= len(titulo) <= 120: 
        p += 5
    if len(desc) >= 50: 
        p += 3
    
    return min(p, 100)

def es_contenido_repetido(titulo, desc, historial):
    if not historial:
        return False
    
    titulo_hash = generar_hash(titulo)
    desc_hash = generar_hash(desc[:100]) if desc else ""
    
    if titulo_hash in historial.get('hashes_titulos', []):
        return True
    if desc_hash in historial.get('hashes_desc', []):
        return True
    
    for t in historial.get('titulos', []):
        if calcular_similitud(titulo, t) >= UMBRAL_SIMILITUD_TITULO:
            return True
    
    return False

# =============================================================================
# EXTRACCIÓN DE CONTENIDO MEJORADA
# =============================================================================

def extraer_contenido_web(url):
    if not url:
        return None, None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Eliminar elementos no deseados
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        content = None
        
        # Selectores mejorados
        selectors = [
            'article', '.entry-content', '.post-content', '.article-content',
            '.content', 'main', '[role="main"]', '.news-content', 
            '.story-content', '.the-content', '.post-body'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                paragraphs = elem.find_all('p')
                if len(paragraphs) >= 2:
                    text = ' '.join([limpiar_texto(p.get_text()) for p in paragraphs if len(p.get_text()) > 30])
                    if len(text) > 200:
                        content = text[:2000]  # Más contenido para Gemini
                        break
        
        # Extraer imagen
        imagen = None
        for meta in ['og:image', 'twitter:image']:
            tag = soup.find('meta', property=meta) or soup.find('meta', attrs={'name': meta})
            if tag and tag.get('content'):
                img_url = tag['content'].strip()
                if img_url.startswith('http'):
                    imagen = img_url
                    break
        
        if not imagen:
            article = soup.find('article') or soup.find('main') or soup.find('body')
            if article:
                img = article.find('img')
                if img:
                    src = img.get('data-src') or img.get('src', '')
                    if src.startswith('http'):
                        imagen = src
        
        return content, imagen
        
    except Exception as e:
        log(f"Error extrayendo contenido: {e}", 'debug')
        return None, None

def descargar_imagen(url):
    if not url:
        return None
    
    for bad in ['google.com', 'gstatic.com', 'facebook.com', 'logo', 'icon', 'favicon']:
        if bad in url.lower():
            return None
    
    try:
        from PIL import Image
        from io import BytesIO
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=20, stream=True)
        r.raise_for_status()
        
        content_type = r.headers.get('content-type', '')
        if 'image' not in content_type:
            return None
        
        img = Image.open(BytesIO(r.content))
        w, h = img.size
        
        if w < 400 or h < 300:  # Requisitos más estrictos
            return None
        if w/h > 3 or h/w > 3:
            return None
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        img.thumbnail((1200, 1200))
        path = f'/tmp/anime_{generar_hash(url)}.jpg'
        img.save(path, 'JPEG', quality=90)
        
        if os.path.getsize(path) < 10000:
            os.remove(path)
            return None
        
        return path
        
    except Exception as e:
        log(f"Error descargando imagen: {e}", 'debug')
        return None

def crear_imagen_default(titulo):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        
        # Fondo con gradiente anime-style
        img = Image.new('RGB', (1200, 630), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        # Barra decorativa superior
        draw.rectangle([(0, 0), (1200, 15)], fill='#e94560')
        draw.rectangle([(0, 615), (1200, 630)], fill='#16213e')
        
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        except:
            font_title = font_sub = ImageFont.load_default()
        
        wrapped = textwrap.fill(titulo[:100], width=28)
        lines = wrapped.split('\n')
        
        y_start = (630 - len(lines) * 70) // 2 - 30
        
        for i, line in enumerate(lines):
            draw.text((60, y_start + i * 70), line, font=font_title, fill='#ffffff')
        
        draw.text((60, 540), "🇯🇵 Noticias Anime | Nuevo Anime", font=font_sub, fill='#e94560')
        draw.text((60, 580), "🎌 Tu fuente de noticias otaku", font=font_sub, fill='#a0a0a0')
        
        path = f'/tmp/anime_default_{generar_hash(titulo)}.jpg'
        img.save(path, 'JPEG', quality=95)
        return path
        
    except Exception as e:
        log(f"Error creando imagen default: {e}", 'error')
        return None

# =============================================================================
# FUENTES DE NOTICIAS
# =============================================================================

def obtener_rss_anime():
    noticias = []
    
    for feed_url in RSS_FEEDS:
        try:
            log(f"📡 RSS: {feed_url[:50]}...", 'debug')
            
            feed = feedparser.parse(feed_url, request_headers={
                'User-Agent': 'Mozilla/5.0'
            })
            
            if not feed or not feed.entries:
                continue
            
            for entry in feed.entries[:8]:  # Tomar 8 más recientes
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo:
                    continue
                
                titulo = re.sub(r'\s*[-|]\s*[^-]*$', '', titulo)
                
                link = entry.get('link', '')
                if not link:
                    continue
                
                desc = entry.get('summary', '') or entry.get('description', '')
                desc = re.sub(r'<[^>]+>', '', desc)
                desc = limpiar_texto(desc)
                
                fecha = entry.get('published', '')
                
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for link_obj in entry.links:
                        if link_obj.get('type', '').startswith('image/'):
                            imagen = link_obj.get('href')
                            break
                
                # Detectar tipo de contenido
                tipo = detectar_tipo_contenido(titulo, desc)
                
                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': desc,
                    'url': link,
                    'imagen': imagen,
                    'fuente': extraer_dominio(link),
                    'fecha': fecha,
                    'tipo': tipo,
                    'puntaje': calcular_puntaje(titulo, desc)
                })
                
        except Exception as e:
            log(f"Error RSS {feed_url}: {e}", 'debug')
            continue
    
    log(f"📰 Total recopilado: {len(noticias)} noticias", 'info')
    return noticias

def extraer_dominio(url):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split('.')
        if len(parts) > 2:
            return '.'.join(parts[-2:])
        return netloc
    except:
        return "anime"

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {
        'urls': [],
        'urls_normalizadas': [],
        'hashes_titulos': [],
        'hashes_desc': [],
        'titulos': [],
        'descripciones': [],
        'timestamps': [],
        'estadisticas': {'total_publicadas': 0, 'hoy': 0, 'ultima_fecha': None}
    }
    
    h = cargar_json(HISTORIAL_PATH, default)
    
    for k in default:
        if k not in h:
            h[k] = default[k]
    
    return h

def guardar_historial(historial, url, titulo, desc):
    url_norm = normalizar_url(url)
    titulo_hash = generar_hash(titulo)
    desc_hash = generar_hash(desc[:100]) if desc else ""
    
    if url_norm in historial.get('urls_normalizadas', []):
        log("⚠️ URL ya existe en historial", 'advertencia')
        return historial
    
    historial['urls'].append(url)
    historial['urls_normalizadas'].append(url_norm)
    historial['hashes_titulos'].append(titulo_hash)
    historial['hashes_desc'].append(desc_hash)
    historial['titulos'].append(titulo)
    historial['descripciones'].append(desc[:200] if desc else "")
    historial['timestamps'].append(datetime.now().isoformat())
    
    historial['estadisticas']['total_publicadas'] += 1
    historial['estadisticas']['hoy'] += 1
    historial['estadisticas']['ultima_fecha'] = datetime.now().strftime('%Y-%m-%d')
    
    for key in ['urls', 'urls_normalizadas', 'hashes_titulos', 'hashes_desc', 
                'titulos', 'descripciones', 'timestamps']:
        if len(historial[key]) > 300:
            historial[key] = historial[key][-300:]
    
    guardar_json(HISTORIAL_PATH, historial)
    return historial

def verificar_limite_diario():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None, 'contador_hoy': 0, 'fecha': None})
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if estado.get('fecha') != hoy:
        estado = {
            'ultima_publicacion': None,
            'contador_hoy': 0,
            'fecha': hoy
        }
    
    if estado['contador_hoy'] >= MAX_PUBLICACIONES_DIA:
        log(f"🚫 Límite diario alcanzado: {MAX_PUBLICACIONES_DIA}", 'advertencia')
        return False, estado
    
    ultima = estado.get('ultima_publicacion')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            minutos = (datetime.now() - ultima_dt).total_seconds() / 60
            if minutos < TIEMPO_ENTRE_PUBLICACIONES:
                log(f"⏱️ Esperando... Última hace {minutos:.0f} min (objetivo: {TIEMPO_ENTRE_PUBLICACIONES} min)", 'info')
                return False, estado
        except:
            pass
    
    return True, estado

# =============================================================================
# PUBLICACIÓN FACEBOOK MEJORADA
# =============================================================================

def publicar_facebook(mensaje, imagen_path):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales de Facebook", 'error')
        return False
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as img_file:
            files = {'file': ('anime.jpg', img_file, 'image/jpeg')}
            data = {
                'message': mensaje[:2000],  # Límite de Facebook
                'access_token': FB_ACCESS_TOKEN
            }
            
            response = requests.post(url, files=files, data=data, timeout=60)
            result = response.json()
        
        if 'id' in result:
            log(f"✅ Publicado ID: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {})
            log(f"❌ Error Facebook ({error.get('code')}): {error.get('message')}", 'error')
            return False
            
    except Exception as e:
        log(f"❌ Excepción publicando: {e}", 'error')
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL MEJORADA
# =============================================================================

def main():
    print("\n" + "="*70)
    print("🇯🇵 BOT DE NOTICIAS ANIME CON GEMINI AI - V2.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Gemini AI: {'✅ Activo' if model else '❌ Desactivado'}")
    print("="*70)
    
    # Verificar límite
    puede_publicar, estado = verificar_limite_diario()
    if not puede_publicar:
        return False
    
    # Cargar historial
    historial = cargar_historial()
    log(f"📊 Publicaciones hoy: {estado.get('contador_hoy', 0)}/{MAX_PUBLICACIONES_DIA}", 'info')
    log(f"📚 Historial: {len(historial.get('urls', []))} URLs registradas", 'info')
    
    # Obtener noticias
    log("🔍 Buscando noticias de anime, personajes e historias...", 'info')
    noticias = obtener_rss_anime()
    
    if not noticias:
        log("❌ No se encontraron noticias", 'error')
        return False
    
    # Filtrar duplicados
    noticias_unicas = []
    for n in noticias:
        if not es_contenido_repetido(n['titulo'], n['descripcion'], historial):
            noticias_unicas.append(n)
    
    log(f"🎯 Noticias únicas: {len(noticias_unicas)}", 'info')
    
    if not noticias_unicas:
        log("⚠️ Todas las noticias ya fueron publicadas", 'advertencia')
        return False
    
    # Ordenar por puntaje
    noticias_unicas.sort(key=lambda x: x['puntaje'], reverse=True)
    
    # Seleccionar y procesar
    seleccionada = None
    contenido_final = None
    imagen_final = None
    mensaje_final = None
    
    for noticia in noticias_unicas[:15]:
        log(f"🔍 Verificando: {noticia['titulo'][:50]}... [Tipo: {noticia['tipo']} | Score: {noticia['puntaje']}]", 'debug')
        
        # Extraer contenido
        contenido, imagen_web = extraer_contenido_web(noticia['url'])
        
        texto_base = contenido if (contenido and len(contenido) >= 150) else noticia['descripcion']
        
        if len(texto_base) >= 100:
            seleccionada = noticia
            contenido_final = texto_base
            imagen_final = noticia.get('imagen') or imagen_web
            
            # Generar texto con Gemini o manual
            log(f"✍️ Generando texto con {'Gemini AI' if model else 'motor básico'}...", 'info')
            
            if model:
                mensaje_gemini = redactar_con_gemini(
                    noticia['titulo'], 
                    contenido_final, 
                    noticia['tipo']
                )
                if mensaje_gemini:
                    mensaje_final = mensaje_gemini
                else:
                    mensaje_final = generar_texto_manual(
                        noticia['titulo'], 
                        contenido_final, 
                        noticia['tipo'],
                        noticia['fuente']
                    )
            else:
                mensaje_final = generar_texto_manual(
                    noticia['titulo'], 
                    contenido_final, 
                    noticia['tipo'],
                    noticia['fuente']
                )
            
            break
    
    if not seleccionada or not mensaje_final:
        log("❌ No se encontró noticia procesable", 'error')
        return False
    
    # Mostrar selección
    print(f"\n📝 NOTICIA SELECCIONADA:")
    log(f"   Título: {seleccionada['titulo'][:60]}...", 'info')
    log(f"   Tipo: {seleccionada['tipo'].upper()}", 'info')
    log(f"   Fuente: {seleccionada['fuente']}", 'info')
    log(f"   Puntaje: {seleccionada['puntaje']}/100", 'info')
    
    # Procesar imagen
    log("🖼️ Procesando imagen...", 'info')
    imagen_path = None
    
    if imagen_final:
        imagen_path = descargar_imagen(imagen_final)
    
    if not imagen_path:
        log("⚠️ Creando imagen default...", 'advertencia')
        imagen_path = crear_imagen_default(seleccionada['titulo'])
    
    if not imagen_path:
        log("❌ No se pudo crear imagen", 'error')
        return False
    
    # Publicar
    log("📘 Publicando en Facebook...", 'info')
    exito = publicar_facebook(mensaje_final, imagen_path)
    
    # Limpiar
    try:
        if os.path.exists(imagen_path):
            os.remove(imagen_path)
    except:
        pass
    
    if exito:
        historial = guardar_historial(historial, seleccionada['url'], 
                                     seleccionada['titulo'], contenido_final)
        
        estado['ultima_publicacion'] = datetime.now().isoformat()
        estado['contador_hoy'] = estado.get('contador_hoy', 0) + 1
        guardar_json(ESTADO_PATH, estado)
        
        log(f"✅ ÉXITO - Total histórico: {historial['estadisticas']['total_publicadas']}", 'exito')
        return True
    else:
        log("❌ Falló la publicación", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except KeyboardInterrupt:
        log("🛑 Interrumpido por usuario", 'advertencia')
        exit(0)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
