""" Avatar utility functions for Mailu """

import os
import uuid
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps
from flask import current_app as app
import mimetypes
import magic


# Allowed image formats
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_MIME_TYPES = {'image/png', 'image/jpeg', 'image/webp'}

# Avatar configuration
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB
AVATAR_SIZE = (512, 512)  # Target size for avatars
THUMBNAIL_SIZE = (64, 64)  # Thumbnail size


def allowed_file(filename):
    """ Check if file extension is allowed """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_mime_type(mime_type):
    """ Check if MIME type is allowed """
    return mime_type in ALLOWED_MIME_TYPES


def get_avatar_storage_path():
    """ Get the avatar storage directory path """
    storage_path = app.config.get('AVATAR_STORAGE_PATH', '/data/avatars')
    os.makedirs(storage_path, exist_ok=True)
    return storage_path


def generate_avatar_filename(user_email, original_filename):
    """ Generate a unique filename for the avatar """
    # Create a hash of the user email for uniqueness
    email_hash = hashlib.md5(user_email.encode()).hexdigest()[:8]
    # Generate a random UUID for additional uniqueness
    unique_id = str(uuid.uuid4())[:8]
    # Get file extension
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'png'
    return f"avatar_{email_hash}_{unique_id}.{ext}"


def validate_image_file(file_path):
    """ Validate image file for security """
    try:
        # Check file size
        if os.path.getsize(file_path) > MAX_AVATAR_SIZE:
            return False, "File too large (max 2MB)"
        
        # Check MIME type using python-magic
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_file(file_path)
        if not allowed_mime_type(detected_mime):
            return False, f"Invalid file type: {detected_mime}"
        
        # Try to open with PIL to verify it's a valid image
        with Image.open(file_path) as img:
            img.verify()
        
        return True, None
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"


def process_avatar_image(file_path, output_path):
    """ Process uploaded avatar image (resize, optimize) """
    try:
        with Image.open(file_path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Resize image while maintaining aspect ratio
            img = ImageOps.fit(img, AVATAR_SIZE, Image.Resampling.LANCZOS)
            
            # Save optimized image
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            
        return True, None
    except Exception as e:
        return False, f"Error processing image: {str(e)}"


def _load_font_with_fallback(font_size):
    """ Load font with fallback chain for better error handling """
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/arial.ttf",
        "/System/Library/Fonts/Arial.ttf",  # macOS
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",  # Common Linux
    ]
    
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue
    
    # Use default font as final fallback
    return ImageFont.load_default()


def generate_initials_avatar(initials, size=AVATAR_SIZE, background_color=None):
    """ Generate an avatar image with user initials """
    if background_color is None:
        # Generate a color based on the initials for consistency
        color_hash = hashlib.md5(initials.encode()).hexdigest()
        background_color = (
            int(color_hash[0:2], 16),
            int(color_hash[2:4], 16),
            int(color_hash[4:6], 16)
        )
    
    # Create image
    img = Image.new('RGB', size, background_color)
    draw = ImageDraw.Draw(img)
    
    # Calculate font size (roughly 40% of image height)
    font_size = int(size[1] * 0.4)
    
    # Load font with fallback chain
    font = _load_font_with_fallback(font_size)
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2
    
    # Draw text (white color)
    draw.text((x, y), initials, fill=(255, 255, 255), font=font)
    
    return img


def save_initials_avatar(user_email, initials, storage_path):
    """ Save an initials-based avatar for a user """
    filename = generate_avatar_filename(user_email, f"{initials}.png")
    filepath = os.path.join(storage_path, filename)
    
    avatar_img = generate_initials_avatar(initials)
    avatar_img.save(filepath, 'PNG', optimize=True)
    
    return filename


def delete_avatar_file(filepath):
    """ Safely delete an avatar file """
    try:
        if filepath and os.path.exists(filepath):
            os.unlink(filepath)
            return True
    except OSError:
        pass
    return False


def get_avatar_info(user):
    """ Get avatar information for a user """
    if user.avatar_filename:
        avatar_path = user.avatar_path
        if avatar_path and os.path.exists(avatar_path):
            return {
                'has_avatar': True,
                'filename': user.avatar_filename,
                'path': avatar_path,
                'url': user.avatar_url,
                'type': 'uploaded'
            }
    
    # Return initials-based avatar info
    return {
        'has_avatar': False,
        'filename': None,
        'path': None,
        'url': None,
        'type': 'initials',
        'initials': user.get_avatar_initials()
    }
