import bson
import motor
from tornado import web, gen, ioloop


db = motor.MotorClient().habr_tornado
gridfs = motor.MotorGridFS(db)


class UploadHandler(web.RequestHandler):
    @gen.coroutine
    def get(self):
        files = yield gridfs.find({}).sort("uploadDate", -1).to_list(20)
        self.render('upload.html', files=files)

    @gen.coroutine
    def post(self):
        file = self.request.files['file'][0]
        gridin = yield gridfs.new_file(content_type=file.content_type)
        yield gridin.write(file.body)
        yield gridin.close()
        self.redirect('')


class ShowImageHandler(web.RequestHandler):
    @gen.coroutine
    def get(self, img_id):
        try:
            gridout = yield gridfs.get(bson.objectid.ObjectId(img_id))
        except (bson.errors.InvalidId, motor.gridfs.NoFile):
            raise web.HTTPError(404)
        self.set_header('Content-Type', gridout.content_type)
        self.set_header('Content-Length', gridout.length)
        yield gridout.stream_to_handler(self)


app = web.Application([
    web.url(r'/', UploadHandler),
    web.url(r'/imgs/([\w\d]+)', ShowImageHandler, name='show_image'),
], debug=True)


app.listen(8000)
ioloop.IOLoop.instance().start()
