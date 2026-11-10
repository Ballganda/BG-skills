---
"bg-skills": patch
---

The plugin has an icon in the plugin menu: a stick figure beating a dead horse, as flat line art on an off-white square. `scripts/draw-icon.py` draws it with Pillow into `.claude-plugin/icon.png` (1024 px square), and rerunning the script reproduces the committed PNG. The static check fails if the icon is missing, not square, outside 512 to 2048 px on a side, or over 2 MB.
