from PIL import Image
import pillow_heif

# Register the HEIF opener with Pillow
pillow_heif.register_heif_opener()

def heic_to_raw(input_path: str, output_raw_path: str) -> tuple[bytes, tuple[int, int]]:
    img = Image.open(input_path)
    
    # Convert to RBG
    img = img.convert('RGB')

    raw_data = img.tobytes()
    
    # Save to a binary file
    with open(output_raw_path, 'wb') as f:
        f.write(raw_data)
        
    print(f"Success! Dimensions: {img.width}x{img.height}")
    print(f"Total bytes: {len(raw_data)}")
    return raw_data, (img.width, img.height)

def trim_image(image: bytes, resolution: tuple[int, int], image_size: tuple[int, int]) -> tuple[list[list[bytes]], int]:
    # Image is currently 1-byte per colour channel, thus 3-bytes per pixel
    res_x, res_y = resolution
    image_size_x, image_size_y = image_size
    num_channels = 3

    # Trimmed sizes for target resolution
    trimmed_x = image_size_x - (image_size_x % res_x)
    trimmed_y = (trimmed_x // res_x) * res_y

    # Convert the bytes to a 2D array, each element is a pixel
    frame = [[bytes(0) for _ in range(trimmed_x)] for _ in range(trimmed_y)]
    assert len(frame) == trimmed_y
    assert len(frame[0]) == trimmed_x
    for y in range((image_size_y - trimmed_y) // 2, ((image_size_y - trimmed_y) // 2) + trimmed_y):
        for x in range((image_size_x - trimmed_x) // 2, ((image_size_x - trimmed_x) // 2) + trimmed_x):
            frame[y - ((image_size_y - trimmed_y) // 2)][x - ((image_size_x - trimmed_x) // 2)] = image[(y*image_size_x + x) * num_channels:(y*image_size_x + x + 1) * num_channels]
    
    # Image is now trimmed to give the correct resolution
    return frame, trimmed_x // res_x

def downscale_image(image: list[list[bytes]], scale_factor: int) -> list[list[bytes]]:
    # Combine scale_factor * scale_factor squares of pixels into a single pixel
    downscaled = [[bytes(0) for _ in range(len(image[0]) // scale_factor)] for _ in range(len(image) // scale_factor)]
    assert len(downscaled) == 64
    assert len(downscaled[0]) == 100
    for y in range(0, len(image), scale_factor):
        for x in range(0, len(image[0]), scale_factor):
            # x, y is the top-left index of a square. Here we combine that square into a single pixel
            total_r, total_g, total_b = 0, 0, 0
            for i in range(scale_factor):
                for j in range(scale_factor):
                    total_r += image[y+i][x+j][0]
                    total_g += image[y+i][x+j][1]
                    total_b += image[y+i][x+j][2]
            avg = bytes([total_r // (scale_factor**2), total_g // (scale_factor**2), total_b // (scale_factor**2)]) # Take average and put back into RGB bytes form
            downscaled[y // scale_factor][x // scale_factor] = avg

    return downscaled

def apply_palette(frame: list[list[bytes]], palette: list[bytes]) -> list[list[bytes]]:
    """
    Reduces the colors of the frame to the closest matches in the palette.
    """
    new_frame = []
    
    # Optimization: Cache the palette as integer tuples to avoid repeated indexing
    palette_ints = [tuple(c) for c in palette]

    for row in frame:
        new_row = []
        for pixel in row:
            # Convert current pixel bytes to (R, G, B) integers
            p_r, p_g, p_b = pixel[0], pixel[1], pixel[2]
            
            best_color = palette_ints[0]
            min_dist = float('inf')
            
            for c_r, c_g, c_b in palette_ints:
                # Calculate squared Euclidean distance
                dist = (p_r - c_r)**2 + (p_g - c_g)**2 + (p_b - c_b)**2
                
                if dist < min_dist:
                    min_dist = dist
                    best_color = (c_r, c_g, c_b)
            
            # Convert back to 3-byte bytes object
            new_row.append(bytes(best_color))
            
        new_frame.append(new_row)
        
    return new_frame


if __name__ == "__main__":
    data, (width, height) = heic_to_raw("MariaRafe.heic", "image.raw")

    # The screen total is 800x600
    # We are currently displaying 400x300
    # 400 x 300 = 120,000, our RAMs are 13-bit address, which is only 8,192 addressable space
    # This means we'll have to display in 100x75, which uses 7500 bytes, we'll use 2 bits per colour within a byte, possibly 3 for red and blue?
    # The address on the RAM will be made up of (x >> 2) concatenated with (Y >> 3), because X goes up to 400, but Y goes up to 600. X and Y are both 9 bits, so X >> 2 is 7 bits and Y >> 3 is 6 bits, so the concatenation is 13 bits, perfect fit
    # Note that the image also has to live on the EEPROM which takes up code space for the Z80, however the Z80 code is very simple with a simple LDIR sequence, then write to a location to kickstart the VGA, then sit in a loop.
    # This won't require more than the remaining 692 bytes :)
    # Actually possibly slightly small issue. The image data that lives on the eeprom will need to be compressed together, so literally taking up exactly 7,500 bytes of space, meaning we will need to use several LDIR instructions to move each line (75 specifically)
    # So memory might be a little tight. total mem = (3 bytes to set BC, 3 bytes to set DE, 1 byte to do LDIR) * 75 + 3 bytes to set HL + 2 bytes to LD A + 3 bytes to LD HL + 1 byte to ST A HL + 5 bytes to loop = ~529 btyes, so its okay

    # So we need to trim the image to be a multiple of 100*75, we need to know the multiple too
    trimmed, scale_factor = trim_image(data, (100, 64), (width, height))

    for i in trimmed:
        for j in i:
            assert len(j) == 3, f"{i}, {j}"
    # Now we downscale the image to get a 100x75 image.
    downscaled = downscale_image(trimmed, scale_factor)

    # Now apply the colour palette to the image - currently using a 64 colour greyscale
    grayscale_palette = []
    for i in range(64):
        # Calculate the gray level (0 to 255)
        level = round(i * (255 / 63))
        
        # Create the 3-byte RGB representation (R=G=B)
        pixel_bytes = bytes([level, level, level])
        grayscale_palette.append(pixel_bytes)
    quantised = apply_palette(downscaled, grayscale_palette) # TODO: Once resistor values are decided, then this will dictate the available colour palette
    
    # Now we flatten the list into a single long bytearray
    flat = bytearray()
    for row in quantised:
        for pixel in row:
            flat.extend(pixel)
    
    assert len(flat) == 100*64*3
    img = Image.frombytes('RGB', (100, 64), bytes(flat))
    img.save("babi.png")