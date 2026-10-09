# Session Notes: converting kc0wih.pdf to a Marp deck

**Date:** 2026-10-09
**Directory:** `/home/mpayne/git/BARCslidesOct2026`
**Request:** Write and run a program that converts `kc0wih.pdf` into a Marp presentation called `kc0wih.md`, and record the session in a Markdown file.

## Result

| File | Description |
|---|---|
| `pdf2marp.py` | The converter (Python 3, uses only the standard library plus poppler-utils) |
| `kc0wih.md` | The generated Marp deck: 50 slides, 4:3, chalkboard background |
| `kc0wih-assets/chalkboard.jpg` | The slide background, taken from the PDF |
| `SESSION_NOTES.md` | This file |

To regenerate the deck:

```bash
python3 pdf2marp.py kc0wih.pdf kc0wih.md
```

To preview or export it (marp-cli is fetched through npx; it isn't installed globally):

```bash
npx @marp-team/marp-cli kc0wih.md --allow-local-files --pdf     # or --html, --images png
```

Marp.app and the VS Code Marp extension can also open `kc0wih.md` directly. The background is referenced by a relative path, so keep `kc0wih-assets/` next to the `.md` file.

## What the PDF contained

- `pdfinfo` showed the title "KernelCon - Be a Ham", creator Google (a Google Slides export), 50 pages, 800×600 pt (4:3).
- The talk is "Never a Better Time to be a Ham" by Aaron Grothe / KC0WIH, given at KernelCon on April 9, 2026.
- `pdfimages -list` showed one image, a chalkboard JPEG (object 11), reused on all 50 pages. There are no other pictures.
- `pdffonts` showed Comic Sans MS for the text and Arial for the bullet glyphs.
- The PDF has no link annotations (checked with `qpdf --json`). Any URL that wraps onto a second line had to be stitched back together from the text.
- The text uses `●`, `○` and `■` for bullet levels 1–3, and some slides use numbered lists ("1.", "2.", …).

## Tools available on the machine

- Available: `pdftotext`, `pdfimages`, `pdftoppm`, `pdfinfo`, `pdffonts` (poppler), `qpdf`, `python3` (3.14), `npx` (Node 26), ImageMagick `magick`.
- Not available: PyMuPDF, pypdf, mutool, a global `marp` command, pip, or uv. Because of this, the script calls the poppler tools with `subprocess` and needs no Python packages.

## How the converter works

1. **Geometry extraction.** `pdftotext -bbox-layout` returns XHTML with bounding boxes for every line and word. The script parses it with `xml.etree`.
2. **Row merging** (`merge_rows`). On some slides (such as "Five Cool Things") the bullet glyph is exported as a separate line from its text. Fragments whose vertical centres are within 6 pt are merged into one row.
3. **Title detection.** Title lines are about 46 pt tall and body lines about 29 pt. The title is the first run of lines at least 38 pt tall with no paragraph gap between them. That rule keeps the title slide's subtitle lines out of the heading.
4. **Bullets and numbered lists.** `●`, `○` and `■` map to nesting levels 0, 1 and 2. Tokens like `1.` become Markdown ordered list items. An indented line under a bullet is treated as that bullet's wrapped continuation.
5. **Soft-wrap and hard-break detection** (`is_soft_wrap`). A line counts as a soft wrap only when the next line's first word would not have fit within the right margin of the line above. The right margin is the widest body line in the deck. A line is always treated as a deliberate break when it:
   - starts with a URL,
   - starts with a `Label:` token, or
   - follows another line in the same "X - description" pattern, such as the Baofeng/Quansheng and OpenRTX/OpenGD77 lines.

   Deliberate breaks within a paragraph become Markdown hard breaks (`\`), which keeps addresses and similar line-by-line text intact.
6. **URL repair** (`join_wrapped`). When a line ends with a URL and that line reaches the right margin, the next line is appended with no space. This repairs URLs such as `…license-exam-s` + `ession` and the long YouTube playlist and KB6NU PDF links.
7. **Escaping.** Characters that mean something in Markdown are escaped. `$` is escaped specifically, because Marp's math plugin would otherwise read "$30+ … $30+" as LaTeX. URLs are wrapped in `<…>` autolinks.
8. **Styling.** The front matter sets `marp: true`, `size: 4:3` and `paginate: true`, plus a global `backgroundImage` pointing at the extracted chalkboard. A small inline style sets:
   - the font to Comic Sans MS, falling back to Comic Neue loaded from Google Fonts;
   - white text and light-blue links;
   - top-aligned content (`place-content: start`);
   - a centred `lead` class, which is used for the title slide.

## Problems found and fixed during the session

| Symptom (first run) | Cause | Fix |
|---|---|---|
| The title slide became one long `#` heading that included "KernelCon April 9, 2026 By …" | All of slide 1's lines are tall, so every line passed the height test | Stop the title at the first vertical gap |
| "The 6 Excuses" came out as text lines joined with `\` instead of a list | `1.`, `2.`, … weren't recognised | Added `NUMBERED_RE` and an ordered-list block type |
| "Five Cool Things" had its first item outside the list and an empty `- ` at the end | The bullet glyphs were separate lines in the bbox output, and sorting put them out of order | Added `merge_rows` |
| "Baofeng … \$30+ Quansheng …", "OpenRTX … OpenGD77 …", and two URLs ran together on one line | The fit test alone can't tell a deliberate break from a wrap | Added hard-break heuristics (URL start, `Label:`, parallel " - " lines) |
| The rendered deck used a serif font | Comic Sans isn't installed on this Linux machine | Added a Google Fonts `@import` for Comic Neue as a fallback |
| Short slides were vertically centred, unlike the top-aligned original | Marp's default theme sets `place-content: safe center center`, and current Chromium honours that on block containers. Overriding only `justify-content` had no effect. | Override with `place-content: start !important` (and `safe center` for `.lead`) |

A final refactor replaced a small helper class with plain function arguments and removed a hardcoded author line from the front matter, so the script isn't tied to this one deck. The regenerated deck was otherwise identical.

## Verification

- Rendered all 50 slides to PNG with `npx @marp-team/marp-cli@latest kc0wih.md --images png --allow-local-files` (marp-cli v4.5.1, marp-core v4.4.0). The PNGs went to a scratch directory, not the project.
- Checked contact sheets (ImageMagick `montage`) of the title slide, nested bullets, numbered list, link slides, the address slide and the densest text slides. All 50 slides fit with no overflow, and the chalkboard background, Comic-style font and page numbers render.
- Confirmed the slide count: the front matter plus 49 `---` separators gives 50 slides.
- Checked that every wrapped URL in the PDF was rejoined correctly, for example `https://www.arrl.org/find-an-amateur-radio-license-exam-session` and `https://www.kb6nu.com/wp-content/uploads/2023/03/2022-no-nonsense-tech-study-guide-v2-20230204.pdf`.

## Known limitations and things left as they are

- **Content copied faithfully, not corrected.** The source's typos are reproduced exactly:
  - "KCOWIH" uses the letter O, not a zero;
  - "Technican" and "Intrest";
  - "https://wwwomamesh.net" has no dot after "www";
  - "the the Quangsheng".
- **Truncated sentence.** Slide 23 ends "…good way to add to your". The sentence is cut off in the original PDF as well.
- **No speaker notes.** The Google Slides export has none.
- **Heuristics tuned to this deck.** The hard-break and soft-wrap rules were tuned for this deck. Another PDF with a different layout may need different values for `TITLE_MIN_HEIGHT` and `PARA_GAP`, or new break rules.
- **Fonts on the machine running Marp.** Comic Sans MS is used where it is installed. Elsewhere the deck falls back to Comic Neue, which needs internet access to load from Google Fonts.
