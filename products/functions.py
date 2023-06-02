import base64
import hashlib
import urllib
from io import BytesIO


def parse_image(image_url: str) -> BytesIO:
    response = urllib.request.urlopen(image_url)
    image_io = BytesIO(response.read())
    return image_io


def get_image_base64md5(image: BytesIO) -> str:
    return hashlib.md5(base64.b64encode(image.getvalue())).hexdigest()
