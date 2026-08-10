#!/bin/bash
# Optional. Installs two background jobs so the dashboard keeps itself current:
#   • every 4 hours  — grab new plays (Spotify only keeps your last 50)
#   • Sunday 23:00   — pull scrobbles, enrich new music, rebuild the page
# Paths and the label prefix are derived from YOUR machine, not baked in.
# Undo any time with:  launchctl unload ~/Library/LaunchAgents/<file>
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ME="$(id -un)"
mkdir -p ~/Library/LaunchAgents

mk(){ # $1 label  $2 script  $3 schedule-xml
cat > ~/Library/LaunchAgents/com.$ME.spotifydive.$1.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.$ME.spotifydive.$1</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$DIR/$2</string></array>
  $3
  <key>StandardOutPath</key><string>$DIR/agent.log</string>
  <key>StandardErrorPath</key><string>$DIR/agent.log</string>
</dict></plist>
PLIST
launchctl unload ~/Library/LaunchAgents/com.$ME.spotifydive.$1.plist 2>/dev/null || true
launchctl load  ~/Library/LaunchAgents/com.$ME.spotifydive.$1.plist
echo "  installed com.$ME.spotifydive.$1"
}

cat > "$DIR/poll_wrapper.sh" <<'W'
#!/bin/bash
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
[ -f .env ] && source .env
python3 poll_recent.py
W
chmod +x "$DIR/poll_wrapper.sh"

mk poll   poll_wrapper.sh  "<key>StartInterval</key><integer>14400</integer><key>RunAtLoad</key><true/>"
mk weekly weekly_refresh.sh "<key>StartCalendarInterval</key><dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>23</integer><key>Minute</key><integer>0</integer></dict>"

echo
echo "Done. Check with:  launchctl list | grep spotifydive"
echo "Note: macOS defers these while on battery with the lid shut — keep the"
echo "laptop plugged in if you want them to run reliably."
