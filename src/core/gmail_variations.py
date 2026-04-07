"""
gmail_variations.py — Generate Gmail alias variations từ một base email.

Gmail coi các địa chỉ sau là CÙNG một inbox:
  - abc@gmail.com  ≡  a.b.c@gmail.com  (dot trick)
  - abc@gmail.com  ≡  abc+tag@gmail.com (plus tag)
  - abc@gmail.com  ≡  abc@googlemail.com (domain alias)

Module này enumerate tất cả biến thể hợp lệ để dùng khi đăng ký tài khoản trên
các dịch vụ khác nhau — mỗi variation về mặt kỹ thuật là email riêng biệt với
hầu hết các site, nhưng email vẫn gửi về inbox gốc.
"""
from __future__ import annotations

import re
from itertools import product
from typing import NamedTuple


class GmailVariation(NamedTuple):
    email: str
    technique: str   # "plus" | "dot" | "googlemail"
    tag: str | None  # plus tag nếu có


def _parse_gmail(email: str) -> tuple[str, str] | None:
    """
    Tách base username và domain từ gmail address.
    Loại bỏ dấu chấm và plus tag đã có sẵn để lấy username gốc.
    Trả None nếu không phải gmail.
    """
    m = re.fullmatch(r"([^+@]+)(?:\+[^@]*)?\@(gmail\.com|googlemail\.com)", email.lower().strip())
    if not m:
        return None
    username = m.group(1).replace(".", "")  # loại bỏ dấu chấm → base username
    return username, "gmail.com"


def generate_dot_variations(username: str, max_username_len: int = 12, mid_divisor: int = 2) -> list[str]:
    """
    Tạo tất cả biến thể dấu chấm cho username (không có @ domain).
    Số lượng: 2^(len-1) — exponential, nên cap ở max_username_len ký tự.
    Ví dụ: "abc" → ["abc", "a.bc", "ab.c", "a.b.c"]
    """
    n = len(username)
    if n <= 1:
        return [username]
    if n > max_username_len:
        # Quá nhiều → chỉ lấy một số mẫu đặc biệt
        mid = n // mid_divisor
        full = ".".join(username)
        return [username, username[:mid] + "." + username[mid:], full]

    # Mỗi "khe" giữa ký tự có thể có dấu chấm hoặc không
    gaps = n - 1
    results: list[str] = []
    for mask in product([False, True], repeat=gaps):
        chars: list[str] = [username[0]]
        for i, has_dot in enumerate(mask):
            if has_dot:
                chars.append(".")
            chars.append(username[i + 1])
        results.append("".join(chars))
    return results


def generate_plus_variations(username: str, tags: list[str]) -> list[str]:
    """
    Tạo variations dạng username+tag@gmail.com.
    tags: danh sách tag strings cần tạo.
    """
    return [f"{username}+{tag}" for tag in tags if tag]


def generate_variations(
    base_email: str,
    use_plus: bool = True,
    use_dot: bool = True,
    use_googlemail: bool = True,
    plus_tags: list[str] | None = None,
    dot_max_username_len: int = 12,
    dot_long_sample_mid_divisor: int = 2,
) -> list[GmailVariation]:
    """
    Tạo tất cả Gmail variations từ base_email.

    Args:
        base_email: Gmail gốc (e.g. "abc@gmail.com")
        use_plus: bật biến thể +tag
        use_dot: bật biến thể dot-trick
        use_googlemail: bật/nhân đôi sang @googlemail.com
        plus_tags: danh sách tag cho +tag (default: ["1","2",...,"20"])
        dot_max_username_len: username dài hơn này → sample thay vì enumerate toàn bộ
        dot_long_sample_mid_divisor: divisor tính điểm giữa khi username dài

    Returns:
        List[GmailVariation] (không bao gồm base_email gốc)
    """
    parsed = _parse_gmail(base_email)
    if not parsed:
        raise ValueError(f"Không phải địa chỉ Gmail hợp lệ: {base_email!r}")
    username, _ = parsed

    if plus_tags is None:
        plus_tags = [str(i) for i in range(1, 21)]

    results: list[GmailVariation] = []

    # Plus variations (@gmail.com)
    if use_plus:
        for tag in plus_tags:
            results.append(GmailVariation(
                email=f"{username}+{tag}@gmail.com",
                technique="plus",
                tag=tag,
            ))

    # Dot variations (@gmail.com)
    if use_dot:
        for variant in generate_dot_variations(username, dot_max_username_len, dot_long_sample_mid_divisor):
            if variant == username:
                continue  # bỏ qua base (không có dấu chấm = nguyên gốc)
            results.append(GmailVariation(
                email=f"{variant}@gmail.com",
                technique="dot",
                tag=None,
            ))

    # Googlemail: @googlemail.com cho từng technique đang bật
    # — base googlemail alias
    if use_googlemail:
        results.append(GmailVariation(
            email=f"{username}@googlemail.com",
            technique="googlemail",
            tag=None,
        ))
        # — plus + googlemail
        if use_plus:
            for tag in plus_tags:
                results.append(GmailVariation(
                    email=f"{username}+{tag}@googlemail.com",
                    technique="googlemail",
                    tag=tag,
                ))
        # — dot + googlemail
        if use_dot:
            for variant in generate_dot_variations(username, dot_max_username_len, dot_long_sample_mid_divisor):
                if variant == username:
                    continue
                results.append(GmailVariation(
                    email=f"{variant}@googlemail.com",
                    technique="googlemail",
                    tag=None,
                ))

    return results


def normalize_gmail(email: str) -> str:
    """
    Normalize bất kỳ Gmail variation nào về dạng canonical (username không chấm, không tag).
    Dùng để lookup trong DB.
    Ví dụ: "a.b+tag@googlemail.com" → "ab@gmail.com"
    """
    parsed = _parse_gmail(email)
    if not parsed:
        return email.lower().strip()
    username, _ = parsed
    return f"{username}@gmail.com"
