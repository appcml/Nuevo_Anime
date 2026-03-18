#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Anime V2.5 - Publicaciones cortas, ordenadas y completas
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
from urllib.parse import urlparse

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', os.path.join(BASE_DIR, 'data', 'historial_anime.json'))
ESTADO_PATH = os.getenv('ESTADO_PATH', os.path.join(BASE_DIR, 'data', 'estado_bot_anime.json'))

TIEMPO_ENTRE_PUBLICACIONES = 60
MAX_PUBLICACIONES_DIA = 24
UMBRAL_SIMILITUD_TITULO = 0.80
MAX_CARACTERES_FB = 1500

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
# FUENTES RSS
# =============================================================================

RSS_FEEDS = [
    'https://somoskudasai.com/feed/',
    'https://www.animenewsnetwork.com/all/rss.xml',
    'https://myanimelist.net/rss/news.xml',
    'https://otakumode.com/news/feed',
    'https://honeysanime.com/feed/',
    'https://animehunch.com/feed/',
    'https://www.anime-planet.com/rss',
]

PALABRAS_ANIME = {
    "attack on titan": 20, "demon slayer": 20, "kimetsu": 20, "jujutsu kaisen": 20,
    "my hero academia": 18, "one piece": 18, "spy x family": 18, "chainsaw man": 18,
    "dragon ball": 15, "naruto": 15, "bleach": 15, "hunter x hunter": 15,
    "evangelion": 15, "studio ghibli": 15, "temporada": 12, "estreno": 12,
    "trailer": 10, "nuevo anime": 10, "personaje": 8, "protagonista": 8
}

# =============================================================================
# REDACCIÓN - FORMATO ORDENADO Y COMPLETO
# =============================================================================

def truncar_texto(texto, max_chars=MAX_CARACTERES_FB):
    """Trunca texto respetando palabras"""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars].rsplit(' ', 1)[0] + "..."

def redactar_con_ia(titulo, contenido, tipo="noticia"):
    """Genera publicación estructurada y completa"""
    
    emojis_tipo = {
        "personaje": "🎭",
        "historia": "📖",
        "estreno": "🚨",
        "noticia": "📢"
    }
    
    emoji_header = emojis_tipo.get(tipo, "📢")
    
    prompt = f"""Crea una publicación de Facebook sobre anime en ESPAÑOL LATINO.

TÍTULO ORIGINAL: {titulo}
CONTENIDO: {contenido[:600]}
TIPO: {tipo}

REGLAS:
1. ESPAÑOL LATINO (tú, no usted)
2. Estructura OBLIGATORIA con saltos de línea:
   - Línea 1: Hook con emoji {emoji_header}
   - Línea 2: Título traducido/resumido (máx 60 chars)
   - Línea 3: Resumen de la noticia (2-3 oraciones, máx 150 chars)
   - Línea 4: CTA para comentar
   - Línea 5: 3 hashtags
3. Máximo 1300 caracteres totales
4. Emojis estratégicos (no excesivos)
5. Incluir la INFORMACIÓN CLAVE de la noticia

FORMATO EJEMPLO:
🚨 ¡Nueva temporada confirmada!

Jujutsu Kaisen anuncia su temporada final para 2025. El estudio MAPPA confirma que será la conclusión del arco de Shibuya.

¿Listos para el final? 👇

#Anime #JujutsuKaisen #NuevoAnime"""

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
                    "max_tokens": 400
                },
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return truncar_texto(data['choices'][0]['message']['content'].strip(), 1300)
        except Exception as e:
            print(f"⚠️ Error OpenRouter: {e}")
    
    if AI_SERVICE == "gemini":
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=400)
            )
            if response and response.text:
                return truncar_texto(response.text.strip(), 1300)
        except Exception as e:
            print(f"⚠️ Error Gemini: {e}")
    
    return None

