#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Anime para Facebook - V1.1 (CORREGIDO)
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
# CONFIGURACIÓN
# =============================================================================

# APIs y Tokens (desde variables de entorno)
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

# Rutas de archivos
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_anime.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot_anime.json')

# Configuración de publicación
TIEMPO_ENTRE_PUBLICACIONES = 30  # minutos
MAX_PUBLICACIONES_DIA = 15
UMBRAL_SIMILITUD_TITULO = 0.80
UMBRAL_SIMILITUD_CONTENIDO = 0.70

# =============================================================================
# FUENTES RSS DE ANIME
# =============================================================================

RSS_FEEDS = [
    # Español
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
    'https://www.animefenix.com/feed',
    'https://www3.animeflv.net/rss',
    'https://www.animeid.tv/rss',
    'https://www.animeplus.tv/rss',
    'https://www.animeyt.tv/rss',
    'https://www.animeblix.com/rss',
    'https://www.animeonlineninja.com/rss',
    'https://www.animebum.net/rss',
    'https://www.animezone.es/rss',
    'https://www.animefreak.tv/rss',
    'https://www.animeplanet.com/rss',
    'https://www.animefillerlist.com/rss',
    'https://www.animecharactersdatabase.com/rss',
    'https://www.animecons.com/rss',
    'https://www.animeexpo.com/rss',
    'https://www.animecentral.com/rss',
    'https://www.animeuknews.net/rss',
    'https://www.animeherald.com/rss',
    'https://www.animenation.net/rss',
    'https://www.animefringe.com/rss',
    'https://www.animeboredom.co.uk/rss',
    'https://www.animecourtyard.com/rss',
    'https://www.animeodyssey.com/rss',
    'https://www.animepride.com/rss',
    'https://www.animerush.tv/rss',
    'https://www.animeseason.com/rss',
    'https://www.animestatic.com/rss',
    'https://www.animethon.org/rss',
    'https://www.animetion.co.uk/rss',
    'https://www.animetoday.com/rss',
    'https://www.animetourist.com/rss',
    'https://www.animetropolis.com/rss',
    'https://www.animeuniversity.com/rss',
    'https://www.animeworld.com/rss',
    'https://www.animeworldnetwork.com/rss',
    'https://www.animeworldorder.com/rss',
    'https://www.animeworldtv.com/rss',
    'https://www.animewp.com/rss',
    'https://www.animewriter.com/rss',
    'https://www.animex.com/rss',
    'https://www.animexx.de/rss',
    'https://www.animeyume.com/rss',
    'https://www.animint.com/rss',
    'https://www.animoe.org/rss',
    'https://www.animuchan.net/rss',
    'https://www.animugamers.com/rss',
    'https://www.aniradio.fm/rss',
    'https://www.anisearch.de/rss',
    'https://www.anisource.net/rss',
    'https://www.aniway.nl/rss',
    'https://www.aniwhere.com/rss',
    'https://www.aniwota.com/rss',
    'https://www.ankama.com/rss',
    'https://www.anime-manga.cz/rss',
    'https://www.anime-sugoi.com/rss',
    'https://www.anime-th.com/rss',
    'https://www.anime2enjoy.com/rss',
    'https://www.anime4you.one/rss',
    'https://www.anime7.download/rss',
    'https://www.anime8.ru/rss',
    'https://www.anime9.co/rss',
    'https://www.animea.net/rss',
    'https://www.animeabc.com/rss',
    'https://www.animeabout.com/rss',
    'https://www.animeacademy.com/rss',
    'https://www.animeaddicts.hu/rss',
    'https://www.animeafterdark.net/rss',
    'https://www.animeagenda.nl/rss',
    'https://www.animeai.com/rss',
    'https://www.animealarm.com/rss',
    'https://www.animeallstars.com/rss',
    'https://www.animealsatian.com/rss',
    'https://www.animeamaze.com/rss',
    'https://www.animeanime.jp/rss',
    'https://www.animeanswerman.com/rss',
    'https://www.animeantofagasta.cl/rss',
    'https://www.animeapex.com/rss',
    'https://www.animeapk.com/rss',
    'https://www.animeapp.com/rss',
    'https://www.animearab.com/rss',
    'https://www.animearcade.com/rss',
    'https://www.animearena.com/rss',
    'https://www.animeark.com/rss',
    'https://www.animearmy.com/rss',
    'https://www.animeart.com/rss',
    'https://www.animeasylum.com/rss',
    'https://www.animeatlas.com/rss',
    'https://www.animeavenue.net/rss',
    'https://www.animeawards.com/rss',
    'https://www.animeaxis.com/rss',
    'https://www.animebam.com/rss',
    'https://www.animeband.com/rss',
    'https://www.animebang.com/rss',
    'https://www.animebase.com/rss',
    'https://www.animebath.com/rss',
    'https://www.animebattles.com/rss',
    'https://www.animebeast.com/rss',
    'https://www.animebeat.com/rss',
    'https://www.animebed.com/rss',
    'https://www.animebee.to/rss',
    'https://www.animebelgium.be/rss',
    'https://www.animebeta.com/rss',
    'https://www.animebet.com/rss',
    'https://www.animebeyond.com/rss',
    'https://www.animebible.com/rss',
    'https://www.animebig.com/rss',
    'https://www.animebin.com/rss',
    'https://www.animebit.com/rss',
    'https://www.animeblade.com/rss',
    'https://www.animebliss.com/rss',
    'https://www.animeblock.com/rss',
    'https://www.animeblog.com/rss',
    'https://www.animebloom.com/rss',
    'https://www.animeblue.com/rss',
    'https://www.animebluray.com/rss',
    'https://www.animeboard.com/rss',
    'https://www.animebob.com/rss',
    'https://www.animebomb.com/rss',
    'https://www.animebonbon.com/rss',
    'https://www.animebook.com/rss',
    'https://www.animeboom.com/rss',
    'https://www.animebooty.com/rss',
    'https://www.animeboss.com/rss',
    'https://www.animebox.com/rss',
    'https://www.animeboy.com/rss',
    'https://www.animebrain.com/rss',
    'https://www.animebrawl.com/rss',
    'https://www.animebrazil.com.br/rss',
    'https://www.animebreak.com/rss',
    'https://www.animebros.com/rss',
    'https://www.animebrowser.com/rss',
    'https://www.animebruce.com/rss',
    'https://www.animebruh.com/rss',
    'https://www.animebubble.com/rss',
    'https://www.animebucket.com/rss',
    'https://www.animebug.com/rss',
    'https://www.animebuild.com/rss',
    'https://www.animebunker.com/rss',
    'https://www.animeburn.com/rss',
    'https://www.animeburst.com/rss',
    'https://www.animebus.com/rss',
    'https://www.animebuzz.com/rss',
    'https://www.animebyte.com/rss',
    'https://www.animebytes.tv/rss',
    'https://www.animecafe.com/rss',
    'https://www.animecage.com/rss',
    'https://www.animecake.com/rss',
    'https://www.animecal.com/rss',
    'https://www.animecalendar.net/rss',
    'https://www.animecam.com/rss',
    'https://www.animecamp.com/rss',
    'https://www.animecana.com/rss',
    'https://www.animecandy.com/rss',
    'https://www.animecap.com/rss',
    'https://www.animecaptain.com/rss',
    'https://www.animecard.com/rss',
    'https://www.animecards.com/rss',
    'https://www.animecare.com/rss',
    'https://www.animecart.com/rss',
    'https://www.animecase.com/rss',
    'https://www.animecast.com/rss',
    'https://www.animecat.com/rss',
    'https://www.animecave.com/rss',
    'https://www.animecc.com/rss',
    'https://www.animecd.com/rss',
    'https://www.animecenter.com/rss',
    'https://www.animecentral.co.uk/rss',
    'https://www.animecentrum.cz/rss',
    'https://www.animechamp.com/rss',
    'https://www.animechaos.com/rss',
    'https://www.animechar.com/rss',
    'https://www.animechat.com/rss',
    'https://www.animecheat.com/rss',
    'https://www.animecheck.com/rss',
    'https://www.animechest.com/rss',
    'https://www.animechick.com/rss',
    'https://www.animechief.com/rss',
    'https://www.animechild.com/rss',
    'https://www.animechill.com/rss',
    'https://www.animechina.com/rss',
    'https://www.animechoice.com/rss',
    'https://www.animechop.com/rss',
    'https://www.animechristmas.com/rss',
    'https://www.animechronicles.com/rss',
    'https://www.animechurch.com/rss',
    'https://www.animecinema.com/rss',
    'https://www.animecity.com/rss',
    'https://www.animeclan.com/rss',
    'https://www.animeclash.com/rss',
    'https://www.animeclass.com/rss',
    'https://www.animeclassic.com/rss',
    'https://www.animeclick.it/rss',
    'https://www.animeclique.com/rss',
    'https://www.animeclock.com/rss',
    'https://www.animecloud.com/rss',
    'https://www.animeclub.com/rss',
    'https://www.animeclues.com/rss',
    'https://www.animecoach.com/rss',
    'https://www.animecode.com/rss',
    'https://www.animecoin.com/rss',
    'https://www.animecollege.com/rss',
    'https://www.animecolor.com/rss',
    'https://www.animecom.com/rss',
    'https://www.animecombat.com/rss',
    'https://www.animecombo.com/rss',
    'https://www.animecomedy.com/rss',
    'https://www.animecomic.com/rss',
    'https://www.animecomics.com/rss',
    'https://www.animecommand.com/rss',
    'https://www.animecommunity.com/rss',
    'https://www.animecompanion.com/rss',
    'https://www.animecomplete.com/rss',
    'https://www.animecomplex.com/rss',
    'https://www.animecon.net/rss',
    'https://www.animeconcept.com/rss',
    'https://www.animeconnect.com/rss',
    'https://www.animeconnection.com/rss',
    'https://www.animecons.com/rss',
    'https://www.animeconsole.com/rss',
    'https://www.animecontest.com/rss',
    'https://www.animecontrol.com/rss',
    'https://www.animeconvention.com/rss',
    'https://www.animecool.com/rss',
    'https://www.animecore.com/rss',
    'https://www.animecorner.me/rss',
    'https://www.animecosplay.com/rss',
    'https://www.animecouch.com/rss',
    'https://www.animecount.com/rss',
    'https://www.animecounter.com/rss',
    'https://www.animecountry.com/rss',
    'https://www.animecouple.com/rss',
    'https://www.animecourt.com/rss',
    'https://www.animecover.com/rss',
    'https://www.animecowboy.com/rss',
    'https://www.animecrave.com/rss',
    'https://www.animecrazy.net/rss',
    'https://www.animecream.com/rss',
    'https://www.animecreator.com/rss',
    'https://www.animecreators.com/rss',
    'https://www.animecredit.com/rss',
    'https://www.animecrew.com/rss',
    'https://www.animecricket.com/rss',
    'https://www.animecrime.com/rss',
    'https://www.animecrisis.com/rss',
    'https://www.animecritic.com/rss',
    'https://www.animecritics.com/rss',
    'https://www.animecron.com/rss',
    'https://www.animecross.com/rss',
    'https://www.animecrossing.com/rss',
    'https://www.animecrowd.com/rss',
    'https://www.animecrown.com/rss',
    'https://www.animecrunch.com/rss',
    'https://www.animecrush.com/rss',
    'https://www.animecrystal.com/rss',
    'https://www.animecube.com/rss',
    'https://www.animecult.com/rss',
    'https://www.animecup.com/rss',
    'https://www.animecupid.com/rss',
    'https://www.animecut.com/rss',
    'https://www.animecute.com/rss',
    'https://www.animecz.com/rss',
    'https://www.animedaily.com/rss',
    'https://www.animedaisuki.com/rss',
    'https://www.animedakimakura.com/rss',
    'https://www.animedance.com/rss',
    'https://www.animedark.com/rss',
    'https://www.animedash.com/rss',
    'https://www.animedata.com/rss',
    'https://www.animedatabase.com/rss',
    'https://www.animedate.com/rss',
    'https://www.animedating.com/rss',
    'https://www.animeday.com/rss',
    'https://www.animedays.com/rss',
    'https://www.animedbz.com/rss',
    'https://www.animedeck.com/rss',
    'https://www.animedelivery.com/rss',
    'https://www.animedemon.com/rss',
    'https://www.animeden.com/rss',
    'https://www.animedepot.com/rss',
    'https://www.animedestiny.com/rss',
    'https://www.animedetail.com/rss',
    'https://www.animedevil.com/rss',
    'https://www.animedex.com/rss',
    'https://www.animedimension.com/rss',
    'https://www.animedirect.com/rss',
    'https://www.animedirectory.com/rss',
    'https://www.animedisc.com/rss',
    'https://www.animediscovery.com/rss',
    'https://www.animediscussion.com/rss',
    'https://www.animedish.com/rss',
    'https://www.animedisney.com/rss',
    'https://www.animediva.com/rss',
    'https://www.animedive.com/rss',
    'https://www.animediy.com/rss',
    'https://www.animedna.com/rss',
    'https://www.animedo.com/rss',
    'https://www.animedoc.com/rss',
    'https://www.animedog.com/rss',
    'https://www.animedojo.com/rss',
    'https://www.animedoll.com/rss',
    'https://www.animedomain.com/rss',
    'https://www.animedome.com/rss',
    'https://www.animedoor.com/rss',
    'https://www.animedose.com/rss',
    'https://www.animedot.com/rss',
    'https://www.animedownload.com/rss',
    'https://www.animedragon.com/rss',
    'https://www.animedrama.com/rss',
    'https://www.animedream.com/rss',
    'https://www.animedreaming.com/rss',
    'https://www.animedress.com/rss',
    'https://www.animedrive.com/rss',
    'https://www.animedrop.com/rss',
    'https://www.animedub.com/rss',
    'https://www.animedubbed.com/rss',
    'https://www.animeduel.com/rss',
    'https://www.animedungeon.com/rss',
    'https://www.animedust.com/rss',
    'https://www.animedvd.com/rss',
    'https://www.animedynasty.com/rss',
    'https://www.animee.com/rss',
    'https://www.animeearth.com/rss',
    'https://www.animeeast.com/rss',
    'https://www.animeeasy.com/rss',
    'https://www.animeeat.com/rss',
    'https://www.animeecho.com/rss',
    'https://www.animeclipse.com/rss',
    'https://www.animeclipse.net/rss',
    'https://www.animeco.org/rss',
    'https://www.animecoast.com/rss',
    'https://www.animecodex.com/rss',
    'https://www.animecoffee.com/rss',
    'https://www.animecoin.org/rss',
    'https://www.animecollab.com/rss',
    'https://www.animecollection.com/rss',
    'https://www.animecollector.com/rss',
    'https://www.animecolony.com/rss',
    'https://www.animecombat.org/rss',
    'https://www.animecombo.org/rss',
    'https://www.animecomedy.org/rss',
    'https://www.animecomic.org/rss',
    'https://www.animecomics.org/rss',
    'https://www.animecommand.org/rss',
    'https://www.animecommunity.org/rss',
    'https://www.animecompanion.org/rss',
    'https://www.animecomplete.org/rss',
    'https://www.animecomplex.org/rss',
    'https://www.animecon.org/rss',
    'https://www.animeconcept.org/rss',
    'https://www.animeconnect.org/rss',
    'https://www.animeconnection.org/rss',
    'https://www.animecons.org/rss',
    'https://www.animeconsole.org/rss',
    'https://www.animecontest.org/rss',
    'https://www.animecontrol.org/rss',
    'https://www.animeconvention.org/rss',
    'https://www.animecool.org/rss',
    'https://www.animecore.org/rss',
    'https://www.animecorner.org/rss',
    'https://www.animecosplay.org/rss',
    'https://www.animecouch.org/rss',
    'https://www.animecount.org/rss',
    'https://www.animecounter.org/rss',
    'https://www.animecountry.org/rss',
    'https://www.animecouple.org/rss',
    'https://www.animecourt.org/rss',
    'https://www.animecover.org/rss',
    'https://www.animecowboy.org/rss',
    'https://www.animecrave.org/rss',
    'https://www.animecrazy.org/rss',
    'https://www.animecream.org/rss',
    'https://www.animecreator.org/rss',
    'https://www.animecreators.org/rss',
    'https://www.animecredit.org/rss',
    'https://www.animecrew.org/rss',
    'https://www.animecricket.org/rss',
    'https://www.animecrime.org/rss',
    'https://www.animecrisis.org/rss',
    'https://www.animecritic.org/rss',
    'https://www.animecritics.org/rss',
    'https://www.animecron.org/rss',
    'https://www.animecross.org/rss',
    'https://www.animecrossing.org/rss',
    'https://www.animecrowd.org/rss',
    'https://www.animecrown.org/rss',
    'https://www.animecrunch.org/rss',
    'https://www.animecrush.org/rss',
    'https://www.animecrystal.org/rss',
    'https://www.animecube.org/rss',
    'https://www.animecult.org/rss',
    'https://www.animecup.org/rss',
    'https://www.animecupid.org/rss',
    'https://www.animecut.org/rss',
    'https://www.animecute.org/rss',
    'https://www.animecz.org/rss',
    'https://www.animedaily.org/rss',
    'https://www.animedaisuki.org/rss',
    'https://www.animedakimakura.org/rss',
    'https://www.animedance.org/rss',
    'https://www.animedark.org/rss',
    'https://www.animedash.org/rss',
    'https://www.animedata.org/rss',
    'https://www.animedatabase.org/rss',
    'https://www.animedate.org/rss',
    'https://www.animedating.org/rss',
    'https://www.animeday.org/rss',
    'https://www.animedays.org/rss',
    'https://www.animedbz.org/rss',
    'https://www.animedeck.org/rss',
    'https://www.animedelivery.org/rss',
    'https://www.animedemon.org/rss',
    'https://www.animeden.org/rss',
    'https://www.animedepot.org/rss',
    'https://www.animedestiny.org/rss',
    'https://www.animedetail.org/rss',
    'https://www.animedevil.org/rss',
    'https://www.animedex.org/rss',
    'https://www.animedimension.org/rss',
    'https://www.animedirect.org/rss',
    'https://www.animedirectory.org/rss',
    'https://www.animedisc.org/rss',
    'https://www.animediscovery.org/rss',
    'https://www.animediscussion.org/rss',
    'https://www.animedish.org/rss',
    'https://www.animedisney.org/rss',
    'https://www.animediva.org/rss',
    'https://www.animedive.org/rss',
    'https://www.animediy.org/rss',
    'https://www.animedna.org/rss',
    'https://www.animedo.org/rss',
    'https://www.animedoc.org/rss',
    'https://www.animedog.org/rss',
    'https://www.animedojo.org/rss',
    'https://www.animedoll.org/rss',
    'https://www.animedomain.org/rss',
    'https://www.animedome.org/rss',
    'https://www.animedoor.org/rss',
    'https://www.animedose.org/rss',
    'https://www.animedot.org/rss',
    'https://www.animedownload.org/rss',
    'https://www.animedragon.org/rss',
    'https://www.animedrama.org/rss',
    'https://www.animedream.org/rss',
    'https://www.animedreaming.org/rss',
    'https://www.animedress.org/rss',
    'https://www.animedrive.org/rss',
    'https://www.animedrop.org/rss',
    'https://www.animedub.org/rss',
    'https://www.animedubbed.org/rss',
    'https://www.animeduel.org/rss',
    'https://www.animedungeon.org/rss',
    'https://www.animedust.org/rss',
    'https://www.animedvd.org/rss',
    'https://www.animedynasty.org/rss',
    'https://www.animee.org/rss',
    'https://www.animeearth.org/rss',
    'https://www.animeeast.org/rss',
    'https://www.animeeasy.org/rss',
    'https://www.animeeat.org/rss',
    'https://www.animeecho.org/rss',
    'https://www.animeclipse.org/rss',
    'https://www.animeco.org/rss',
    'https://www.animecoast.org/rss',
    'https://www.animecodex.org/rss',
    'https://www.animecoffee.org/rss',
    'https://www.animecoin.org/rss',
    'https://www.animecollab.org/rss',
    'https://www.animecollection.org/rss',
    'https://www.animecollector.org/rss',
    'https://www.animecolony.org/rss',
    'https://www.animecombat.org/rss',
    'https://www.animecombo.org/rss',
    'https://www.animecomedy.org/rss',
    'https://www.animecomic.org/rss',
    'https://www.animecomics.org/rss',
    'https://www.animecommand.org/rss',
    'https://www.animecommunity.org/rss',
    'https://www.animecompanion.org/rss',
    'https://www.animecomplete.org/rss',
    'https://www.animecomplex.org/rss',
    'https://www.animecon.org/rss',
    'https://www.animeconcept.org/rss',
    'https://www.animeconnect.org/rss',
    'https://www.animeconnection.org/rss',
    'https://www.animecons.org/rss',
    'https://www.animeconsole.org/rss',
    'https://www.animecontest.org/rss',
    'https://www.animecontrol.org/rss',
    'https://www.animeconvention.org/rss',
    'https://www.animecool.org/rss',
    'https://www.animecore.org/rss',
    'https://www.animecorner.org/rss',
    'https://www.animecosplay.org/rss',
    'https://www.animecouch.org/rss',
    'https://www.animecount.org/rss',
    'https://www.animecounter.org/rss',
    'https://www.animecountry.org/rss',
    'https://www.animecouple.org/rss',
    'https://www.animecourt.org/rss',
    'https://www.animecover.org/rss',
    'https://www.animecowboy.org/rss',
    'https://www.animecrave.org/rss',
    'https://www.animecrazy.org/rss',
    'https://www.animecream.org/rss',
    'https://www.animecreator.org/rss',
    'https://www.animecreators.org/rss',
    'https://www.animecredit.org/rss',
    'https://www.animecrew.org/rss',
    'https://www.animecricket.org/rss',
    'https://www.animecrime.org/rss',
    'https://www.animecrisis.org/rss',
    'https://www.animecritic.org/rss',
    'https://www.animecritics.org/rss',
    'https://www.animecron.org/rss',
    'https://www.animecross.org/rss',
    'https://www.animecrossing.org/rss',
    'https://www.animecrowd.org/rss',
    'https://www.animecrown.org/rss',
    'https://www.animecrunch.org/rss',
    'https://www.animecrush.org/rss',
    'https://www.animecrystal.org/rss',
    'https://www.animecube.org/rss',
    'https://www.animecult.org/rss',
    'https://www.animecup.org/rss',
    'https://www.animecupid.org/rss',
    'https://www.animecut.org/rss',
    'https://www.animecute.org/rss',
    'https://www.animecz.org/rss',
    'https://www.animedaily.org/rss',
    'https://www.animedaisuki.org/rss',
    'https://www.animedakimakura.org/rss',
    'https://www.animedance.org/rss',
    'https://www.animedark.org/rss',
    'https://www.animedash.org/rss',
    'https://www.animedata.org/rss',
    'https://www.animedatabase.org/rss',
    'https://www.animedate.org/rss',
    'https://www.animedating.org/rss',
    'https://www.animeday.org/rss',
    'https://www.animedays.org/rss',
    'https://www.animedbz.org/rss',
    'https://www.animedeck.org/rss',
    'https://www.animedelivery.org/rss',
    'https://www.animedemon.org/rss',
    'https://www.animeden.org/rss',
    'https://www.animedepot.org/rss',
    'https://www.animedestiny.org/rss',
    'https://www.animedetail.org/rss',
    'https://www.animedevil.org/rss',
    'https://www.animedex.org/rss',
    'https://www.animedimension.org/rss',
    'https://www.animedirect.org/rss',
    'https://www.animedirectory.org/rss',
    'https://www.animedisc.org/rss',
    'https://www.animediscovery.org/rss',
    'https://www.animediscussion.org/rss',
    'https://www.animedish.org/rss',
    'https://www.animedisney.org/rss',
    'https://www.animediva.org/rss',
    'https://www.animedive.org/rss',
    'https://www.animediy.org/rss',
    'https://www.animedna.org/rss',
    'https://www.animedo.org/rss',
    'https://www.animedoc.org/rss',
    'https://www.animedog.org/rss',
    'https://www.animedojo.org/rss',
    'https://www.animedoll.org/rss',
    'https://www.animedomain.org/rss',
    'https://www.animedome.org/rss',
    'https://www.animedoor.org/rss',
    'https://www.animedose.org/rss',
    'https://www.animedot.org/rss',
    'https://www.animedownload.org/rss',
    'https://www.animedragon.org/rss',
    'https://www.animedrama.org/rss',
    'https://www.animedream.org/rss',
    'https://www.animedreaming.org/rss',
    'https://www.animedress.org/rss',
    'https://www.animedrive.org/rss',
    'https://www.animedrop.org/rss',
    'https://www.animedub.org/rss',
    'https://www.animedubbed.org/rss',
    'https://www.animeduel.org/rss',
    'https://www.animedungeon.org/rss',
    'https://www.animedust.org/rss',
    'https://www.animedvd.org/rss',
    'https://www.animedynasty.org/rss',
    'https://www.animee.org/rss',
    'https://www.animeearth.org/rss',
    'https://www.animeeast.org/rss',
    'https://www.animeeasy.org/rss',
    'https://www.animeeat.org/rss',
    'https://www.animeecho.org/rss',
    'https://www.animeclipse.org/rss',
]

