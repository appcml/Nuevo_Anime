#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias ANIME para Facebook - V1.0
Publica 15+ noticias diarias de anime en español y comparte en historias
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

# ============================================
# CONFIGURACIÓN - VARIABLES DE ENTORNO
# ============================================

# Facebook (OBLIGATORIO)
FB_PAGE_ID = os.getenv('FB_PAGE_ID')  # ID de la página "Nuevo Anime"
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')  # Token de acceso de página

# APIs de Noticias (OPCIONAL pero recomendado)
NEWS_API_KEY = os.getenv('NEWS_API_KEY')  # newsapi.org
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')  # gnews.io

# Configuración de publicación
TIEMPO_ENTRE_PUBLICACIONES = 90  # Minutos entre posts (para 15+ diarias: ~90-96 min)
MIN_PUBLICACIONES_DIARIAS = 15
MAX_PUBLICACIONES_DIARIAS = 20

# Archivos de estado
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_anime.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot_anime.json')
IMAGENES_PATH = 'data/imagenes/'

# Umbrales anti-duplicados
UMBRAL_SIMILITUD_TITULO = 0.78
UMBRAL_SIMILITUD_CONTENIDO = 0.70
MAX_HISTORIAL = 200

# ============================================
# PALABRAS CLAVE PARA ANIME
# ============================================

PALABRAS_ALTA_PRIORIDAD = [
    "anime", "manga", "estreno", "temporada", "tráiler", "trailer", 
    "adaptación", "secuela", "nueva temporada", "fecha de estreno",
    "crunchyroll", "netflix anime", "simulcast", "ova", "película anime",
    "studio ghibli", "mappa", "ufotable", "wit studio", "a-1 pictures",
    "attack on titan", "one piece", "demon slayer", "kimetsu", "jujutsu kaisen",
    "spy x family", "chainsaw man", "my hero academia", "boku no hero",
    "dragon ball", "naruto", "boruto", "bleach", "hunter x hunter",
    "evangelion", "gundam", "isekai", "shonen", "seinen", "shojo",
    "voice actor", "seiyuu", "opening", "ending", "soundtrack",
    "cosplay", "convention", "expo", "anime expo", "comic con",
    "merchandising", "figura", "nendoroid", "manga plus", "shonen jump"
]

PALABRAS_MEDIA_PRIORIDAD = [
    "otaku", "waifu", "husbando", "weeb", "japon", "japón", "tokio",
    "akihabara", "light novel", "visual novel", "videojuego", "game",
    "collaboración", "crossover", "spin-off", "remake", "reboot",
    "doblaje", "latino", "español", "subtitulado", "fansub"
]

# Blacklist de títulos genéricos o no deseados
BLACKLIST_TITULOS = [
    r'^\s*última hora\s*$', 
    r'^\s*breaking news\s*$', 
    r'^\s*noticias de hoy\s*$',
    r'^\s*top\s+\d+\s*$',
    r'^\s*mejores\s+',
    r'^\s*peores\s+',
    r'.*\b(porn|hentai|xxx|adult|sex)\b.*'
]

# ============================================
# FUENTES RSS DE ANIME EN ESPAÑOL
# ============================================

FEEDS_RSS_ANIME = [
    # Español Latinoamérica / España
    'https://somoskudasai.com/noticias/feed/',  # Kudasai - Principal fuente ES
    'https://www.crunchyroll.com/es/news/rss',  # Crunchyroll News ES
    'https://www.crunchyroll.com/es-es/news/rss',  # Crunchyroll España
    'https://feeds.feedburner.com/crunchyroll/animenews',  # Feed alternativo
    
    # Ingles (con contenido traducible o relevante)
    'https://www.animenewsnetwork.com/all/rss.xml',  # ANN - Muy completo
    'https://myanimelist.net/rss/news.xml',  # MAL News
    'https://otakumode.com/news/feed',  # Tokyo Otaku Mode
    'https://honeysanime.com/feed/',  # Honey's Anime
    'https://anitrendz.net/news/feed/',  # Anime Trending
    'https://randomc.net/feed/',  # Random Curiosity (reviews y news)
    'https://theanimedaily.com/feed/',  # Anime Daily
    'https://animehunch.com/feed/',  # Animehunch
]

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================

def log(mensaje, tipo='info'):
    """Sistema de logging con emojis"""
    iconos = {
        'info': 'ℹ️', 
        'exito': '✅', 
        'error': '❌', 
        'advertencia': '⚠️', 
        'debug': '🔍',
        'anime': '🇯🇵',
        'facebook': '📘',
        'hora': '⏰'
    }
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    """Carga archivo JSON con manejo de errores"""
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else default.copy()
        except Exception as e:
            log(f"Error cargando JSON {ruta}: {e}", 'error')
            # Backup del archivo corrupto
            try:
                backup = f"{ruta}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                os.rename(ruta, backup)
                log(f"Backup creado: {backup}", 'advertencia')
            except:
                pass
    return default.copy()

def guardar_json(ruta, datos):
    """Guarda archivo JSON de forma atómica"""
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
    """Genera hash MD5 de texto normalizado"""
    if not texto:
        return ""
    t = re.sub(r'[^\w\s]', '', texto.lower().strip())
    t = re.sub(r'\s+', ' ', t)
    return hashlib.md5(t.encode()).hexdigest()

