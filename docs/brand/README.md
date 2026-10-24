# Brand sources

HTML sources for the images in `docs/img/`, in the app's own colours (`theme.css`) with the munshi from `src/munshi/ui/static/munshi.svg`. System fonts only; the pages load nothing from the network.

| Page | Image | Size |
|---|---|---|
| `banner.html` | `docs/img/banner.png` | 1280 × 400 |
| `devto-cover.html` | `docs/img/devto-cover.png` | 1000 × 420 (content within the middle 80 %) |
| `social-preview.html` | `docs/img/social-preview.png` | 1280 × 640 |
| `architecture.html` | `docs/img/diagrams/architecture.png` | 1600 wide |
| `writer-run.html` | `docs/img/diagrams/writer-run.png` | 1600 wide |
| `privacy-gates.html` | `docs/img/diagrams/privacy-gates.png` | 1600 wide |
| `data-model.html` | `docs/img/diagrams/data-model.png` | 1600 wide |

Render with Playwright and the installed Google Chrome (`NODE_PATH` points at a folder holding the `playwright` package):

```sh
NODE_PATH=<node_modules> node docs/brand/render.cjs                 # all, device scale 1, into docs/img
NODE_PATH=<node_modules> node docs/brand/render.cjs banner          # one
NODE_PATH=<node_modules> node docs/brand/render.cjs --scale 2 --out /tmp/check   # 2x check renders
```
