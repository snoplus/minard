""" module for code relating to detector visualization image generation """
from PIL import Image
import os
import operator

import pca_flags


def color_add(color1, color2):
    """ Return the result of adding color1 and color2, clamped """
    #return tuple([min(c1[x] + c2[x], 255) for x in range(0, len(c1))])
    return (min(color1[0] + color2[0], 255),
            min(color1[1] + color2[1], 255),
            min(color1[2] + color2[2], 255))


def chunks(iterable, chunksize):
    """
    Yield successive n-sized chunks from the given iterable
    From http://stackoverflow.com/questions/312443
    """
    for i in xrange(0, len(iterable), chunksize):
        yield iterable[i:i+chunksize]


def scaled_bitmap(pixels, original_width, scale):
    """
    Return the result of simple two-dimensional scaling of the given input
    pixels using pixel duplication
    """
    scaled_px = list()
    for row in chunks(pixels, original_width):
        scaled_row = list()
        for pixel in row:
            scaled_row.extend([pixel] * scale)
        scaled_px.extend(scaled_row * scale)
    return scaled_px


def status_list_to_pixels(status_list, target_flag):
    """
    Return a list containing pixel color information for each channel status
    in the given list of channel status integers

    Color information comes from the pca module's colors dict.
    A pixel is given a color if the given target_flag appears in the channel
    status. fixme: make this make sense
    """
    flag_bit = target_flag['bit']
    channel_color = pca_flags.colors[target_flag['type']]
    return [channel_color if status & 2**flag_bit else (255, 255, 255)
            for status in status_list]


def generate_image(pixels, filename, scale=1):
    """
    Create an image that represents the data and write it to a new file with
    the specified filename. If the optional scale is given, the image is
    scaled in both dimensions by the given factor.

    The overly wordy description of the desired image:
    - five crates per row, in 4 rows
    - crates oriented vertically
    - In the crates the cards are oriented vertically with channel numbers
    ascending as they progress upward.
    - Cards are ordered left to right 0 to 15
    - In each crate:
        - bottom left pixel is card 0, channel 0
        - top left pixel is card 0, channel 31
        - top right pixel is card 15, channel 31
        - bottom right pixel is card 15, channel 0
    - In the image:
        - crate zero is top left
        - crate 4 is top right
        - ghost crate 19 is bottom right
        - crate 15 is bottom left

    I accept the existence of ghost crate 19.
    """
    # We have this blob which represents the channel values for the crate BUT
    # the values are in LCN order, which basically means they are exactly what
    # we want, but they are rotated to the right by 90 degrees. There is a
    # matrix operation that takes care of this, but I'm blanking. So here is a
    # function that gives us the indexes we want in the order we want.
    #
    # The [list comprehension] gives us a list of lists, the reduce makes it
    # one large list.
    indexes = reduce(operator.add, [range(x, x+481, 32)
                                    for x in xrange(31, -1, -1)])
    reorder_channels = operator.itemgetter(*indexes)

    # Image specific stuff
    bg_color = (247, 247, 249)

    crate_width = 16 * scale
    crate_height = 32 * scale
    margin = 2 * scale  # margin around all elements, intercrate margins merge
    total_width = margin + ((crate_width + margin) * 5)
    total_height = margin + ((crate_height + margin) * 4)

    overall_image = Image.new("RGB", (total_width, total_height), bg_color)

    for crate_num, raw_crate_data in enumerate(chunks(pixels, 512)):
        crate_image = Image.new("RGB", (crate_width, crate_height), bg_color)

        pixel_data = reorder_channels(raw_crate_data)

        if scale > 1:
            pixel_data = scaled_bitmap(pixel_data, 16, scale)

        crate_image.putdata(pixel_data)

        # paste the crate image into the overall image
        ypos, xpos = divmod(crate_num, 5)
        paste_x = margin + (margin * xpos) + (crate_width * xpos)
        paste_y = margin + (margin * ypos) + (crate_height * ypos)

        overall_image.paste(crate_image, (paste_x, paste_y))

    overall_image.save(filename)


def image_for_run_mode_flag(scratch_dir, run, mode, flag, scale=6):
    """
    Return the path of the image for the given run, mode, and flag. If the
    image does not exist, create it.
    """
    if not os.path.exists(scratch_dir):
        os.mkdir(scratch_dir, 0777)

    image_base = os.path.join(scratch_dir, run['name'])
    image_path = os.path.join(image_base,
                              "{0}-flag-{1:02d}.bmp".format(mode, flag['bit']))

    if not os.path.exists(image_path):
        if not os.path.exists(image_base):
            os.mkdir(image_base, 0755)
        generate_image(status_list_to_pixels(run['status'], flag),
                       image_path, scale=scale)

    # we need a leading slash, so leave the ''
    return "/".join(['', os.path.basename(scratch_dir), run['name'],
                     os.path.basename(image_path)])
