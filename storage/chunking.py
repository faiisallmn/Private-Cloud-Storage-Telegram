
import math
from typing import List, Dict

from crypto.aes import AESCipher



CHUNK_SIZE = 1_800_000_000  


class FileChunker:


    def __init__(self, chunk_size: int = CHUNK_SIZE):

        self.chunk_size = chunk_size
        self._cipher = AESCipher()

    #  1. should_chunk
    def should_chunk(self, file_size: int) -> bool:

        return file_size > self.chunk_size

    #  2. split_file
    def split_file(self, file_bytes: bytes) -> List[bytes]:
        chunks = []
        total = len(file_bytes)

        for offset in range(0, total, self.chunk_size):
            chunk = file_bytes[offset:offset + self.chunk_size]
            chunks.append(chunk)

        return chunks

    #  3. merge_chunks
    def merge_chunks(self, chunks: List[bytes]) -> bytes:
        if not chunks:
            raise ValueError('Daftar chunk tidak boleh kosong')

        return b''.join(chunks)

    #  4. get_chunk_info
    def get_chunk_info(self, file_size: int) -> Dict:
        if file_size <= 0:
            return {
                'total_chunks': 0,
                'chunk_size': self.chunk_size,
                'last_chunk_size': 0,
            }

        total_chunks = math.ceil(file_size / self.chunk_size)
        last_chunk_size = file_size % self.chunk_size

        # Jika file tepat habis dibagi, chunk terakhir = chunk_size
        if last_chunk_size == 0:
            last_chunk_size = self.chunk_size

        return {
            'total_chunks': total_chunks,
            'chunk_size': self.chunk_size,
            'last_chunk_size': last_chunk_size,
        }

    #  5. encrypt_chunks
    def encrypt_chunks(self, chunks: List[bytes]) -> List[Dict]:
        encrypted_chunks = []

        for index, chunk in enumerate(chunks):
            # Generate key & IV unik per chunk
            key = self._cipher.generate_key()
            iv = self._cipher.generate_iv()

            # Hitung hash SEBELUM enkripsi (integritas plaintext)
            sha256_hash = self._cipher.compute_sha256(chunk)

            # Enkripsi chunk
            encrypted = self._cipher.encrypt_file(chunk, key, iv)

            encrypted_chunks.append({
                'chunk_index': index,
                'encrypted_bytes': encrypted,
                'key_hex': key.hex(),
                'iv_hex': iv.hex(),
                'sha256_hash': sha256_hash,
                'original_size': len(chunk),
            })

        return encrypted_chunks

    #  6. decrypt_chunks
    def decrypt_chunks(self, encrypted_chunks: List[Dict]) -> List[bytes]:
        # Urutkan berdasarkan index untuk menjamin urutan benar
        sorted_chunks = sorted(encrypted_chunks, key=lambda c: c['chunk_index'])

        decrypted_chunks = []

        for chunk_info in sorted_chunks:
            key = bytes.fromhex(chunk_info['key_hex'])
            iv = bytes.fromhex(chunk_info['iv_hex'])
            expected_hash = chunk_info['sha256_hash']

            # Dekripsi
            decrypted = self._cipher.decrypt_file(
                chunk_info['encrypted_bytes'], key, iv
            )

            # Verifikasi integritas
            if not self._cipher.verify_integrity(decrypted, expected_hash):
                raise ValueError(
                    f'Integritas chunk {chunk_info["chunk_index"]} gagal! '
                    f'File mungkin corrupt atau telah dimodifikasi.'
                )

            decrypted_chunks.append(decrypted)

        return decrypted_chunks


#  Unit Test
if __name__ == '__main__':
    print('=' * 60)
    print('  FileChunker — Unit Test')
    print('=' * 60)

    # Gunakan chunk kecil (1 KB) untuk test cepat
    chunker = FileChunker(chunk_size=1024)

    # --- Test 1: should_chunk ---
    assert not chunker.should_chunk(512), 'File 512B seharusnya tidak di-chunk'
    assert chunker.should_chunk(2048), 'File 2KB seharusnya di-chunk'
    print('\n[1] should_chunk      ✅ PASSED')

    # --- Test 2: get_chunk_info ---
    info = chunker.get_chunk_info(2560)  # 2.5 KB → 3 chunks
    assert info['total_chunks'] == 3
    assert info['chunk_size'] == 1024
    assert info['last_chunk_size'] == 512
    print(f'[2] get_chunk_info    ✅ PASSED  →  {info}')

    # --- Test 3: split_file & merge_chunks ---
    original = b'A' * 1000 + b'B' * 1000 + b'C' * 560  # 2560 bytes
    chunks = chunker.split_file(original)
    assert len(chunks) == 3, f'Seharusnya 3 chunk, dapat {len(chunks)}'
    assert len(chunks[0]) == 1024
    assert len(chunks[1]) == 1024
    assert len(chunks[2]) == 512
    merged = chunker.merge_chunks(chunks)
    assert merged == original, 'Merge tidak menghasilkan data asli!'
    print(f'[3] split + merge     ✅ PASSED  →  {len(chunks)} chunks')

    # --- Test 4: encrypt_chunks ---
    enc_chunks = chunker.encrypt_chunks(chunks)
    assert len(enc_chunks) == 3
    # Pastikan setiap chunk punya key & IV berbeda
    keys = [c['key_hex'] for c in enc_chunks]
    ivs = [c['iv_hex'] for c in enc_chunks]
    assert len(set(keys)) == 3, 'Setiap chunk harus punya key BERBEDA!'
    assert len(set(ivs)) == 3, 'Setiap chunk harus punya IV BERBEDA!'
    print(f'[4] encrypt_chunks    ✅ PASSED  →  {len(set(keys))} unique keys')

    # --- Test 5: decrypt_chunks + integrity ---
    dec_chunks = chunker.decrypt_chunks(enc_chunks)
    reassembled = chunker.merge_chunks(dec_chunks)
    assert reassembled == original, 'Data setelah decrypt+merge tidak cocok!'
    print('[5] decrypt + verify  ✅ PASSED')

    # --- Test 6: Tampered chunk → error ---
    tampered = enc_chunks.copy()
    tampered[1] = {**tampered[1], 'sha256_hash': 'abc123'}
    try:
        chunker.decrypt_chunks(tampered)
        print('[6] tamper detect     ❌ FAILED — seharusnya raise ValueError')
    except ValueError as e:
        print(f'[6] tamper detect     ✅ PASSED  →  {e}')

    # --- Test 7: Shuffle order → still works ---
    import random
    shuffled = enc_chunks.copy()
    random.shuffle(shuffled)
    dec_shuffled = chunker.decrypt_chunks(shuffled)
    assert chunker.merge_chunks(dec_shuffled) == original
    print('[7] shuffle order     ✅ PASSED  →  auto-sorted by chunk_index')

    print('\n' + '=' * 60)
    print('  Semua test PASSED! ✅')
    print('=' * 60)
