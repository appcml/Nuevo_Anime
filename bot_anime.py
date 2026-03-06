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

historial = {'urls': [], 'titulos': [], 'personajes': [], 'ultima_publicacion': None}

if os.path.exists(HISTORIAL_FILE):
    try:
        with open(HISTORIAL_FILE, 'r', encoding='utf-8') as f:
            historial = json.load(f)
        print(f"📚 Historial: {len(historial['urls'])} publicaciones")
    except Exception as e:
        print(f"⚠️ Error cargando historial: {e}")

def guardar_historial(url, titulo, personaje=''):
    historial['urls'].append(url)
    historial['titulos'].append(titulo[:100])
    if personaje:
        historial['personajes'].append(personaje.lower())
    historial['ultima_publicacion'] = datetime.now().isoformat()
    
    for key in ['urls', 'titulos', 'personajes']:
        if key in historial:
            historial[key] = historial[key][-500:]
    
    try:
        with open(HISTORIAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
        print(f"💾 Historial guardado")
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
                   anime.get('title', {}).get('native') or 
                   'Anime')
    
    nombre_personaje = personaje.get('name', {}).get('full', 'Personaje')
    descripcion = personaje.get('description', '') or anime.get('description', '')
    
    if ya_publicado(f"{nombre_anime} {nombre_personaje}", nombre_personaje):
        return None
    
    return generar_texto_ia(
        tipo='invocacion',
        nombre_anime=nombre_anime,
        nombre_personaje=nombre_personaje,
        descripcion=descripcion,
        imagen=personaje.get('image', {}).get('large') or anime.get('coverImage', {}).get('extraLarge')
    )

def generar_contenido_personaje():
    print("\n🎯 Generando contenido tipo PERSONAJE...")
    
    personaje = buscar_personaje_jikan()
    if not personaje:
        return None
    
    nombre = personaje.get('name', '')
    about = personaje.get('about', '')
    
    if ya_publicado(nombre, nombre):
        return None
    
    animes = personaje.get('anime', [])
    anime_nombre = ''
    if animes:
        anime_nombre = animes[0].get('anime', {}).get('title', '')
    
    return generar_texto_ia(
        tipo='personaje',
        nombre_personaje=nombre,
        nombre_anime=anime_nombre,
        descripcion=about,
        imagen=personaje.get('images', {}).get('jpg', {}).get('image_url')
    )

def generar_contenido_retro():
    print("\n🎯 Generando contenido tipo RETRO...")
    
    retro_ids = [1, 30, 47, 57, 199, 200, 232, 235, 288, 358, 422, 431, 529, 552, 568]
    
    try:
        anime_id = random.choice(retro_ids)
        url = f"https://api.jikan.moe/v4/anime/{anime_id}/full"
        resp = requests.get(url, timeout=15)
        anime = resp.json().get('data', {})
        
        if not anime:
            return None
        
        titulo = anime.get('title', '')
        if ya_publicado(titulo):
            return None
        
        return generar_texto_ia(
            tipo='retro',
            nombre_anime=titulo,
            descripcion=anime.get('synopsis', ''),
            year=anime.get('year', 'desconocido'),
            imagen=anime.get('images', {}).get('jpg', {}).get('large_image_url')
        )
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return None

