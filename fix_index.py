#!/usr/bin/env python3
"""
Run this ONCE from C:\Users\rotas\Documents\Anvil Daily
It adds injectable markers to index.html so the bot can update it reliably.

Usage:
  cd "C:\Users\rotas\Documents\Anvil Daily"
  python fix_index.py
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent
index_path = REPO_ROOT / "public" / "index.html"

content = index_path.read_text(encoding="utf-8")

if "BOT:TOP_THREE_START" in content:
    print("Markers already present - nothing to do")
    exit(0)

NEW_TOP_THREE = '''<!-- BOT:TOP_THREE_START -->
      <div class="top-three">
        <a href="#" class="story lead"><article>
          <div class="media-wrap lead-ratio"><div class="placeholder"><span class="placeholder-label">Loading</span></div></div>
          <div class="head"><span class="rank">01</span><span class="kicker accent">Politics</span></div>
          <h3>Loading latest stories...</h3>
          <p class="standfirst">Articles load every hour automatically.</p>
          <p class="byline"><strong>The Anvil Daily</strong> &middot; Just now</p>
        </article></a>
        <div class="secondaries">
          <div class="pair"><a href="#" class="story feature"><article>
            <div class="media-wrap feature-ratio"><div class="placeholder"><span class="placeholder-label">Photograph</span></div></div>
            <div class="head"><span class="rank">02</span><span class="kicker">Politics</span></div>
            <h3>Loading...</h3>
            <p class="byline"><strong>The Anvil Daily</strong> &middot; Just now</p>
          </article></a></div>
          <div class="pair bottom"><a href="#" class="story feature"><article>
            <div class="media-wrap feature-ratio"><div class="placeholder"><span class="placeholder-label">Photograph</span></div></div>
            <div class="head"><span class="rank">03</span><span class="kicker">Politics</span></div>
            <h3>Loading...</h3>
            <p class="byline"><strong>The Anvil Daily</strong> &middot; Just now</p>
          </article></a></div>
        </div>
      </div>
      <!-- BOT:TOP_THREE_END -->'''

NEW_LATEST = '''<!-- BOT:LATEST_START -->
      <div class="latest-feed">
        <div class="row"><a href="#" class="story compact"><article>
          <div class="media-wrap compact-ratio"><div class="placeholder"><span class="placeholder-label">Photo</span></div></div>
          <div class="body">
            <div class="head"><span class="kicker">Politics</span></div>
            <h3>Loading latest stories...</h3>
            <p class="byline"><strong>The Anvil Daily</strong> &middot; Just now</p>
          </div>
        </article></a></div>
      </div>
      <!-- BOT:LATEST_END -->'''

content = re.sub(
    r'<div class="top-three">.*?</div>\s*</div>\s*</section>',
    NEW_TOP_THREE + '\n      </div>\n    </section>',
    content, flags=re.DOTALL, count=1
)

content = re.sub(
    r'<div class="latest-feed">.*?</div>\s*</div>\s*</section>',
    NEW_LATEST + '\n    </div>\n  </section>',
    content, flags=re.DOTALL, count=1
)

index_path.write_text(content, encoding="utf-8")

# Verify
content2 = index_path.read_text(encoding="utf-8")
ok1 = "BOT:TOP_THREE_START" in content2
ok2 = "BOT:LATEST_START" in content2
print(f"TOP_THREE marker: {'OK' if ok1 else 'FAILED'}")
print(f"LATEST marker:    {'OK' if ok2 else 'FAILED'}")
if ok1 and ok2:
    print("index.html ready for bot injection. Now run newsbot_anvil.py")
else:
    print("ERROR: markers not found - check index.html structure")
