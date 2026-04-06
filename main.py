from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
import sqlite3
import threading

DB_PATH = "./debloatube.db"
HOST = "0.0.0.0"
PORT = 8080
in_use = threading.Lock()

### Server ###
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header("Content-type", "text/html")
        self.end_headers()
        if self.path == "/":
            self.wfile.write(bytes(get_html(get_vids_from_sql()),"UTF-8"))
            t = threading.Thread(target=get_homepage)
            t.start()
            t.join()
        elif self.path.startswith("/watch_later"):
            query = """
            SELECT t1.*
            FROM stored_videos AS t1
            INNER JOIN watch_later AS t2
                ON t1.id = t2.id
            ORDER BY t2.added DESC;
            """
            self.wfile.write(bytes(get_html(get_vids_from_sql(query), hide_video_btn=False, show_remove_from_watch_later_btn=True),"UTF-8"))
        elif self.path.startswith("/search"):
            query = self.path.split("=")[1]
            self.wfile.write(bytes(get_html(get_search(query), hide_video_btn=False),"UTF-8"))
        elif self.path.startswith("/channel/"):
            query = self.path.split("/")[2]
            self.wfile.write(bytes(get_html(get_channel(query), show_author=False, hide_video_btn=False),"UTF-8"))
        elif self.path.endswith(".ico") or self.path.endswith(".png"):
            with open("."+self.path,"rb") as f:
                self.wfile.write(f.read())
        elif self.path.startswith("/new"):
            self.wfile.write(bytes(get_html(get_homepage()),"UTF-8"))
    def do_POST(self):
        # Get length of the data
        content_length = int(self.headers.get('Content-Length', 0))
        # Read POST data
        post_data = self.rfile.read(content_length).decode()
        params = parse_qs(post_data)
        if self.path.endswith("/feed"):
            url = params.get('url', [''])[0]
            feed_algorithm(url)
        elif self.path.endswith("/hide"):
            id = params.get('video_id', [''])[0]
            print("hiding" + id)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE stored_videos SET hidden = TRUE WHERE id = (?)",(id,))
            conn.commit()
            conn.close()
        elif self.path.endswith("/addwl"):
            id = params.get('video_id', [''])[0]
            print("adding to watch_later: "+id)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO watch_later (id, added) VALUES (?, ?)",(id,int(time.time())))
            conn.commit()
            conn.close()
        elif self.path.endswith("/rmwl"):
            id = params.get('video_id', [''])[0]
            print("removing from watch_later: "+id)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watch_later WHERE id = ?",(id,))
            conn.commit()
            conn.close()
        self.send_response(200)
        self.end_headers()   


def run():
    server = ThreadingHTTPServer((HOST, PORT), MyHandler)
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
    driver.close()
    global in_use
    in_use.release()
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
    in_use.acquire()
    options = Options()
    options.add_argument("Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.35 Mobile Safari/537.36")

    options.binary_location = "/usr/bin/chromium"  # Adjust path if needed (e.g., "chromium-browser")

    HOME = os.environ["HOME"]
    user_data_dir = f"{HOME}/.config/chromium"  # Default location on Linux
    options.add_argument(f"--user-data-dir={user_data_dir}")

    options.add_argument("--profile-directory=Default") 

    options.add_argument("--headless=new")  
    options.add_argument("--disable-gpu")   
    options.add_argument("--no-sandbox")    
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")  
    driver = webdriver.Chrome(options=options)
    return driver

def get_vids_from_sql(query="SELECT * FROM stored_videos WHERE hidden = FALSE ORDER BY added DESC LIMIT 250"):
    videos = []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    for id, url, title, channel, thumbnail, timestamp, hidden, uploaded in rows:
        videos.append({
            "url": url,
            "title": title,
            "author": channel,    # channel -> author
            "img": thumbnail,      # thumbnail -> img
            "uploaded": uploaded
            })
    return videos

