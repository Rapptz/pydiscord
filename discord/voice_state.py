"""
The MIT License (MIT)

Copyright (c) 2015-present Rapptz

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


Some documentation to refer to:

- Our main web socket (mWS) sends opcode 4 with a guild ID and channel ID.
- The mWS receives VOICE_STATE_UPDATE and VOICE_SERVER_UPDATE.
- We pull the session_id from VOICE_STATE_UPDATE.
- We pull the token, endpoint and server_id from VOICE_SERVER_UPDATE.
- Then we initiate the voice web socket (vWS) pointing to the endpoint.
- We send opcode 0 with the user_id, server_id, session_id and token using the vWS.
- The vWS sends back opcode 2 with an ssrc, port, modes(array) and heartbeat_interval.
- We send a UDP discovery packet to endpoint:port and receive our IP and our port in LE.
- Then we send our IP and port via vWS with opcode 1.
- When that's all done, we receive opcode 4 from the vWS.
- Finally we can transmit data to endpoint:port.
"""

from __future__ import annotations

import select
import socket
import asyncio
import logging
import threading

from typing import TYPE_CHECKING, Optional, Dict, List, Callable, Coroutine, Any, Tuple

from .enums import Enum
from .utils import MISSING, sane_wait_for
from .errors import ConnectionClosed
from .backoff import ExponentialBackoff
from .gateway import DiscordVoiceWebSocket

if TYPE_CHECKING:
    from . import abc
    from .guild import Guild
    from .user import ClientUser
    from .member import VoiceState
    from .voice_client import VoiceClient

    from .types.voice import (
        GuildVoiceState as GuildVoiceStatePayload,
        VoiceServerUpdate as VoiceServerUpdatePayload,
        SupportedModes,
    )

    WebsocketHook = Optional[Callable[[DiscordVoiceWebSocket, Dict[str, Any]], Coroutine[Any, Any, Any]]]
    SocketReaderCallback = Callable[[bytes], Any]


__all__ = ('VoiceConnectionState',)

_log = logging.getLogger(__name__)


class SocketReader(threading.Thread):
    def __init__(self, state: VoiceConnectionState, *, start_paused: bool = True) -> None:
        super().__init__(daemon=True, name=f'voice-socket-reader:{id(self):#x}')
        self.state: VoiceConnectionState = state
        self.start_paused = start_paused
        self._callbacks: List[SocketReaderCallback] = []
        self._running = threading.Event()
        self._end = threading.Event()
        # If we have paused reading due to having no callbacks
        self._idle_paused: bool = True

    def register(self, callback: SocketReaderCallback) -> None:
        self._callbacks.append(callback)
        if self._idle_paused:
            self._idle_paused = False
            self._running.set()

    def unregister(self, callback: SocketReaderCallback) -> None:
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass
        else:
            if not self._callbacks and self._running.is_set():
                # If running is not set, we are either explicitly paused and
                # should be explicitly resumed, or we are already idle paused
                self._idle_paused = True
                self._running.clear()

    def pause(self) -> None:
        self._idle_paused = False
        self._running.clear()

    def resume(self, *, force: bool = False) -> None:
        if self._running.is_set():
            return
        # Don't resume if there are no callbacks registered
        if not force and not self._callbacks:
            # We tried to resume but there was nothing to do, so resume when ready
            self._idle_paused = True
            return
        self._idle_paused = False
        self._running.set()

    def stop(self) -> None:
        self._end.set()
        self._running.set()

    def run(self) -> None:
        self._end.clear()
        self._running.set()
        if self.start_paused:
            self.pause()
        try:
            self._do_run()
        except Exception:
            _log.exception('Error in %s', self)
        finally:
            self.stop()
            self._running.clear()
            self._callbacks.clear()

    def _do_run(self) -> None:
        while not self._end.is_set():
            if not self._running.is_set():
                self._running.wait()
                continue

            # Since this socket is a non blocking socket, select has to be used to wait on it for reading.
            try:
                readable, _, _ = select.select([self.state.socket], [], [], 30)
            except (ValueError, TypeError, OSError) as e:
                _log.debug(
                    "Select error handling socket in reader, this should be safe to ignore: %s: %s", e.__class__.__name__, e
                )
                # The socket is either closed or doesn't exist at the moment
                continue

            if not readable:
                continue

            try:
                data = self.state.socket.recv(2048)
            except OSError:
                _log.debug('Error reading from socket in %s, this should be safe to ignore', self, exc_info=True)
            else:
                for cb in self._callbacks:
                    try:
                        cb(data)
                    except Exception:
                        _log.exception('Error calling %s in %s', cb, self)


