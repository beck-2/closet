"""Pipeline configuration — tweak these knobs, nothing else in the code should need editing."""

# Longest edge (px) of the stored, processed image. Aspect ratio is preserved;
# images already smaller than this are not upscaled.
TARGET_LONG_EDGE = 1024

# rembg model. "u2net" is the general-purpose default and works well for
# clothing-on-a-hanger / flat-lay / worn photos. Swap to "isnet-general-use"
# if you want to try an alternative and compare quality.
REMBG_MODEL = "u2net"

# Output is always a transparent PNG (RGBA) so cutouts can be composited
# onto any background later (e.g. outfit collages).
OUTPUT_FORMAT = "PNG"
OUTPUT_EXTENSION = ".png"

# Source file types we'll look for when scanning an input folder.
SUPPORTED_INPUT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tiff", ".tif",
}
