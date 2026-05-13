# ================= Witanime API - FastAPI Version =================
import requests
import re
import base64
import urllib.parse
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup

app = FastAPI(title="Witanime API", description="API لاستخراج بيانات الأنمي من witanime.you", version="1.0")

website = "https://witanime.you/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ------------------- Helper Functions -------------------
def get_post_id(url: str):
    try:
        html = requests.get(url, headers=HEADERS).text
        shortlink = BeautifulSoup(html, "html.parser").find("link", rel="shortlink")
        if shortlink and "href" in shortlink.attrs:
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
        response = requests.get(api_url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
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

# ------------------- API Endpoints -------------------
@app.get("/")
def root():
    return {
        "message": "مرحباً بك في Witanime API",
        "endpoints": {
            "/episode-info": "GET?url=... - معلومات حلقة معينة",
            "/episodes": "GET?page=1 - قائمة الحلقات من الأرشيف",
            "/search": "GET?q=اسم_الانمي&page=1 - البحث عن أنمي",
            "/anime": "GET?url=... - تفاصيل الأنمي (باستخدام RSS)",
            "/anime-episodes": "GET?url=... - استخراج الحلقات من صفحة الأنمي (Base64)"
        }
    }

@app.get("/episode-info")
def episode_info(url: str = Query(..., description="رابط الحلقة مثل: https://witanime.you/episode/...")):
    post_id = get_post_id(url)
    if not post_id:
        raise HTTPException(status_code=404, detail="لم يتم العثور على معرف الحلقة")
    return get_episode_data(post_id)

@app.get("/episodes")
def episodes(page: int = Query(1, ge=1, description="رقم الصفحة")):
    try:
        page_url = f"{website}episode/" + (f"page/{page}/" if page > 1 else "")
        soup = BeautifulSoup(requests.get(page_url, headers=HEADERS).text, 'html.parser')
        titles = soup.select('.episodes-card-title h3 a')
        images = soup.select('.anime-card-poster img')
        result = [
            {"name": a.text.strip(), "url": a['href'], "image": img['src']}
            for a, img in zip(titles, images)
        ]
        return {"page": page, "episodes": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
def search_anime(q: str = Query(..., description="اسم الأنمي للبحث"), page: int = Query(1, ge=1)):
    try:
        if page == 1:
            search_url = f"{website}?search_param=animes&s={q}"
        else:
            search_url = f"https://witanime.you/search/{q}/page/{page}/"
        soup = BeautifulSoup(requests.get(search_url, headers=HEADERS).text, 'html.parser')
        titles = soup.select('.anime-card-details h3 a')
        images = soup.select('.anime-card-poster img')
        results = [
            {"name": a.text.strip(), "url": a['href'], "image": img['src']}
            for a, img in zip(titles, images)
        ]
        return {"query": q, "page": page, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anime")
def anime_details(url: str = Query(..., description="رابط صفحة الأنمي مثل: https://witanime.you/anime/...")):
    try:
        soup = BeautifulSoup(requests.get(url, headers=HEADERS).text, 'html.parser')
        rss_url = url.rstrip('/') + '/feed/'
        rss_resp = requests.get(rss_url, headers=HEADERS)

        info = {}
        info_divs = soup.find_all('div', class_='anime-info')
        for div in info_divs:
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
        if rss_resp.ok:
            root = ET.fromstring(rss_resp.text)
            for item in root.findall('.//item'):
                ep_title = item.findtext('title', 'بدون عنوان')
                ep_link = item.findtext('link', 'بدون رابط')
                episodes.append({"title": ep_title, "url": ep_link})

        return {
            "title": title,
            "image": image,
            "info": info,
            "episodes": episodes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anime-episodes")
def anime_episodes_base64(url: str = Query(..., description="رابط صفحة الأنمي (الحلقات)")):
    try:
        html = requests.get(url, headers=HEADERS).text
        matches = re.findall(r"onclick=\"openEpisode\('([^']+)'\)\">([^<]+)</a>", html)
        episodes = []
        for encoded, title in matches:
            try:
                decoded_url = urllib.parse.unquote(base64.b64decode(encoded).decode())
                episodes.append({"title": title.strip(), "url": decoded_url})
            except Exception:
                episodes.append({"title": title.strip(), "url": "فك التشفير فشل"})
        return {"episodes": episodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
