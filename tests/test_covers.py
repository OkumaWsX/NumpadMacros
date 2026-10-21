import base64
import io
import os
import struct
import tempfile
import unittest

from npm import covers

try:
    from PIL import Image
except Exception:            # pragma: no cover
    Image = None


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 80, 20)).save(buf, "PNG")
    return buf.getvalue()


def _synch(n):
    return bytes(((n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F))


@unittest.skipIf(Image is None, "Pillow no está")
class CoversTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.img = _png()

    def path(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_id3v23_apic(self):
        body = b"\x00image/png\x00\x03desc\x00" + self.img
        frame = b"APIC" + struct.pack(">I", len(body)) + b"\x00\x00" + body
        tag = b"ID3\x03\x00\x00" + _synch(len(frame)) + frame
        p = self.path("a.mp3", tag + b"\xff\xfb" + b"\x00" * 100)
        self.assertEqual(covers.embedded(p), self.img)
        self.assertEqual(covers.cover_image(p, 64).size, (64, 64))

    def test_id3v24_utf16_description(self):
        body = b"\x01image/png\x00\x03" + "hola".encode("utf-16") + b"\x00\x00" + self.img
        frame = b"APIC" + _synch(len(body)) + b"\x00\x00" + body
        tag = b"ID3\x04\x00\x00" + _synch(len(frame)) + frame
        self.assertEqual(covers.embedded(self.path("b.mp3", tag)), self.img)

    def _flac_block(self):
        m = b"image/png"
        return (struct.pack(">II", 3, len(m)) + m + struct.pack(">I", 0) + struct.pack(">IIII", 40, 30, 24, 0)
                + struct.pack(">I", len(self.img)) + self.img)

    def test_flac_picture(self):
        blk = self._flac_block()
        streaminfo = bytes([0]) + (34).to_bytes(3, "big") + b"\x00" * 34
        pic = bytes([0x80 | 6]) + len(blk).to_bytes(3, "big") + blk
        self.assertEqual(covers.embedded(self.path("c.flac", b"fLaC" + streaminfo + pic)), self.img)

    def test_ogg_metadata_block_picture(self):
        def page(packet, seq):
            segs, rest = [], len(packet)
            while rest >= 255:
                segs.append(255)
                rest -= 255
            segs.append(rest)
            return b"OggS" + b"\x00" * 22 + bytes([len(segs)]) + bytes(segs) + packet
        ident = b"\x01vorbis" + b"\x00" * 23
        val = b"METADATA_BLOCK_PICTURE=" + base64.b64encode(self._flac_block())
        comment = b"\x03vorbis" + struct.pack("<I", 3) + b"abc" + struct.pack("<I", 1) + struct.pack("<I", len(val)) + val
        p = self.path("d.ogg", page(ident, 0) + page(comment, 1))
        self.assertEqual(covers.embedded(p), self.img)

    def test_sidecar_and_none(self):
        p = self.path("Tambores.wav", b"RIFF\x04\x00\x00\x00WAVE")
        self.assertIsNone(covers.cover_image(p))
        self.path("tambores.PNG", self.img)
        self.assertIsNotNone(covers.cover_image(p))

    def test_fmt_duration(self):
        self.assertEqual(covers.fmt_duration(65.4), "1:05")
        self.assertEqual(covers.fmt_duration(None), "—")


if __name__ == "__main__":
    unittest.main()
