import requests
import re

url = "https://www.youtube.com/@GUNDAM"
try:
    r = requests.get(url)
    content = r.text
    match = re.search(r'"channelId":"(UC[\w-]+)"', content)
    if match:
        print(f"FOUND ID: {match.group(1)}")
    else:
        print("ID NOT FOUND")
        # Print snippet to debug
        print(content[:500])
except Exception as e:
    print(f"Error: {e}")
