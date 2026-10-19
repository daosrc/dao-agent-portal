---
name: image-ocr
description: >
  Image analysis via Gemini (Qiniu AI) for models that can't read images.
  A plugin overrides Read — reads on image files are delegated to the
  analyze_image.py script automatically. The script checks ~/Downloads,
  ~/Desktop, ~/Pictures, and the macOS clipboard for screenshots.
  Triggers: @image-ocr, screenshot, UI review, text extraction from
  images, "what is this image".
---

Run silently. Do not show the command. Present only the analysis result:

```bash
python3 ~/dao-agent-portal/shared/skills/image-ocr/scripts/analyze_image.py "<question>"
```

If the result is empty or an error, check `echo $QINIU_AI_API_KEY` is set.
If not set, tell user: add `export QINIU_AI_API_KEY="<key>"` to ~/.zshrc.
