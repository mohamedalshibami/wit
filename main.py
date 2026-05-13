# ================= Witanime API - ScraperAPI Version (تصحيح الخطأ) =================
import requests
import json
import re
import base64
import urllib.parse
import xml.etree.ElementTree as ET
import time
from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup

app = FastAPI(title="Witanime API", description="API لاستخراج بيانات الأنمي عبر ScraperAPI", version="1.5")

website = "https://witanime.you/"
API_KEY = "bf565c4a886c08ff401e4999d76e451c"  # يفضل استخدام متغير بيئة
SCRAPERAPI_URL = "https://api.scraperapi.com/"

def scraperapi_get(target_url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            params = {'api_key': API_KEY, 'url': target_url}
            response = requests.get(SCRAPERAPI_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt == retries - 1:
                raise Exception(f"فشل بعد {retries} محاولات: {e}")
            time.sleep(2 ** attempt)

def get_post_id(url: str):
    try:
        html = scraperapi_get(url)
        shortlink = BeautifulSoup(html, "html.parser").find("link", rel="shortlink")
        if shortlink and shortlink.get("href"):
            match = re.search(r"p=(\d+)", shortlink["href"])
            if match:
                return match.group(1)
        return None
    except Exception:
        return None

def get_episode_data(post_id: str):
    if not post_id:
        return {"error": "لم يتم العثور على الـ ID أو الرابط غير صالح."}
    try:
        api_url = f"https://witanime.you/wp-json/custom-api/blue/ldo/frum/chd/not/loaded/v1/episode/{post_id}"
        text_response = scraperapi_get(api_url)
        data = json.loads(text_response)  # تصحيح الخطأ هنا
        meta = data.get("meta", {})
        return {
            "anime_name": data.get("taxonomy", {}).get("anime", ["غير متوفر"])[0],
            "episode_title": data.get("title", "غير متوفر"),
            "episode_number": meta.get("episode_number", "غير متوفر"),
            "views": meta.get("post_views_count", "غير متوفر"),
            "screenshot": meta.get("screenshot", "غير متوفر"),
            "streaming_servers": meta.get("servers", []),
            "download_links": {
                "FHD": meta.get("dfhd", []),
                "HD": meta.get("dhd", []),
                "SD": meta.get("dsd", []),
            },
        }
    except Exception as e:
        return {"error": f"خطأ أثناء جلب البيانات: {str(e)}"}

# ------------------- نهايات API -------------------
@app.get("/")
def root():
    return {
        "message": "مرحباً بك في Witanime API (عبر ScraperAPI - نسخة مصححة)",
        "endpoints": {
            "/episode-info": "GET?url=... - معلومات حلقة",
            "/episodes": "GET?page=1 - آخر الحلقات",
            "/search": "GET?q=... - بحث",
            "/anime": "GET?url=... - تفاصيل أنمي",
            "/anime-episodes": "GET?url=... - فك base64"
        }
    }

@app.get("/episode-info")
def episode_info(url: str = Query(...)):
    post_id = get_post_id(url)
    if not post_id:
        raise HTTPException(404, "لم يتم العثور على معرف الحلقة")
    return get_episode_data(post_id)

@app.get("/episodes")
def episodes(page: int = Query(1, ge=1)):
    try:
        page_url = f"{website}episode/" + (f"page/{page}/" if page > 1 else "")
        html = scraperapi_get(page_url)
        soup = BeautifulSoup(html, 'html.parser')
        titles = soup.select('.episodes-card-title h3 a')
        images = soup.select('.anime-card-poster img')
        result = [
            {"name": a.text.strip(), "url": a['href'], "image": img['src']}
            for a, img in zip(titles, images) if a and img
        ]
        return {"page": page, "episodes": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/search")
def search_anime(q: str = Query(...), page: int = Query(1, ge=1)):
    try:
        if page == 1:
            search_url = f"{website}?search_param=animes&s={q}"
        else:
            search_url = f"https://witanime.you/search/{q}/page/{page}/"
        html = scraperapi_get(search_url)
        soup = BeautifulSoup(html, 'html.parser')
        titles = soup.select('.anime-card-details h3 a')
        images = soup.select('.anime-card-poster img')
        results = [
            {"name": a.text.strip(), "url": a['href'], "image": img['src']}
            for a, img in zip(titles, images) if a and img
        ]
        return {"query": q, "page": page, "results": results}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/anime")
def anime_details(url: str = Query(...)):
    try:
        html = scraperapi_get(url)
        soup = BeautifulSoup(html, 'html.parser')
        rss_url = url.rstrip('/') + '/feed/'
        try:
            rss_text = scraperapi_get(rss_url)
            rss_ok = True
        except:
            rss_ok = False

        info = {}
        for div in soup.find_all('div', class_='anime-info'):
            span = div.find('span')
            if span:
                key = span.text.strip(':')
                value = div.text.replace(span.text, '').strip()
                info[key] = value
        story_tag = soup.find('p', class_='anime-story')
        if story_tag:
            info['story'] = story_tag.text.strip()

        title_tag = soup.find('h1', class_='anime-details-title')
        title = title_tag.text.strip() if title_tag else ""

        image_tag = soup.find('img', class_='thumbnail')
        image = image_tag.get('src', '') if image_tag else ""

        episodes = []
        if rss_ok:
            root_xml = ET.fromstring(rss_text)
            for item in root_xml.findall('.//item'):
                ep_title = item.findtext('title', 'بدون عنوان')
                ep_link = item.findtext('link', 'بدون رابط')
                episodes.append({"title": ep_title, "url": ep_link})

        return {"title": title, "image": image, "info": info, "episodes": episodes}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/anime-episodes")
def anime_episodes_base64(url: str = Query(...)):
    try:
        html = scraperapi_get(url)
        matches = re.findall(r"onclick=\"openEpisode\('([^']+)'\)\">([^<]+)</a>", html)
        episodes = []
        for encoded, title in matches:
            try:
                decoded_url = urllib.parse.unquote(base64.b64decode(encoded).decode())
                episodes.append({"title": title.strip(), "url": decoded_url})
            except:
                episodes.append({"title": title.strip(), "url": "فك التشفير فشل"})
        return {"episodes": episodes}
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