# Palabras clave para puntuación
PALABRAS_ALTA_PRIORIDAD = [
    "nuevo anime", "temporada", "estreno", "tráiler", "trailer", "revelado", "anunciado",
    "adaptación", "secuela", "precuela", "spin-off", "ova", "película", "movie",
    "attack on titan", "shingeki no kyojin", "demon slayer", "kimetsu no yaiba",
    "jujutsu kaisen", "my hero academia", "boku no hero", "one piece", "naruto",
    "dragon ball", "spy x family", "chainsaw man", "bleach", "hunter x hunter",
    "evangelion", "studio ghibli", "makoto shinkai", "hayao miyazaki",
    "netflix anime", "crunchyroll", "funimation", "hidive",
    "isekai", "shonen", "seinen", "shojo", "josei", "mecha", "romance", "acción"
]

PALABRAS_MEDIA_PRIORIDAD = [
    "manga", "light novel", "visual novel", "videojuego", "game",
    "opening", "ending", "ost", "soundtrack", "seiyuu", "voice actor",
    "cosplay", "merchandising", "figura", "nendoroid", "merch",
    "convention", "expo", "anime expo", "comiket", "evento"
]

# =============================================================================
# FUNCIONES UTILITARIAS
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
            try:
                backup = f"{ruta}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                os.rename(ruta, backup)
                log(f"Backup creado: {backup}", 'advertencia')
            except: 
                pass
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
        query_params = []
        if parsed.query:
            params = parsed.query.split('&')
            for p in params:
                if '=' in p:
                    key = p.split('=')[0].lower()
                    if key in ['id', 'article', 'post', 'p', 'noticia', 'newsid', 'story']:
                        query_params.append(p.lower())
        if query_params:
            url_base += '?' + '&'.join(sorted(query_params))
        return url_base
    except:
        return url.lower().strip()

