import os
import io
from concurrent.futures import ThreadPoolExecutor

from tornado import web, gen, ioloop
from tornado.options import define, options
from tornado.concurrent import run_on_executor

import bson
import motor
from PIL import Image


define('port', default=8000, help='run on the given port', type=int)
define('db_uri', default='localhost', help='mongodb uri')
define('db_name', default='habr_tornado', help='name of database')
define('debug', default=True, help='debug mode', type=bool)

options.parse_command_line()
db = motor.MotorClient(options.db_uri)[options.db_name]
gridfs = motor.MotorGridFS(db)


class UploadHandler(web.RequestHandler):
    executor = ThreadPoolExecutor(max_workers=os.cpu_count())

    @gen.coroutine
    def get(self):
        imgs = yield db.imgs.find().sort('_id', -1).to_list(20)
        self.render('upload.html', imgs=imgs)

    @gen.coroutine
    def post(self):
        file = self.request.files['file'][0]
        try:
            thumbnail = yield self.make_thumbnail(file.body)
        except OSError:
            raise web.HTTPError(400, 'Cannot identify image file')
        orig_id, thumb_id = yield [
            gridfs.put(file.body, content_type=file.content_type),
            gridfs.put(thumbnail, content_type='image/png')]
        yield db.imgs.save({'orig': orig_id, 'thumb': thumb_id})
        self.redirect('')

    @run_on_executor
    def make_thumbnail(self, content):
        im = Image.open(io.BytesIO(content))
        im.convert('RGB')
        im.thumbnail((128, 128), Image.ANTIALIAS)
        with io.BytesIO() as output:
            im.save(output, 'PNG')
            return output.getvalue()


class ShowImageHandler(web.RequestHandler):
    @gen.coroutine
    def get(self, img_id, size):
        try:
            img_id = bson.objectid.ObjectId(img_id)
        except bson.errors.InvalidId:
            raise web.HTTPError(404, 'Bad ObjectId')
        img = yield db.imgs.find_one(img_id)
        if not img:
            raise web.HTTPError(404, 'Image not found')
        gridout = yield gridfs.get(img[size])
        self.set_header('Content-Type', gridout.content_type)
        self.set_header('Content-Length', gridout.length)
        yield gridout.stream_to_handler(self)


app = web.Application([
    web.url(r'/', UploadHandler),
    web.url(r'/imgs/([\w\d]+)/(orig|thumb)', ShowImageHandler,
            name='show_image'),
],
    debug=options.debug,
    xsrf_cookies=True,
)


app.listen(options.port)
ioloop.IOLoop.instance().start()