def redactar_manual_mejorado(titulo, contenido, tipo="noticia", fuente=""):
    """Redacción manual estructurada y completa"""
    
    # Hooks por tipo
    hooks = {
        "personaje": ["🎭 ¡Nuevo personaje revelado!", "✨ ¡Diseño de personaje filtrado!", "🔥 ¡Sobre el protagonista!"],
        "historia": ["📖 ¡La historia avanza!", "🔮 ¡Nuevo arco confirmado!", "⚔️ ¡Plot twist anunciado!"],
        "estreno": ["🚨 ¡Estreno confirmado!", "🎉 ¡Nueva temporada!", "✨ ¡Fecha revelada!"],
        "noticia": ["📢 ¡Noticia importante!", "🔥 ¡Última hora anime!", "🎌 ¡Anuncio oficial!"]
    }
    
    # CTAs variados
    ctas = [
        "¿Qué opinan? ¡Los leo! 👇",
        "¿Emocionados? ¡Comenten! 👇",
        "¿Lo esperaban? ¡Diganme! 👇",
        "¿Fav o flop? ¡Debatamos! 👇"
    ]
    
    # Limpiar y extraer información clave
    hook = random.choice(hooks.get(tipo, hooks["noticia"]))
    cta = random.choice(ctas)
    
    # Procesar contenido: extraer oraciones completas
    oraciones = re.split(r'[.!?]+', contenido)
    oraciones = [s.strip() for s in oraciones if len(s.strip()) > 20]
    
    # Tomar 2 oraciones con información sustancial
    resumen_parts = []
    chars_count = 0
    for oracion in oraciones[:3]:
        if chars_count + len(oracion) < 180:
            resumen_parts.append(oracion)
            chars_count += len(oracion)
    
    resumen = ". ".join(resumen_parts)
    if not resumen:
        resumen = contenido[:150].rsplit(' ', 1)[0] + "..."
    
    # Limpiar título
    titulo_limpio = re.sub(r'\s+', ' ', titulo).strip()[:70]
    
    # Hashtags relevantes
    hashtags_map = {
        "personaje": "#Anime #Personajes #Otaku",
        "historia": "#Anime #Historia #Spoilers",
        "estreno": "#Anime #Estreno #NuevoAnime",
        "noticia": "#Anime #Noticias #Otaku"
    }
    hashtags = hashtags_map.get(tipo, "#Anime #Otaku #Noticias")
    
    # Construir publicación estructurada
    partes = [
        hook,
        "",  # Línea en blanco
        f"🎌 {titulo_limpio}",
        "",  # Línea en blanco
        f"📰 {resumen}.",
        "",  # Línea en blanco
        f"💬 {cta}",
        "",  # Línea en blanco
        hashtags
    ]
    
    texto = "\n".join(partes)
    return truncar_texto(texto, MAX_CARACTERES_FB)

def verificar_espanol(texto):
    """Verifica español básico"""
    palabras = ["el", "la", "de", "que", "y", "en", "un", "es", "se", "no", "lo", "su", "con", "por", "para"]
    texto_lower = texto.lower()
    return sum(1 for p in palabras if f" {p} " in f" {texto_lower} ") >= 3

def detectar_tipo(titulo, desc):
    texto = f"{titulo} {desc}".lower()
    if any(p in texto for p in ["personaje", "protagonista", "seiyuu", "diseño"]): return "personaje"
    if any(p in texto for p in ["historia", "trama", "sinopsis", "arco"]): return "historia"
    if any(p in texto for p in ["estreno", "trailer", "temporada", "fecha"]): return "estreno"
    return "noticia"

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

def es_repetido(titulo, historial):
    if not historial: return False
    if generar_hash(titulo) in historial.get('hashes_titulos', []): return True
    for t in historial.get('titulos', []):
        if calcular_similitud(titulo, t) >= UMBRAL_SIMILITUD_TITULO: return True
    return False

# =============================================================================
# EXTRACCIÓN Y PROCESAMIENTO
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
                    content = text[:1000]
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

