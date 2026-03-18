#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Anime para Facebook - V2.1 (API ACTUALIZADA)
Correcciones: Google GenAI + Facebook Graph API v22 + Manejo de errores
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

# =============================================================================
# CONFIGURACIÓN - NUEVA API DE GOOGLE GENAI
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', os.path.join(BASE_DIR, 'data', 'historial_anime.json'))
ESTADO_PATH = os.getenv('ESTADO_PATH', os.path.join(BASE_DIR, 'data', 'estado_bot_anime.json'))

TIEMPO_ENTRE_PUBLICACIONES = 60
MAX_PUBLICACIONES_DIA = 24
UMBRAL_SIMILITUD_TITULO = 0.80

# NUEVO: Inicialización de Gemini con google-genai (API actualizada)
model = None
if GEMINI_API_KEY:
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        # Verificar que funciona
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Hola"
        )
        model = client  # Guardar el cliente
        print("✅ Gemini AI 2.0 Flash conectado correctamente")
    except Exception as e:
        print(f"⚠️ Error conectando Gemini: {e}")
        model = None
else:
    print("⚠️ No se encontró GEMINI_API_KEY - Se usará redacción básica")

# =============================================================================
# FUENTES RSS OPTIMIZADAS (solo las que funcionan)
# =============================================================================

RSS_FEEDS = [
    'https://somoskudasai.com/feed/',  # URL corregida
    'https://www.animenewsnetwork.com/all/rss.xml',
    'https://myanimelist.net/rss/news.xml',
    'https://otakumode.com/news/feed',
    'https://honeysanime.com/feed/',
    'https://animehunch.com/feed/',
    'https://www.anime-planet.com/rss',
]

PALABRAS_ANIME_POPULAR = [
    "attack on titan", "demon slayer", "jujutsu kaisen", "my hero academia", 
    "one piece", "spy x family", "chainsaw man", "dragon ball", "naruto",
    "bleach", "hunter x hunter", "evangelion", "studio ghibli"
]

PALABRAS_PERSONAJES = [
    "personaje", "protagonista", "seiyuu", "tanjiro", "goku", "luffy", 
    "gojo", "denji", "anya", "deku"
]

PALABRAS_HISTORIA = ["historia", "trama", "sinopsis", "arco", "saga", "temporada"]
PALABRAS_ESTRENO = ["estreno", "trailer", "nuevo anime", "temporada", "anunciado"]

# =============================================================================
# REDACCIÓN CON GEMINI 2.0 (API NUEVA)
# =============================================================================

def redactar_con_gemini(titulo, contenido, tipo="noticia"):
    """Usa Gemini 2.0 Flash para redactar publicaciones"""
    if not model:
        return None
    
    try:
        emojis_por_tipo = {
            "personaje": "🎭🎌✨🌟💫🗡️🛡️⚡🔥",
            "historia": "📖✨🎭🔮🌟⚔️🛡️💫🎪",
            "noticia": "🎌🔥✨📢🚨🎉🎊🌟💥⚡"
        }
        
        emojis = emojis_por_tipo.get(tipo, "✨🎌🔥")
        
        prompt = f"""Eres un redactor experto en anime para redes sociales. Crea una publicación viral para Facebook.

TÍTULO: {titulo}
CONTENIDO: {contenido[:600]}
TIPO: {tipo}

INSTRUCCIONES:
1. Escribe en español, entusiasta y natural
2. Usa MUCHOS emojis relevantes: {emojis}
3. Máximo 1500 caracteres
4. Incluye hashtags: #Anime #Otaku #NuevoAnime
5. Termina con pregunta para engagement
6. Destaca lo más importante primero

FORMATO:
🚨 [Título llamativo con emojis]

[Cuerpo con emojis y entusiasmo]

📎 Fuente: [mención breve]

[Hashtags]

¿Qué opinas? 👇"""

        response = model.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=800,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                ]
            )
        )
        
        if response and response.text:
            return response.text.strip()
        return None
        
    except Exception as e:
        print(f"⚠️ Error Gemini: {e}")
        return None

def detectar_tipo_contenido(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in PALABRAS_PERSONAJES[:3]): return "personaje"
    if any(p in texto for p in PALABRAS_HISTORIA[:3]): return "historia"
    if any(p in texto for p in PALABRAS_ESTRENO[:3]): return "estreno"
    return "noticia"

