# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2015-2016 Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

"""Some documentation to refer to:

- Our main web socket (mWS) sends opcode 4 with a server ID and channel ID.
- The mWS receives VOICE_STATE_UPDATE and VOICE_SERVER_UPDATE.
- We pull the session_id from VOICE_STATE_UPDATE.
- We pull the token, endpoint and guild_id from VOICE_SERVER_UPDATE.
- Then we initiate the voice web socket (vWS) pointing to the endpoint.
- We send opcode 0 with the user_id, guild_id, session_id and token using the vWS.
- The vWS sends back opcode 2 with an ssrc, port, modes(array) and hearbeat_interval.
- We send a UDP discovery packet to endpoint:port and receive our IP and our port in LE.
- Then we send our IP and port via vWS with opcode 1.
- When that's all done, we receive opcode 4 from the vWS.
- Finally we can transmit data to endpoint:port.
"""

import asyncio
import websockets
import socket
import json, time
import logging
import struct
import threading
import subprocess
import shlex
import functools
import datetime
import nacl.secret

log = logging.getLogger(__name__)

from . import utils
from .errors import ClientException, InvalidArgument
from .opus import Encoder as OpusEncoder

class StreamPlayer(threading.Thread):
    def __init__(self, stream, encoder, connected, player, after, **kwargs):
        threading.Thread.__init__(self, **kwargs)
        self.buff = stream
        self.frame_size = encoder.frame_size
        self.player = player
        self._end = threading.Event()
        self._resumed = threading.Event()
        self._resumed.set() # we are not paused
        self._connected = connected
        self.after = after
        self.delay = encoder.frame_length / 1000.0

    def run(self):
        self.loops = 0
        self._start = time.time()
        while not self._end.is_set():
            # are we paused?
            if not self._resumed.is_set():
                # wait until we aren't
                self._resumed.wait()

            if not self._connected.is_set():
                self.stop()
                break

            self.loops += 1
            data = self.buff.read(self.frame_size)
            if len(data) != self.frame_size:
                self.stop()
                break

            self.player(data)
            next_time = self._start + self.delay * self.loops
            delay = max(0, self.delay + (next_time - time.time()))
            time.sleep(delay)

    def stop(self):
        self._end.set()
        if callable(self.after):
            try:
                self.after()
            except:
                pass

    def pause(self):
        self._resumed.clear()

    def resume(self):
        self.loops = 0
        self._start = time.time()
        self._resumed.set()

    def is_playing(self):
        return self._resumed.is_set() and not self.is_done()

    def is_done(self):
        return not self._connected.is_set() or self._end.is_set()

class ProcessPlayer(StreamPlayer):
    def __init__(self, process, client, after, **kwargs):
        super().__init__(process.stdout, client.encoder,
                         client._connected, client.play_audio, after, **kwargs)
        self.process = process

    def stop(self):
        self.process.kill()
        if self.process.poll() is None:
            self.process.communicate(timeout=0.100)
        super().stop()

