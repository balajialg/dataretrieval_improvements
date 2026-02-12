import string
import hashlib
import re
import os


_ord = lambda byte: byte
_escape_slug_safe_chars = set(string.ascii_lowercase + string.digits)
SAFE = set(string.ascii_letters + string.digits)
ESCAPE_CHAR = "-"


_alpha_lower = tuple(string.ascii_lowercase)
_alphanum_lower = tuple(string.ascii_lowercase + string.digits)

# patterns _do not_ need to cover length or start/end conditions,
# which are handled separately
_object_pattern = re.compile(r"^[a-z0-9\-]+$")
_label_pattern = re.compile(r"^[a-z0-9\.\-_]+$", flags=re.IGNORECASE)
# match anything that's not lowercase alphanumeric (will be stripped, replaced with '-')
_non_alphanum_pattern = re.compile(r"[^a-z0-9]+")

_hash_length = 8


def escape(to_escape, safe=SAFE, escape_char=ESCAPE_CHAR, allow_collisions=False):
    if isinstance(to_escape, bytes):
        to_escape = to_escape.decode("utf8")
    if not isinstance(safe, set):
        safe = set(safe)
    if allow_collisions:
        safe.add(escape_char)
    elif escape_char in safe:
        warnings.warn(
            f"Escape character {escape_char!r} cannot be a safe character."
            " Set allow_collisions=True if you want to allow ambiguous escaped strings.",
            RuntimeWarning,
            stacklevel=2,
        )
        safe.remove(escape_char)

    chars = []
    for c in to_escape:
        if c in safe:
            chars.append(c)
        else:
            chars.append(_escape_char(c, escape_char))
    return "".join(chars)


def escape_slug(name):
    """Generate a slug with the legacy system, safe_slug is preferred."""
    return escape(
        name,
        safe=_escape_slug_safe_chars,
        escape_char="-",
    ).lower()


def _escape_char(c, escape_char):
    buf = []
    for byte in c.encode("utf8"):
        buf.append(escape_char)
        buf.append(f"{_ord(byte):X}")
    return "".join(buf)


def _extract_safe_name(name, max_length):
    """Generate safe substring of a name

    Guarantees:

    - always starts with a lowercase letter
    - always ends with a lowercase letter or number
    - never more than one hyphen in a row (no '--')
    - only contains lowercase letters, numbers, and hyphens
    - length at least 1 ('x' if other rules strips down to empty string)
    - max length not exceeded
    """
    # compute safe slug from name (don't worry about collisions, hash handles that)
    # cast to lowercase
    # replace any sequence of non-alphanumeric characters with a single '-'
    safe_name = _non_alphanum_pattern.sub("-", name.lower())
    # truncate to max_length chars, strip '-' off ends
    safe_name = safe_name.lstrip("-")[:max_length].rstrip("-")
    # ensure starts with lowercase letter
    if safe_name and not safe_name.startswith(_alpha_lower):
        safe_name = "x-" + safe_name[: max_length - 2]
    if not safe_name:
        # make sure it's non-empty
        safe_name = "x"
    return safe_name


def strip_and_hash(name, max_length=32):
    """Generate an always-safe, unique string for any input

    truncates name to max_length - len(hash_suffix) to fit in max_length
    after adding hash suffix
    """
    name_length = max_length - (_hash_length + 3)
    if name_length < 1:
        raise ValueError(f"Cannot make safe names shorter than {_hash_length + 4}")
    # quick, short hash to avoid name collisions
    name_hash = hashlib.sha256(name.encode("utf8")).hexdigest()[:_hash_length]
    safe_name = _extract_safe_name(name, name_length)
    # due to stripping of '-' in _extract_safe_name,
    # the result will always have _exactly_ '---', never '--' nor '----'
    # use '---' to avoid colliding with `{username}--{servername}` template join
    return f"{safe_name}---{name_hash}"


def is_valid_default(s):
    """Strict is_valid

    Returns True if it's valid for _all_ our known uses

    Currently, this is the same as is_valid_object_name,
    which produces a valid DNS label under RFC1035 AND RFC 1123,
    which is always also a valid label value.
    """
    return is_valid_object_name(s)


def _is_valid_general(
    s, starts_with=None, ends_with=None, pattern=None, min_length=None, max_length=None
):
    """General is_valid check

    Checks rules:
    """
    if min_length and len(s) < min_length:
        return False
    if max_length and len(s) > max_length:
        return False
    if starts_with and not s.startswith(starts_with):
        return False
    if ends_with and not s.endswith(ends_with):
        return False
    if pattern and not pattern.match(s):
        return False
    return True


def is_valid_object_name(s):
    """is_valid check for object names

    Ensures all strictest object rules apply,
    satisfying both RFC 1035 and 1123 dns label name rules

    - 63 characters
    - starts with letter, ends with letter or number
    - only lowercalse letters, numbers, '-'
    """
    # object rules: https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names
    return _is_valid_general(
        s,
        starts_with=_alpha_lower,
        ends_with=_alphanum_lower,
        pattern=_object_pattern,
        max_length=63,
        min_length=1,
    )


def is_valid_label(s):
    """is_valid check for label values"""
    # label rules: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set
    if not s:
        # empty strings are valid labels
        return True
    return _is_valid_general(
        s,
        starts_with=_alphanum,
        ends_with=_alphanum,
        pattern=_label_pattern,
        max_length=63,
    )


def safe_slug(name, is_valid=is_valid_default, max_length=None):
    """Always generate a safe slug
    is_valid should be a callable that returns True if a given string follows appropriate rules,
    and False if it does not.

    Given a string, if it's already valid, use it.
    If it's not valid, follow a safe encoding scheme that ensures:

    1. validity, and
    2. no collisions
    """
    if "--" in name:
        # don't accept any names that could collide with the safe slug
        return strip_and_hash(name, max_length=max_length or 32)
    # allow max_length override for truncated sub-strings
    if is_valid(name) and (max_length is None or len(name) <= max_length):
        return name
    else:
        return strip_and_hash(name, max_length=max_length or 32)


def email_matches_foldername(email, foldername):
    foldername = foldername.split('.tar')[0].lower()
    username = email.split('@')[0].lower()
    if escape_slug(username) == foldername:
        return True
    if safe_slug(username) == foldername:
        return True
    if escape_slug(email.lower()) == foldername:
        return True
    if safe_slug(email.lower()) == foldername:
        return True
    return False


def main():
    email = os.getenv('RECEIVER_EMAIL')
    extracted_link = os.getenv('EXTRACTED_LINK')
    all_links = extracted_link.split(',')
    valid_mapping = "valid"
    for link in all_links:
        foldername = link.split('/')[-1]
        if not email_matches_foldername(email, foldername):
            valid_mapping = "invalid"
            break

    env_file = os.getenv('GITHUB_ENV')
    with open(env_file, "a") as myfile:
        myfile.write(f"emailMatchesFolder={valid_mapping}\n")
    

# Run the main function
if __name__ == "__main__":
    main()