def generar_texto_manual(titulo, contenido, tipo="noticia", fuente=""):
    """Fallback si Gemini no funciona"""
    emojis = random.choice(["🎌", "✨", "🔥", "💫", "🌟", "🚨"])
    
    plantillas = {
        "personaje": f"{emojis} ¡Personaje destacado! 🎭\n\n{titulo}\n\n{contenido[:350]}...\n\n💬 ¿Favorito? 👇\n\n#Anime #Personajes",
        "historia": f"{emojis} ¡Historia épica! 📖\n\n{titulo}\n\n{contenido[:350]}...\n\n🔮 ¿La viste? 🤫\n\n#Anime #Historia",
        "noticia": f"{emojis} ¡Noticia anime! 🚨\n\n{titulo}\n\n{contenido[:350]}...\n\n🤔 ¿Opiniones? 👇\n\n#Anime #Noticias"
    }
    
    return plantillas.get(tipo, plantillas["noticia"])

# =============================================================================
# FUNCIONES UTILITARIAS
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
    t = re.sub(r'\s+', ' ', t)
    return hashlib.md5(t.encode()).hexdigest()

def normalizar_url(url):
    if not url: return ""
    try:
        parsed = urlparse(url)
        netloc = re.sub(r'^(www\.|m\.)', '', parsed.netloc.lower())
        path = re.sub(r'/index\.html?$', '/', parsed.path.lower().rstrip('/'))
        return f"{netloc}{path}"
    except:
        return url.lower().strip()

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
    p = sum(15 for f in PALABRAS_ANIME_POPULAR if f in txt)
    p += sum(10 for f in PALABRAS_ESTRENO if f in txt)
    p += 5 if 20 <= len(titulo) <= 120 else 0
    return min(p, 100)

def es_contenido_repetido(titulo, desc, historial):
    if not historial: return False
    titulo_hash = generar_hash(titulo)
    if titulo_hash in historial.get('hashes_titulos', []): return True
    for t in historial.get('titulos', []):
        if calcular_similitud(titulo, t) >= UMBRAL_SIMILITUD_TITULO: return True
    return False

# =============================================================================
# EXTRACCIÓN DE CONTENIDO
# =============================================================================

def extraer_contenido_web(url):
    if not url: return None, None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        for elem in soup(['script', 'style', 'nav', 'header', 'footer']): elem.decompose()
        
        content = None
        for selector in ['article', '.entry-content', '.post-content', 'main']:
            elem = soup.select_one(selector)
            if elem:
                paragraphs = elem.find_all('p')
                text = ' '.join([limpiar_texto(p.get_text()) for p in paragraphs if len(p.get_text()) > 30])
                if len(text) > 200:
                    content = text[:1500]
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
    for bad in ['google.com', 'gstatic.com', 'facebook.com', 'logo', 'icon']:
        if bad in url.lower(): return None
    
    try:
        from PIL import Image
        from io import BytesIO
        
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20, stream=True)
        content_type = r.headers.get('content-type', '')
        if 'image' not in content_type: return None
        
        img = Image.open(BytesIO(r.content))
        w, h = img.size
        if w < 400 or h < 300 or w/h > 3 or h/w > 3: return None
        
        if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
        img.thumbnail((1200, 1200))
        
        path = f'/tmp/anime_{generar_hash(url)[:8]}.jpg'
        img.save(path, 'JPEG', quality=90)
        
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
        
        img = Image.new('RGB', (1200, 630), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        draw.rectangle([(0, 0), (1200, 15)], fill='#e94560')
        draw.rectangle([(0, 615), (1200, 630)], fill='#16213e')
        
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font_title = font_sub = ImageFont.load_default()
        
        wrapped = textwrap.fill(titulo[:100], width=30)
        lines = wrapped.split('\n')
        y_start = (630 - len(lines) * 60) // 2 - 20
        
        for i, line in enumerate(lines):
            draw.text((60, y_start + i * 60), line, font=font_title, fill='#ffffff')
        
        draw.text((60, 540), "🇯🇵 Noticias Anime", font=font_sub, fill='#e94560')
        draw.text((60, 580), "🎌 Nuevo Anime", font=font_sub, fill='#a0a0a0')
        
        path = f'/tmp/anime_default_{generar_hash(titulo)[:8]}.jpg'
        img.save(path, 'JPEG', quality=95)
        return path
    except Exception as e:
        log(f"Error imagen default: {e}", 'error')
        return None

# =============================================================================
# FUENTES DE NOTICIAS
# =============================================================================

def obtener_rss_anime():
    noticias = []
    for feed_url in RSS_FEEDS:
        try:
            log(f"📡 RSS: {feed_url[:50]}...", 'debug')
            feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
            
            if not feed or not feed.entries: continue
            
            for entry in feed.entries[:6]:
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo: continue
                
                link = entry.get('link', '')
                if not link: continue
                
                desc = limpiar_texto(entry.get('summary', '') or entry.get('description', ''))
                desc = re.sub(r'<[^>]+>', '', desc)
                
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for link_obj in entry.links:
                        if link_obj.get('type', '').startswith('image/'):
                            imagen = link_obj.get('href')
                            break
                
                tipo = detectar_tipo_contenido(titulo, desc)
                
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
    
    log(f"📰 Total: {len(noticias)} noticias", 'info')
    return noticias

def extraer_dominio(url):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split('.')
        return '.'.join(parts[-2:]) if len(parts) > 2 else netloc
    except:
        return "anime"

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {
        'urls': [], 'urls_normalizadas': [], 'hashes_titulos': [],
        'titulos': [], 'timestamps': [],
        'estadisticas': {'total_publicadas': 0, 'hoy': 0, 'ultima_fecha': None}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h: h[k] = default[k]
    return h

def guardar_historial(historial, url, titulo, desc):
    url_norm = normalizar_url(url)
    if url_norm in historial.get('urls_normalizadas', []):
        log("⚠️ URL ya existe", 'advertencia')
        return historial
    
    historial['urls'].append(url)
    historial['urls_normalizadas'].append(url_norm)
    historial['hashes_titulos'].append(generar_hash(titulo))
    historial['titulos'].append(titulo)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['estadisticas']['total_publicadas'] += 1
    historial['estadisticas']['hoy'] += 1
    historial['estadisticas']['ultima_fecha'] = datetime.now().strftime('%Y-%m-%d')
    
    for key in ['urls', 'urls_normalizadas', 'hashes_titulos', 'titulos', 'timestamps']:
        if len(historial[key]) > 250:
            historial[key] = historial[key][-250:]
    
    guardar_json(HISTORIAL_PATH, historial)
    return historial

def verificar_limite_diario():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None, 'contador_hoy': 0, 'fecha': None})
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if estado.get('fecha') != hoy:
        estado = {'ultima_publicacion': None, 'contador_hoy': 0, 'fecha': hoy}
    
    if estado['contador_hoy'] >= MAX_PUBLICACIONES_DIA:
        log(f"🚫 Límite diario: {MAX_PUBLICACIONES_DIA}", 'advertencia')
        return False, estado
    
    ultima = estado.get('ultima_publicacion')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            minutos = (datetime.now() - ultima_dt).total_seconds() / 60
            if minutos < TIEMPO_ENTRE_PUBLICACIONES:
                log(f"⏱️ Esperando... {minutos:.0f}min/{TIEMPO_ENTRE_PUBLICACIONES}min", 'info')
                return False, estado
        except: pass
    
    return True, estado

