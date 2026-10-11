"""backend/app/passwords.py - scrambles passwords before they're saved, and
checks them at login.

Uses the bcrypt library directly. The popular wrapper, passlib, is no longer
maintained and prints a warning with current versions of bcrypt.
"""

import functools
import os

import bcrypt

# How much work scrambling takes - bcrypt's own default. Slow enough that
# guessing passwords from a stolen database is expensive, fast enough that
# logging in doesn't feel slow. The tests turn it down, because they log in
# dozens of times; the real default is unchanged.
BCRYPT_ROUNDS = int(os.environ.get("RETURNS_DASHBOARD_BCRYPT_ROUNDS", "12"))

# bcrypt only uses the first 72 bytes of a password and silently ignores the
# rest. Longer passwords are refused rather than quietly cut short, so the
# password you type is always the password that's checked.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    if len(pw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # A damaged saved password counts as "wrong password", not a crash.
        return False


@functools.lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A scrambled password that matches nothing, made the first time it's
    needed (not at startup, so restarts stay fast)."""
    return hash_password(os.urandom(24).hex())


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    """Check a password. Takes the same time whether or not the user exists.

    Pass None if there's no account with that email. If that case returned
    straight away, "no such account" would answer instantly while "wrong
    password" took longer - and an attacker could time the difference to find
    out which emails have accounts. So a check always runs.
    """
    if password_hash is None:
        verify_password(password, _dummy_hash())
        return False
    return verify_password(password, password_hash)