def crear_imagen_default(titulo):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        
        img = Image.new('RGB', (1200, 630), color='#0f0f23')
        draw = ImageDraw.Draw(img)
        
        draw.rectangle([(0, 0), (1200, 8)], fill='#ff006e')
        draw.rectangle([(0, 622), (1200, 630)], fill='#3a0ca3')
        
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
        
        draw.text((60, 550), "🇯🇵 Noticias Anime | Nuevo Anime", font=font_sub, fill='#ff006e')
        draw.text((60, 590), "🎌 Tu fuente otaku de confianza", font=font_sub, fill='#a0a0a0')
        
        path = f'/tmp/anime_def_{generar_hash(titulo)[:8]}.jpg'
        img.save(path, 'JPEG', quality=90)
        return path
    except Exception as e:
        log(f"Error imagen default: {e}", 'error')
        return None

def obtener_noticias():
    noticias = []
    for feed_url in RSS_FEEDS:
        try:
            log(f"📡 {feed_url[:45]}...", 'debug')
            feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
            if not feed or not feed.entries: continue
            
            for entry in feed.entries[:3]:
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo: continue
                
                link = entry.get('link', '')
                if not link: continue
                
                desc = limpiar_texto(entry.get('summary', '') or entry.get('description', ''))
                
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for l in entry.links:
                        if l.get('type', '').startswith('image/'):
                            imagen = l.get('href')
                            break
                
                tipo = detectar_tipo(titulo, desc)
                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': desc,
                    'url': link,
                    'imagen': imagen,
                    'fuente': extraer_dominio(link),
                    'tipo': tipo,
                    'puntaje': calcular_puntaje(titulo, desc)
                })
        except Exception as e:
            log(f"Error RSS: {e}", 'debug')
            continue
    
    log(f"📰 Total: {len(noticias)}", 'info')
    return noticias

def extraer_dominio(url):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split('.')
        return '.'.join(parts[-2:]) if len(parts) > 2 else netloc
    except: return "anime"

# =============================================================================
# HISTORIAL
# =============================================================================

