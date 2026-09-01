# 0003. Enforce Markdown-before-HTML freshness

Host hooks cannot guarantee the next tool call and external writes can bypass them, so combine host-native edit checks with a shared SHA-256 digest policy and Git pre-commit / CI freshness gates. Allow HTML edits only after the paired Markdown is newer than its recorded digest, reject stale or HTML-only changes at commit, and retain an explicit bootstrap path for legacy companions.
