"""
pronunciation_client.py — ElevenLabs Pronunciation Dictionaries API client.

Chức năng:
  list_dicts()      — GET /v1/pronunciation-dictionaries
  get_dict()        — GET /v1/pronunciation-dictionaries/{id}
  create_dict()     — POST /v1/pronunciation-dictionaries (từ rules JSON)
  create_dict_pls() — POST /v1/pronunciation-dictionaries (upload PLS file)
  add_rules()       — POST /v1/pronunciation-dictionaries/{id}/{vid}/add-rules
  remove_rules()    — POST /v1/pronunciation-dictionaries/{id}/{vid}/remove-rules
  delete_dict()     — DELETE /v1/pronunciation-dictionaries/{id}/version/{vid}
"""
from __future__ import annotations


from ._http import api_delete, api_get, api_post_form, api_post_json

_BASE = "/v1/pronunciation-dictionaries"


async def list_dicts(
    api_key: str,
    page_size: int = 100,
    cursor: str | None = None,
) -> dict:
    """Lấy list pronunciation dictionaries. Trả về {"pronunciation_dictionaries": [...], "has_more": bool}."""
    params: dict = {"page_size": page_size}
    if cursor:
        params["cursor"] = cursor
    return await api_get(api_key, _BASE, params=params)


async def get_dict(api_key: str, pronunciation_dictionary_id: str) -> dict:
    """Lấy thông tin chi tiết của 1 pronunciation dictionary."""
    return await api_get(api_key, f"{_BASE}/{pronunciation_dictionary_id}")


async def create_dict(
    api_key: str,
    name: str,
    rules: list[dict],
    description: str | None = None,
    workspace_access: str | None = None,
) -> dict:
    """Tạo pronunciation dictionary từ rules trực tiếp.

    rules: list of rule objects:
      For alias:   {"type": "alias", "string_to_replace": "AI", "alias": "Artificial Intelligence"}
      For phoneme: {"type": "phoneme", "string_to_replace": "tomato",
                    "phoneme": "təˈmeɪtoʊ", "alphabet": "ipa"}
    workspace_access: "admin" | "editor" | None (private)
    """
    body: dict = {"name": name, "rules": rules}
    if description:
        body["description"] = description
    if workspace_access:
        body["workspace_access"] = workspace_access
    return await api_post_json(api_key, _BASE, body)


async def create_dict_pls(
    api_key: str,
    name: str,
    pls_file_bytes: bytes,
    pls_filename: str = "dictionary.pls",
    description: str | None = None,
    workspace_access: str | None = None,
) -> dict:
    """Tạo pronunciation dictionary từ PLS file (XML-based Pronunciation Lexicon Specification).

    pls_file_bytes: nội dung file .pls
    """
    data: dict = {"name": name}
    if description:
        data["description"] = description
    if workspace_access:
        data["workspace_access"] = workspace_access
    files = [("file", (pls_filename, pls_file_bytes, "application/x-pls"))]
    return await api_post_form(api_key, _BASE, data=data, files=files)


async def add_rules(
    api_key: str,
    pronunciation_dictionary_id: str,
    version_id: str,
    rules: list[dict],
) -> dict:
    """Thêm rules vào pronunciation dictionary, tạo version mới.

    Trả về version mới của dictionary.
    """
    return await api_post_json(
        api_key,
        f"{_BASE}/{pronunciation_dictionary_id}/{version_id}/add-rules",
        {"rules": rules},
    )


async def remove_rules(
    api_key: str,
    pronunciation_dictionary_id: str,
    version_id: str,
    rule_strings: list[str],
) -> dict:
    """Xóa rules khỏi pronunciation dictionary theo string_to_replace.

    rule_strings: list các string_to_replace cần xóa.
    Trả về version mới của dictionary.
    """
    return await api_post_json(
        api_key,
        f"{_BASE}/{pronunciation_dictionary_id}/{version_id}/remove-rules",
        {"rule_strings": rule_strings},
    )


async def delete_dict(
    api_key: str,
    pronunciation_dictionary_id: str,
    version_id: str,
) -> dict:
    """Xóa 1 version của pronunciation dictionary."""
    return await api_delete(
        api_key,
        f"{_BASE}/{pronunciation_dictionary_id}/version/{version_id}",
    )
