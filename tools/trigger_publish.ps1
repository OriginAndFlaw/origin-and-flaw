# Run by Windows Task Scheduler at 22:30 Qatar every day: makes the publish workflow start on the minute
# (GitHub's own timer often runs 30-60 min late). If the PC is off, the GitHub timer still posts, just later.
$repo = Split-Path -Parent $PSScriptRoot
git -C $repo pull -q --rebase
(Get-Date).ToUniversalTime().ToString("s") + "Z" | Set-Content -Encoding ascii "$repo\queue\go.txt"
git -C $repo add queue/go.txt
git -C $repo commit -qm "go: publish now"
git -C $repo push -q