# =============================================================================
# PUBLICACIÓN FACEBOOK (API V22 + MEJOR MANEJO DE ERRORES)
# =============================================================================

def publicar_facebook(mensaje, imagen_path):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales Facebook", 'error')
        return False
    
    # Verificar permisos del token primero
    try:
        debug_url = f"https://graph.facebook.com/v22.0/debug_token"
        debug_params = {
            'input_token': FB_ACCESS_TOKEN,
            'access_token': f"{FB_PAGE_ID}|{FB_ACCESS_TOKEN}"  # App token format
        }
        debug_resp = requests.get(debug_url, params=debug_params, timeout=10)
        debug_data = debug_resp.json()
        
        if 'data' in debug_data:
            token_data = debug_data['data']
            if not token_data.get('is_valid'):
                log(f"❌ Token inválido: {token_data.get('error', {}).get('message', 'Unknown')}", 'error')
                return False
            scopes = token_data.get('scopes', [])
            log(f"🔐 Token válido. Scopes: {scopes}", 'info')
            
            # Verificar permisos necesarios
            needed = ['pages_manage_posts', 'pages_read_engagement']
            missing = [p for p in needed if p not in scopes]
            if missing:
                log(f"⚠️ Faltan permisos: {missing}", 'advertencia')
    except Exception as e:
        log(f"⚠️ No se pudo verificar token: {e}", 'advertencia')
    
    # Intentar publicar
    try:
        # Método 1: Publicación con foto (requiere pages_manage_posts)
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as img_file:
            files = {'file': ('anime.jpg', img_file, 'image/jpeg')}
            data = {
                'message': mensaje[:2000],
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            
            response = requests.post(url, files=files, data=data, timeout=60)
            result = response.json()
        
        if 'id' in result or 'post_id' in result:
            post_id = result.get('post_id', result.get('id'))
            log(f"✅ Publicado: {post_id}", 'exito')
            return True
        
        # Si falla, intentar como feed post sin imagen
        error = result.get('error', {})
        error_code = error.get('code')
        error_msg = error.get('message', 'Unknown error')
        
        log(f"❌ Error Facebook ({error_code}): {error_msg}", 'error')
        
        # Si es error de permisos, intentar publicar solo texto
        if error_code == 200 or 'Permissions' in error_msg:
            log("🔄 Intentando publicar solo texto...", 'advertencia')
            return publicar_facebook_solo_texto(mensaje)
        
        return False
            
    except Exception as e:
        log(f"❌ Excepción: {e}", 'error')
        return False

def publicar_facebook_solo_texto(mensaje):
    """Fallback: publicar solo texto si las fotos fallan por permisos"""
    try:
        url = f"https://graph.facebook.com/v22.0/{FB_PAGE_ID}/feed"
        data = {
            'message': mensaje[:2000],
            'access_token': FB_ACCESS_TOKEN,
            'link': 'https://nuevo-anime.com'  # Link para preview
        }
        
        response = requests.post(url, data=data, timeout=30)
        result = response.json()
        
        if 'id' in result:
            log(f"✅ Publicado (solo texto): {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {})
            log(f"❌ Error texto ({error.get('code')}): {error.get('message')}", 'error')
            return False
    except Exception as e:
        log(f"❌ Error texto: {e}", 'error')
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    print("\n" + "="*70)
    print("🇯🇵 BOT ANIME V2.1 - Gemini 2.0 + Facebook API v22")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Gemini: {'✅' if model else '❌'} | FB: {'✅' if FB_ACCESS_TOKEN else '❌'}")
    print("="*70)
    
    puede_publicar, estado = verificar_limite_diario()
    if not puede_publicar:
        return False
    
    historial = cargar_historial()
    log(f"📊 Hoy: {estado.get('contador_hoy', 0)}/{MAX_PUBLICACIONES_DIA}", 'info')
    
    log("🔍 Buscando noticias...", 'info')
    noticias = obtener_rss_anime()
    
    if not noticias:
        log("❌ Sin noticias", 'error')
        return False
    
    noticias_unicas = [n for n in noticias if not es_contenido_repetido(n['titulo'], n['descripcion'], historial)]
    log(f"🎯 Únicas: {len(noticias_unicas)}", 'info')
    
    if not noticias_unicas:
        log("⚠️ Todo publicado", 'advertencia')
        return False
    
    noticias_unicas.sort(key=lambda x: x['puntaje'], reverse=True)
    
    seleccionada = None
    mensaje_final = None
    imagen_final = None
    
    for noticia in noticias_unicas[:10]:
        contenido, imagen_web = extraer_contenido_web(noticia['url'])
        texto_base = contenido if (contenido and len(contenido) >= 100) else noticia['descripcion']
        
        if len(texto_base) >= 80:
            seleccionada = noticia
            imagen_final = noticia.get('imagen') or imagen_web
            
            log(f"✍️ Generando texto ({'Gemini' if model else 'manual'})...", 'info')
            
            if model:
                mensaje_gemini = redactar_con_gemini(noticia['titulo'], texto_base, noticia['tipo'])
                mensaje_final = mensaje_gemini if mensaje_gemini else generar_texto_manual(noticia['titulo'], texto_base, noticia['tipo'], noticia['fuente'])
            else:
                mensaje_final = generar_texto_manual(noticia['titulo'], texto_base, noticia['tipo'], noticia['fuente'])
            break
    
    if not seleccionada or not mensaje_final:
        log("❌ No procesable", 'error')
        return False
    
    print(f"\n📝 {seleccionada['titulo'][:60]}... | {seleccionada['tipo']} | {seleccionada['puntaje']}pts")
    
    log("🖼️ Imagen...", 'info')
    imagen_path = descargar_imagen(imagen_final) if imagen_final else None
    if not imagen_path:
        imagen_path = crear_imagen_default(seleccionada['titulo'])
    
    if not imagen_path:
        log("❌ Sin imagen", 'error')
        return False
    
    log("📘 Publicando...", 'info')
    exito = publicar_facebook(mensaje_final, imagen_path)
    
    try:
        if os.path.exists(imagen_path): os.remove(imagen_path)
    except: pass
    
    if exito:
        historial = guardar_historial(historial, seleccionada['url'], seleccionada['titulo'], texto_base)
        estado['ultima_publicacion'] = datetime.now().isoformat()
        estado['contador_hoy'] = estado.get('contador_hoy', 0) + 1
        guardar_json(ESTADO_PATH, estado)
        log(f"✅ Total: {historial['estadisticas']['total_publicadas']}", 'exito')
        return True
    else:
        log("❌ Falló", 'error')
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
