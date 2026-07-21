# Private Cloud Storage - AES-256-CBC encryption module.

import hashlib
import hmac      # Timing-safe comparison via hmac.compare_digest
import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


class AESCipher:
    # Operasi kriptografi AES-256-CBC: enkripsi/dekripsi file dan verifikasi integritas.

    KEY_SIZE = 32
    IV_SIZE = 16
    BLOCK_SIZE = AES.block_size

    @staticmethod
    def generate_key() -> bytes:
        # Generate random AES-256 key (32 bytes).
        return get_random_bytes(32)

    @staticmethod
    def generate_iv() -> bytes:
        # Generate random IV (16 bytes). Harus baru setiap enkripsi — jangan reuse.
        return get_random_bytes(16)

    @staticmethod
    def encrypt_file(file_bytes: bytes, key: bytes, iv: bytes) -> bytes:
        # Enkripsi data dengan AES-256-CBC + PKCS7 padding. Return ciphertext.
        if len(key) != 32:
            raise ValueError(f'Key harus 32 bytes, diterima {len(key)} bytes')
        if len(iv) != 16:
            raise ValueError(f'IV harus 16 bytes, diterima {len(iv)} bytes')

        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(pad(file_bytes, AES.block_size))

    @staticmethod
    def decrypt_file(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        # Dekripsi data dari AES-256-CBC. Return plaintext.
        if len(key) != 32:
            raise ValueError(f'Key harus 32 bytes, diterima {len(key)} bytes')
        if len(iv) != 16:
            raise ValueError(f'IV harus 16 bytes, diterima {len(iv)} bytes')

        cipher = AES.new(key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(ciphertext), AES.block_size)

    @staticmethod
    def stream_encrypt_to_file(stream_generator, key: bytes, iv: bytes, output_filepath: str):
        # Enkripsi AES-256-CBC secara streaming dari generator dan tulis langsung ke file.
        # Menghindari pemuatan seluruh file ke memori.
        if len(key) != 32:
            raise ValueError(f'Key harus 32 bytes, diterima {len(key)} bytes')
        if len(iv) != 16:
            raise ValueError(f'IV harus 16 bytes, diterima {len(iv)} bytes')

        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        with open(output_filepath, 'wb') as f_out:
            # Karena AES block cipher (16 bytes), data sebelum blok terakhir harus kelipatan 16.
            # Generator asalnya membaca block besar (misal 64KB), kita kumpulkan dan pastikan
            # kelipatan 16 sebelum encrypt.
            buffer = bytearray()
            for chunk in stream_generator:
                buffer.extend(chunk)
                if len(buffer) >= AES.block_size:
                    process_len = (len(buffer) // AES.block_size) * AES.block_size
                    to_process = bytes(buffer[:process_len])
                    del buffer[:process_len]
                    f_out.write(cipher.encrypt(to_process))
                    
            # Padding blok terakhir (PKCS7)
            f_out.write(cipher.encrypt(pad(bytes(buffer), AES.block_size)))

    @staticmethod
    def stream_decrypt_file(stream_generator, key: bytes, iv: bytes):
        # Dekripsi AES-256-CBC secara streaming dari generator.
        # Menghasilkan chunk plaintext dan melakukan unpad hanya pada blok terakhir.
        if len(key) != 32:
            raise ValueError(f'Key harus 32 bytes, diterima {len(key)} bytes')
        if len(iv) != 16:
            raise ValueError(f'IV harus 16 bytes, diterima {len(iv)} bytes')

        cipher = AES.new(key, AES.MODE_CBC, iv)
        previous_chunk = b""

        for chunk in stream_generator:
            data = previous_chunk + chunk
            if not data:
                continue
            
            # Kita harus menyisakan setidaknya 1 blok (16 bytes) di previous_chunk
            # untuk di-unpad di akhir aliran.
            if len(data) <= AES.block_size:
                previous_chunk = data
                continue
                
            process_len = (len(data) - AES.block_size) // AES.block_size * AES.block_size
            if process_len == 0:
                previous_chunk = data
                continue
                
            to_process = data[:process_len]
            previous_chunk = data[process_len:]
            
            yield cipher.decrypt(to_process)
            
        if previous_chunk:
            last_decrypted = cipher.decrypt(previous_chunk)
            yield unpad(last_decrypted, AES.block_size)

    @staticmethod
    def compute_sha256(file_bytes: bytes) -> str:
        # Return SHA-256 hex digest dari data.
        return hashlib.sha256(file_bytes).hexdigest()

    @staticmethod
    def verify_integrity(file_bytes: bytes, expected_hash: str) -> bool:
        # Verifikasi integritas file via SHA-256.
        #
        # Menggunakan hmac.compare_digest() untuk mencegah timing attack
        # (attacker tidak bisa mengukur waktu perbandingan karakter per karakter).
        actual_hash = hashlib.sha256(file_bytes).hexdigest()
        return hmac.compare_digest(actual_hash, expected_hash)


# OWASP 2023 merekomendasikan ≥ 600.000 iterasi PBKDF2-SHA256 untuk password/key derivation
_KDF_ITERATIONS = 600_000


def _derive_key(master_key: str, salt: bytes) -> bytes:
    # Derive 32-byte AES key dari master key menggunakan PBKDF2-HMAC-SHA256.
    #
    # Salt random 16-byte mencegah rainbow table attack.
    # 600.000 iterasi memperlambat brute force ~600.000× vs SHA-256 tunggal.
    return hashlib.pbkdf2_hmac(
        'sha256',
        master_key.encode('utf-8'),
        salt,
        iterations=_KDF_ITERATIONS,
        dklen=32,
    )


def encrypt_key(aes_key: bytes, master_key: str) -> str:
    # Enkripsi AES key per-file dengan master key aplikasi.
    #
    # Format output (base64): [salt (16B)] + [IV (16B)] + [ciphertext]
    #
    # ⚠️  BREAKING CHANGE: Format lama adalah [IV + ciphertext] tanpa salt.
    # Data yang dienkripsi dengan versi sebelumnya TIDAK kompatibel.
    # Diperlukan migrasi DB untuk re-encrypt semua aes_key_encrypted.
    salt = get_random_bytes(16)
    derived_key = _derive_key(master_key, salt)
    iv = get_random_bytes(16)
    cipher = AES.new(derived_key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(aes_key, AES.block_size))
    return base64.b64encode(salt + iv + encrypted).decode('utf-8')


def decrypt_key(encrypted_key: str, master_key: str) -> bytes:
    # Dekripsi AES key yang dienkripsi oleh encrypt_key().
    #
    # Format input (base64): [salt (16B)] + [IV (16B)] + [ciphertext]
    #
    # ⚠️  BREAKING CHANGE: Tidak kompatibel dengan format lama [IV + ciphertext].
    raw = base64.b64decode(encrypted_key)
    salt = raw[:16]
    iv = raw[16:32]
    ciphertext = raw[32:]

    derived_key = _derive_key(master_key, salt)
    cipher = AES.new(derived_key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)


def derive_user_key(password: str, salt: str) -> bytes:
    # Derive a 32-byte key directly from a password and string salt
    return _derive_key(password, salt.encode('utf-8'))


def encrypt_string(data: str, derived_key: bytes) -> str:
    # Encrypts a plaintext string using a pre-derived 32-byte key
    iv = get_random_bytes(16)
    cipher = AES.new(derived_key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
    return base64.b64encode(iv + encrypted).decode('utf-8')


def decrypt_string(encrypted_data: str, derived_key: bytes) -> str:
    # Decrypts a base64 string back to plaintext using a pre-derived 32-byte key
    raw = base64.b64decode(encrypted_data)
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = AES.new(derived_key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode('utf-8')


if __name__ == '__main__':
    print('=' * 60)
    print('  AES-256-CBC — Unit Test')
    print('=' * 60)

    cipher = AESCipher()

    key = cipher.generate_key()
    iv = cipher.generate_iv()
    print(f'\n[1] Generate Key : {key.hex()} ({len(key)} bytes)')
    print(f'    Generate IV  : {iv.hex()} ({len(iv)} bytes)')
    assert len(key) == 32
    assert len(iv) == 16
    print('    ✅ PASSED')

    plaintext = b'Hello, Private Cloud Storage! Ini adalah data rahasia.'
    encrypted = cipher.encrypt_file(plaintext, key, iv)
    decrypted = cipher.decrypt_file(encrypted, key, iv)
    print(f'\n[2] Plaintext    : {plaintext}')
    print(f'    Encrypted    : {encrypted[:40].hex()}... ({len(encrypted)} bytes)')
    print(f'    Decrypted    : {decrypted}')
    assert decrypted == plaintext
    assert encrypted != plaintext
    print('    ✅ PASSED')

    big_data = b'X' * 10_000_000
    enc_big = cipher.encrypt_file(big_data, key, iv)
    dec_big = cipher.decrypt_file(enc_big, key, iv)
    assert dec_big == big_data
    print(f'\n[3] File 10MB    : encrypt {len(enc_big)} bytes → decrypt {len(dec_big)} bytes')
    print('    ✅ PASSED')

    hash_val = cipher.compute_sha256(plaintext)
    print(f'\n[4] SHA-256      : {hash_val}')
    assert len(hash_val) == 64
    assert cipher.verify_integrity(plaintext, hash_val)
    assert not cipher.verify_integrity(b'data lain', hash_val)
    print('    ✅ PASSED')

    master = 'my-super-secret-master-key'
    enc_key = encrypt_key(key, master)
    dec_key = decrypt_key(enc_key, master)
    print(f'\n[5] Master Key   : "{master}"')
    print(f'    Encrypted Key: {enc_key[:50]}...')
    print(f'    Decrypted Key: {dec_key.hex()}')
    assert dec_key == key
    print('    ✅ PASSED')

    wrong_key = cipher.generate_key()
    try:
        cipher.decrypt_file(encrypted, wrong_key, iv)
        print('\n[6] ❌ FAILED — seharusnya error dengan key salah')
    except Exception:
        print('\n[6] Wrong key    : ValueError raised sebagaimana diharapkan')
        print('    ✅ PASSED')

    print('\n' + '=' * 60)
    print('  Semua test PASSED! ✅')
    print('=' * 60)
