import machine
import uasyncio as asyncio
import usys

from leviot import conf, ulog
from leviot.constants import FAN_SPEED_MAP
from leviot.http import uhttp, html, ufirewall
from leviot.http.uhttp import HTTPError
from leviot.state import state_tracker

log = ulog.Logger("http_server")


async def close_streams(*streams):
    for stream in streams:
        stream.close()
    for stream in streams:
        await stream.wait_closed()


class HttpServer:
    def __init__(self, leviot):
        # type: ("leviot.main.LevIoT") -> None
        self.leviot = leviot

    async def serve(self):
        await asyncio.start_server(self.on_http_connection, conf.http_listen, conf.http_port)
        log.i("HTTP server up at {}:{}".format(conf.http_listen, conf.http_port))

    async def on_http_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        # noinspection PyBroadException
        try:
            ip, port = reader.get_extra_info('peername')

            if not ufirewall.is_allowed(ip):
                log.w("IP not allowed: {}".format(ip))
                await close_streams(writer)
                return

            req = await uhttp.HTTPRequest.parse(reader)

            log.d("New connection from {}:{}".format(ip, port))
            log.d("{} {}".format(req.method, req.path))

            if getattr(conf, 'http_basic_auth'):
                if not req.check_basic_auth(conf.http_basic_auth):
                    log.w("Request has invalid auth")
                    await uhttp.HTTPResponse.unauthorized(writer, realm="LevIoT")
                    await close_streams(writer)
                    return

            if req.method == "GET":
                if req.path == "/" or req.path == "/index.html":
                    await self.handle_http_index(req, writer)
                elif req.path == "/priv-api/fan":
                    await self.handle_priv_set_fan(req, writer)
                elif req.path == "/priv-api/on":
                    await self.handle_priv_set_power(writer, True)
                elif req.path == "/priv-api/off":
                    await self.handle_priv_set_power(writer, False)
                elif req.path == "/priv-api/timer":
                    await self.handle_priv_set_timer(req, writer)
                elif req.path == "/priv-api/reset":
                    await self.handle_priv_reset(writer)
                else:
                    await uhttp.HTTPResponse.not_found(writer)

            else:
                await uhttp.HTTPResponse.not_found(writer)
        except (OSError, HTTPError) as e:
            if "Empty request" not in str(e):
                usys.print_exception(e)
        except Exception:
            await uhttp.HTTPResponse.internal_server_error(writer)
        finally:
            await close_streams(writer)

    @staticmethod
    async def handle_http_index(req: uhttp.HTTPRequest, writer: asyncio.StreamWriter):

        await uhttp.HTTPResponse(
            200,
            body=html.index.format(
                power='ON' if state_tracker.power else "OFF",
                speed=FAN_SPEED_MAP[state_tracker.speed],
                timer=state_tracker.timer_left
            ),
            headers={'Content-Type': 'text/html;charset=utf-8'}
        ).write_into(writer)

    async def handle_priv_set_fan(self, req: uhttp.HTTPRequest, writer: asyncio.StreamWriter):
        speed_str = req.query.get("speed", None)
        if not speed_str:
            return await uhttp.HTTPResponse.bad_request(writer)
        try:
            speed = int(speed_str)
            await self.leviot.set_fan_speed(speed, cause="http")
        except Exception as e:
            print(e)
            return await uhttp.HTTPResponse.bad_request(writer)

        await uhttp.HTTPResponse.see_other(writer, "/")

    async def handle_priv_set_power(self, writer: asyncio.StreamWriter, power: bool):
        try:
            await self.leviot.set_power(power, cause="http")
        except Exception as e:
            log.e(e)
            return await uhttp.HTTPResponse.internal_server_error(writer)

        await uhttp.HTTPResponse.see_other(writer, "/")

    async def handle_priv_set_timer(self, req: uhttp.HTTPRequest, writer: asyncio.StreamWriter):
        timer_str = req.query.get("minutes", None)
        if not timer_str:
            return await uhttp.HTTPResponse.bad_request(writer)
        try:
            timer = int(timer_str)
            await self.leviot.set_timer(timer, cause="http")
        except Exception as e:
            print(e)
            return await uhttp.HTTPResponse.bad_request(writer)

        await uhttp.HTTPResponse.see_other(writer, "/")

    @staticmethod
    async def handle_priv_reset(writer: asyncio.StreamWriter):
        await uhttp.HTTPResponse().write_into(writer)
        machine.reset()
