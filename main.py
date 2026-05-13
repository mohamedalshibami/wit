# ================= Witanime API - Enhanced Requests Version with provided headers & cookies =================
import requests
import re
import base64
import urllib.parse
import xml.etree.ElementTree as ET
import time
from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = FastAPI(title="Witanime API", description="API لاستخراج بيانات الأنمي باستخدام Cookies/Headers محسّنة", version="1.3")

website = "https://witanime.you/"

# ========== البيانات المقدمة من المستخدم ==========
COOKIES = {
    '_ga': 'GA1.1.142760803.1778638162',
    'wordpress_test_cookie': 'WP%20Cookie%20check',
    'cf_clearance': '7h09fSf9XPwlOR0UuwqoV8qGbYDb1g79Z0f1ElU44lY-1778646327-1.2.1.1-EuZwVqo94L7KVtTVpKOY.uBUAMcbBQp1CDHZsBG2nPaNi.ypQRPBr44AAkw4.7R9O5_oq7qT3sbfvwFaEN0pgVHaSHfwin761Do3suW98C9LBxD0qxHLPzPxAiDSDdMPrEQagNmDk7aiNzRoymG63mGaeFd6gpWVnD3ueFg0GH8CZU0Rgquu6vRADX8L7dVRbABbZxlqawQuEYWtSdFqdwYqmnkBlICeh8zk_6cxIKoU6la0zZZPKF99YLZC1m8K.7_YWrtfHXYPkVHTV9wSS.TJqPxDHr6ifq1MiEMRv6HKrbxYX.37rhayJkgKY.khoP.nuIjLWHcYII0wt57UZw',
    '_ga_ZVB2E4FQBQ': 'GS2.1.s1778638161$o1$g1$t1778646869$j60$l0$h0',
}

HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'ar,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
    'priority': 'u=0, i',
    'referer': 'https://witanime.you/',
    'sec-ch-ua': '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-arch': '""',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"148.0.3967.54"',
    'sec-ch-ua-full-version-list': '"Chromium";v="148.0.7778.97", "Microsoft Edge";v="148.0.3967.54", "Not/A)Brand";v="99.0.0.0"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-model': '"Nexus 5"',
    'sec-ch-ua-platform': '"Android"',
    'sec-ch-ua-platform-version': '"6.0"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36 Edg/148.0.0.0',
}

# ========== إعداد الجلسة المتقدمة ==========
def create_session():
    session = requests.Session()
    # إعادة محاولات تلقائية
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    # تعيين الهيدرات وملفات الارتباط
    session.headers.update(HEADERS)
    session.cookies.update(COOKIES)
    return session

# إنشاء جلسة عالمية لإعادة الاستخدام (تعيد استخدام الكوكيز والهيدرات نفسها)
session = create_session()

def fetch_with_retry(url, method='get', **kwargs):
    """مرونة الطلب مع إعادة محاولة تلقائية"""
    for attempt in range(3):
        try:
            response = session.request(method, url, timeout=15, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1 * (attempt + 1))
    raise Exception("Failed to fetch after retries")

# ------------------- دوال المساعدة -------------------
def get_post_id(url: str):
    try:
        response = fetch_with_retry(url)
        html = response.text
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
        response = fetch_with_retry(api_url)
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

# ------------------- نقاط النهاية -------------------
@app.get("/")
def root():
    return {
        "message": "مرحباً بك في Witanime API (مع Cookies و Headers محسّنة)",
        "endpoints": {
            "/episode-info": "GET?url=... - معلومات حلقة معينة",
            "/episodes": "GET?page=1 - قائمة الحلقات من الأرشيف",
            "/search": "GET?q=اسم_الانمي&page=1 - البحث عن أنمي",
            "/anime": "GET?url=... - تفاصيل الأنمي (باستخدام RSS)",
            "/anime-episodes": "GET?url=... - استخراج الحلقات من صفحة الأنمي (Base64)"
        }
    }

@app.get("/episode-info")
def episode_info(url: str = Query(...)):
    post_id = get_post_id(url)
    if not post_id:
        raise HTTPException(status_code=404, detail="لم يتم العثور على معرف الحلقة")
    return get_episode_data(post_id)

@app.get("/episodes")
def episodes(page: int = Query(1, ge=1)):
    try:
        page_url = f"{website}episode/" + (f"page/{page}/" if page > 1 else "")
        response = fetch_with_retry(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
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
        response = fetch_with_retry(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
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
        response = fetch_with_retry(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        rss_url = url.rstrip('/') + '/feed/'
        try:
            rss_resp = fetch_with_retry(rss_url)
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
            root = ET.fromstring(rss_resp.text)
            for item in root.findall('.//item'):
                ep_title = item.findtext('title', 'بدون عنوان')
                ep_link = item.findtext('link', 'بدون رابط')
                episodes.append({"title": ep_title, "url": ep_link})

        return {"title": title, "image": image, "info": info, "episodes": episodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anime-episodes")
def anime_episodes_base64(url: str = Query(...)):
    try:
        response = fetch_with_retry(url)
        html = response.text
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
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
