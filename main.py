from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

HOST = "0.0.0.0"
PORT = 8080
in_use = False

### Server ###
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header("Content-type", "text/html")
        self.end_headers()
        if self.path == "/":
            self.wfile.write(bytes(get_html(get_homepage()),"UTF-8"))
        elif self.path.startswith("/search"):
            query = self.path.split("=")[1]
            self.wfile.write(bytes(get_html(get_search(query)),"UTF-8"))
        elif self.path.startswith("/channel/"):
            query = self.path.split("/")[2]
            self.wfile.write(bytes(get_html(get_channel(query)),"UTF-8"))
        elif self.path.endswith(".ico") or self.path.endswith(".png"):
            with open("."+self.path,"rb") as f:
                self.wfile.write(f.read())
    def do_POST(self):
        # Get length of the data
        content_length = int(self.headers.get('Content-Length', 0))
        # Read POST data
        post_data = self.rfile.read(content_length).decode()
        params = parse_qs(post_data)
        url = params.get('url', [''])[0]
        self.send_response(200)
        self.end_headers()   
        feed_algorithm(url)
    

def run():
    server = HTTPServer((HOST, PORT), MyHandler)
    print(f"Serving on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Server stopped.")

def feed_algorithm(url, load_time=5):
    print("feeding the algorithm: " + url)
    driver = get_driver()
    driver.get(url)
    time.sleep(load_time)
    global in_use
    in_use = False
    driver.close()
### Scraping ###
def auto_scroll(driver, pause_time=0.5, max_scrolls=2):
    last_height = driver.execute_script("return document.documentElement.scrollHeight")
    
    prev_scrolled = 0
    for _ in range(max_scrolls):
        # Scroll down to bottom
        for i in range(0,25):
            scrpct = i *0.05
            scramt = int(round(last_height * scrpct) + prev_scrolled)

            driver.execute_script(f"window.scrollTo(0, {scramt});")
            time.sleep(pause_time)
        prev_scrolled = last_height

        # Check if new content loaded
        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break  # No more content
        last_height = new_height
def get_driver():
    global in_use
    while in_use:
        time.sleep(1)
    in_use = True
    options = Options()
    options.add_argument("Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.35 Mobile Safari/537.36")
    
    options.binary_location = "/usr/bin/chromium"  # Adjust path if needed (e.g., "chromium-browser")
    
    user_data_dir = os.path.expanduser("~/.config/chromium")  # Default location on Linux
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    options.add_argument("--profile-directory=Default") 

    options.add_argument("--headless=new")  
    options.add_argument("--disable-gpu")   
    options.add_argument("--no-sandbox")    
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")  
    driver = webdriver.Chrome(options=options)
    return driver

def get_homepage():
    driver = get_driver()
    videos = []
    driver.get("https://www.youtube.com")
    auto_scroll(driver)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    with open("scrape.html", "w") as f:
        f.write(soup.prettify())
    vids = soup.find_all("div", {
        "class": "yt-lockup-metadata-view-model-wiz__text-container"
    })
    
    for vid in vids:
        try:
            link = vid.find('a', {
            "aria-haspopup": "false",
            'class': 'yt-lockup-metadata-view-model-wiz__title'
            })

            author_tag = vid.find("a",{'class': 'yt-core-attributed-string__link yt-core-attributed-string__link--call-to-action-color yt-core-attributed-string--link-inherit-color'} ) 
            author = author_tag['href'].split('@')[1] if author_tag.has_attr("href") and "@" in author_tag['href'] else "DNF"
            title_tag = link["aria-label"]
            title = title_tag.strip() if title_tag else "N/A"
            url_tag = link["href"]
            url = url_tag.strip().split("&")[0] if url_tag else "N/A"
            thumbnail_url = "https://i.ytimg.com/vi/" + url.split("=")[1] + "/hq720.jpg"
            vid = {"title": title, "url": "https://www.youtube.com" + url, "img": thumbnail_url, "author":author}
            videos.append(vid)
        except:
            print("error with video: "+ vid.prettify())
            continue
    driver.close()
    global in_use 
    in_use = False
    return videos

def get_search(query):
    driver = get_driver()
    videos = []
    driver.get("https://www.youtube.com/results?search_query=" + query)
    auto_scroll(driver)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    with open("scrape.html", "w") as f:
        f.write(soup.prettify())
    video_tags = soup.find_all("ytd-video-renderer")
    for v in video_tags:
        try:
            author = "DNF"
            url = "/"
            title = ""
            thumbnail_url = "/"

            author_tag = v.find("a",{"class":"yt-simple-endpoint style-scope yt-formatted-string"})
            if author_tag:
               author = author_tag["href"].split("@")[1]
            url_tag = v.find("a",{"class":"yt-simple-endpoint style-scope ytd-video-renderer"})
            if url_tag:
                url = url_tag["href"].split("&")[0]
                if "shorts" in url:
                    continue

                thumbnail_url = "https://i.ytimg.com/vi/" + url.split("=")[1] + "/hq720.jpg"
            if url_tag:
                title_tag = url_tag.find("yt-formatted-string")
                if title_tag:
                    title = title_tag["aria-label"]
            vid = {"title": title, "url": "https://www.youtube.com" + url, "img": thumbnail_url, "author":author}
            videos.append(vid)
        except:
            print("error with video: "+ v.prettify())
            continue
    driver.close()
    global in_use 
    in_use = False
    return videos