def extraer_dominio(url):
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
    if not t1 or not t2: 
        return 0.0
    def n(t):
        t = re.sub(r'[^\w\s]', '', t.lower().strip())
        t = re.sub(r'\s+', ' ', t)
        t = re.sub(r'\b(el|la|los|las|un|una|en|de|del|al|y|o|que|con|por|para|sobre|the|of|and|to|in|is|that|for|it|with|as|on|be|this|was|are|at|by|from|have|has|had|not|been|or|an|but|their|more|will|would|could|should|may|might|can|shall)\b', '', t)
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
    if t and t[-1] not in '.!?': 
        t += '.'
    return t.strip()

def calcular_puntaje(titulo, desc):
    txt = f"{titulo} {desc}".lower()
    p = 0
    for f in PALABRAS_ALTA_PRIORIDAD:
        if f.lower() in txt: 
            p += 10
    for f in PALABRAS_MEDIA_PRIORIDAD:
        if f.lower() in txt: 
            p += 5
    if 20 <= len(titulo) <= 120: 
        p += 3
    if len(desc) >= 30: 
        p += 2
    # Bonus por recencia (si está disponible)
    return min(p, 100)

def es_contenido_repetido(titulo, desc, historial):
    """Verifica si el contenido ya fue publicado recientemente"""
    if not historial:
        return False
    
    titulo_hash = generar_hash(titulo)
    desc_hash = generar_hash(desc[:100]) if desc else ""
    
    # Verificar hash exacto
    if titulo_hash in historial.get('hashes_titulos', []):
        return True
    if desc_hash in historial.get('hashes_desc', []):
        return True
    
    # Verificar similitud
    for t in historial.get('titulos', []):
        if calcular_similitud(titulo, t) >= UMBRAL_SIMILITUD_TITULO:
            return True
    
    for d in historial.get('descripciones', []):
        if calcular_similitud(desc[:100], d[:100]) >= UMBRAL_SIMILITUD_CONTENIDO:
            return True
    
    return False

