from __future__ import annotations

from flask import Flask, request, render_template, redirect, Response
from werkzeug.middleware.proxy_fix import ProxyFix
import random
import os
import time
import datetime

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# Config Start
BASE_URL = "https://share.pirchner.me"
UPLOAD_DIR = "up"
FILE_DELETE_TIME_IN_H = 12
MAX_SIZE_IN_GB = 15
MAX_FILESIZE_IN_GB = 1
# Config End

FILE_DELETE_TIME = FILE_DELETE_TIME_IN_H * 3600  # In Sekunden
MAX_FILESIZE = MAX_FILESIZE_IN_GB * 1073741824  # Ein Gigabyte
MAX_SIZE = MAX_SIZE_IN_GB * 1073741824  # Ein Gigabyte

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


def is_code_used(code: int) -> bool:
    return os.path.exists(os.path.join(UPLOAD_DIR, str(code)))


def can_upload(content: bytes, email: str, mimetype: str, name: str) -> str | None:
    size = 0
    size += len(name.encode("utf-8"))
    size += len("\n")
    size += len(mimetype.encode("utf-8"))
    size += len("\n")
    size += len(email.encode("utf-8"))
    size += len("\n")
    size += len(content)

    if size > MAX_FILESIZE:
        return "File too big"

    if os.path.getsize(UPLOAD_DIR) + size > MAX_SIZE:
        return "Too many Files in Upload-Folder, try again later"
    return None


def back_upload(content: bytes, email: str, mimetype: str, name: str) -> int:
    code = random.randint(0, 100000000000)
    while is_code_used(code):
        code = random.randint(0, 100000000000)
    f = open(os.path.join(UPLOAD_DIR, str(code)), "wb")
    f.write(name.encode("utf-8") + b"\n")
    f.write(mimetype.encode("utf-8") + b"\n")
    f.write(email.encode("utf-8") + b"\n")
    f.write(content)
    f.close()

    return code


def back_download(_id: int) -> list:
    f = open(os.path.join(UPLOAD_DIR, str(_id)), "rb")
    data = f.read()
    f.close()

    data = data.split(b"\n", 3)
    return data


@app.before_request
def cronjob():
    for file in os.listdir(UPLOAD_DIR):
        if int(time.time() - os.path.getmtime(os.path.join(UPLOAD_DIR, file))) > FILE_DELETE_TIME:
            os.remove(os.path.join(UPLOAD_DIR, file))


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/api/up', methods=['PUT', 'POST'])
def api_upload():
    email = request.form.get("email")
    file = request.files.get("file")

    if not email:
        return "{\"success\" : false, \"reason\": \"No Email\"}"
    if not file:
        return "{\"success\" : false, \"reason\": \"No File\"}"

    filedata = file.read()

    res = can_upload(filedata, email, file.mimetype, file.filename)
    if res:
        return "{\"success\" : false, \"reason\": \"" + res + "\"}"

    _id = back_upload(filedata, email, file.mimetype, file.filename)

    return "{\"success\" : true, \"url\": \"" + BASE_URL + "/upload/" + str(_id) + "\"}"


@app.route('/upload/<_id>')
@app.route('/upload/<_id>/')
def uploaded(_id):  # put application's code here
    try:
        int(_id)
    except ValueError:
        return redirect(BASE_URL)

    if not is_code_used(int(_id)):
        return render_template("error.html", error="File not available")

    data = back_download(int(_id))
    name = data[0].decode("utf-8")
    email = data[2].decode("utf-8")
    t = os.path.getmtime(os.path.join(UPLOAD_DIR, _id))
    d = datetime.datetime.fromtimestamp(t)

    size = os.path.getsize(os.path.join(UPLOAD_DIR, _id))
    mes = "B"

    if size >= 1024:
        size /= 1024
        mes = "KB"
    if size >= 1024:
        size /= 1024
        mes = "MB"
    if size >= 1024:
        size /= 1024
        mes = "GB"
    size = round(size, 2)

    return render_template("upload.html", email=email, link=BASE_URL + "/upload/" + _id + "/direct", clink=request.url,
                           name=name, size=str(size) + mes, time=d.strftime("%H:%M"), date=d.strftime("%d. %m. %Y"))


@app.route('/upload/<_id>/direct')
@app.route('/upload/<_id>/direct/')
def download(_id):  # put application's code here
    try:
        int(_id)
    except ValueError:
        return redirect(BASE_URL)

    if not is_code_used(int(_id)):
        return "Does not exist"

    data = back_download(int(_id))
    name = data[0].decode("utf-8")
    mime = data[1].decode("utf-8")
    content = data[3]

    r = Response(content, 200,
                 headers={"Content-Type": mime, "Content-Disposition": f"attachment; filename=\"{name}\""})

    return r


@app.route('/upload')
@app.route('/upload/')
def uploadedWithoutId():
    return redirect(BASE_URL)


if __name__ == '__main__':
    app.run()
