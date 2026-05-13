# ================= Witanime API - CloudScraper + Proxies =================
import cloudscraper
import re
import base64
import urllib.parse
import xml.etree.ElementTree as ET
import random
import time
from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup

app = FastAPI(title="Witanime API", description="API مع بروكسيات متعددة و CloudScraper", version="2.0")

website = "https://witanime.you/"

# ========== البروكسيات المقدمة ==========
PROXY_LIST = [
    {"http": "http://213.131.85.26:1981", "https": "http://213.131.85.26:1981"},
    {"http": "http://196.204.83.233:1976", "https": "http://196.204.83.233:1976"},
    {"http": "http://41.33.219.140:1981", "https": "http://41.33.219.140:1981"},
    {"http": "http://196.204.83.232:1981", "https": "http://196.204.83.232:1981"},
    {"http": "http://196.219.64.252:80", "https": "http://196.219.64.252:80"},
    {"http": "http://41.33.219.140:1976", "https": "http://41.33.219.140:1976"},
]

# ========== الكوكيز والهيدرات المقدمة ==========
COOKIES = {
    '_ga': 'GA1.1.142760803.1778638162',
    'wordpress_test_cookie': 'WP%20Cookie%20check',
    'cf_clearance': '7h09fSf9XPwlOR0UuwqoV8qGbYDb1g79Z0f1ElU44lY-1778646327-1.2.1.1-EuZwVqo94L7KVtTVpKOY.uBUAMcbBQp1CDHZsBG2nPaNi.ypQRPBr44AAkw4.7R9O5_oq7qT3sbfvwFaEN0pgVHaSHfwin761Do3suW98C9LBxD0qxHLPzPxAiDSDdMPrEQagNmDk7aiNzRoymG63mGaeFd6gpWVnD3ueFg0GH8CZU0Rgquu6vRADX8L7dVRbABbZxlqawQuEYWtSdFqdwYqmnkBlICeh8zk_6cxIKoU6la0zZZPKF99YLZC1m8K.7_YWrtfHXYPkVHTV9wSS.TJqPxDHr6ifq1MiEMRv6HKrbxYX.37rhayJkgKY.khoP.nuIjLWHcYII0wt57UZw',
    '_ga_ZVB2E4FQBQ': 'GS2.1.s1778638161$o1$g1$t1778646869$j60$l0$h0',
}

HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'ar,en;q=0.9',
    'referer': 'https://witanime.you/',
    'sec-ch-ua': '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36 Edg/148.0.0.0',
}

# ========== دالة لإنشاء سكرابر مع بروكسي عشوائي ==========
def create_scraper_with_proxy(proxy=None):
    scraper = cloudscraper.create_scrazer()  # لاحظ: يجب create_scraper وليس create_scrazer (تصحيح)
    # تصحيح:
    scraper = cloudscraper.create_scraper()
    scraper.headers.update(HEADERS)
    scraper.cookies.update(COOKIES)
    if proxy:
        scraper.proxies = proxy
    return scraper

# ========== دالة طلب مع إعادة المحاولة وتغيير البروكسي ==========
def fetch_with_retry(url, max_retries=3):
    available_proxies = PROXY_LIST.copy()
    random.shuffle(available_proxies)
    
    for attempt in range(max_retries):
        proxy = available_proxies[attempt % len(available_proxies)] if available_proxies else None
        try:
            scraper = create_scraper_with_proxy(proxy)
            response = scraper.get(url, timeout=20)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"محاولة {attempt+1} فشلت باستخدام البروكسي {proxy.get('http') if proxy else 'بدون بروكسي'}: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    raise Exception("فشل بعد جميع المحاولات")

# ========== باقي الدوال (نفس السابق لكن تستخدم fetch_with_retry) ==========
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
        return {"error": "لم يتم العثور على الـ ID"}
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

# ------------------- Endpoints -------------------
@app.get("/")
def root():
    return {"message": "Witanime API with rotating proxies + CloudScraper"}

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
