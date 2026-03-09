import requests
import random
import re
import hashlib
import os
import json
import time
from datetime import datetime
from PIL import Image
from io import BytesIO

# ==================== CONFIGURACIÓN ====================

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID', '878451012010195')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_FILE = 'historial_anime.json'

# EMOJIS POR CATEGORÍA
EMOJIS_CATEGORIA = {
    'invocacion': ['👹', '✨', '🔥', '⚡', '🌪️', '💥', '🔮', '🌀'],
    'personaje': ['👤', '💪', '⚔️', '🛡️', '👁️', '🎭', '👑', '🔥'],
    'tecnica': ['⚡', '🔥', '💨', '⚔️', '🎯', '💥', '✨', '🔮'],
    'retro': ['📼', '📺', '🎞️', '🌸', '⏳', '🏯', '🎌', '👾']
}

print("="*60)
print("🎌 BOT NUEVO ANIME - Generador de Contenido")
print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
print(f"📄 Página ID: {FB_PAGE_ID}")
print(f"🔑 Token configurado: {'Sí' if FB_ACCESS_TOKEN else 'No'}")
print("="*60)

# ==================== HISTORIAL ====================

historial = {'urls': [], 'titulos': [], 'personajes': [], 'ultima_publicacion': None, 'ultimo_estado': None}

if os.path.exists(HISTORIAL_FILE):
    try:
        with open(HISTORIAL_FILE, 'r', encoding='utf-8') as f:
            historial = json.load(f)
        print(f"📚 Historial: {len(historial['urls'])} publicaciones")
    except Exception as e:
        print(f"⚠️ Error cargando historial: {e}")

def guardar_historial(url, titulo, personaje='', estado='publicado'):
    historial['urls'].append(url)
    historial['titulos'].append(titulo[:100])
    if personaje:
        historial['personajes'].append(personaje.lower())
    historial['ultima_publicacion'] = datetime.now().isoformat()
    historial['ultimo_estado'] = estado
    
    for key in ['urls', 'titulos', 'personajes']:
        if key in historial:
            historial[key] = historial[key][-500:]
    
    try:
        with open(HISTORIAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
        print(f"💾 Historial guardado (estado: {estado})")
    except Exception as e:
        print(f"❌ Error guardando historial: {e}")

def ya_publicado(titulo, personaje=''):
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:30]
    
    for t in historial.get('titulos', []):
        t_simple = re.sub(r'[^\w]', '', t.lower())[:30]
        if titulo_simple and t_simple:
            coincidencia = sum(1 for a, b in zip(titulo_simple, t_simple) if a == b)
            if coincidencia / max(len(titulo_simple), len(t_simple)) > 0.7:
                print(f"   ⏭️ Ya publicado (título similar): {t[:50]}...")
                return True
    
    if personaje and personaje.lower() in historial.get('personajes', []):
        print(f"   ⏭️ Personaje ya publicado: {personaje}")
        return True
    
    return False

# ==================== APIS DE ANIME ====================

def buscar_anime_jikan_random():
    try:
        popular_anime_ids = [
            1, 21, 5114, 30276, 11757, 31964, 1535, 32281, 9253, 11061,
            20, 30, 47, 57, 199, 200, 232, 233, 235, 245, 288, 358,
            422, 431, 457, 508, 529, 552, 568, 578, 6702, 7791, 813,
            16498, 22319, 25777, 29803, 31240, 33486, 34599, 36474, 38000,
            39587, 40748, 41587, 42897, 43608, 44511, 45613, 47164, 48413
        ]
        
        anime_id = random.choice(popular_anime_ids)
        url = f"https://api.jikan.moe/v4/anime/{anime_id}/full"
        
        print(f"   🔍 Buscando anime ID: {anime_id}")
        resp = requests.get(url, timeout=15)
        data = resp.json()
        
        anime = data.get('data', {})
        if anime:
            print(f"   ✅ Encontrado: {anime.get('title', 'Desconocido')}")
            return anime
            
    except Exception as e:
        print(f"   ⚠️ Error Jikan: {e}")
    
    return None

def buscar_personaje_jikan():
    try:
        char_ids = [
            1, 2, 3, 5, 6, 8, 9, 11, 13, 14, 15, 16, 17, 18, 20, 22, 23, 25, 27, 28,
            40, 45, 50, 62, 71, 80, 91, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120,
            160, 170, 180, 200, 220, 240, 260, 280, 300, 320, 340, 360, 380, 400, 420, 440,
            460, 480, 500, 520, 540, 560, 580, 600, 620, 640, 660, 680, 700, 800, 900, 1000
        ]
        
        char_id = random.choice(char_ids)
        url = f"https://api.jikan.moe/v4/characters/{char_id}/full"
        
        print(f"   🔍 Buscando personaje ID: {char_id}")
        resp = requests.get(url, timeout=15)
        data = resp.json()
        
        char = data.get('data', {})
        if char:
            print(f"   ✅ Personaje: {char.get('name', 'Desconocido')}")
            return char
            
    except Exception as e:
        print(f"   ⚠️ Error Jikan Character: {e}")
    
    return None

def buscar_anilist_trending():
    query = """
    query {
      Page(page: 1, perPage: 20) {
        media(type: ANIME, sort: TRENDING_DESC) {
          id
          title { romaji english native }
          description
          coverImage { extraLarge large }
          characters(sort: FAVOURITES_DESC, page: 1, perPage: 3) {
            nodes {
              id
              name { full native }
              description
              image { large }
            }
          }
          genres
        }
      }
    }
    """
    
    try:
        print("   🔍 Buscando en AniList...")
        resp = requests.post(
            'https://graphql.anilist.co',
            json={'query': query},
            timeout=15
        )
        data = resp.json()
        
        medias = data.get('data', {}).get('Page', {}).get('media', [])
        if medias:
            anime = random.choice(medias)
            print(f"   ✅ AniList: {anime.get('title', {}).get('romaji', 'Desconocido')}")
            return anime
            
    except Exception as e:
        print(f"   ⚠️ Error AniList: {e}")
    
    return None

# ==================== GENERADORES DE CONTENIDO ====================

def generar_contenido_invocacion():
    print("\n🎯 Generando contenido tipo INVOCACIÓN...")
    
    anime = buscar_anilist_trending()
    if not anime:
        return None
    
    personajes = anime.get('characters', {}).get('nodes', [])
    if not personajes:
        return None
    
    personaje = random.choice(personajes)
    
    nombre_anime = (anime.get('title', {}).get('romaji') or 
                   anime.get('title', {}).get('english') or 
                  
