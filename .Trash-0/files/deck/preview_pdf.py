import fitz, os
src = r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\Assignment1_Deck.pdf"
doc = fitz.open(src)
print("pages:", doc.page_count)
out_dir = r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\preview"
os.makedirs(out_dir, exist_ok=True)
for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=110)
    pix.save(os.path.join(out_dir, f"slide_{i:02d}.png"))
print("rendered")
