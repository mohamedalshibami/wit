# ================= Witanime API - ScraperAPI Version =================
import requests
import re
import base64
import urllib.parse
import xml.etree.ElementTree as ET
import time
from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup

app = FastAPI(title="Witanime API", description="API لاستخراج بيانات الأنمي عبر ScraperAPI", version="1.4")

website = "https://witanime.you/"
API_KEY = "bf565c4a886c08ff401e4999d76e451c"  # مفتاح ScraperAPI
SCRAPERAPI_URL = "https://api.scraperapi.com/"

def scraperapi_get(target_url: str, retries: int = 3):
    """
    إرسال طلب عبر ScraperAPI وإعادة المحتوى (نص) مع إعادة محاولة تلقائية.
    """
    for attempt in range(retries):
        try:
            params = {
                'api_key': API_KEY,
                'url': target_url,
                # يمكن إضافة 'render' => 'true' إذا كان الموقع يستخدم JS لكن ليس مطلوباً هنا
            }
            response = requests.get(SCRAPERAPI_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt == retries - 1:
                raise Exception(f"فشل بعد {retries} محاولات عبر ScraperAPI: {e}")
            time.sleep(2 ** attempt)  # تأخير تصاعدي

# ------------------- Helper Functions -------------------
def get_post_id(url: str):
    try:
        html = scraperapi_get(url)
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
        json_text = scraperapi_get(api_url)
        data = requests.json() if isinstance(json_text, str) else json_text  # تأكد من التحويل
        # لكن scraperapi_get يعيد نص، نحتاج إلى تحميل JSON
        import json
        data = json.loads(json_text)
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
        "message": "مرحباً بك في Witanime API (عبر ScraperAPI)",
        "endpoints": {
            "/episode-info": "GET?url=... - معلومات حلقة معينة",
            "/episodes": "GET?page=1 - قائمة الحلقات من الأرشيف",
            "/search": "GET?q=اسم_الانمي&page=1 - البحث عن أنمي",
            "/anime": "GET?url=... - تفاصيل الأنمي (باستخدام RSS)",
            "/anime-episodes": "GET?url=... - استخراج الحلقات من صفحة الأنمي (Base64)"
        }
    }

@app.get("/episode-info")
def episode_info(url: str = Query(..., description="رابط الحلقة")):
    post_id = get_post_id(url)
    if not post_id:
        raise HTTPException(status_code=404, detail="لم يتم العثور على معرف الحلقة")
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
            for a, img in zip(titles, images)
        ]
        return {"page": page, "episodes": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            for a, img in zip(titles, images)
        ]
        return {"query": q, "page": page, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        if rss_ok:
            root_xml = ET.fromstring(rss_text)
            for item in root_xml.findall('.//item'):
                ep_title = item.findtext('title', 'بدون عنوان')
                ep_link = item.findtext('link', 'بدون رابط')
                episodes.append({"title": ep_title, "url": ep_link})

        return {"title": title, "image": image, "info": info, "episodes": episodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            except Exception:
                episodes.append({"title": title.strip(), "url": "فك التشفير فشل"})
        return {"episodes": episodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
