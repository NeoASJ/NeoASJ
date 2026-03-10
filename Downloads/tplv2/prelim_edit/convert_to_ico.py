from PIL import Image

# Open JPEG image
img = Image.open(r"C:\Users\HP\Downloads\tpl_v1\Helmet-vest-Detection\prelim_edit\data\TPL_Logo.PNG")

# Convert to RGBA (ICO needs this)
img = img.convert("RGBA")

# Save as ICO (multiple sizes is best practice)
img.save(
    "output_logo.ico",
    format="ICO",
    sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
)

print("JPEG converted to ICO successfully!")