def cargar_historial():
    default = {
        'urls': [], 'urls_normalizadas': [], 'hashes_titulos': [],
        'titulos': [], 'timestamps': [],
        'estadisticas': {'total': 0, 'hoy': 0, 'fecha': None}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h: h[k] = default[k]
    return h

def guardar_historial(historial, url, titulo):
    url_norm = normalizar_url(url)
    if url_norm in historial.get('urls_normalizadas', []):
        return historial
    
    historial['urls'].append(url)
    historial['urls_normalizadas'].append(url_norm)
    historial['hashes_titulos'].append(generar_hash(titulo))
    historial['titulos'].append(titulo)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['estadisticas']['total'] += 1
    historial['estadisticas']['hoy'] += 1
    historial['estadisticas']['fecha'] = datetime.now().strftime('%Y-%m-%d')
    
    for key in ['urls', 'urls_normalizadas', 'hashes_titulos', 'titulos', 'timestamps']:
        if len(historial[key]) > 200:
            historial[key] = historial[key][-200:]
    
    guardar_json(HISTORIAL_PATH, historial)
    return historial

def verificar_limite():
    estado = cargar_json(ESTADO_PATH, {'ultima': None, 'hoy': 0, 'fecha': None})
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if estado.get('fecha') != hoy:
        estado = {'ultima': None, 'hoy': 0, 'fecha': hoy}
    
    if estado['hoy'] >= MAX_PUBLICACIONES_DIA:
        log(f"🚫 Límite diario", 'advertencia')
        return False, estado
    
    ultima = estado.get('ultima')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            minutos = (datetime.now() - ultima_dt).total_seconds() / 60
            if minutos < TIEMPO_ENTRE_PUBLICACIONES:
                log(f"⏱️ Esperando {minutos:.0f}min", 'info')
                return False, estado
        except: pass
    
    return True, estado

# =============================================================================
# FACEBOOK
# =============================================================================

def publicar_facebook(mensaje, imagen_path):
    """Publica en Facebook con manejo de límites"""
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
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("🇯🇵 BOT ANIME V2.5 - Publicaciones ordenadas y completas")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 IA: {AI_SERVICE or 'Manual'} | FB: {'✅' if FB_ACCESS_TOKEN else '❌'}")
    print("="*70)
    
    puede, estado = verificar_limite()
    if not puede:
        return False
    
    historial = cargar_historial()
    log(f"📊 Hoy: {estado.get('hoy', 0)}/{MAX_PUBLICACIONES_DIA}", 'info')
    
    log("🔍 Buscando noticias...", 'info')
    noticias = obtener_noticias()
    if not noticias:
        log("❌ Sin noticias", 'error')
        return False
    
    unicas = [n for n in noticias if not es_repetido(n['titulo'], historial)]
    log(f"🎯 Únicas: {len(unicas)}", 'info')
    if not unicas:
        log("⚠️ Todo publicado", 'advertencia')
        return False
    
    unicas.sort(key=lambda x: x['puntaje'], reverse=True)
    
    seleccionada = None
    mensaje_final = None
    imagen_url = None
    
    for noticia in unicas[:5]:
        contenido, img_web = extraer_web(noticia['url'])
        texto = contenido if (contenido and len(contenido) >= 50) else noticia['descripcion']
        
        if len(texto) >= 40:
            seleccionada = noticia
            imagen_url = noticia.get('imagen') or img_web
            
            log(f"✍️ Generando ({AI_SERVICE or 'manual'})...", 'info')
            
            texto_ia = redactar_con_ia(noticia['titulo'], texto, noticia['tipo'])
            if texto_ia:
                mensaje_final = texto_ia
                if not verificar_espanol(mensaje_final):
                    log("⚠️ IA no generó español, usando manual...", 'advertencia')
                    mensaje_final = redactar_manual_mejorado(noticia['titulo'], texto, noticia['tipo'], noticia['fuente'])
                else:
                    log("✅ Texto IA en español", 'exito')
            else:
                mensaje_final = redactar_manual_mejorado(noticia['titulo'], texto, noticia['tipo'], noticia['fuente'])
                log("✅ Texto manual", 'info')
            break
    
    if not seleccionada or not mensaje_final:
        log("❌ No procesable", 'error')
        return False
    
    if not verificar_espanol(mensaje_final):
        mensaje_final = redactar_manual_mejorado(seleccionada['titulo'], "noticia anime", seleccionada['tipo'], seleccionada['fuente'])
    
    mensaje_final = truncar_texto(mensaje_final, MAX_CARACTERES_FB)
    
    # Mostrar preview formateada
    print(f"\n{'='*50}")
    print(f"📝 PREVIEW:")
    print(f"{'='*50}")
    print(mensaje_final)
    print(f"{'='*50}")
    print(f"📊 Stats: {len(mensaje_final)} chars | Tipo: {seleccionada['tipo']} | Score: {seleccionada['puntaje']}")
    
    log("🖼️ Procesando imagen...", 'info')
    img_path = descargar_imagen(imagen_url) if imagen_url else None
    if not img_path:
        img_path = crear_imagen_default(seleccionada['titulo'])
    
    if not img_path:
        log("❌ Sin imagen, intentando texto solo...", 'error')
        exito = publicar_solo_texto(mensaje_final, FB_ACCESS_TOKEN)
    else:
        exito = publicar_facebook(mensaje_final, img_path)
        try:
            if os.path.exists(img_path): os.remove(img_path)
        except: pass
    
    if exito:
        historial = guardar_historial(historial, seleccionada['url'], seleccionada['titulo'])
        estado['ultima'] = datetime.now().isoformat()
        estado['hoy'] = estado.get('hoy', 0) + 1
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