def generar_texto_ia(tipo, **kwargs):
    """Genera texto usando OpenRouter con modelos actualizados"""
    
    if not OPENROUTER_API_KEY:
        print("   ⚠️ No hay OPENROUTER_API_KEY, usando plantilla")
        return plantilla_anime(tipo, **kwargs)
    
    prompts = {
        'invocacion': f"""Eres un experto en anime redactando para la página "Nuevo Anime". Escribe una publicación sobre una invocación/criatura de anime.

DATOS:
Anime: {kwargs.get('nombre_anime', 'Desconocido')}
Nombre: {kwargs.get('nombre_personaje', 'Desconocido')}
Descripción base: {kwargs.get('descripcion', 'Sin descripción')[:400]}

ESTILO (Seguir EXACTAMENTE el formato del ejemplo de Baku):
1. Primera línea: "La invocación personal de [Personaje] es [Nombre], [descripción corta y épica]" + emoji
2. Descripción física detallada con bullet points usando emojis (ojos, extremidades, características)
3. "⚡ Poder de [habilidad]" + descripción de la habilidad principal
4. "🔥 Debilidad" + descripción de la debilidad
5. "🌿 Naturaleza" + características especiales
6. Cierre: Frase épica tipo "Una invocación temible... pero peligrosa incluso para quien la invoca 😰"

REGLAS:
- Usa MUCHOS emojis relevantes
- Lenguaje épico y emocionante
- NO menciones fuentes ni "según"
- Escribe como conocimiento general del anime
- Hashtags al final: #Anime #[NombreAnimeSinEspacios] #Invocación #NuevoAnime
- Máximo 900 caracteres""",

        'personaje': f"""Escribe una ficha de personaje de anime para "Nuevo Anime".

DATOS:
Nombre: {kwargs.get('nombre_personaje', 'Desconocido')}
Anime: {kwargs.get('nombre_anime', 'Desconocido')}
Descripción: {kwargs.get('descripcion', 'Sin descripción')[:400]}

ESTILO:
1. "[Nombre] es [descripción corta del personaje]" + emoji
2. Datos clave con emojis: Edad, ocupación, habilidades principales
3. Personalidad y características destacadas
4. Curiosidad interesante
5. Cierre épico tipo "¿Eres fan? ¡Doble tap! ❤️"

REGLAS:
- MUCHOS emojis (👤, 💪, ⚔️, 🛡️, 👁️, 🎭, 👑, 🔥)
- NO fuentes
- Hashtags: #Anime #[NombreAnime] #Personaje #NuevoAnime
- Máximo 900 caracteres""",

        'retro': f"""Escribe sobre un anime clásico/retro.

DATOS:
Anime: {kwargs.get('nombre_anime', 'Desconocido')}
Año: {kwargs.get('year', 'desconocido')}
Descripción: {kwargs.get('descripcion', 'Sin descripción')[:400]}

ESTILO:
1. "📼 [Nombre] ([Año]) 🎞️"
2. Sinopsis breve y atractiva
3. Por qué es legendario/impacto en la industria
4. Dato curioso nostálgico
5. "¿Lo viste? Comenta tu personaje favorito 👇"

REGLAS:
- Emojis retro (📼, 📺, 🎞️, 🌸, ⏳, 🏯)
- NO fuentes
- Hashtags: #AnimeRetro #Clásico #[NombreAnime] #Nostalgia #NuevoAnime
- Máximo 900 caracteres"""
    }
    
    prompt = prompts.get(tipo, prompts['personaje'])
    
    # Modelos actualizados que funcionan en OpenRouter (gratuitos)
    modelos = [
        "google/gemma-2-9b-it:free",
        "microsoft/phi-3-medium-128k-instruct:free",
        "nvidia/llama-3.1-nemotron-70b-instruct:free"
    ]
    
    for modelo in modelos:
        try:
            print(f"   🤖 Intentando con {modelo}...")
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'HTTP-Referer': 'https://facebook.com/nuevoanime',
                    'X-Title': 'Nuevo Anime Bot',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': modelo,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.8,
                    'max_tokens': 1200
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    texto = data['choices'][0]['message']['content']
                    texto = re.sub(r'^(TITULAR:|TEXTO:|PUBLICACIÓN:)\s*', '', texto, flags=re.I)
                    
                    print(f"   ✅ Texto generado: {len(texto)} caracteres")
                    return {
                        'texto': texto.strip(),
                        'imagen': kwargs.get('imagen', ''),
                        'titulo': kwargs.get('nombre_personaje', kwargs.get('nombre_anime', 'Anime')),
                        'tipo': tipo
                    }
            else:
                print(f"   ⚠️ Error {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            print(f"   ⚠️ Error modelo {modelo}: {e}")
            continue
    
    return plantilla_anime(tipo, **kwargs)

def plantilla_anime(tipo, **kwargs):
    """Plantillas manuales si falla la IA"""
    print("   📝 Usando plantilla manual...")
    
    if tipo == 'invocacion':
        emojis = ['👹', '✨', '🔥', '⚡', '🌪️', '💥', '🔮', '🌀']
        nombre = kwargs.get('nombre_personaje', 'Criatura Misteriosa')
        anime = kwargs.get('nombre_anime', 'Anime')
        
        texto = f"""👹 La invocación personal de {nombre} es {nombre}, una criatura mítica de increíble poder {random.choice(emojis)}

🐾 Características:
{random.choice(['👁️ Ojos penetrantes', '⚡ Aura eléctrica', '🔥 Cuerpo ígneo', '🌪️ Forma etérea'])}
{random.choice(['💪 Fuerza descomunal', '👹 Apariencia intimidante', '✨ Brillo místico', '🐾 Garras afiladas'])}

⚡ Poder principal: Control elemental devastador
Capaz de destruir todo a su paso 💥

🔥 Debilidad: Fuego intenso y ataques coordinados

🌿 Naturaleza: No muestra inteligencia humana, actúa por instinto puro 🐾

Una invocación temible... pero peligrosa incluso para quien la invoca 😰

#Anime #{anime.replace(' ', '')} #Invocación #NuevoAnime 🔥"""
    
    elif tipo == 'personaje':
        nombre = kwargs.get('nombre_personaje', '???')
        anime = kwargs.get('nombre_anime', '???')
        
        texto = f"""👤 {nombre} de {anime}

💪 Un personaje legendario que ha marcado época en el mundo del anime.

⚔️ Habilidades: Maestro del combate, estrategia brillante, poderes únicos
🎭 Personalidad: Determinado, carismático y complejo

🔥 Dato épico: Este personaje es considerado uno de los más icónicos de su serie.

¿Eres fan? ¡Doble tap! ❤️

#Anime #{anime.replace(' ', '')} #Personaje #NuevoAnime 👑"""
    
    else:
        anime = kwargs.get('nombre_anime', '???')
        year = kwargs.get('year', '???')
        
        texto = f"""📼 {anime} ({year}) 🎞️

Un clásico que definió una época dorada del anime ⭐

📺 Sinopsis: Una historia legendaria que cautivó a millones de fans alrededor del mundo.

🏆 Legado: Este anime sentó las bases para muchas series modernas.

🌸 ¿Lo recuerdas? Cuéntanos tus memorias favoritas 👇

#AnimeRetro #Clásico #{anime.replace(' ', '')} #Nostalgia #NuevoAnime 📼"""
    
    return {
        'texto': texto,
        'imagen': kwargs.get('imagen', ''),
        'titulo': kwargs.get('nombre_personaje', kwargs.get('nombre_anime', 'Anime')),
        'tipo': tipo
    }

# ==================== DESCARGA Y PUBLICACIÓN ====================

def descargar_imagen(url):
    if not url or not str(url).startswith('http'):
        print("   ⚠️ URL de imagen inválida")
        return None
    
    try:
        print(f"   🖼️ Descargando imagen...")
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content))
            
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            
            path = f'/tmp/anime_{hashlib.md5(str(url).encode()).hexdigest()[:8]}.jpg'
            img.save(path, 'JPEG', quality=90, optimize=True)
            
            print(f"   ✅ Imagen guardada: {path}")
            return path
        else:
            print(f"   ⚠️ Error HTTP {resp.status_code} al descargar imagen")
            
    except Exception as e:
        print(f"   ⚠️ Error descargando imagen: {e}")
    
    return None