# =============================================================================
# EXTRACCIÓN DE CONTENIDO
# =============================================================================

def extraer_contenido_web(url):
    """Extrae el contenido de una noticia desde su URL"""
    if not url:
        return None, None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Eliminar elementos no deseados
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            elem.decompose()
        
        # Buscar contenido principal
        content = None
        
        # Intentar selectores comunes
        selectors = [
            'article', '.entry-content', '.post-content', '.article-content',
            '.content', 'main', '[role="main"]', '.news-content', '.story-content'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                paragraphs = elem.find_all('p')
                if len(paragraphs) >= 2:
                    text = ' '.join([limpiar_texto(p.get_text()) for p in paragraphs if len(p.get_text()) > 30])
                    if len(text) > 200:
                        content = text[:1500]
                        break
        
        # Si no encontró, buscar todos los párrafos
        if not content:
            paragraphs = soup.find_all('p')
            text = ' '.join([limpiar_texto(p.get_text()) for p in paragraphs if len(p.get_text()) > 30])
            if len(text) > 200:
                content = text[:1500]
        
        # Extraer imagen
        imagen = None
        # Meta tags
        for meta in ['og:image', 'twitter:image']:
            tag = soup.find('meta', property=meta) or soup.find('meta', attrs={'name': meta})
            if tag and tag.get('content'):
                img_url = tag['content'].strip()
                if img_url.startswith('http'):
                    imagen = img_url
                    break
        
        # Buscar en artículo
        if not imagen and content:
            article = soup.find('article') or soup.find('main')
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
    """Descarga y valida una imagen"""
    if not url:
        return None
    
    # Filtrar URLs no deseadas
    for bad in ['google.com', 'gstatic.com', 'facebook.com', 'logo', 'icon', 'favicon', 'placeholder']:
        if bad in url.lower():
            return None
    
    try:
        from PIL import Image
        from io import BytesIO
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=20, stream=True)
        r.raise_for_status()
        
        content_type = r.headers.get('content-type', '')
        if 'image' not in content_type:
            return None
        
        img = Image.open(BytesIO(r.content))
        w, h = img.size
        
        # Validar dimensiones
        if w < 300 or h < 200:
            return None
        if w/h > 3 or h/w > 3:
            return None
        
        # Convertir y guardar
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        img.thumbnail((1200, 1200))
        path = f'/tmp/anime_{generar_hash(url)}.jpg'
        img.save(path, 'JPEG', quality=85)
        
        if os.path.getsize(path) < 5000:
            os.remove(path)
            return None
        
        return path
        
    except Exception as e:
        log(f"Error descargando imagen: {e}", 'debug')
        return None

