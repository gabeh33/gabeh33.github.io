# gabeh33.github.io

Personal portfolio. Plain HTML/CSS built by a small Python script (standard library only, no npm).

## Preview

```sh
python3 build.py --serve     # http://localhost:4321, rebuilds when you save
```

## Edit content

| File | What |
|---|---|
| `content/site.json` | Name, headline, intro, status line, links, photo |
| `content/career.json` | Timeline entries, newest first (`type`: `work` or `education`) |
| `content/projects.json` | Featured projects and the coursework list |
| `content/certs.json` | Certifications |
| `content/posts/*.html` | Write-ups. JSON front matter in the top comment; add `"draft": true` to hide one |

Photo: put an image at `src/img/headshot.jpg` and set `"photo": "img/headshot.jpg"` in `site.json`.

## Deploy

Push to `main`. The GitHub Action builds and publishes to GitHub Pages
(repo Settings > Pages > Source: **GitHub Actions**).
