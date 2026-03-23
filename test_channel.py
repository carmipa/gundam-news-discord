import urllib.request
import re

url = "https://www.youtube.com/watch?v=9AVujlNBFbs"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    id_match = re.search(r'"channelId":"(UC[\w-]+)"', html)
    if id_match:
        print("Channel ID:", id_match.group(1))
    else:
        print("Not found")
except Exception as e:
    print(e)
