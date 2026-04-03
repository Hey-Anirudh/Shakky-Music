import os
from PIL import Image, ImageDraw

img = Image.open('static/stencil.jpg')
draw = ImageDraw.Draw(img)

# Center poster guesses
w, h = img.size
x_center = w / 2
y_center = h / 2

# Let's draw a red box at exactly 50%
box_w = 200
box_h = 150
x1 = w/2 - box_w/2
y1 = h/2 - box_h/2 - 20
x2 = x1 + box_w
y2 = y1 + box_h

draw.rectangle([x1, y1, x2, y2], outline="red", width=3)

# Add some text to see where it lands
draw.text((x1, y2 + 10), "TITLE HERE", fill="red")

artifact_dir = r"C:\Users\Anirudh\.gemini\antigravity\brain\deca5b44-9616-47f3-bc42-c8b36405ac7c\artifacts"
os.makedirs(artifact_dir, exist_ok=True)
out_path = os.path.join(artifact_dir, "test_render.jpg")
img.save(out_path)

with open(os.path.join(artifact_dir, "test_view.md"), "w") as f:
    f.write("![test_render](/C:/Users/Anirudh/.gemini/antigravity/brain/deca5b44-9616-47f3-bc42-c8b36405ac7c/artifacts/test_render.jpg)")

print("Done")
