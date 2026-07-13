from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        valid = password_hasher.verify(password_hash, candidate)
    except InvalidHashError, VerificationError, VerifyMismatchError:
        return False
    return bool(valid)


def needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
