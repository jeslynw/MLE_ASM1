import fitz
from PIL import Image
from collections import Counter
import io

src = r"C:\Users\Jeslyn\Downloads\www.reallygreatsite.com.pdf"
doc = fitz.open(src)
print("pages:", doc.page_count)

# Render a handful of representative pages
sample_pages = [0, 30, 60, 90, 120, 150, doc.page_count - 1]
all_colors = Counter()
for p in sample_pages:
    if p >= doc.page_count:
        continue
    page = doc.load_page(p)
    pix = page.get_pixmap(dpi=72)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img.thumbnail((200, 200))
    # quantize for dominant color extraction
    q = img.convert("RGB").quantize(colors=12)
    palette = q.getpalette()
    counts = q.getcolors() or []
    for cnt, idx in counts:
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        # skip near-white / near-black
        if (r > 240 and g > 240 and b > 240) or (r < 20 and g < 20 and b < 20):
            continue
        all_colors[(r, g, b)] += cnt
    # also save thumb for visual reference
    img.save(rf"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\sample_p{p}.png")

print("top colours:")
for col, cnt in all_colors.most_common(15):
    print(f"  #{col[0]:02x}{col[1]:02x}{col[2]:02x}  count={cnt}")
