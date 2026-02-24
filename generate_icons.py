"""
Generate PNG icons for the browser extension.
Uses PIL/Pillow to create simple lock icons.
"""
from PIL import Image, ImageDraw
import os

def create_icon(size):
    """Create a lock icon at the specified size."""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    bg_color = (79, 70, 229, 255)  # #4f46e5
    fg_color = (255, 255, 255, 255)  # white
    
    # Draw rounded rectangle background
    padding = size // 8
    radius = size // 5
    draw.rounded_rectangle(
        [padding//2, padding//2, size - padding//2, size - padding//2],
        radius=radius,
        fill=bg_color
    )
    
    # Draw lock body
    lock_width = size * 0.45
    lock_height = size * 0.3
    lock_x = (size - lock_width) / 2
    lock_y = size * 0.5
    
    draw.rounded_rectangle(
        [lock_x, lock_y, lock_x + lock_width, lock_y + lock_height],
        radius=size // 16,
        fill=fg_color
    )
    
    # Draw lock shackle (the curved part)
    shackle_width = lock_width * 0.6
    shackle_height = size * 0.25
    shackle_x = (size - shackle_width) / 2
    shackle_y = lock_y - shackle_height + size // 32
    
    # Draw shackle as arc
    line_width = max(2, size // 10)
    draw.arc(
        [shackle_x, shackle_y, shackle_x + shackle_width, lock_y + size // 16],
        start=180,
        end=360,
        fill=fg_color,
        width=line_width
    )
    
    # Draw keyhole
    keyhole_radius = size // 16
    keyhole_x = size // 2
    keyhole_y = lock_y + lock_height * 0.4
    draw.ellipse(
        [keyhole_x - keyhole_radius, keyhole_y - keyhole_radius,
         keyhole_x + keyhole_radius, keyhole_y + keyhole_radius],
        fill=bg_color
    )
    
    return img

def main():
    # Determine script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(script_dir, 'extension', 'icons')
    
    # Create icons directory if it doesn't exist
    os.makedirs(icons_dir, exist_ok=True)
    
    # Generate icons at different sizes
    sizes = [16, 48, 128]
    
    for size in sizes:
        icon = create_icon(size)
        icon_path = os.path.join(icons_dir, f'icon{size}.png')
        icon.save(icon_path, 'PNG')
        print(f"Created: {icon_path}")
    
    print("\n✅ All icons generated successfully!")

if __name__ == '__main__':
    main()
