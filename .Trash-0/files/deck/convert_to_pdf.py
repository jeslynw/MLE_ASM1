"""Convert PPTX to PDF using PowerPoint COM (Windows + Office)."""
import os, sys, time

src = os.path.abspath(r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\Assignment1_Deck.pptx")
dst = os.path.abspath(r"D:\SMU\Courses\Machine Learning Engineer\MLE_ASM1\deck\Assignment1_Deck.pdf")

if os.path.exists(dst):
    os.remove(dst)

try:
    import comtypes.client
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "comtypes"])
    import comtypes.client

# Kill any stale PowerPoint sessions
ppt = comtypes.client.CreateObject("PowerPoint.Application")
# Some versions reject WindowState change in headless mode; wrap defensively
try:
    ppt.Visible = 1
except Exception:
    pass

deck = ppt.Presentations.Open(src, WithWindow=False)
# 32 = ppSaveAsPDF
deck.SaveAs(dst, 32)
deck.Close()
ppt.Quit()
time.sleep(0.5)
print("saved", dst, "size", os.path.getsize(dst))
