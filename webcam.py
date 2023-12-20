import asyncio
import cv2
import json
import logging
import os
from av import VideoFrame
import time

from aiohttp import web
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)

ROOT = os.path.dirname(__file__)

pcs = set()


async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    await server(pc, offer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def server(pc, offer):
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            t = VideoStream(track)
            pc.addTrack(t)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)


async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


class VideoStream(VideoStreamTrack):
    kind = "video"

    def __init__(self, source_track):
        super().__init__()
        self.source_track = source_track
        self.cap = cv2.VideoCapture("rtsp://admin:Water44!@10.0.0.108:554/cam/realmonitor?channel=1&subtype=0")

    async def recv(self):
        ret, img = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from the camera.")
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = int(time.time() * 90000)
        frame.time_base = 90000
        return frame


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    web.run_app(app, host="0.0.0.0", port=8080)
