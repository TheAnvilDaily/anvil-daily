# Anvil Daily Newsbot — ThinkPad Setup

## 1. Install Python dependencies
```bash
pip3 install feedparser anthropic
```

## 2. Copy repo to ThinkPad
Place the `anvil-daily` folder at:
`/home/rotas/Documents/anvil-daily`

## 3. Set your Anthropic API key
Edit the service file first:
```bash
nano /home/rotas/Documents/anvil-daily/scripts/newsbot-anvil.service
# Replace YOUR_API_KEY_HERE with your real key
```
Or export it in your shell for testing:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 4. Test run first
```bash
cd /home/rotas/Documents/anvil-daily
python3 scripts/newsbot_anvil.py
```
Watch the log output. First run creates posts in public/posts/

## 5. Install systemd service
```bash
sudo cp scripts/newsbot-anvil.service /etc/systemd/system/
sudo cp scripts/newsbot-anvil.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now newsbot-anvil.timer
```

## 6. Verify timer is running
```bash
systemctl status newsbot-anvil.timer
journalctl -u newsbot-anvil.service -f
```

## Notes
- Git must be configured with your GitHub credentials on the ThinkPad
- The bot pushes to origin/main which triggers Cloudflare Pages rebuild
- Logs: /home/rotas/Documents/anvil-daily/scripts/newsbot.log
- posted_ids.json tracks what's been published to avoid duplicates