class ConnectionFlowState(Enum):
    """Enum representing voice connection flow state."""

    # fmt: off
    disconnected            = 0
    set_guild_voice_state   = 1
    got_voice_state_update  = 2
    got_voice_server_update = 3
    got_both_voice_updates  = 4
    websocket_connected     = 5
    got_websocket_ready     = 6
    got_ip_discovery        = 7
    connected               = 8
    # fmt: on


class VoiceConnectionState:
    """Represents the internal state of a voice connection."""

    def __init__(self, voice_client: VoiceClient, *, hook: Optional[WebsocketHook] = None) -> None:
        self.voice_client = voice_client
        self.hook = hook

        self.timeout: float = 30.0
        self.reconnect: bool = True
        self.self_deaf: bool = False
        self.self_mute: bool = False
        self.token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.endpoint: Optional[str] = None
        self.endpoint_ip: Optional[str] = None
        self.server_id: Optional[int] = None
        self.ip: Optional[str] = None
        self.port: Optional[int] = None
        self.voice_port: Optional[int] = None
        self.secret_key: List[int] = MISSING
        self.ssrc: int = MISSING
        self.mode: SupportedModes = MISSING
        self.socket: socket.socket = MISSING
        self.ws: DiscordVoiceWebSocket = MISSING

        self._state: ConnectionFlowState = ConnectionFlowState.disconnected
        self._expecting_disconnect: bool = False
        self._connected = threading.Event()
        self._state_event = asyncio.Event()
        self._disconnected = asyncio.Event()
        self._runner: Optional[asyncio.Task] = None
        self._connector: Optional[asyncio.Task] = None
        self._socket_reader = SocketReader(self)
        self._socket_reader.start()

    @property
    def state(self) -> ConnectionFlowState:
        return self._state

    @state.setter
    def state(self, state: ConnectionFlowState) -> None:
        if state is not self._state:
            _log.debug('Connection state changed to %s', state.name)
        self._state = state
        self._state_event.set()
        self._state_event.clear()

        if state is ConnectionFlowState.connected:
            self._connected.set()
        else:
            self._connected.clear()

    @property
    def guild(self) -> Guild:
        return self.voice_client.guild

    @property
    def user(self) -> ClientUser:
        return self.voice_client.user

    @property
    def supported_modes(self) -> Tuple[SupportedModes, ...]:
        return self.voice_client.supported_modes

    @property
    def self_voice_state(self) -> Optional[VoiceState]:
        return self.guild.me.voice

    async def voice_state_update(self, data: GuildVoiceStatePayload) -> None:
        channel_id = data['channel_id']

        if channel_id is None:
            self._disconnected.set()

            # If we know we're going to get a voice_state_update where we have no channel due to
            # being in the reconnect or disconnect flow, we ignore it.  Otherwise, it probably wasn't from us.
            if self._expecting_disconnect:
                self._expecting_disconnect = False
            else:
                _log.debug('We were externally disconnected from voice.')
                await self.disconnect()

            return

        channel_id = int(channel_id)
        self.session_id = data['session_id']

        # we got the event while connecting
        if self.state in (ConnectionFlowState.set_guild_voice_state, ConnectionFlowState.got_voice_server_update):
            if self.state is ConnectionFlowState.set_guild_voice_state:
                self.state = ConnectionFlowState.got_voice_state_update

                # we moved ourselves
                if channel_id != self.voice_client.channel.id:
                    self._update_voice_channel(channel_id)

            else:
                self.state = ConnectionFlowState.got_both_voice_updates
            return

        if self.state is ConnectionFlowState.connected:
            self._update_voice_channel(channel_id)

        elif self.state is not ConnectionFlowState.disconnected:
            if channel_id != self.voice_client.channel.id:
                # For some unfortunate reason we were moved during the connection flow
                _log.info('Handling channel move while connecting...')

                self._update_voice_channel(channel_id)
                await self.soft_disconnect(with_state=ConnectionFlowState.got_voice_state_update)
                await self.connect(
                    reconnect=self.reconnect,
                    timeout=self.timeout,
                    self_deaf=(self.self_voice_state or self).self_deaf,
                    self_mute=(self.self_voice_state or self).self_mute,
                    resume=False,
                    wait=False,
                )
            else:
                _log.debug('Ignoring unexpected voice_state_update event')

    async def voice_server_update(self, data: VoiceServerUpdatePayload) -> None:
        previous_token = self.token
        previous_server_id = self.server_id
        previous_endpoint = self.endpoint

        self.token = data['token']
        self.server_id = int(data['guild_id'])
        endpoint = data.get('endpoint')

        if self.token is None or endpoint is None:
            _log.warning(
                'Awaiting endpoint... This requires waiting. '
                'If timeout occurred considering raising the timeout and reconnecting.'
            )
            return

        self.endpoint, _, _ = endpoint.rpartition(':')
        if self.endpoint.startswith('wss://'):
            # Just in case, strip it off since we're going to add it later
            self.endpoint = self.endpoint[6:]

        # we got the event while connecting
        if self.state in (ConnectionFlowState.set_guild_voice_state, ConnectionFlowState.got_voice_state_update):
            # This gets set after READY is received
            self.endpoint_ip = MISSING
            self._create_socket()

            if self.state is ConnectionFlowState.set_guild_voice_state:
                self.state = ConnectionFlowState.got_voice_server_update
            else:
                self.state = ConnectionFlowState.got_both_voice_updates

        elif self.state is ConnectionFlowState.connected:
            _log.debug('Voice server update, closing old voice websocket')
            await self.ws.close(4014)
            self.state = ConnectionFlowState.got_voice_server_update

        elif self.state is not ConnectionFlowState.disconnected:
            # eventual consistency
            if previous_token == self.token and previous_server_id == self.server_id and previous_endpoint == self.endpoint:
                return

            _log.debug('Unexpected server update event, attempting to handle')

            await self.soft_disconnect(with_state=ConnectionFlowState.got_voice_server_update)
            await self.connect(
                reconnect=self.reconnect,
                timeout=self.timeout,
                self_deaf=(self.self_voice_state or self).self_deaf,
                self_mute=(self.self_voice_state or self).self_mute,
                resume=False,
                wait=False,
            )
            self._create_socket()

    async def connect(
        self, *, reconnect: bool, timeout: float, self_deaf: bool, self_mute: bool, resume: bool, wait: bool = True
    ) -> None:
        if self._connector:
            self._connector.cancel()
            self._connector = None

        if self._runner:
            self._runner.cancel()
            self._runner = None

        self.timeout = timeout
        self.reconnect = reconnect
        self._connector = self.voice_client.loop.create_task(
            self._wrap_connect(reconnect, timeout, self_deaf, self_mute, resume), name='Voice connector'
        )
        if wait:
            await self._connector

    async def _wrap_connect(self, *args: Any) -> None:
        try:
            await self._connect(*args)
        except asyncio.CancelledError:
            _log.debug('Cancelling voice connection')
            await self.soft_disconnect()
            raise
        except asyncio.TimeoutError:
            _log.info('Timed out connecting to voice')
            await self.disconnect()
            raise
        except Exception:
            _log.exception('Error connecting to voice... disconnecting')
            await self.disconnect()
            raise

    async def _inner_connect(self, reconnect: bool, self_deaf: bool, self_mute: bool, resume: bool) -> None:
        for i in range(5):
            _log.info('Starting voice handshake... (connection attempt %d)', i + 1)

            await self._voice_connect(self_deaf=self_deaf, self_mute=self_mute)
            # Setting this unnecessarily will break reconnecting
            if self.state is ConnectionFlowState.disconnected:
                self.state = ConnectionFlowState.set_guild_voice_state

            await self._wait_for_state(ConnectionFlowState.got_both_voice_updates)

            _log.info('Voice handshake complete. Endpoint found: %s', self.endpoint)

            try:
                self.ws = await self._connect_websocket(resume)
                await self._handshake_websocket()
                break
            except ConnectionClosed:
                if reconnect:
                    wait = 1 + i * 2.0
                    _log.exception('Failed to connect to voice... Retrying in %ss...', wait)
                    await self.disconnect(cleanup=False)
                    await asyncio.sleep(wait)
                    continue
                else:
                    await self.disconnect()
                    raise

    async def _connect(self, reconnect: bool, timeout: float, self_deaf: bool, self_mute: bool, resume: bool) -> None:
        _log.info('Connecting to voice...')

        await asyncio.wait_for(
            self._inner_connect(reconnect=reconnect, self_deaf=self_deaf, self_mute=self_mute, resume=resume),
            timeout=timeout,
        )
        _log.info('Voice connection complete.')

        if not self._runner:
            self._runner = self.voice_client.loop.create_task(self._poll_voice_ws(reconnect), name='Voice websocket poller')

    async def disconnect(self, *, force: bool = True, cleanup: bool = True, wait: bool = False) -> None:
        if not force and not self.is_connected():
            return

        try:
            await self._voice_disconnect()
            if self.ws:
                await self.ws.close()
        except Exception:
            _log.debug('Ignoring exception disconnecting from voice', exc_info=True)
        finally:
            self.state = ConnectionFlowState.disconnected
            self._socket_reader.pause()

            # Stop threads before we unlock waiters so they end properly
            if cleanup:
                self._socket_reader.stop()
                self.voice_client.stop()

            # Flip the connected event to unlock any waiters
            self._connected.set()
            self._connected.clear()

            if self.socket:
                self.socket.close()

            self.ip = MISSING
            self.port = MISSING

            # Skip this part if disconnect was called from the poll loop task
            if wait and not self._inside_runner():
                # Wait for the voice_state_update event confirming the bot left the voice channel.
                # This prevents a race condition caused by disconnecting and immediately connecting again.
                # The new VoiceConnectionState object receives the voice_state_update event containing channel=None while still
                # connecting leaving it in a bad state.  Since there's no nice way to transfer state to the new one, we have to do this.
                try:
                    await asyncio.wait_for(self._disconnected.wait(), timeout=self.timeout)
                except TimeoutError:
                    _log.debug('Timed out waiting for voice disconnection confirmation')
                except asyncio.CancelledError:
                    pass

            if cleanup:
                self.voice_client.cleanup()

    async def soft_disconnect(self, *, with_state: ConnectionFlowState = ConnectionFlowState.got_both_voice_updates) -> None:
        _log.debug('Soft disconnecting from voice')
        # Stop the websocket reader because closing the websocket will trigger an unwanted reconnect
        if self._runner:
            self._runner.cancel()
            self._runner = None

        try:
            if self.ws:
                await self.ws.close()
        except Exception:
            _log.debug('Ignoring exception soft disconnecting from voice', exc_info=True)
        finally:
            self.state = with_state
            self._socket_reader.pause()

            if self.socket:
                self.socket.close()

            self.ip = MISSING
            self.port = MISSING

    async def move_to(self, channel: Optional[abc.Snowflake], timeout: Optional[float]) -> None:
        if channel is None:
            # This function should only be called externally so its ok to wait for the disconnect.
            await self.disconnect(wait=True)
            return

        if self.voice_client.channel and channel.id == self.voice_client.channel.id:
            return

        previous_state = self.state

        # this is only an outgoing ws request
        # if it fails, nothing happens and nothing changes (besides self.state)
        await self._move_to(channel)

        last_state = self.state
        try:
            await self.wait_async(timeout)
        except asyncio.TimeoutError:
            _log.warning('Timed out trying to move to channel %s in guild %s', channel.id, self.guild.id)
            if self.state is last_state:
                _log.debug('Reverting to previous state %s', previous_state.name)
                self.state = previous_state

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._connected.wait(timeout)

    async def wait_async(self, timeout: Optional[float] = None) -> None:
        await self._wait_for_state(ConnectionFlowState.connected, timeout=timeout)

    def is_connected(self) -> bool:
        return self.state is ConnectionFlowState.connected

    def send_packet(self, packet: bytes) -> None:
        self.socket.sendall(packet)

    def add_socket_listener(self, callback: SocketReaderCallback) -> None:
        _log.debug('Registering socket listener callback %s', callback)
        self._socket_reader.register(callback)

    def remove_socket_listener(self, callback: SocketReaderCallback) -> None:
        _log.debug('Unregistering socket listener callback %s', callback)
        self._socket_reader.unregister(callback)

    def _inside_runner(self) -> bool:
        return self._runner is not None and asyncio.current_task() == self._runner

    async def _wait_for_state(
        self, state: ConnectionFlowState, *other_states: ConnectionFlowState, timeout: Optional[float] = None
    ) -> None:
        states = (state, *other_states)
        while True:
            if self.state in states:
                return
            await sane_wait_for([self._state_event.wait()], timeout=timeout)

    async def _voice_connect(self, *, self_deaf: bool = False, self_mute: bool = False) -> None:
        channel = self.voice_client.channel
        await channel.guild.change_voice_state(channel=channel, self_deaf=self_deaf, self_mute=self_mute)

    async def _voice_disconnect(self) -> None:
        _log.info(
            'The voice handshake is being terminated for Channel ID %s (Guild ID %s)',
            self.voice_client.channel.id,
            self.voice_client.guild.id,
        )
        self.state = ConnectionFlowState.disconnected
        await self.voice_client.channel.guild.change_voice_state(channel=None)
        self._expecting_disconnect = True
        self._disconnected.clear()

    async def _connect_websocket(self, resume: bool) -> DiscordVoiceWebSocket:
        ws = await DiscordVoiceWebSocket.from_connection_state(self, resume=resume, hook=self.hook)
        self.state = ConnectionFlowState.websocket_connected
        return ws

    async def _handshake_websocket(self) -> None:
        while not self.ip:
            await self.ws.poll_event()
        self.state = ConnectionFlowState.got_ip_discovery
        while self.ws.secret_key is None:
            await self.ws.poll_event()
        self.state = ConnectionFlowState.connected

    def _create_socket(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self._socket_reader.resume()

    async def _poll_voice_ws(self, reconnect: bool) -> None:
        backoff = ExponentialBackoff()
        while True:
            try:
                await self.ws.poll_event()
            except asyncio.CancelledError:
                return
            except (ConnectionClosed, asyncio.TimeoutError) as exc:
                if isinstance(exc, ConnectionClosed):
                    # The following close codes are undocumented so I will document them here.
                    # 1000 - normal closure (obviously)
                    # 4014 - we were externally disconnected (voice channel deleted, we were moved, etc)
                    # 4015 - voice server has crashed
                    if exc.code in (1000, 4015):
                        # Don't call disconnect a second time if the websocket closed from a disconnect call
                        if not self._expecting_disconnect:
                            _log.info('Disconnecting from voice normally, close code %d.', exc.code)
                            await self.disconnect()
                        break

                    if exc.code == 4014:
                        # We were disconnected by discord
                        # This condition is a race between the main ws event and the voice ws closing
                        if self._disconnected.is_set():
                            _log.info('Disconnected from voice by discord, close code %d.', exc.code)
                            await self.disconnect()
                            break

                        # We may have been moved to a different channel
                        _log.info('Disconnected from voice by force... potentially reconnecting.')
                        successful = await self._potential_reconnect()
                        if not successful:
                            _log.info('Reconnect was unsuccessful, disconnecting from voice normally...')
                            # Don't bother to disconnect if already disconnected
                            if self.state is not ConnectionFlowState.disconnected:
                                await self.disconnect()
                            break
                        else:
                            continue

                    _log.debug('Not handling close code %s (%s)', exc.code, exc.reason or 'no reason')

                if not reconnect:
                    await self.disconnect()
                    raise

                retry = backoff.delay()
                _log.exception('Disconnected from voice... Reconnecting in %.2fs.', retry)
                await asyncio.sleep(retry)
                await self.disconnect(cleanup=False)

                try:
                    await self._connect(
                        reconnect=reconnect,
                        timeout=self.timeout,
                        self_deaf=(self.self_voice_state or self).self_deaf,
                        self_mute=(self.self_voice_state or self).self_mute,
                        resume=False,
                    )
                except asyncio.TimeoutError:
                    # at this point we've retried 5 times... let's continue the loop.
                    _log.warning('Could not connect to voice... Retrying...')
                    continue

    async def _potential_reconnect(self) -> bool:
        try:
            await self._wait_for_state(
                ConnectionFlowState.got_voice_server_update,
                ConnectionFlowState.got_both_voice_updates,
                ConnectionFlowState.disconnected,
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            return False
        else:
            if self.state is ConnectionFlowState.disconnected:
                return False

        previous_ws = self.ws
        try:
            self.ws = await self._connect_websocket(False)
            await self._handshake_websocket()
        except (ConnectionClosed, asyncio.TimeoutError):
            return False
        else:
            return True
        finally:
            await previous_ws.close()

    async def _move_to(self, channel: abc.Snowflake) -> None:
        await self.voice_client.channel.guild.change_voice_state(channel=channel)
        self.state = ConnectionFlowState.set_guild_voice_state

    def _update_voice_channel(self, channel_id: Optional[int]) -> None:
        self.voice_client.channel = channel_id and self.guild.get_channel(channel_id)  # type: ignore