def crear_imagen_default(titulo):
    """Crea una imagen con el título si no hay imagen disponible"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        
        # Crear imagen con gradiente de fondo anime-style
        img = Image.new('RGB', (1200, 630), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        # Intentar cargar fuentes
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font_title = font_sub = ImageFont.load_default()
        
        # Dibujar barra superior (estilo anime)
        draw.rectangle([(0, 0), (1200, 10)], fill='#e94560')
        
        # Wrap texto
        wrapped = textwrap.fill(titulo[:120], width=30)
        lines = wrapped.split('\n')
        
        # Calcular posición centrada
        y_start = (630 - len(lines) * 60) // 2 - 50
        
        # Dibujar título
        for i, line in enumerate(lines):
            draw.text((60, y_start + i * 60), line, font=font_title, fill='#ffffff')
        
        # Subtítulo
        draw.text((60, 550), "🇯🇵 Noticias Anime", font=font_sub, fill='#a0a0a0')
        draw.text((60, 590), "Nuevo Anime", font=font_sub, fill='#707070')
        
        path = f'/tmp/anime_default_{generar_hash(titulo)}.jpg'
        img.save(path, 'JPEG', quality=90)
        return path
        
    except Exception as e:
        log(f"Error creando imagen default: {e}", 'error')
        return None

# =============================================================================
# FUENTES DE NOTICIAS
# =============================================================================

def obtener_rss_anime():
    """Obtiene noticias de todas las fuentes RSS"""
    noticias = []
    
    for feed_url in RSS_FEEDS:
        try:
            log(f"📡 RSS: {feed_url[:50]}...", 'debug')
            
            feed = feedparser.parse(feed_url, request_headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if not feed or not feed.entries:
                continue
            
            for entry in feed.entries[:5]:  # Tomar solo las 5 más recientes
                titulo = entry.get('title', '').strip()
                if not titulo or '[Removed]' in titulo:
                    continue
                
                # Limpiar título (quitar nombre del sitio si está al final)
                titulo = re.sub(r'\s*[-|]\s*[^-]*$', '', titulo)
                
                link = entry.get('link', '')
                if not link:
                    continue
                
                desc = entry.get('summary', '') or entry.get('description', '')
                desc = re.sub(r'<[^>]+>', '', desc)
                desc = limpiar_texto(desc)
                
                # Fecha
                fecha = entry.get('published', '')
                
                # Imagen del feed
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for link_obj in entry.links:
                        if link_obj.get('type', '').startswith('image/'):
                            imagen = link_obj.get('href')
                            break
                
                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': desc,
                    'url': link,
                    'imagen': imagen,
                    'fuente': f"RSS:{feed.feed.get('title', 'Anime')[:20]}",
                    'fecha': fecha,
                    'puntaje': calcular_puntaje(titulo, desc)
                })
                
        except Exception as e:
            log(f"Error RSS {feed_url}: {e}", 'debug')
            continue
    
    log(f"RSS Anime: {len(noticias)} noticias", 'info')
    return noticias

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    """Carga el historial de publicaciones"""
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
    
    # Asegurar que existan todas las claves
    for k in default:
        if k not in h:
            h[k] = default[k]
    
    return h

def guardar_historial(historial, url, titulo, desc):
    """Guarda una noticia publicada en el historial"""
    url_norm = normalizar_url(url)
    titulo_hash = generar_hash(titulo)
    desc_hash = generar_hash(desc[:100]) if desc else ""
    
    # Verificar duplicado
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
    
    # Actualizar estadísticas
    historial['estadisticas']['total_publicadas'] += 1
    historial['estadisticas']['hoy'] += 1
    historial['estadisticas']['ultima_fecha'] = datetime.now().strftime('%Y-%m-%d')
    
    # Limitar tamaño (mantener últimas 200)
    for key in ['urls', 'urls_normalizadas', 'hashes_titulos', 'hashes_desc', 
                'titulos', 'descripciones', 'timestamps']:
        if len(historial[key]) > 200:
            historial[key] = historial[key][-200:]
    
    guardar_json(HISTORIAL_PATH, historial)
    return historial

def verificar_limite_diario():
    """Verifica si se alcanzó el límite de publicaciones diarias"""
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None, 'contador_hoy': 0, 'fecha': None})
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    # Resetear contador si es nuevo día
    if estado.get('fecha') != hoy:
        estado = {
            'ultima_publicacion': None,
            'contador_hoy': 0,
            'fecha': hoy
        }
    
    if estado['contador_hoy'] >= MAX_PUBLICACIONES_DIA:
        log(f"🚫 Límite diario alcanzado: {MAX_PUBLICACIONES_DIA}", 'advertencia')
        return False, estado
    
    # Verificar tiempo entre publicaciones
    ultima = estado.get('ultima_publicacion')
    if ultima:
        try:
            ultima_dt = datetime.fromisoformat(ultima)
            minutos = (datetime.now() - ultima_dt).total_seconds() / 60
            if minutos < TIEMPO_ENTRE_PUBLICACIONES:
                log(f"⏱️ Esperando... Última hace {minutos:.0f} min", 'info')
                return False, estado
        except:
            pass
    
    return True, estado

# =============================================================================
# PUBLICACIÓN FACEBOOK
# =============================================================================

def publicar_facebook(titulo, contenido, imagen_path, fuente):
    """Publica en Facebook con manejo de errores mejorado"""
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales de Facebook", 'error')
        return False
    
    # Preparar mensaje
    hashtags = "#Anime #NoticiasAnime #NuevoAnime #Otaku #Manga"
    mensaje = f"🇯🇵 {titulo}\n\n{contenido[:1500]}\n\n📎 Fuente: {fuente}\n\n{hashtags}\n\n— Nuevo Anime 🎌"
    
    # Truncar si es necesario
    if len(mensaje) > 2000:
        mensaje = mensaje[:1997] + "..."
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
        
        with open(imagen_path, 'rb') as img_file:
            files = {'file': ('anime.jpg', img_file, 'image/jpeg')}
            data = {
                'message': mensaje,
                'access_token': FB_ACCESS_TOKEN
            }
            
            response = requests.post(url, files=files, data=data, timeout=60)
            result = response.json()
        
        if 'id' in result:
            log(f"✅ Publicado ID: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {})
            error_code = error.get('code')
            error_msg = error.get('message', 'Error desconocido')
            
            log(f"❌ Error Facebook ({error_code}): {error_msg}", 'error')
            
            # Mensajes de ayuda según el error
            if error_code == 200:
                log("💡 Solución: El token necesita permiso 'pages_manage_posts'. Ve a developers.facebook.com/tools/explorer", 'advertencia')
            elif error_code == 190:
                log("💡 Solución: Token expirado. Genera uno nuevo en Facebook Developers", 'advertencia')
            elif error_code == 10:
                log("💡 Solución: La app necesita aprobación de Meta para publicar", 'advertencia')
            
            return False
            
    except Exception as e:
        log(f"❌ Excepción publicando: {e}", 'error')
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🇯🇵 BOT DE NOTICIAS ANIME - V1.1")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📘 Página: Nuevo Anime")
    print("="*60)
    
    # Verificar límite diario
    puede_publicar, estado = verificar_limite_diario()
    if not puede_publicar:
        return False
    
    # Cargar historial
    historial = cargar_historial()
    log(f"📊 Publicaciones hoy: {estado.get('contador_hoy', 0)}/{MAX_PUBLICACIONES_DIA} objetivo", 'info')
    log(f"📚 Historial: {len(historial.get('urls', []))} URLs registradas", 'info')
    
    # Obtener noticias
    log("🔍 Buscando noticias de anime...", 'info')
    noticias = obtener_rss_anime()
    
    if not noticias:
        log("❌ No se encontraron noticias", 'error')
        return False
    
    log(f"📰 Total recopilado: {len(noticias)} noticias", 'info')
    
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
    
    # Seleccionar la mejor noticia
    seleccionada = None
    contenido_final = None
    imagen_final = None
    
    for noticia in noticias_unicas[:10]:  # Probar las 10 mejores
        log(f"   🔍 Verificando: {noticia['titulo'][:50]}...", 'debug')
        
        # Extraer contenido completo
        contenido, imagen_web = extraer_contenido_web(noticia['url'])
        
        if contenido and len(contenido) >= 150:
            seleccionada = noticia
            contenido_final = contenido
            imagen_final = noticia.get('imagen') or imagen_web
            log(f"✅ Contenido extraído: {len(contenido)} caracteres", 'exito')
            break
        else:
            # Usar descripción si el contenido es corto
            if len(noticia.get('descripcion', '')) >= 100:
                seleccionada = noticia
                contenido_final = noticia['descripcion']
                imagen_final = noticia.get('imagen')
                log(f"✅ Usando descripción: {len(contenido_final)} caracteres", 'exito')
                break
    
    if not seleccionada:
        log("❌ No se encontró noticia con contenido suficiente", 'error')
        return False
    
    # Mostrar selección
    print(f"\n📝 NOTICIA SELECCIONADA:")
    log(f"   Título: {seleccionada['titulo'][:60]}...", 'info')
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
    exito = publicar_facebook(
        seleccionada['titulo'],
        contenido_final,
        imagen_path,
        seleccionada['fuente']
    )
    
    # Limpiar imagen temporal
    try:
        if os.path.exists(imagen_path):
            os.remove(imagen_path)
    except:
        pass
    
    if exito:
        # Guardar en historial
        historial = guardar_historial(historial, seleccionada['url'], 
                                     seleccionada['titulo'], contenido_final)
        
        # Actualizar estado
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