def normalizar_url(url):
    """Normaliza URL para detectar duplicados"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Remover www, m, mobile, amp
        netloc = re.sub(r'^(www\.|m\.|mobile\.|amp\.)', '', netloc)
        
        # Remover index.html, tracking params
        path = re.sub(r'/index\.(html|php|htm|asp)$', '/', path)
        path = path.rstrip('/')
        path = re.sub(r'\.html?$', '', path)
        
        # Reconstruir
        url_base = f"{netloc}{path}"
        
        # Mantener solo params esenciales
        query_params = []
        if parsed.query:
            params = parsed.query.split('&')
            for p in params:
                if '=' in p:
                    key = p.split('=')[0].lower()
                    if key in ['id', 'post', 'p', 'noticia', 'newsid', 'story', 'anime_id']:
                        query_params.append(p.lower())
        
        if query_params:
            url_base += '?' + '&'.join(sorted(query_params))
        
        return url_base
    except:
        return url.lower().strip()

def extraer_dominio(url):
    """Extrae dominio principal"""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split('.')
        if len(parts) > 2:
            return '.'.join(parts[-2:])
        return netloc
    except:
        return ""

def calcular_similitud(t1, t2):
    """Calcula similitud entre dos textos"""
    if not t1 or not t2:
        return 0.0
    
    def normalizar(t):
        t = re.sub(r'[^\w\s]', '', t.lower().strip())
        t = re.sub(r'\s+', ' ', t)
        # Quitar palabras comunes
        t = re.sub(r'\b(el|la|los|las|un|una|en|de|del|al|y|o|que|con|por|para|the|of|and|to|in|is|that|for|it)\b', '', t)
        return t.strip()
    
    return SequenceMatcher(None, normalizar(t1), normalizar(t2)).ratio()

def es_titulo_valido(titulo):
    """Verifica si el título es válido y no genérico"""
    if not titulo:
        return False
    
    tl = titulo.lower().strip()
    
    # Verificar blacklist
    for patron in BLACKLIST_TITULOS:
        if re.match(patron, tl):
            return False
    
    # Debe tener al menos 4 palabras significativas
    stop_words = {'el','la','de','y','en','the','of','to','hoy','a','con'}
    palabras = [p for p in re.findall(r'\b\w+\b', tl) 
                if p not in stop_words and len(p) > 3]
    
    return len(set(palabras)) >= 4

def limpiar_texto(texto):
    """Limpia HTML y normaliza texto"""
    if not texto:
        return ""
    import html
    t = html.unescape(texto)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'https?://\S*', '', t)
    t = t.strip()
    if t and t[-1] not in '.!?':
        t += '.'
    return t.strip()

def calcular_puntaje_anime(titulo, descripcion):
    """Calcula puntaje de relevancia para anime"""
    texto = f"{titulo} {descripcion}".lower()
    puntaje = 0
    
    # Palabras de alta prioridad
    for palabra in PALABRAS_ALTA_PRIORIDAD:
        if palabra.lower() in texto:
            puntaje += 8
            # Bonus si está en el título
            if palabra.lower() in titulo.lower():
                puntaje += 5
    
    # Palabras de media prioridad
    for palabra in PALABRAS_MEDIA_PRIORIDAD:
        if palabra.lower() in texto:
            puntaje += 2
    
    # Bonus por longitud adecuada
    if 40 <= len(titulo) <= 120:
        puntaje += 3
    
    if len(descripcion) >= 80:
        puntaje += 2
    
    # Bonus por contenido multimedia mencionado
    if any(x in texto for x in ['tráiler', 'trailer', 'video', 'imagen', 'foto', 'visual']):
        puntaje += 3
    
    return puntaje

# ============================================
# GESTIÓN DE HISTORIAL
# ============================================

def cargar_historial():
    """Carga historial de publicaciones"""
    default = {
        'urls': [],
        'urls_normalizadas': [],
        'hashes': [],
        'timestamps': [],
        'titulos': [],
        'descripciones': [],
        'hashes_contenido': [],
        'hashes_permanentes': [],
        'estadisticas': {
            'total_publicadas': 0,
            'hoy_publicadas': 0,
            'ultima_fecha': None
        }
    }
    
    h = cargar_json(HISTORIAL_PATH, default)
    
    # Asegurar que existan todas las claves
    for k in default:
        if k not in h:
            h[k] = default[k]
    
    # Resetear contador diario si es nuevo día
    hoy = datetime.now().strftime('%Y-%m-%d')
    if h['estadisticas'].get('ultima_fecha') != hoy:
        h['estadisticas']['hoy_publicadas'] = 0
        h['estadisticas']['ultima_fecha'] = hoy
    
    limpiar_historial_antiguo(h)
    return h

def limpiar_historial_antiguo(h):
    """Limpia entradas antiguas del historial"""
    try:
        ahora = datetime.now()
        indices_mantener = []
        
        for i, ts in enumerate(h.get('timestamps', [])):
            try:
                fecha = datetime.fromisoformat(ts)
                if (ahora - fecha).days < 3:  # Mantener 3 días
                    indices_mantener.append(i)
            except:
                continue
        
        # Filtrar listas
        for key in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 
                    'titulos', 'descripciones', 'hashes_contenido']:
            if key in h and isinstance(h[key], list):
                h[key] = [h[key][i] for i in indices_mantener if i < len(h[key])]
        
        # Limitar hashes permanentes
        if len(h.get('hashes_permanentes', [])) > 150:
            h['hashes_permanentes'] = h['hashes_permanentes'][-150:]
            
    except Exception as e:
        log(f"Error limpiando historial: {e}", 'error')

def noticia_ya_publicada(h, url, titulo, desc=""):
    """Verifica si una noticia ya fue publicada (múltiples métodos)"""
    if not h:
        return False, "sin_historial"
    
    url_n = normalizar_url(url)
    hash_t = generar_hash(titulo)
    hash_d = generar_hash(desc[:200]) if desc else ""
    dominio = extraer_dominio(url)
    
    log(f"   🔍 Verificando: {titulo[:50]}...", 'debug')
    
    # 1. Verificar URL normalizada
    for uh in h.get('urls_normalizadas', []):
        if isinstance(uh, str) and url_n == uh:
            return True, "url_duplicada"
    
    # 2. Verificar mismo dominio + título similar
    for i, uh in enumerate(h.get('urls', [])):
        if not isinstance(uh, str):
            continue
        if extraer_dominio(uh) == dominio:
            titulo_h = h['titulos'][i] if i < len(h['titulos']) else ""
            if titulo_h and calcular_similitud(titulo, titulo_h) >= 0.85:
                return True, "misma_noticia_sitio"
    
    # 3. Verificar hash de título
    todos_hashes = list(dict.fromkeys(
        h.get('hashes', []) + h.get('hashes_permanentes', [])
    ))
    if hash_t in todos_hashes:
        return True, "hash_titulo"
    
    # 4. Verificar hash de contenido
    if hash_d and hash_d in h.get('hashes_contenido', []):
        return True, "hash_contenido"
    
    # 5. Verificar similitud de títulos
    for th in h.get('titulos', []):
        if isinstance(th, str) and calcular_similitud(titulo, th) >= UMBRAL_SIMILITUD_TITULO:
            return True, f"similitud_titulo"
    
    # 6. Verificar similitud de descripción
    if desc:
        for dh in h.get('descripciones', []):
            if isinstance(dh, str) and dh:
                if calcular_similitud(desc[:150], dh[:150]) >= UMBRAL_SIMILITUD_CONTENIDO:
                    return True, "similitud_contenido"
    
    return False, "nuevo"

def guardar_historial(h, url, titulo, desc=""):
    """Guarda noticia en historial"""
    # Asegurar listas
    for k in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 
              'titulos', 'descripciones', 'hashes_contenido', 'hashes_permanentes']:
        if k not in h:
            h[k] = []
    
    if 'estadisticas' not in h:
        h['estadisticas'] = {'total_publicadas': 0, 'hoy_publicadas': 0, 'ultima_fecha': None}
    
    url_n = normalizar_url(url)
    hash_t = generar_hash(titulo)
    
    # Doble verificación
    if url_n in h.get('urls_normalizadas', []):
        log("⚠️ Intento de duplicado detectado", 'advertencia')
        return h
    
    # Agregar datos
    h['urls'].append(url)
    h['urls_normalizadas'].append(url_n)
    h['hashes'].append(hash_t)
    h['timestamps'].append(datetime.now().isoformat())
    h['titulos'].append(titulo)
    h['descripciones'].append(desc[:500] if desc else "")
    h['hashes_contenido'].append(generar_hash(desc[:200]) if desc else "")
    h['hashes_permanentes'].append(hash_t)
    
    # Actualizar estadísticas
    h['estadisticas']['total_publicadas'] += 1
    h['estadisticas']['hoy_publicadas'] += 1
    hoy = datetime.now().strftime('%Y-%m-%d')
    h['estadisticas']['ultima_fecha'] = hoy
    
    # Limitar tamaño
    for k in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 
              'titulos', 'descripciones', 'hashes_contenido']:
        if len(h[k]) > MAX_HISTORIAL:
            h[k] = h[k][-MAX_HISTORIAL:]
    
    if len(h['hashes_permanentes']) > 300:
        h['hashes_permanentes'] = h['hashes_permanentes'][-300:]
    
    if guardar_json(HISTORIAL_PATH, h):
        log(f"💾 Historial guardado: {h['estadisticas']['hoy_publicadas']} hoy, {h['estadisticas']['total_publicadas']} total", 'exito')
    
    return h

# ============================================
# OBTENCIÓN DE NOTICIAS
# ============================================

def obtener_rss_anime():
    """Obtiene noticias de feeds RSS de anime"""
    noticias = []
    
    for feed_url in FEEDS_RSS_ANIME:
        try:
            log(f"📡 RSS: {feed_url[:50]}...", 'debug')
            
            # Configurar headers para evitar bloqueos
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Parsear feed
            feed = feedparser.parse(feed_url, request_headers=headers)
            
            if not feed or not feed.entries:
                continue
            
            fuente_nombre = feed.feed.get('title', 'Anime RSS')[:25]
            
            for entry in feed.entries[:15]:  # Tomar últimas 15
                titulo = entry.get('title', '')
                if not titulo or '[Removed]' in titulo:
                    continue
                
                # Limpiar título (quitar sufijos de fuente)
                titulo = re.sub(r'\s*[-–|]\s*[^-]*$', '', titulo)
                
                link = entry.get('link', '')
                if not link:
                    continue
                
                descripcion = entry.get('summary', '') or entry.get('description', '')
                descripcion = re.sub(r'<[^>]+>', '', descripcion)
                
                # Extraer imagen si existe
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for l in entry.links:
                        if l.get('type', '').startswith('image/'):
                            imagen = l.get('href')
                            break
                
                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': limpiar_texto(descripcion),
                    'url': link,
                    'imagen': imagen,
                    'fuente': f"RSS:{fuente_nombre}",
                    'fecha': entry.get('published', datetime.now().isoformat()),
                    'puntaje': calcular_puntaje_anime(titulo, descripcion)
                })
                
        except Exception as e:
            log(f"Error RSS {feed_url}: {e}", 'error')
            continue
    
    log(f"RSS Anime: {len(noticias)} noticias", 'info')
    return noticias

def obtener_newsapi_anime():
    """Busca noticias de anime via NewsAPI"""
    if not NEWS_API_KEY:
        return []
    
    noticias = []
    queries = [
        'anime estreno temporada',
        'manga adaptación anime',
        'crunchyroll anime',
        'netflix anime',
        'trailer anime',
        'seiyuu voice actor',
        'studio anime'
    ]
    
    for q in queries:
        try:
            url = 'https://newsapi.org/v2/everything'
            params = {
                'apiKey': NEWS_API_KEY,
                'q': q,
                'language': 'es',
                'sortBy': 'publishedAt',
                'pageSize': 5
            }
            
            r = requests.get(url, params=params, timeout=15).json()
            
            if r.get('status') == 'ok':
                for art in r.get('articles', []):
                    titulo = art.get('title', '')
                    if not titulo or '[Removed]' in titulo:
                        continue
                    
                    desc = art.get('description', '')
                    
                    noticias.append({
                        'titulo': limpiar_texto(titulo),
                        'descripcion': limpiar_texto(desc),
                        'url': art.get('url', ''),
                        'imagen': art.get('urlToImage'),
                        'fuente': f"NewsAPI:{art.get('source', {}).get('name', 'News')}",
                        'fecha': art.get('publishedAt'),
                        'puntaje': calcular_puntaje_anime(titulo, desc)
                    })
        except:
            continue
    
    log(f"NewsAPI Anime: {len(noticias)} noticias", 'info')
    return noticias

def obtener_gnews_anime():
    """Busca noticias de anime via GNews"""
    if not GNEWS_API_KEY:
        return []
    
    noticias = []
    queries = ['anime', 'manga', 'crunchyroll', 'otaku']
    
    for q in queries:
        try:
            url = 'https://gnews.io/api/v4/search'
            params = {
                'apikey': GNEWS_API_KEY,
                'q': q,
                'lang': 'es',
                'max': 10
            }
            
            r = requests.get(url, params=params, timeout=15).json()
            
            for art in r.get('articles', []):
                titulo = art.get('title', '')
                if not titulo:
                    continue
                
                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': limpiar_texto(art.get('description', '')),
                    'url': art.get('url', ''),
                    'imagen': art.get('image'),
                    'fuente': f"GNews:{art.get('source', {}).get('name', 'News')}",
                    'fecha': art.get('publishedAt'),
                    'puntaje': calcular_puntaje_anime(titulo, art.get('description', ''))
                })
        except:
            continue
    
    log(f"GNews Anime: {len(noticias)} noticias", 'info')
    return noticias

def scrapear_noticias_adicionales():
    """Scraping adicional de sitios específicos si es necesario"""
    noticias = []
    
    # Aquí puedes agregar scraping específico de sitios que no tengan RSS
    # Por ejemplo: AnimeFenix, JKAnime, etc. (respetando robots.txt)
    
    return noticias

# ============================================
# PROCESAMIENTO DE CONTENIDO
# ============================================

def extraer_contenido_web(url):
    """Extrae contenido completo de la URL"""
    if not url:
        return None, None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Remover elementos no deseados
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        # Buscar artículo
        articulo = soup.find('article')
        if articulo:
            parrafos = articulo.find_all('p')
            if len(parrafos) >= 3:
                texto = ' '.join([
                    limpiar_texto(p.get_text()) 
                    for p in parrafos 
                    if len(p.get_text()) > 40
                ])
                if len(texto) > 300:
                    return texto[:2000], None
        
        # Clases comunes de contenido
        for clase in ['entry-content', 'post-content', 'article-content', 'content']:
            elem = soup.find(class_=lambda x: x and clase in x.lower())
            if elem:
                parrafos = elem.find_all('p')
                if len(parrafos) >= 2:
                    texto = ' '.join([
                        limpiar_texto(p.get_text()) 
                        for p in parrafos 
                        if len(p.get_text()) > 40
                    ])
                    if len(texto) > 300:
                        return texto[:2000], None
        
        return None, None
        
    except Exception as e:
        log(f"Error extrayendo contenido: {e}", 'error')
        return None, None

def dividir_parrafos(texto, max_palabras=45):
    """Divide texto en párrafos para Facebook"""
    if not texto:
        return []
    
    oraciones = [
        o.strip() 
        for o in re.split(r'(?<=[.!?])\s+', texto) 
        if len(o.strip()) > 15
    ]
    
    if len(oraciones) < 3:
        return [texto] if len(texto) > 100 else []
    
    parrafos = []
    actual = []
    palabras = 0
    
    for i, oracion in enumerate(oraciones):
        actual.append(oracion)
        palabras += len(oracion.split())
        
        if palabras >= max_palabras or i == len(oraciones) - 1:
            if len(' '.join(actual).split()) >= 15:
                parrafos.append(' '.join(actual))
            actual = []
            palabras = 0
    
    return parrafos[:6]  # Máximo 6 párrafos

def construir_publicacion(titulo, contenido, creditos, fuente):
    """Construye el texto de la publicación para Facebook"""
    titulo_limpio = limpiar_texto(titulo)
    parrafos = dividir_parrafos(contenido)
    
    if len(parrafos) < 2:
        # Si no hay párrafos, dividir por oraciones
        oraciones = [
            o.strip() 
            for o in re.split(r'(?<=[.!?])\s+', contenido) 
            if len(o.strip()) > 20
        ]
        parrafos = [' '.join(oraciones[i:i+2]) for i in range(0, len(oraciones), 2)][:6]
    
    lineas = [f"🇯🇵 {titulo_limpio}", ""]
    
    for i, p in enumerate(parrafos):
        lineas.append(p)
        if i < len(parrafos) - 1:
            lineas.append("")
    
    lineas.extend(["", "────────────────────────", ""])
    
    if creditos:
        lineas.extend([f"✍️ {creditos}", ""])
    
    lineas.append(f"📎 Fuente: {fuente}")
    
    return '\n'.join(lineas)

def generar_hashtags_anime(titulo, contenido):
    """Genera hashtags relevantes para anime"""
    texto = f"{titulo} {contenido}".lower()
    hashtags = ['#Anime', '#Manga', '#Otaku', '#NoticiasAnime']
    
    # Hashtags temáticos
    temas = {
        r'estreno|nueva temporada|anuncio': '#NuevoAnime',
        r'tráiler|trailer|avance': '#Trailer',
        r'crunchyroll': '#Crunchyroll',
        r'netflix': '#NetflixAnime',
        r'one piece': '#OnePiece',
        r'attack on titan|shingeki': '#AttackOnTitan',
        r'demon slayer|kimetsu': '#DemonSlayer',
        r'jujutsu kaisen': '#JujutsuKaisen',
        r'spy x family': '#SpyXFamily',
        r'chainsaw man': '#ChainsawMan',
        r'studio ghibli': '#Ghibli',
        r'cosplay': '#Cosplay',
        r'figura|merchandising': '#FigurasAnime',
        r'seiyuu|voice actor': '#Seiyuu'
    }
    
    agregados = set()
    for patron, hashtag in temas.items():
        if re.search(patron, texto) and hashtag not in agregados:
            hashtags.append(hashtag)
            agregados.add(hashtag)
            if len(hashtags) >= 8:
                break
    
    return ' '.join(hashtags)

# ============================================
# IMÁGENES
# ============================================

def extraer_imagen_web(url):
    """Extrae imagen principal de la URL"""
    if not url:
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Meta tags Open Graph
        for meta in ['og:image', 'twitter:image']:
            tag = soup.find('meta', property=meta) or soup.find('meta', attrs={'name': meta})
            if tag:
                img_url = tag.get('content', '').strip()
                if img_url and img_url.startswith('http'):
                    return img_url
        
        # Buscar en artículo
        articulo = soup.find('article') or soup.find('main')
        if articulo:
            for img in articulo.find_all('img'):
                src = img.get('data-src') or img.get('src', '')
                if src and src.startswith('http') and not any(x in src.lower() for x in ['logo', 'icon', 'avatar']):
                    return src
        
        return None
        
    except:
        return None

def descargar_imagen(url):
    """Descarga y optimiza imagen"""
    if not url:
        return None
    
    # Filtrar URLs no deseadas
    bloqueados = ['google.com', 'gstatic.com', 'facebook.com', 'logo', 'icon', 'favicon', 'avatar']
    if any(b in url.lower() for b in bloqueados):
        return None
    
    try:
        from PIL import Image
        from io import BytesIO
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        r = requests.get(url, headers=headers, timeout=20, stream=True)
        
        if r.status_code != 200:
            return None
        
        content_type = r.headers.get('content-type', '')
        if 'image' not in content_type:
            return None
        
        img = Image.open(BytesIO(r.content))
        ancho, alto = img.size
        
        # Validar dimensiones
        if ancho < 400 or alto < 300:
            return None
        
        if ancho/alto > 4 or ancho/alto < 0.2:
            return None
        
        # Convertir a RGB si es necesario
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Redimensionar manteniendo proporción
        img.thumbnail((1200, 1200))
        
        # Guardar
        os.makedirs(IMAGENES_PATH, exist_ok=True)
        nombre = f"anime_{generar_hash(url)}.jpg"
        ruta = os.path.join(IMAGENES_PATH, nombre)
        
        img.save(ruta, 'JPEG', quality=85)
        
        # Verificar tamaño mínimo
        if os.path.getsize(ruta) < 5000:
            os.remove(ruta)
            return None
        
        return ruta
        
    except Exception as e:
        log(f"Error descargando imagen: {e}", 'error')
        return None

def crear_imagen_anime(titulo):
    """Crea imagen con título si no hay imagen disponible"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        
        # Crear imagen base con gradiente oscuro (estilo anime)
        img = Image.new('RGB', (1200, 630), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        # Fondo decorativo
        draw.rectangle([(0, 0), (1200, 8)], fill='#e94560')  # Línea roja anime
        
        # Fuentes
        try:
            fuente_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
            fuente_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            fuente_titulo = fuente_sub = ImageFont.load_default()
        
        # Título envuelto
        titulo_wrap = textwrap.fill(titulo[:120], width=32)
        lineas = titulo_wrap.split('\n')
        
        # Calcular posición centrada
        y = (630 - len(lineas) * 50) // 2 - 30
        
        # Dibujar título
        draw.text((60, y), titulo_wrap, font=fuente_titulo, fill='white')
        
        # Subtítulos
        draw.text((60, 540), "🇯🇵 Nuevo Anime", font=fuente_sub, fill='#e94560')
        draw.text((60, 580), "Noticias • Estrenos • Cultura Otaku", font=fuente_sub, fill='#888888')
        
        # Guardar
        os.makedirs(IMAGENES_PATH, exist_ok=True)
        nombre = f"anime_gen_{generar_hash(titulo)}.jpg"
        ruta = os.path.join(IMAGENES_PATH, nombre)
        
        img.save(ruta, 'JPEG', quality=90)
        return ruta
        
    except Exception as e:
        log(f"Error creando imagen: {e}", 'error')
        return None

# ============================================
# FACEBOOK API
# ============================================

def publicar_facebook_feed(titulo, texto, imagen_path, hashtags):
    """Publica en el feed de la página de Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False, None
    
    # Construir mensaje
    mensaje = f"{texto}\n\n{hashtags}\n\n— 🌸 Nuevo Anime | Tu fuente de noticias otaku"
    
    # Truncar si es muy largo
    if len(mensaje) > 2200:
        lineas = texto.split('\n')
        texto_corto = ""
        for linea in lineas:
            if len(texto_corto + linea + "\n") < 1800:
                texto_corto += linea + "\n"
            else:
                break
        mensaje = f"{texto_corto.rstrip()}\n\n[...]\n\n{hashtags}\n\n— 🌸 Nuevo Anime"
    
    # Limpiar URLs del mensaje (Facebook las agrega como preview)
    mensaje = re.sub(r'https?://\S+', '', mensaje)
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as f:
            files = {'file': ('anime.jpg', f, 'image/jpeg')}
            data = {
                'message': mensaje,
                'access_token': FB_ACCESS_TOKEN
            }
            
            r = requests.post(url, files=files, data=data, timeout=60)
            resultado = r.json()
        
        if 'id' in resultado:
            post_id = resultado['id']
            log(f"✅ Publicado en Feed: {post_id}", 'exito')
            return True, post_id
        else:
            error = resultado.get('error', {}).get('message', 'Unknown')
            log(f"❌ Error Facebook: {error}", 'error')
            return False, None
            
    except Exception as e:
        log(f"❌ Excepción publicando: {e}", 'error')
        return False, None

def compartir_historia_facebook(post_id, imagen_path):
    """
    Comparte la publicación en las historias de la página.
    Nota: Requiere permisos adicionales de Instagram/Facebook
    """
    if not post_id:
        return False
    
    try:
        # Método 1: Crear historia directa (requiere permisos específicos)
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/stories"
        
        with open(imagen_path, 'rb') as f:
            files = {'file': ('story.jpg', f, 'image/jpeg')}
            data = {
                'access_token': FB_ACCESS_TOKEN,
                'caption': '🇯🇵 Nueva noticia de anime'
            }
            
            r = requests.post(url, files=files, data=data, timeout=60)
            resultado = r.json()
        
        if 'id' in resultado:
            log(f"✅ Compartido en Historias: {resultado['id']}", 'exito')
            return True
        else:
            # No es error crítico, las historias pueden requerir configuración adicional
            log(f"⚠️ No se pudo compartir en historias (se requiere configuración adicional)", 'advertencia')
            return False
            
    except Exception as e:
        log(f"⚠️ Error en historias: {e}", 'advertencia')
        return False

def verificar_limite_diario():
    """Verifica si se alcanzó el límite de publicaciones diarias"""
    estado = cargar_json(ESTADO_PATH, {
        'ultima_publicacion': None,
        'publicaciones_hoy': 0,
        'fecha_ultima': None
    })
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    # Resetear si es nuevo día
    if estado.get('fecha_ultima') != hoy:
        estado['publicaciones_hoy'] = 0
        estado['fecha_ultima'] = hoy
        guardar_json(ESTADO_PATH, estado)
    
    return estado['publicaciones_hoy'] < MAX_PUBLICACIONES_DIARIAS, estado['publicaciones_hoy']

def verificar_tiempo_entre_posts():
    """Verifica si ha pasado suficiente tiempo desde la última publicación"""
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    
    ultima = estado.get('ultima_publicacion')
    if not ultima:
        return True
    
    try:
        ultima_dt = datetime.fromisoformat(ultima)
        minutos_transcurridos = (datetime.now() - ultima_dt).total_seconds() / 60
        
        if minutos_transcurridos < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"⏱️ Esperando... Última publicación hace {minutos_transcurridos:.0f} min", 'hora')
            return False
        
        return True
    except:
        return True

def actualizar_estado():
    """Actualiza el estado del bot"""
    estado = cargar_json(ESTADO_PATH, {
        'ultima_publicacion': None,
        'publicaciones_hoy': 0,
        'fecha_ultima': None
    })
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if estado.get('fecha_ultima') != hoy:
        estado['publicaciones_hoy'] = 0
        estado['fecha_ultima'] = hoy
    
    estado['ultima_publicacion'] = datetime.now().isoformat()
    estado['publicaciones_hoy'] = estado.get('publicaciones_hoy', 0) + 1
    
    guardar_json(ESTADO_PATH, estado)

# ============================================
# FUNCIÓN PRINCIPAL
# ============================================

def main():
    """Función principal del bot"""
    print("\n" + "="*60)
    print("🇯🇵 BOT DE NOTICIAS ANIME - V1.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📘 Página: Nuevo Anime")
    print("="*60)
    
    # Verificar credenciales
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales de Facebook", 'error')
        log("Configura FB_PAGE_ID y FB_ACCESS_TOKEN", 'error')
        return False
    
    # Verificar límites
    puede_publicar, publicadas_hoy = verificar_limite_diario()
    if not puede_publicar:
        log(f"✋ Límite diario alcanzado: {publicadas_hoy}/{MAX_PUBLICACIONES_DIARIAS}", 'advertencia')
        return False
    
    if not verificar_tiempo_entre_posts():
        return False
    
    log(f"📊 Publicaciones hoy: {publicadas_hoy}/{MIN_PUBLICACIONES_DIARIAS} objetivo", 'info')
    
    # Cargar historial
    historial = cargar_historial()
    log(f"📚 Historial: {len(historial.get('urls', []))} URLs registradas", 'info')
    
    # Obtener noticias de todas las fuentes
    todas_noticias = []
    
    log("🔍 Buscando noticias de anime...", 'anime')
    
    # 1. RSS (principal fuente)
    rss_noticias = obtener_rss_anime()
    todas_noticias.extend(rss_noticias)
    
    # 2. NewsAPI (si hay API key)
    if NEWS_API_KEY and len(todas_noticias) < 30:
        api_noticias = obtener_newsapi_anime()
        todas_noticias.extend(api_noticias)
    
    # 3. GNews (si hay API key)
    if GNEWS_API_KEY and len(todas_noticias) < 30:
        gnews_noticias = obtener_gnews_anime()
        todas_noticias.extend(gnews_noticias)
    
    # 4. Scraping adicional
    if len(todas_noticias) < 20:
        extra = scrapear_noticias_adicionales()
        todas_noticias.extend(extra)
    
    log(f"📰 Total recopilado: {len(todas_noticias)} noticias", 'info')
    
    if not todas_noticias:
        log("ERROR: No se encontraron noticias", 'error')
        return False
    
    # Deduplicación temporal
    urls_vistas = set()
    titulos_vistos = []
    noticias_unicas = []
    
    for noticia in todas_noticias:
        url_n = normalizar_url(noticia.get('url', ''))
        titulo = noticia.get('titulo', '')
        
        if url_n in urls_vistas:
            continue
        
        # Verificar similitud con títulos ya vistos en esta ejecución
        duplicado = False
        for t in titulos_vistos:
            if calcular_similitud(titulo, t) > 0.8:
                duplicado = True
                break
        
        if duplicado:
            continue
        
        urls_vistas.add(url_n)
        titulos_vistos.append(titulo)
        noticias_unicas.append(noticia)
    
    log(f"🎯 Noticias únicas: {len(noticias_unicas)}", 'info')
    
    # Ordenar por puntaje
    noticias_unicas.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Buscar noticia válida
    seleccionada = None
    contenido_final = None
    creditos = None
    intentos = 0
    max_intentos = min(50, len(noticias_unicas))
    
    for i, noticia in enumerate(noticias_unicas):
        if intentos >= max_intentos:
            break
        
        url = noticia.get('url', '')
        titulo = noticia.get('titulo', '')
        desc = noticia.get('descripcion', '')
        
        if not url or not titulo:
            continue
        
        intentos += 1
        
        # Verificar duplicados en historial
        es_dup, razon = noticia_ya_publicada(historial, url, titulo, desc)
        if es_dup:
            log(f"   ❌ Duplicado ({razon}): {titulo[:40]}...", 'debug')
            continue
        
        # Verificar título válido
        if not es_titulo_valido(titulo):
            log(f"   ❌ Título inválido: {titulo[:40]}...", 'debug')
            continue
        
        # Verificar puntaje mínimo
        if noticia.get('puntaje', 0) < 5:
            log(f"   ❌ Puntaje bajo ({noticia.get('puntaje', 0)}): {titulo[:40]}...", 'debug')
            continue
        
        log(f"\n📝 NOTICIA SELECCIONADA:", 'exito')
        log(f"   Título: {titulo[:60]}...", 'info')
        log(f"   Fuente: {noticia['fuente']}", 'info')
        log(f"   Puntaje: {noticia.get('puntaje', 0)}/100", 'info')
        
        # Extraer contenido completo
        contenido, creditos = extraer_contenido_web(url)
        
        if contenido and len(contenido) >= 200:
            log(f"   ✅ Contenido extraído: {len(contenido)} caracteres", 'exito')
            seleccionada = noticia
            contenido_final = contenido
            break
        else:
            # Usar descripción si el contenido es corto
            if len(desc) >= 150:
                log(f"   ⚠️ Usando descripción: {len(desc)} caracteres", 'advertencia')
                seleccionada = noticia
                contenido_final = desc
                break
            else:
                log(f"   ❌ Contenido insuficiente, siguiente...", 'advertencia')
                continue
    
    if not seleccionada:
        log("ERROR: No se encontró noticia válida después de revisar todas", 'error')
        return False
    
    # Construir publicación
    texto_publicacion = construir_publicacion(
        seleccionada['titulo'],
        contenido_final,
        creditos,
        seleccionada['fuente']
    )
    
    hashtags = generar_hashtags_anime(seleccionada['titulo'], contenido_final)
    
    # Procesar imagen
    log("🖼️ Procesando imagen...", 'info')
    ruta_imagen = None
    
    # 1. Intentar usar imagen de la noticia
    if seleccionada.get('imagen'):
        ruta_imagen = descargar_imagen(seleccionada['imagen'])
    
    # 2. Extraer de la web
    if not ruta_imagen:
        img_url = extraer_imagen_web(seleccionada['url'])
        if img_url:
            ruta_imagen = descargar_imagen(img_url)
    
    # 3. Crear imagen generada
    if not ruta_imagen:
        log("🎨 Creando imagen generada...", 'info')
        ruta_imagen = crear_imagen_anime(seleccionada['titulo'])
    
    if not ruta_imagen:
        log("ERROR: No se pudo obtener imagen", 'error')
        return False
    
    # Publicar en Facebook
    log("📘 Publicando en Facebook...", 'facebook')
    exito, post_id = publicar_facebook_feed(
        seleccionada['titulo'],
        texto_publicacion,
        ruta_imagen,
        hashtags
    )
    
    # Intentar compartir en historias (opcional)
    if exito and post_id:
        log("📱 Intentando compartir en historias...", 'facebook')
        compartir_historia_facebook(post_id, ruta_imagen)
    
    # Limpieza
    try:
        if os.path.exists(ruta_imagen):
            os.remove(ruta_imagen)
    except:
        pass
    
    # Guardar estado
    if exito:
        historial = guardar_historial(
            historial,
            seleccionada['url'],
            seleccionada['titulo'],
            seleccionada.get('descripcion', '') + ' ' + contenido_final[:400]
        )
        actualizar_estado()
        
        log(f"\n{'='*60}", 'exito')
        log(f"✅ ÉXITO - Publicación #{historial['estadisticas']['hoy_publicadas']} del día", 'exito')
        log(f"📊 Total histórico: {historial['estadisticas']['total_publicadas']} noticias", 'exito')
        log(f"{'='*60}\n", 'exito')
        return True
    else:
        log("❌ Falló la publicación", 'error')
        return False

def modo_daemon():
    """Ejecuta el bot en modo daemon para 15+ publicaciones diarias"""
    log("🤖 Iniciando modo DAEMON (15+ publicaciones diarias)", 'info')
    
    while True:
        try:
            exito = main()
            
            if exito:
                # Calcular espera hasta siguiente publicación
                # Para 15 publicaciones en 24h = cada 96 minutos
                espera_minutos = TIEMPO_ENTRE_PUBLICACIONES + random.randint(-10, 10)
                siguiente = datetime.now() + timedelta(minutes=espera_minutos)
                
                log(f"⏰ Siguiente publicación: {siguiente.strftime('%H:%M')}", 'hora')
                time.sleep(espera_minutos * 60)
            else:
                # Si falló, esperar menos tiempo para reintentar
                log("⏱️ Esperando 10 minutos para reintentar...", 'hora')
                time.sleep(600)
                
        except KeyboardInterrupt:
            log("👋 Bot detenido por usuario", 'info')
            break
        except Exception as e:
            log(f"💥 Error crítico: {e}", 'error')
            import traceback
            traceback.print_exc()
            time.sleep(300)  # Esperar 5 minutos antes de reintentar

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        modo_daemon()
    else:
        # Ejecución única
        try:
            exito = main()
            sys.exit(0 if exito else 1)
        except Exception as e:
            log(f"Error crítico: {e}", 'error')
            import traceback
            traceback.print_exc()
            sys.exit(1)
