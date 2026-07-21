import io
import time
import logging
import asyncio
import threading
import queue
from typing import Tuple, Generator
from pyrogram import Client

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)


class TelegramUploadError(Exception):
    # Exception untuk error upload/download/delete ke Telegram.

    def __init__(self, message: str, status_code: int = None, response_body: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TelegramStorage:
    # Client untuk menyimpan dan mengambil file via Pyrogram MTProto.

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # detik

    def __init__(self, session_name: str, bot_token: str, storage_chat_id: str, api_id: int, api_hash: str):
        self.session_name = session_name
        self.bot_token = bot_token
        self.storage_chat_id = int(storage_chat_id)
        self.api_id = api_id
        self.api_hash = api_hash

        # Event untuk sinkronisasi: main thread menunggu sampai client siap
        self._ready = threading.Event()
        self._init_error = None
        self.loop = None
        self.client = None

        logger.info(f'TelegramStorage Pyrogram initializing... session={self.session_name}')

        # Jalankan SELURUH inisialisasi Pyrogram di background thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        # Tunggu hingga client benar-benar siap (maks 3600 detik untuk FLOOD_WAIT)
        if not self._ready.wait(timeout=3600):
            raise TelegramUploadError('Pyrogram gagal start dalam waktu yang ditentukan')
        if self._init_error:
            raise TelegramUploadError(f'Pyrogram init error: {self._init_error}')

        logger.info(f'TelegramStorage Pyrogram Client started sukses — chat_id={storage_chat_id}')

    def _run_loop(self):
        # Background thread: buat event loop, buat Client, start, lalu run_forever.
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Session disimpan ke disk agar tidak perlu re-login setiap restart
        # Ini mencegah FLOOD_WAIT dari Telegram
        self.client = Client(
            self.session_name,
            api_id=self.api_id,
            api_hash=self.api_hash,
            bot_token=self.bot_token,
            no_updates=True,
            workdir="instance"
        )

        async def _start():
            from pyrogram.errors import FloodWait
            from pyrogram import raw

            try:
                await self.client.start()
            except FloodWait as e:
                logger.warning('FLOOD_WAIT dari Telegram — menunggu %d detik...', e.value)
                await asyncio.sleep(e.value)
                await self.client.start()

            # Resolve storage chat peer via raw MTProto API
            chat_id = self.storage_chat_id
            raw_id = abs(chat_id)

            logger.info('Resolving storage peer — chat_id=%d', chat_id)

            # Coba sebagai regular group terlebih dahulu (messages.GetChats)
            try:
                result = await self.client.invoke(
                    raw.functions.messages.GetChats(id=[raw_id])
                )
                chat_title = result.chats[0].title if result.chats else 'Unknown'
                logger.info('Storage peer resolved (group) — title=%s', chat_title)
                return
            except Exception as e:
                logger.debug('Bukan regular group: %s', e)

            # Jika bukan group, coba sebagai channel/supergroup
            id_str = str(raw_id)
            if id_str.startswith('100') and len(id_str) > 10:
                raw_id = int(id_str[3:])

            try:
                result = await self.client.invoke(
                    raw.functions.channels.GetChannels(
                        id=[raw.types.InputChannel(
                            channel_id=raw_id, access_hash=0
                        )]
                    )
                )
                self.storage_chat_id = int(f'-100{raw_id}')
                chat_title = result.chats[0].title if result.chats else 'Unknown'
                logger.info('Storage peer resolved (channel) — title=%s, id=%d', chat_title, self.storage_chat_id)
            except Exception as e:
                logger.error('Gagal resolve storage peer: %s', e)
                raise

        try:
            self.loop.run_until_complete(_start())
            self._ready.set()
            self.loop.run_forever()
        except Exception as e:
            self._init_error = str(e)
            self._ready.set()

    def _run_sync(self, coro):
        # Jalankan coroutine di background loop, tunggu hasilnya di Flask thread.
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=3600)

    def upload_file_from_path(self, filepath: str, filename: str) -> Tuple[str, int]:
        # Upload file ke Telegram langsung dari path disk. Return (file_id, message_id).
        import os
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info('Upload mulai (dari disk) — file=%s, size=%.2f MB', filename, file_size_mb)

        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug('Upload attempt %d/%d — %s', attempt, self.MAX_RETRIES, filename)

                async def _upload():
                    # Tambahkan track progress agar console tidak terlihat stuck
                    last_percent = 0
                    async def progress(current, total):
                        nonlocal last_percent
                        percent = int((current / total) * 100)
                        if percent >= last_percent + 10:
                            logger.info('Upload progress %s: %d%% (%.2f MB / %.2f MB)', 
                                        filename, percent, current / (1024*1024), total / (1024*1024))
                            last_percent = percent
                            
                    return await self.client.send_document(
                        chat_id=self.storage_chat_id,
                        document=filepath,
                        file_name=filename,
                        force_document=True,
                        progress=progress
                    )

                msg = self._run_sync(_upload())

                file_id = msg.document.file_id
                message_id = msg.id
                logger.info('Upload selesai — %s (msg_id: %d)', filename, message_id)
                return file_id, message_id

            except Exception as e:
                last_error = e
                logger.warning('Upload attempt %d gagal: %s', attempt, e)
                if attempt < self.MAX_RETRIES:
                    import time
                    time.sleep(2 ** attempt)

        logger.error('Upload gagal setelah %d percobaan. File: %s', self.MAX_RETRIES, filename)
        raise TelegramUploadError(f'Gagal mengunggah {filename}: {str(last_error)}')

    def upload_file(self, file_bytes: bytes, filename: str) -> Tuple[str, int]:
        # Upload file ke Telegram via send_document. Return (file_id, message_id).
        file_size_mb = len(file_bytes) / (1024 * 1024)
        logger.info('Upload mulai — file=%s, size=%.2f MB', filename, file_size_mb)

        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug('Upload attempt %d/%d — %s', attempt, self.MAX_RETRIES, filename)

                # Kirim bytes mentah ke async function; BytesIO dibuat di dalam loop
                raw = bytes(file_bytes)
                fname = str(filename)

                async def _upload():
                    fobj = io.BytesIO(raw)
                    fobj.name = fname
                    
                    # Tambahkan track progress agar console tidak terlihat stuck
                    last_percent = 0
                    async def progress(current, total):
                        nonlocal last_percent
                        percent = int((current / total) * 100)
                        # Log setiap kelipatan 10%
                        if percent >= last_percent + 10:
                            logger.info('Upload progress %s: %d%% (%.2f MB / %.2f MB)', 
                                        fname, percent, current / (1024*1024), total / (1024*1024))
                            last_percent = percent
                            
                    return await self.client.send_document(
                        chat_id=self.storage_chat_id,
                        document=fobj,
                        file_name=fname,
                        force_document=True,
                        progress=progress
                    )

                msg = self._run_sync(_upload())

                file_id = msg.document.file_id
                message_id = msg.id

                logger.info(
                    'Upload berhasil — file=%s, file_id=%s, message_id=%d',
                    filename, file_id[:20] + '...', message_id
                )

                return file_id, message_id

            except Exception as e:
                last_error = e
                delay = self.RETRY_DELAY * attempt

                logger.warning(
                    'Upload gagal attempt %d/%d — %s — retry dalam %ds',
                    attempt, self.MAX_RETRIES, str(e), delay
                )

                if attempt < self.MAX_RETRIES:
                    time.sleep(delay)

        raise TelegramUploadError(
            f'Upload gagal setelah {self.MAX_RETRIES} percobaan: {filename} — {last_error}'
        )

    def download_file_stream(self, file_id: str) -> Generator[bytes, None, None]:
        # Alirkan file dari Telegram secara on-the-fly via stream_media.
        logger.info('Download stream mulai — file_id=%s...', file_id[:20])

        q = queue.Queue(maxsize=20)

        async def fetch_stream():
            try:
                async for chunk in self.client.stream_media(file_id):
                    q.put(("CHUNK", chunk))
                q.put(("DONE", None))
            except Exception as e:
                logger.error("Error di fetch_stream: %s", e)
                q.put(("ERROR", e))

        asyncio.run_coroutine_threadsafe(fetch_stream(), self.loop)

        def stream_generator():
            while True:
                status, data = q.get()
                if status == "DONE":
                    break
                elif status == "ERROR":
                    raise TelegramUploadError(f"Streaming error dari Telegram: {str(data)}")
                yield data

        return stream_generator()

    def delete_file(self, message_id: int) -> bool:
        # Hapus pesan (file) dari chat Telegram.
        try:
            async def _delete():
                return await self.client.delete_messages(
                    chat_id=self.storage_chat_id,
                    message_ids=message_id
                )

            self._run_sync(_delete())
            logger.info('Berhasil menghapus pesan %d', message_id)
            return True
        except Exception as e:
            logger.warning('Gagal menghapus file (mungkin sudah terhapus): %s', e)
            return False

    def upload_chunk(self, chunk_bytes: bytes, chunk_index: int,
                     original_filename: str) -> tuple[str, int]:
        # Upload satu chunk dengan naming convention {filename}.chunk{index:04d}.
        chunk_filename = f'{original_filename}.chunk{chunk_index:04d}'

        logger.info(
            'Upload chunk %d — %s (%.2f MB)',
            chunk_index, chunk_filename,
            len(chunk_bytes) / (1024 * 1024)
        )

        return self.upload_file(chunk_bytes, chunk_filename)