def get_channel(channel):
    driver = get_driver()
    videos = []
    driver.get("https://www.youtube.com/@" + channel +"/videos")
    auto_scroll(driver)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    with open("scrape.html", "w") as f:
        f.write(soup.prettify())
    video_tags = soup.find_all("ytd-rich-item-renderer")
    for v in video_tags:
        try:
            author = channel
            url = "/"
            title = ""
            thumbnail_url = "/"

            url_tag = v.find("a",{"class":"yt-simple-endpoint focus-on-expand style-scope ytd-rich-grid-media"})
            if url_tag:
                url = url_tag["href"]
                if "shorts" in url:
                    continue

                thumbnail_url = "https://i.ytimg.com/vi/" + url.split("=")[1] + "/hq720.jpg"
            if url_tag and url_tag.has_attr("aria-label"):
                    title = url_tag["aria-label"]
            vid = {"title": title, "url": "https://www.youtube.com" + url, "img": thumbnail_url, "author":author}
            videos.append(vid)
        except:
            print("error with video: "+ v.prettify())
            continue
    driver.close()
    global in_use 
    in_use = False
    return videos



    
def get_html(videos):
    ret_str = """<!DOCTYPE html>
    <html lang="en">
    <head>
    <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon">
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
      <meta charset="UTF-8">
      <title>Debloatube</title>
      <style>
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
    
        body {
          background-color: #121212;
          color: #e0e0e0;
          font-family: Arial, sans-serif;
          padding: 2rem;
        }
    
        h1 {
          text-align: center;
          margin-bottom: 2rem;
          font-size: 2rem;
        }
    
        .grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(200px, 1fr));
          gap: 1.5rem;
        }
    
        .card {
          background-color: #1e1e1e;
          border-radius: 8px;
          overflow: hidden;
          text-decoration: none;
          color: inherit;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
    
        .card:hover {
          transform: translateY(-4px);
          box-shadow: 0 4px 12px rgba(255, 255, 255, 0.1);
        }
    
        .card img {
          width: 100%;
          height: auto;
          display: block;
        }
    
        .card-title {
          padding: 1rem;
          font-size: 1.1rem;
          text-align: center;
        }
        .card-author {
           padding: 0 1rem 1rem;
           font-size: 0.9rem;
           text-align: center;
           color: #aaaaaa;
         }
        #flash {
          position: fixed;
          top: 0; left: 0;
          width: 100%; height: 100%;
          background: white;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.2s ease;
          z-index: 9999;
        }
        #flash.show {
          opacity: 1;
        }
      </style>
    </head>
    <body>
    <a href='/'>
    <h1>Debloatube</h1>
    </a>
  <form action="/search" method="get">
        <label for="query">Enter something:</label>
        <input type="text" id="query" name="q" required>
        <button type="submit">Submit</button>
    </form>     
      <div id="flash"></div>
      <div class="grid">
    """
    for v in videos:
        ret_str += "<div class=\"card\">"
        ret_str += "<div onclick=\"copyLink('"+v["url"]+"')\">"
        ret_str += "<img src=\""+v["img"]+"\">"
        ret_str += "<div class=\"card-title\">"+v["title"]+"</div>"
        ret_str += "</div>"
        ret_str += "<a href=\"/channel/"+ v["author"]+"\"><div class=\"card-author\">"+v["author"]+"</div></a>"
        ret_str += "<button data-body=\"" + v["url"] + "\" class=\"post-btn\">Feed algorithm</button>"
        ret_str += "</div>"


    ret_str += """
      </div>
      <script>
      function copyLink(text) {
        if (navigator.clipboard && window.isSecureContext) {
            // Modern secure clipboard API
            navigator.clipboard.writeText(text).then(function() {
                console.log("Copied to clipboard (secure API): " + text);
                flashScreen();
            }).catch(function(err) {
                console.error("Failed to copy using clipboard API", err);
            });
        } else {
            // Fallback for insecure HTTP or older browsers
            const tempInput = document.createElement("textarea");
            tempInput.value = text;
            tempInput.style.position = "fixed"; // prevent scrolling
            tempInput.style.opacity = "0";
            document.body.appendChild(tempInput);
            tempInput.focus();
            tempInput.select();
            try {
                document.execCommand("copy");
                console.log("Copied to clipboard (fallback): " + text);
                flashScreen();
            } catch (err) {
                console.error("Fallback copy failed", err);
            }
            document.body.removeChild(tempInput);
        }
    }

    function flashScreen() {
        // Create overlay
        const flash = document.createElement("div");
        flash.style.position = "fixed";
        flash.style.top = "0";
        flash.style.left = "0";
        flash.style.width = "100%";
        flash.style.height = "100%";
        flash.style.background = "#1a1a1a";
        flash.style.opacity = "1";
        flash.style.zIndex = "9999";
        flash.style.pointerEvents = "none";
        flash.style.transition = "opacity 0.5s ease";
    
        // Add to page
        document.body.appendChild(flash);
    
        // Trigger fade-out after short delay
        setTimeout(() => {
            flash.style.opacity = "0";
        }, 50);
    
        // Remove from DOM after fade-out completes
        setTimeout(() => {
            flash.remove();
        }, 300);
    }
    document.querySelectorAll('.post-btn').forEach(button => {
      button.onclick = () => {
        const body = 'url=' + encodeURIComponent(button.dataset.body);
        fetch('/feed', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body
        }).catch(console.error);
      };
    });
      </script>
    
    </body>
    </html>

    """
    return ret_str

if __name__ == "__main__":
    in_use = False
    run()