def publicar_facebook(texto, img_path):
    """Publica en Facebook usando el método correcto para páginas"""
    
    if not FB_ACCESS_TOKEN:
        print("❌ Falta FB_ACCESS_TOKEN")
        return False
    
    print(f"\n   📝 PREVIEW ({len(texto)} caracteres):")
    print(f"   {'='*50}")
    lineas = texto.split('\n')
    for linea in lineas[:8]:
        preview = linea[:60] + "..." if len(linea) > 60 else linea
        print(f"   {preview}")
    if len(lineas) > 8:
        print(f"   ... ({len(lineas)-8} líneas más)")
    print(f"   {'='*50}")
    
    try:
        # MÉTODO CORREGIDO: Usar /photos para publicar con imagen
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
        
        with open(img_path, 'rb') as f:
            files = {'file': ('image.jpg', f, 'image/jpeg')}
            data = {
                'message': texto,
                'access_token': FB_ACCESS_TOKEN
            }
            
            print(f"   📤 Publicando en Facebook...")
            print(f"   🔗 URL: {url}")
            print(f"   📄 Page ID: {FB_PAGE_ID}")
            
            resp = requests.post(url, files=files, data=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200 and 'id' in result:
                post_id = result['id']
                print(f"   ✅ ¡PUBLICADO! ID: {post_id}")
                print(f"   🔗 https://facebook.com/{post_id}")
                return True
            else:
                error = result.get('error', {})
                error_msg = error.get('message', str(result))
                error_code = error.get('code', 'unknown')
                error_subcode = error.get('error_subcode', 'none')
                
                print(f"   ❌ Error Facebook ({error_code}/{error_subcode}): {error_msg}")
                
                # Mensajes de ayuda según el error
                if error_code == 200:
                    print("   💡 Solución: El token necesita permiso 'pages_manage_posts'")
                    print("   💡 Ve a: https://developers.facebook.com/tools/explorer/")
                    print("   💡 Asegúrate de seleccionar 'Página' y no 'Usuario'")
                elif error_code == 190:
                    print("   💡 El token expiró. Genera uno nuevo.")
                
    except Exception as e:
        print(f"   ❌ Error publicando: {e}")
        import traceback
        traceback.print_exc()
    
    return False

# ==================== MAIN ====================

def main():
    # Verificar credenciales
    if not FB_ACCESS_TOKEN:
        print("❌ ERROR: Falta FB_ACCESS_TOKEN")
        print("   Configúralo en GitHub Secrets o variable de entorno")
        return False
    
    if not FB_PAGE_ID:
        print("❌ ERROR: Falta FB_PAGE_ID")
        return False
    
    print(f"\n🔑 Configuración:")
    print(f"   FB_PAGE_ID: {FB_PAGE_ID}")
    print(f"   FB_ACCESS_TOKEN: {'Configurado (' + FB_ACCESS_TOKEN[:20] + '...)' if FB_ACCESS_TOKEN else 'No configurado'}")
    print(f"   OPENROUTER_API_KEY: {'Configurado' if OPENROUTER_API_KEY else 'No configurado (usando plantillas)'}")
    
    print("\n🎲 Seleccionando tipo de contenido...")
    
    estrategias = [
        ('invocacion', generar_contenido_invocacion),
        ('personaje', generar_contenido_personaje),
        ('retro', generar_contenido_retro),
    ]
    
    random.shuffle(estrategias)
    
    for tipo, funcion in estrategias:
        print(f"\n{'='*60}")
        print(f"🎌 INTENTANDO: {tipo.upper()}")
        print(f"{'='*60}")
        
        try:
            resultado = funcion()
            
            if not resultado:
                print("   ⏭️ Sin datos, probando siguiente tipo...")
                continue
            
            if ya_publicado(resultado['titulo']):
                print("   ⏭️ Ya publicado anteriormente...")
                continue
            
            img_path = descargar_imagen(resultado['imagen'])
            if not img_path:
                print("   ⏭️ No se pudo obtener imagen...")
                continue
            
            if publicar_facebook(resultado['texto'], img_path):
                guardar_historial(
                    resultado['imagen'], 
                    resultado['titulo'],
                    resultado['titulo']
                )
                
                try:
                    os.remove(img_path)
                    print(f"   🗑️ Imagen temporal eliminada")
                except:
                    pass
                
                print(f"\n{'='*60}")
                print("✅ ÉXITO - Publicación completada")
                print(f"{'='*60}")
                return True
            
            try:
                os.remove(img_path)
            except:
                pass
                
        except Exception as e:
            print(f"   💥 Error en {tipo}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n❌ No se pudo generar contenido nuevo después de intentar todas las opciones")
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        print(f"\n💥 Error crítico: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