class VoiceClient:
    """Represents a Discord voice connection.

    This client is created solely through :meth:`Client.join_voice_channel`
    and its only purpose is to transmit voice.

    Warning
    --------
    In order to play audio, you must have loaded the opus library
    through :func:`opus.load_opus`.

    If you don't do this then the library will not be able to
    transmit audio.

    Attributes
    -----------
    session_id : str
        The voice connection session ID.
    token : str
        The voice connection token.
    user : :class:`User`
        The user connected to voice.
    endpoint : str
        The endpoint we are connecting to.
    channel : :class:`Channel`
        The voice channel connected to.
    loop
        The event loop that the voice client is running on.
    """
    def __init__(self, user, main_ws, session_id, channel, data, loop):
        self.user = user
        self.main_ws = main_ws
        self.channel = channel
        self.session_id = session_id
        self.loop = loop
        self._connected = asyncio.Event(loop=self.loop)
        self.token = data.get('token')
        self.guild_id = data.get('guild_id')
        self.endpoint = data.get('endpoint')
        self.sequence = 0
        self.timestamp = 0
        self.encoder = OpusEncoder(48000, 2)
        self.secret_key = []
        log.info('created opus encoder with {0.__dict__}'.format(self.encoder))

    def checked_add(self, attr, value, limit):
        val = getattr(self, attr)
        if val + value > limit:
            setattr(self, attr, 0)
        else:
            setattr(self, attr, val + value)

    @asyncio.coroutine
    def keep_alive_handler(self, delay):
        try:
            while True:
                payload = {
                    'op': 3,
                    'd': int(time.time())
                }

                msg = 'Keeping voice websocket alive with timestamp {}'
                log.debug(msg.format(payload['d']))
                yield from self.ws.send(utils.to_json(payload))
                yield from asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass

    @asyncio.coroutine
    def received_message(self, msg):
        log.debug('Voice websocket frame received: {}'.format(msg))
        op = msg.get('op')
        data = msg.get('d')

        if op == 2:
            delay = (data['heartbeat_interval'] / 100.0) - 5
            self.keep_alive = utils.create_task(self.keep_alive_handler(delay), loop=self.loop)
            yield from self.initial_connection(data)
        elif op == 4:
            yield from self.connection_ready(data)

    @asyncio.coroutine
    def initial_connection(self, data):
        self.ssrc = data.get('ssrc')
        self.voice_port = data.get('port')
        packet = bytearray(70)
        struct.pack_into('>I', packet, 0, self.ssrc)
        self.socket.sendto(packet, (self.endpoint_ip, self.voice_port))
        recv = yield from self.loop.sock_recv(self.socket, 70)
        log.debug('received packet in initial_connection: {}'.format(recv))

        # the ip is ascii starting at the 4th byte and ending at the first null
        ip_start = 4
        ip_end = recv.index(0, ip_start)
        self.ip = recv[ip_start:ip_end].decode('ascii')

        # the port is a little endian unsigned short in the last two bytes
        # yes, this is different endianness from everything else
        self.port = struct.unpack_from('<H', recv, len(recv) - 2)[0]

        log.debug('detected ip: {} port: {}'.format(self.ip, self.port))

        payload = {
            'op': 1,
            'd': {
                'protocol': 'udp',
                'data': {
                    'address': self.ip,
                    'port': self.port,
                    'mode': 'xsalsa20_poly1305'
                }
            }
        }

        yield from self.ws.send(utils.to_json(payload))
        log.debug('sent {} to initialize voice connection'.format(payload))
        log.info('initial voice connection is done')

    @asyncio.coroutine
    def connection_ready(self, data):
        log.info('voice connection is now ready')
        self.secret_key = data.get('secret_key')
        speaking = {
            'op': 5,
            'd': {
                'speaking': True,
                'delay': 0
            }
        }

        yield from self.ws.send(utils.to_json(speaking))
        self._connected.set()

    # connection related

    @asyncio.coroutine
    def connect(self):
        log.info('voice connection is connecting...')
        self.endpoint = self.endpoint.replace(':80', '')
        self.endpoint_ip = socket.gethostbyname(self.endpoint)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)

        log.info('Voice endpoint found {0.endpoint} (IP: {0.endpoint_ip})'.format(self))
        self.ws = yield from websockets.connect('wss://' + self.endpoint, loop=self.loop)
        self.ws.max_size = None

        payload = {
            'op': 0,
            'd': {
                'server_id': self.guild_id,
                'user_id': self.user.id,
                'session_id': self.session_id,
                'token': self.token
            }
        }

        yield from self.ws.send(utils.to_json(payload))

        while not self._connected.is_set():
            msg = yield from self.ws.recv()
            if msg is None:
                yield from self.disconnect()
                raise ClientException('Unexpected websocket close on voice websocket')

            yield from self.received_message(json.loads(msg))

    @asyncio.coroutine
    def disconnect(self):
        """|coro|

        Disconnects all connections to the voice client.

        In order to reconnect, you must create another voice client
        using :meth:`Client.join_voice_channel`.
        """
        if not self._connected.is_set():
            return

        self.keep_alive.cancel()
        self.socket.close()
        self._connected.clear()
        yield from self.ws.close()

        payload = {
            'op': 4,
            'd': {
                'guild_id': self.guild_id,
                'channel_id': None,
                'self_mute': True,
                'self_deaf': False
            }
        }

        yield from self.main_ws.send(utils.to_json(payload))

    def is_connected(self):
        """bool : Indicates if the voice client is connected to voice."""
        return self._connected.is_set()

    # audio related

    def _get_voice_packet(self, data):
        header = bytearray(12)
        nonce = bytearray(24)
        box = nacl.secret.SecretBox(bytes(self.secret_key))
        
        #Formulate header
        header[0] = 0x80
        header[1] = 0x78
        struct.pack_into('>H', header, 2, self.sequence)
        struct.pack_into('>I', header, 4, self.timestamp)
        struct.pack_into('>I', header, 8, self.ssrc)
        
        #Copy header to nonce's first 12 bytes
        for i in range(0, len(header)):
            nonce[i] = header[i]
        
		#Encrypt the Opus data with the nonce
		#This weird lib also prepends the nonce to the data
		#So we extract the data after the 24th spot
        encrypted = box.encrypt(bytes(data), bytes(nonce))
        encrypted_ba = bytearray(encrypted[24:])
        return header + encrypted_ba

    def create_ffmpeg_player(self, filename, *, use_avconv=False, pipe=False, options=None, headers=None, after=None):
        """Creates a stream player for ffmpeg that launches in a separate thread to play
        audio.

        The ffmpeg player launches a subprocess of ``ffmpeg`` to a specific
        filename and then plays that file.

        You must have the ffmpeg or avconv executable in your path environment variable
        in order for this to work.

        The operations that can be done on the player are the same as those in
        :meth:`create_stream_player`.

        Examples
        ----------

        Basic usage: ::

            voice = yield from client.join_voice_channel(channel)
            player = voice.create_ffmpeg_player('cool.mp3')
            player.start()

        Parameters
        -----------
        filename
            The filename that ffmpeg will take and convert to PCM bytes.
            If ``pipe`` is True then this is a file-like object that is
            passed to the stdin of ``ffmpeg``.
        use_avconv: bool
            Use ``avconv`` instead of ``ffmpeg``.
        pipe : bool
            If true, denotes that ``filename`` parameter will be passed
            to the stdin of ffmpeg.
        options: str
            Extra command line flags to pass to ``ffmpeg``.
        headers: dict
            HTTP headers dictionary to pass to ``-headers`` command line option
        after : callable
            The finalizer that is called after the stream is done being
            played. All exceptions the finalizer throws are silently discarded.

        Raises
        -------
        ClientException
            Popen failed to due to an error in ``ffmpeg`` or ``avconv``.

        Returns
        --------
        StreamPlayer
            A stream player with specific operations.
            See :meth:`create_stream_player`.
        """
        command = 'ffmpeg' if not use_avconv else 'avconv'
        input_name = '-' if pipe else shlex.quote(filename)
        headers_arg = ""
        if isinstance(headers, dict):
            for key, value in headers.items():
                headers_arg += "{}: {}\r\n".format(key, value)
            headers_arg = ' -headers ' + shlex.quote(headers_arg)
        cmd = command + '{} -i {} -f s16le -ar {} -ac {} -loglevel warning'
        cmd = cmd.format(headers_arg, input_name, self.encoder.sampling_rate, self.encoder.channels)

        if isinstance(options, str):
            cmd = cmd + ' ' + options

        cmd += ' pipe:1'

        stdin = None if not pipe else filename
        args = shlex.split(cmd)
        try:
            p = subprocess.Popen(args, stdin=stdin, stdout=subprocess.PIPE)
            return ProcessPlayer(p, self, after)
        except FileNotFoundError as e:
            raise ClientException('ffmpeg/avconv was not found in your PATH environment variable') from e
        except subprocess.SubprocessError as e:
            raise ClientException('Popen failed: {0.__name__} {1}'.format(type(e), str(e))) from e


    @asyncio.coroutine
    def create_ytdl_player(self, url, *, ytdl_options=None, **kwargs):
        """|coro|

        Creates a stream player for youtube or other services that launches
        in a separate thread to play the audio.

        The player uses the ``youtube_dl`` python library to get the information
        required to get audio from the URL. Since this uses an external library,
        you must install it yourself. You can do so by calling
        ``pip install youtube_dl``.

        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.

        The operations that can be done on the player are the same as those in
        :meth:`create_stream_player`. The player has been augmented and enhanced
        to have some info extracted from the URL. If youtube-dl fails to extract
        the information then the attribute is ``None``. The ``yt``, ``url``, and
        ``download_url`` attributes are always available.

        +---------------------+---------------------------------------------------------+
        |      Operation      |                       Description                       |
        +=====================+=========================================================+
        | player.yt           | The `YoutubeDL <ytdl>` instance.                        |
        +---------------------+---------------------------------------------------------+
        | player.url          | The URL that is currently playing.                      |
        +---------------------+---------------------------------------------------------+
        | player.download_url | The URL that is currently being downloaded to ffmpeg.   |
        +---------------------+---------------------------------------------------------+
        | player.title        | The title of the audio stream.                          |
        +---------------------+---------------------------------------------------------+
        | player.description  | The description of the audio stream.                    |
        +---------------------+---------------------------------------------------------+
        | player.uploader     | The uploader of the audio stream.                       |
        +---------------------+---------------------------------------------------------+
        | player.upload_date  | A datetime.date object of when the stream was uploaded. |
        +---------------------+---------------------------------------------------------+
        | player.duration     | The duration of the audio in seconds.                   |
        +---------------------+---------------------------------------------------------+
        | player.likes        | How many likes the audio stream has.                    |
        +---------------------+---------------------------------------------------------+
        | player.dislikes     | How many dislikes the audio stream has.                 |
        +---------------------+---------------------------------------------------------+
        | player.is_live      | Checks if the audio stream is currently livestreaming.  |
        +---------------------+---------------------------------------------------------+
        | player.views        | How many views the audio stream has.                    |
        +---------------------+---------------------------------------------------------+

        .. _ytdl: https://github.com/rg3/youtube-dl/blob/master/youtube_dl/YoutubeDL.py#L117-L265

        Examples
        ----------

        Basic usage: ::

            voice = await client.join_voice_channel(channel)
            player = await voice.create_ytdl_player('https://www.youtube.com/watch?v=d62TYemN6MQ')
            player.start()

        Parameters
        -----------
        url : str
            The URL that ``youtube_dl`` will take and download audio to pass
            to ``ffmpeg`` or ``avconv`` to convert to PCM bytes.
        ytdl_options : dict
            A dictionary of options to pass into the ``YoutubeDL`` instance.
            See `the documentation <ydl>`_ for more details.
        \*\*kwargs
            The rest of the keyword arguments are forwarded to
            :func:`create_ffmpeg_player`.

        Raises
        -------
        ClientException
            Popen failure from either ``ffmpeg``/``avconv``.

        Returns
        --------
        StreamPlayer
            An augmented StreamPlayer that uses ffmpeg.
            See :meth:`create_stream_player` for base operations.
        """
        import youtube_dl

        use_avconv = kwargs.get('use_avconv', False)
        opts = {
            'format': 'webm[abr>0]/bestaudio/best',
            'prefer_ffmpeg': not use_avconv
        }

        if ytdl_options is not None and isinstance(ytdl_options, dict):
            opts.update(ytdl_options)

        ydl = youtube_dl.YoutubeDL(opts)
        func = functools.partial(ydl.extract_info, url, download=False)
        info = yield from self.loop.run_in_executor(None, func)
        if "entries" in info:
            info = info['entries'][0]

        log.info('playing URL {}'.format(url))
        download_url = info['url']
        player = self.create_ffmpeg_player(download_url, **kwargs)

        # set the dynamic attributes from the info extraction
        player.download_url = download_url
        player.url = url
        player.yt = ydl
        player.views = info.get('view_count')
        player.is_live = bool(info.get('is_live'))
        player.likes = info.get('like_count')
        player.dislikes = info.get('dislike_count')
        player.duration = info.get('duration')
        player.uploader = info.get('uploader')

        is_twitch = 'twitch' in url
        if is_twitch:
            # twitch has 'title' and 'description' sort of mixed up.
            player.title = info.get('description')
            player.description = None
        else:
            player.title = info.get('title')
            player.description = info.get('description')

        # upload date handling
        date = info.get('upload_date')
        if date:
            try:
                date = datetime.datetime.strptime(date, '%Y%M%d').date()
            except ValueError:
                date = None

        player.upload_date = date
        return player

    def encoder_options(self, *, sample_rate, channels=2):
        """Sets the encoder options for the OpusEncoder.

        Calling this after you create a stream player
        via :meth:`create_ffmpeg_player` or :meth:`create_stream_player`
        has no effect.

        Parameters
        ----------
        sample_rate : int
            Sets the sample rate of the OpusEncoder. The unit is in Hz.
        channels : int
            Sets the number of channels for the OpusEncoder.
            2 for stereo, 1 for mono.

        Raises
        -------
        InvalidArgument
            The values provided are invalid.
        """
        if sample_rate not in (8000, 12000, 16000, 24000, 48000):
            raise InvalidArgument('Sample rate out of range. Valid: [8000, 12000, 16000, 24000, 48000]')
        if channels not in (1, 2):
            raise InvalidArgument('Channels must be either 1 or 2.')

        self.encoder = OpusEncoder(sample_rate, channels)
        log.info('created opus encoder with {0.__dict__}'.format(self.encoder))

    def create_stream_player(self, stream, after=None):
        """Creates a stream player that launches in a separate thread to
        play audio.

        The stream player assumes that ``stream.read`` is a valid function
        that returns a *bytes-like* object.

        The finalizer, ``after`` is called after the stream has been exhausted.

        The following operations are valid on the ``StreamPlayer`` object:

        +---------------------+-----------------------------------------------------+
        |      Operation      |                     Description                     |
        +=====================+=====================================================+
        | player.start()      | Starts the audio stream.                            |
        +---------------------+-----------------------------------------------------+
        | player.stop()       | Stops the audio stream.                             |
        +---------------------+-----------------------------------------------------+
        | player.is_done()    | Returns a bool indicating if the stream is done.    |
        +---------------------+-----------------------------------------------------+
        | player.is_playing() | Returns a bool indicating if the stream is playing. |
        +---------------------+-----------------------------------------------------+
        | player.pause()      | Pauses the audio stream.                            |
        +---------------------+-----------------------------------------------------+
        | player.resume()     | Resumes the audio stream.                           |
        +---------------------+-----------------------------------------------------+

        The stream must have the same sampling rate as the encoder and the same
        number of channels. The defaults are 48000 Hz and 2 channels. You
        could change the encoder options by using :meth:`encoder_options`
        but this must be called **before** this function.

        Parameters
        -----------
        stream
            The stream object to read from.
        after:
            The finalizer that is called after the stream is exhausted.
            All exceptions it throws are silently discarded. It is called
            without parameters.

        Returns
        --------
        StreamPlayer
            A stream player with the operations noted above.
        """
        return StreamPlayer(stream, self.encoder, self._connected, self.play_audio, after)

    def play_audio(self, data):
        """Sends an audio packet composed of the data.

        You must be connected to play audio.

        Parameters
        ----------
        data
            The *bytes-like object* denoting PCM voice data.

        Raises
        -------
        ClientException
            You are not connected.
        OpusError
            Encoding the data failed.
        """

        self.checked_add('sequence', 1, 65535)
        encoded_data = self.encoder.encode(data, self.encoder.samples_per_frame)
        packet = self._get_voice_packet(encoded_data)
        sent = self.socket.sendto(packet, (self.endpoint_ip, self.voice_port))
        self.checked_add('timestamp', self.encoder.samples_per_frame, 4294967295)
