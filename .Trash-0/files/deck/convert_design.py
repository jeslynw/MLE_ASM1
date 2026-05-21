import os, time, comtypes.client
src = os.path.abspath(r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\Table_Design_Slides.pptx")
dst = os.path.abspath(r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\Table_Design_Slides.pdf")
if os.path.exists(dst): os.remove(dst)
ppt = comtypes.client.CreateObject("PowerPoint.Application")
try: ppt.Visible = 1
except: pass
deck = ppt.Presentations.Open(src, WithWindow=False)
deck.SaveAs(dst, 32)
deck.Close(); ppt.Quit(); time.sleep(0.5)
print("saved", dst)

import fitz
doc = fitz.open(dst)
out_dir = r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\design_preview"
os.makedirs(out_dir, exist_ok=True)
for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=110)
    pix.save(os.path.join(out_dir, f"design_{i:02d}.png"))
print("rendered", doc.page_count, "pages")