def get_homepage():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    driver = get_driver()
    videos = []
    driver.get("https://www.youtube.com")
    auto_scroll(driver)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    with open("scrape.html", "w") as f:
        f.write(soup.prettify())
    vids = soup.find_all("ytd-rich-item-renderer", {
        "class": "style-scope ytd-rich-grid-renderer"
        })

    for vid in vids:
        try:
            link = vid.find('a', {
                "aria-haspopup": "false",
                'class': 'yt-lockup-metadata-view-model__title'
                })

            author_tag = vid.find("a",{'class': 'yt-core-attributed-string__link yt-core-attributed-string__link--call-to-action-color yt-core-attributed-string--link-inherit-color'} ) 
            author = author_tag['href'].split('@')[1] if author_tag.has_attr("href") and "@" in author_tag['href'] else "DNF"
            title_tag = link["aria-label"]
            title = title_tag.strip() if title_tag else "N/A"
            url_tag = link["href"]
            url = url_tag.strip().split("&")[0] if url_tag else "N/A"
            thumbnail_url = "https://i.ytimg.com/vi/" + url.split("=")[1] + "/hqdefault.jpg"
            uploaded = "unknown"
            uploaded_tags = vid.find_all("span",{'class': 'yt-core-attributed-string ytContentMetadataViewModelMetadataText yt-core-attributed-string--white-space-pre-wrap yt-core-attributed-string--link-inherit-color'})
            for ut in uploaded_tags:
                text = ut.get_text(strip=True)
                if "ago" in text:
                    uploaded = text

            vid = {"title": title, "url": "https://www.youtube.com" + url, "img": thumbnail_url, "author":author, 'uploaded':uploaded}
            videos.append(vid)
        except:
            print("error with video: "+ vid.prettify())
            continue
    driver.close()
    global in_use 
    in_use.release()
    for v in videos:
        cursor.execute("INSERT OR REPLACE INTO stored_videos VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (v['url'].split("=")[1],v['url'],v['title'],v['author'],v['img'], int(time.time()), False, v['uploaded'] ))

        # id TEXT PRIMARY KEY,
        # url TEXT NOT NULL,
        # title TEXT,
        # channel TEXT,
        # thumbnail TEXT
    conn.commit()
    conn.close()

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
            uploaded = "unknown"

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
            uploaded_tags = v.find_all("span",{'class':'inline-metadata-item style-scope ytd-video-meta-block'})
            for ut in uploaded_tags:
                text = ut.get_text(strip=True)
                if "ago" in text:
                    uploaded = text
            vid = {"title": title, "url": "https://www.youtube.com" + url, "img": thumbnail_url, "author":author, 'uploaded':uploaded}
            videos.append(vid)
        except:
            print("error with video: "+ v.prettify())
            continue
    driver.close()
    global in_use 
    in_use.release()
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
            uploaded = "unknown"

            url_tag = v.find("a",{"class":"yt-simple-endpoint focus-on-expand style-scope ytd-rich-grid-media"})
            if url_tag:
                url = url_tag["href"]
                if "shorts" in url:
                    continue

                thumbnail_url = "https://i.ytimg.com/vi/" + url.split("=")[1] + "/hq720.jpg"
            if url_tag and url_tag.has_attr("aria-label"):
                title = url_tag["aria-label"]
            uploaded_tags = v.find_all("span",{'class': 'inline-metadata-item style-scope ytd-video-meta-block'})
            for ut in uploaded_tags:
                text = ut.get_text(strip=True)
                if "ago" in text:
                    uploaded = text
            vid = {"title": title, "url": "https://www.youtube.com" + url, "img": thumbnail_url, "author":author, 'uploaded':uploaded}
            videos.append(vid)
        except:
            print("error with video: "+ v.prettify())
            continue
    driver.close()
    global in_use 
    in_use.release()
    return videos




def get_html(videos, feed_algorithm_btn=True, hide_video_btn=True, show_author=True, show_remove_from_watch_later_btn=False):
    ret_str = """<!DOCTYPE html>
    <html lang="en">
    <head>
    <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon">
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
      <meta charset="UTF-8">
      <title>Debloatube</title>
      <style>
        :root {
      --bg-dark: #121212;
      --card-dark: #1e1e1e;
      --text-light: #e0e0e0;
      --muted: #aaaaaa;
      --accent: #7d4fc2;   /* main purple */
      --accent-hover: #9a6fe0;
      --accent-active: #5b3790;
      --navbar-dark: #1a1a1a;
    }

    body {
      background-color: var(--bg-dark);
      color: var(--text-light);
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
    }
        /* 🔹 Navbar */
    .navbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background-color: var(--navbar-dark);
      padding: 10px 20px;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 2px 5px rgba(0,0,0,0.6);
    }
    /* Remove default browser styling */
.navbar-left form {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;       /* remove default margins */
  padding: 0;      /* remove default padding */
}

.navbar-left label {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

/* Style the input field */
.navbar-left input[type="text"] {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--accent);
  background-color: #000;
  color: var(--text-light);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.navbar-left input[type="text"]:focus {
  border-color: var(--accent-hover);
  box-shadow: 0 0 6px rgba(154, 111, 224, 0.6);
}

/* Style the submit button */
.navbar-left button[type="submit"] {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease;
}

.navbar-left button[type="submit"]:hover {
  background: var(--accent-hover);
  box-shadow: 0 0 8px rgba(154, 111, 224, 0.5);
}

.navbar-left button[type="submit"]:active {
  background: var(--accent-active);
  transform: scale(0.97);
}


    .navbar-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .navbar-right {
      display: flex;
      gap: 10px;
    }
    .navbar-right .nav-btn {
  display: inline-block;
  padding: 8px 14px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease;
}

.navbar-right .nav-btn:hover {
  background: var(--accent-hover);
  box-shadow: 0 0 8px rgba(154, 111, 224, 0.5);
}

.navbar-right .nav-btn:active {
  background: var(--accent-active);
  transform: scale(0.97);
  }

.search-bar {
        width: 100%;
        max-width: 300px;
        padding: 8px 12px;
        border-radius: 6px;
        border: 1px solid var(--accent);
        background: #000;
        color: var(--text-light);
        font-size: 14px;
        }

/* 🔘 Button styling */
    .navbar button,
    .card button {
            padding: 8px 14px;
            border: none;
            border-radius: 6px;
            background: var(--accent);
            color: #fff;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease;
            }

    .navbar button:hover,
    .card button:hover {
            background: var(--accent-hover);
            box-shadow: 0 0 8px rgba(154, 111, 224, 0.5);
            }

    .navbar button:active,
    .card button:active {
            background: var(--accent-active);
            transform: scale(0.97);
            }

    .grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(200px, 1fr));
            gap: 20px;
            }

    .card {
            background-color: var(--card-dark);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            }

    .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 15px rgba(125, 79, 194, 0.4); /* purple glow */
            }

    .card img {
            width: 100%;
            border-radius: 8px;
            }
        /* Card buttons only */
    .card button {
      margin-top: 10px;
      padding: 6px 10px;         /* smaller size */
      border: 1px;
      background: #252525;       
      color: #fff;
      font-size: 12px;           /* smaller text */
      cursor: pointer;
      transition: background 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease;
    }
    
    .card button:hover {
      background: #7d4fc2;       /* brighter on hover */
      box-shadow: 0 0 6px rgba(125, 79, 194, 0.5);
    }
    
    .card button:active {
      background: #4b2b70;       /* darker when pressed */
      transform: scale(0.97);
    }


    .title {
            margin: 10px 0 5px;
            font-size: 18px;
            font-weight: bold;
            color: var(--accent);
            }

    .author {
            font-size: 14px;
            color: var(--muted);
            }

    a {
            color: inherit;
            text-decoration: none;
            }

    a:hover .title {
            color: var(--accent-hover);
            }

    /* 🔘 Button styling with purple motif */
    button {
            margin-top: 12px;
            padding: 5px 7px;
            border: none;
            border-radius: 2px;
            background: var(--accent);
            color: #fff;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s ease, transform 0.1s ease, box-shadow 0.2s ease;
            }

    button:hover {
            background: var(--accent-hover);
            box-shadow: 0 0 8px rgba(154, 111, 224, 0.5);
            }

    button:active {
            background: var(--accent-active);
            transform: scale(0.97);
            }
    </style>
    </head>
    <body>
    <a href='/'>
    <h1>Debloatube</h1>
    </a>
 <!-- 🔹 Navbar -->
  <div class="navbar">
    <div class="navbar-left">
    <a href="/"><img src="/logo.png" height=25px></a>
        <form action="/search" method="get">
        <label for="query">Enter something:</label>
        <input type="text" id="query" name="q" required>
        <button type="submit">Submit</button>
      </form>
    </div>
    <div class="navbar-right">
        <a href="/watch_later" class="nav-btn">Watch Later</a>
        <a href="/new" class="nav-btn">New</a>
    </div>
  </div>
      <div id="flash"></div>
      <div class="grid">
    """
    for v in videos:
        ret_str += "<div class=\"card\">"
        ret_str += "<div onclick=\"copyLink('"+v["url"]+"')\">"
        ret_str += "<img src=\""+v["img"]+"\">"
        ret_str += "<div class=\"card-title\">"+v["title"]+"</div>"
        ret_str += "</div>"
        ret_str += "<div class=\"card-author\">"+v["uploaded"]+"</div>"
        if show_author:
            ret_str += "<a href=\"/channel/"+ v["author"]+"\"><div class=\"card-author\">"+v["author"]+"</div></a>"
        if feed_algorithm_btn:
            ret_str += "<button data-body=\"" + v["url"] + "\" class=\"post-btn\">Feed algorithm</button>"
            ret_str += "<br>"
        if show_remove_from_watch_later_btn:
            ret_str += "<button data-body=\"" + v["url"].split("=")[1] + "\" class=\"rmwl-btn\">Remove from Watch Later</button>"
            ret_str += "<br>"
        else:
            ret_str += "<button data-body=\"" + v["url"].split("=")[1] + "\" class=\"addwl-btn\">Add to Watch Later</button>"
            ret_str += "<br>"
        if hide_video_btn:
            ret_str += "<button data-body=\"" + v["url"].split("=")[1] + "\" class=\"hide-btn\">Hide Video</button>"
            ret_str += "<br>"
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
      // feed algorithm button
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

    // hide button
    document.querySelectorAll('.hide-btn').forEach(button => {
        button.onclick = () => {
            const body = 'video_id=' + encodeURIComponent(button.dataset.body);
            fetch('/hide', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body
                }).catch(console.error).then(() => {location.reload();});
            };
        });

    // add to watch_later
    document.querySelectorAll('.addwl-btn').forEach(button => {
        button.onclick = () => {
            const body = 'video_id=' + encodeURIComponent(button.dataset.body);
            fetch('/addwl', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body
                }).catch(console.error).then(() => {location.reload();});
            };
        });
    // remove from watch_later
    document.querySelectorAll('.rmwl-btn').forEach(button => {
        button.onclick = () => {
            const body = 'video_id=' + encodeURIComponent(button.dataset.body);
            fetch('/rmwl', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body
                }).catch(console.error).then(() => {location.reload();});
            };
        });
    // autorefresh
  //setInterval(() => {
  //    location.reload();
  //    }, 1200000); // 300,000 ms = 5 minutes

  </script>

    </body>
    </html>

    """
    return ret_str

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS stored_videos (
                       id TEXT PRIMARY KEY,
                       url TEXT NOT NULL,
                       title TEXT,
                       author TEXT,
                       thumbnail TEXT,
                       added INTEGER,
                       hidden BOOLEAN,
                       uploaded TEXT
                       )
                   """)
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS watch_later (
                       id TEXT PRIMARY KEY,
                       added INTEGER
                       )
                   """)
    conn.commit()
    conn.close()
    
    run()
