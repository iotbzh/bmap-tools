""" This test verifies the base bmap creation and copying API functionality. It
generates a random sparse file, then creates a bmap fir this file and copies it
to a different file using the bmap. Then it compares the original random sparse
file and the copy and verifies that they are identical. """

# Disable the following pylint recommendations:
#   *  Too many instance attributes - R0902
#   *  Too many public methods - R0904
# pylint: disable=R0902,R0904

import tempfile
import filecmp
import hashlib
import unittest
import itertools

import tests.helpers
from bmaptools import BmapCreate, BmapCopy, Fiemap

class Error(Exception):
    """ A class for exceptions generated by this test. """
    pass

def compare_holes(file1, file2):
    """ Make sure that files 'file1' and 'file2' have holes at the same places.
    The 'file1' and 'file2' arguments may be full file paths or file
    objects. """

    fiemap1 = Fiemap.Fiemap(file1)
    fiemap2 = Fiemap.Fiemap(file2)

    iterator1 = fiemap1.get_unmapped_ranges(0, fiemap1.blocks_cnt)
    iterator2 = fiemap2.get_unmapped_ranges(0, fiemap2.blocks_cnt)

    iterator = itertools.izip_longest(iterator1, iterator2)
    for range1, range2 in iterator:
        if range1 != range2:
            raise Error("mismatch for hole %d-%d, it is %d-%d in file2" \
                        % (range1[0], range1[1], range2[0], range2[1]))

def _calculate_sha1(file_obj):
    """ Calculates SHA1 checksum for the contents of file object
    'file_obj'.  """

    file_obj.seek(0)
    hash_obj = hashlib.new("sha1")

    chunk_size = 1024*1024

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        hash_obj.update(chunk)

    return hash_obj.hexdigest()

def _do_test(f_image):
    """" A basic test for the bmap creation and copying functionality. It first
    generates a bmap for file object 'f_image', and then copies the sparse file
    to a different file, and then checks that the original file and the copy
    are identical. """

    # Create and open a temporary file for a copy of the copy
    f_copy = tempfile.NamedTemporaryFile("wb+")

    # Create and open 2 temporary files for the bmap
    f_bmap1 = tempfile.NamedTemporaryFile("w+")
    f_bmap2 = tempfile.NamedTemporaryFile("w+")

    image_sha1 = _calculate_sha1(f_image)

    #
    # Pass 1: generate the bmap, copy and compare
    #

    # Create bmap for the random sparse file
    creator = BmapCreate.BmapCreate(f_image.name, f_bmap1.name)
    creator.generate()

    # Copy the random sparse file to a different file using bmap
    writer = BmapCopy.BmapCopy(f_image.name, f_copy.name, f_bmap1.name)
    writer.copy(False, True)

    # Compare the original file and the copy are identical
    assert _calculate_sha1(f_copy) == image_sha1

    # Make sure that holes in the copy are identical to holes in the random
    # sparse file.
    compare_holes(f_image.name, f_copy.name)

    #
    # Pass 2: same as pass 1, but use file objects instead of paths
    #

    creator = BmapCreate.BmapCreate(f_image, f_bmap2)
    creator.generate()

    writer = BmapCopy.BmapCopy(f_image, f_copy, f_bmap2)
    writer.copy(False, True)

    assert _calculate_sha1(f_copy) == image_sha1
    compare_holes(f_image, f_copy)

    # Make sure the bmap files generated at pass 1 and pass 2 are identical
    assert filecmp.cmp(f_bmap1.name, f_bmap2.name, False)

    #
    # Pass 3: repeat pass 2 to make sure the same 'BmapCreate' and
    # 'BmapCopy' objects can be used more than once.
    #

    f_bmap2.seek(0)
    creator.generate()
    f_bmap2.seek(0)
    creator.generate()
    writer.copy(True, False)
    writer.copy(False, True)
    writer.sync()
    assert _calculate_sha1(f_copy) == image_sha1
    compare_holes(f_image, f_copy)
    assert filecmp.cmp(f_bmap1.name, f_bmap2.name, False)

    #
    # Pass 4: test compressed files copying with bmap
    #

    for compressed in tests.helpers.compress_test_file(f_image):
        writer = BmapCopy.BmapCopy(compressed, f_copy, f_bmap1)
        writer.copy()

        assert _calculate_sha1(f_copy) == image_sha1

    #
    # Pass 5: copy the sparse file without bmap and make sure it is
    # identical to the original file
    #

    writer = BmapCopy.BmapCopy(f_image, f_copy.name)
    writer.copy(True, True)
    assert _calculate_sha1(f_copy) == image_sha1

    writer = BmapCopy.BmapCopy(f_image, f_copy)
    writer.copy(False, True)
    assert _calculate_sha1(f_copy) == image_sha1

    #
    # Pass 6: test compressed files copying without bmap
    #

    for compressed in tests.helpers.compress_test_file(f_image):
        writer = BmapCopy.BmapCopy(compressed, f_copy)
        writer.copy()

        assert _calculate_sha1(f_copy) == image_sha1

    # Close temporary files, which will also remove them
    f_copy.close()
    f_bmap1.close()
    f_bmap2.close()

class TestCreateCopy(unittest.TestCase):
    """ The test class for this unit tests. Basically executes the '_do_test()'
    function for different sparse files. """

    @staticmethod
    def test():
        """ The test entry point. Executes the '_do_test()' function for files
        of different sizes, holes distribution and format. """

        for f_image, _ in tests.helpers.generate_test_files():
            _do_test(f_image)
