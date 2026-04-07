# Testing

---

## Chạy tests

```powershell
# Unit tests (nhanh, không cần internet/browser)
python -m pytest tests/test_unit.py -v

# Integration tests (cần internet, gọi mail.tm API thật)
python -m pytest tests/test_integration.py -v

# Tất cả
python -m pytest tests/ -v
```

---

## Unit Tests (`tests/test_unit.py`)

**65 tests** — không có network, không có browser, tất cả external calls đều được mock.

### `TestRandomString` (3 tests)

Test `src/mail/client._random_string()`:

| Test | Mô tả |
|---|---|
| `test_length` | `_random_string(10)` trả về đúng 10 ký tự |
| `test_charset` | Chỉ có lowercase + digits |
| `test_unique` | 20 lần generate → ít nhất 2 giá trị khác nhau |

### `TestExtractLinks` (3 tests)

Test `src/mail/client._extract_links()`:

| Test | Mô tả |
|---|---|
| `test_finds_url` | Tìm URL trong text có chứa "verify" |
| `test_filters_by_contains` | Chỉ trả về URL có substring "elevenlabs" |
| `test_empty_body` | Text không có URL → trả về `[]` |

### `TestTempMailClientCreate` (2 tests)

Test `TempMailClient.create()` với mock HTTP:

| Test | Mô tả |
|---|---|
| `test_create_sets_email` | Email kết thúc bằng `@test.example`, token và account_id đúng |
| `test_create_raises_when_no_domains` | `RuntimeError("No domains")` khi mail.tm trả về list trống |

Mock setup:
```python
@patch("src.mail.client.requests.get")   # GET /domains
@patch("src.mail.client.requests.post")  # POST /accounts + POST /token
def test_create_sets_email(self, mock_post, mock_get):
    mock_get.return_value = domains_response
    mock_post.side_effect = [account_response, token_response]
```

### `TestTempMailClientWait` (5 tests)

Test `wait_for_message()` và `extract_link()` với mock:

| Test | Mô tả |
|---|---|
| `test_returns_none_on_timeout` | Poll trống → timeout → return `None` |
| `test_returns_matching_message` | Message từ "elevenlabs" → return message dict |
| `test_extract_link_finds_url` | Extract link có "verify" |
| `test_extract_link_returns_none_when_empty` | Body không có link → `None` |
| `test_extract_link_filters_by_contains` | Filter theo "elevenlabs" |

### `TestGeneratePassword` (5 tests)

Test `src/core/password.generate_password()`:

| Test | Mô tả |
|---|---|
| `test_length` | Độ dài đúng 14 |
| `test_has_uppercase` | Luôn có ít nhất 1 ký tự hoa |
| `test_has_digit` | Luôn có ít nhất 1 chữ số |
| `test_has_special` | Luôn có `@` |
| `test_min_length` | Hoạt động với length=8 |

### `TestGenerateUsername` (3 tests)

Test `src/core/password.generate_username()`:

| Test | Mô tả |
|---|---|
| `test_length` | Độ dài đúng 17 |
| `test_starts_with_letter` | Ký tự đầu luôn là chữ cái |
| `test_lowercase_alphanumeric` | Chỉ chứa lowercase + digits |

### `TestAccountRecord` (3 tests)

Test `src/core/storage.AccountRecord`:

| Test | Mô tả |
|---|---|
| `test_to_json_entry_includes_api_key` | api_key được include khi có |
| `test_to_json_entry_omits_empty_api_key` | api_key bị bỏ khi rỗng |
| `test_to_json_entry_with_api_key` | `service` không xuất hiện trong output |

### `TestAccountRepository` (1 test)

Test `src/core/storage.AccountRepository`:

| Test | Mô tả |
|---|---|
| `test_save_writes_json` | Save vào temp dir → JSON đúng, `accounts.txt` không tồn tại |

```python
with tempfile.TemporaryDirectory() as tmp:
    repo = AccountRepository(Path(tmp))
    repo.save(AccountRecord("ELEVENLABS", "x@y.com", "P@1", "sk_xyz"))

    # accounts.txt intentionally removed
    assert not (Path(tmp) / "accounts.txt").exists()

    data = json.loads((Path(tmp) / "elevenlabs_accounts.json").read_text())
    assert data[0]["email"] == "x@y.com"
    assert data[0]["api_key"] == "sk_xyz"
```

### `TestLoadConfig` (2 tests)

Test `src/config/settings.load_config()`:

| Test | Mô tả |
|---|---|
| `test_loads_yaml_values` | Đọc YAML temp file → `append_log`, `headless`, `email_wait` đúng |
| `test_returns_defaults_on_bad_file` | File không tồn tại → trả về defaults không exception |

### `TestValidCoord` (10 tests)

Test `src/services/elevenlabs/captcha._valid_coord()`:

| Test | Mô tả |
|---|---|
| `test_center` | `{x: 0.5, y: 0.5}` → True |
| `test_origin` | `{x: 0.0, y: 0.0}` → True |
| `test_max` | `{x: 1.0, y: 1.0}` → True |
| `test_x_over` | x = 1.01 → False |
| `test_y_negative` | y = −0.01 → False |
| `test_missing_x` | Dict thiếu `x` → False |
| `test_missing_y` | Dict thiếu `y` → False |
| `test_empty_dict` | `{}` → False |
| `test_not_dict` | List thay vì dict → False |
| `test_string_values` | `{x: "0.5", y: "0.5"}` → False |

### `TestArea` (2 tests)

Test `src/services/elevenlabs/captcha._area()`:

| Test | Mô tả |
|---|---|
| `test_normal` | `400×300` → `120_000` |
| `test_zero_width` | width=0 → `0` |

### `TestFmtBbox` (1 test)

Test `src/services/elevenlabs/captcha._fmt_bbox()`:

| Test | Mô tả |
|---|---|
| `test_contains_all_fields` | Output string chứa tất cả giá trị x/y/width/height |

### `TestFindChallengeBbox` (8 tests)

Test `src/services/elevenlabs/captcha._find_challenge_bbox()` với mock page:

| Test | Mô tả |
|---|---|
| `test_no_iframes_returns_none` | Không có iframe → None |
| `test_none_bounding_box_skipped` | iframe.bounding_box() = None → bỏ qua |
| `test_too_small_returns_none` | iframe 100×100 < ngưỡng → None |
| `test_negative_y_skipped` | y < 0 (off-screen) → bỏ qua |
| `test_valid_iframe_returned` | iframe 400×300 → trả về bbox |
| `test_returns_largest_of_multiple` | 2 iframe hợp lệ → trả về cái lớn hơn |
| `test_exact_min_size_accepted` | Đúng 300×250 → được chấp nhận |
| `test_one_below_min_width_rejected` | 299×300 → None |

### `TestExecuteClicks` (4 tests)

Test `src/services/elevenlabs/captcha._execute_clicks()`:

| Test | Mô tả |
|---|---|
| `test_empty_list_no_mouse_call` | List rỗng → không gọi `mouse.click` |
| `test_single_click_absolute_coords` | norm (0.5,0.5) trong bbox (100,50,400,300) → click (300,200) |
| `test_multiple_clicks_correct_count` | 2 normalized clicks → gọi `mouse.click` đúng 2 lần |
| `test_top_left_click` | norm (0,0) → click đầu trái widget |

### `TestClickVerify` (3 tests)

Test `src/services/elevenlabs/captcha._click_verify()`:

| Test | Mô tả |
|---|---|
| `test_with_btn_uses_llm_coords` | Khi LLM trả về button coords → click vào đó |
| `test_without_btn_uses_fallback` | Khi `btn=None` → click fallback bottom-right (82%, 95%) |
| `test_with_btn_at_offset_bbox` | bbox có offset x/y → tính đúng absolute coords |

### `TestAskLLMAction` (10 tests)

Test `src/services/elevenlabs/captcha._ask_llm_action()` với mock LLM:

| Test | Mô tả |
|---|---|
| `test_click_response_parsed` | LLM trả click JSON → parse đúng type + coords |
| `test_drag_response_parsed` | LLM trả drag JSON → parse đúng from/to coords |
| `test_no_json_returns_empty_clicks` | LLM từ chối → trả `{type: click, clicks: []}` |
| `test_out_of_range_click_filtered` | Click với x=1.5 bị lọc, chỉ giữ click hợp lệ |
| `test_invalid_drag_to_coord_filtered` | Drag với to.x=1.5 bị lọc |
| `test_llm_exception_returns_none` | LLM thước exception → trả `None` |
| `test_missing_type_defaults_to_click` | JSON thiếu `type` field → mặc định `"click"` |
| `test_empty_clicks_list_accepted` | `clicks: []` hợp lệ → không exception |
| `test_json_wrapped_in_markdown_fences` | JSON bọc trong ` ```json ``` ` → parse được |
| `test_all_drag_coords_invalid_returns_empty_drags` | Tất cả drag coords ngoài range → `drags: []` |

---

## Integration Tests (`tests/test_integration.py`)

Gọi **API thật** (mail.tm + LLM server) — cần internet và LLM server chạy.  
Không mở browser, không tạo ElevenLabs account.

> **Lưu ý**: Tests group 2-3 có thể bị skip nếu LLM server offline. Group 4 có thể fail do mail.tm rate limit (429).

### `TestConfigLoad` (9 tests)

Load `config.yaml` thật và validate tất cả sections:

| Test | Mô tả |
|---|---|
| `test_config_yaml_exists` | `config.yaml` tồn tại ở project root |
| `test_llm_base_url_is_http` | `llm.base_url` bắt đầu bằng `http` |
| `test_llm_model_non_empty` | `llm.model` không rỗng |
| `test_captcha_max_rounds_positive` | `captcha.max_rounds` > 0 |
| `test_elevenlabs_signup_url_set` | `elevenlabs.signup_url` có giá trị |
| `test_elevenlabs_api_keys_url_set` | `elevenlabs.api_keys_url` có giá trị |
| `test_elevenlabs_app_base_url_set` | `elevenlabs.app_base_url` có giá trị |
| `test_timeouts_positive` | `email_wait`, `page_load`, `poll_interval` > 0 |
| `test_all_captcha_timing_fields_non_negative` | Tất cả captcha timing fields ≥ 0 |

### `TestLLMConnectivity` (3 tests)

Verify LLM server chạy và nói được OpenAI-compatible API. Tự skip nếu server offline:

| Test | Mô tả | Có thể skip vì |
|---|---|---|
| `test_models_endpoint_reachable` | `GET /v1/models` trả về bất kỳ HTTP response | LLM offline |
| `test_make_llm_client_base_url_matches_config` | `_make_llm_client` dùng đúng `base_url` từ config | |
| `test_plain_text_completion_responds` | Prompt text-only → server trả về non-empty content | LLM offline |

### `TestLLMAction` (6 tests)

Gửi ảnh PNG thật đến `_ask_llm_action` / `_ask_llm_verify_button`, validate response structure. Tự skip nếu LLM offline:

| Test | Mô tả | Có thể fail vì |
|---|---|---|
| `test_ask_llm_action_returns_dict` | Response là dict có key `type` | LLM offline |
| `test_ask_llm_action_has_correct_payload_key` | `type` là `"click"` hoặc `"drag"` | LLM trả format sai |
| `test_ask_llm_action_type_is_click_or_drag` | Validate enum values | LLM trả format sai |
| `test_ask_llm_action_coords_all_in_range` | Tất cả coords trong `[0.0, 1.0]` | LLM trả out-of-range |
| `test_ask_llm_action_repeatable` | Gọi 2 lần → cả 2 trả dict hợp lệ | LLM offline |
| `test_ask_llm_verify_button_structure` | `_ask_llm_verify_button` trả dict hoặc None | LLM offline |

### `TestMailTM` (7 tests)

Gọi **mail.tm API thật** — cần internet:

| Test | Mô tả | Có thể fail vì |
|---|---|---|
| `test_create_returns_valid_email` | Tạo email thật, check format hợp lệ | mail.tm 429 |
| `test_inbox_initially_list` | Inbox mới = list rỗng | mail.tm 429 |
| `test_two_accounts_produce_different_emails` | 2 lần create → 2 email khác nhau | mail.tm 429 |
| `test_wait_for_message_times_out_cleanly` | Timeout trong ~8s với inbox trống | mail.tm 429 |
| `test_extract_link_finds_url` | Extract link có "verify" | |
| `test_extract_link_returns_none_when_missing` | Body không có link → `None` | |
| `test_extract_link_filters_by_contains` | Filter theo "elevenlabs" | |

---

## Trạng thái hiện tại

```
tests/test_unit.py         65 passed ✅
tests/test_integration.py  25 collected (có thể skip/fail nếu LLM server offline hoặc mail.tm rate limit)
```

Integration failures do LLM offline hoặc mail.tm giới hạn tạo account liên tiếp — không phải bug code.

---

## Thêm test mới

```python
# tests/test_unit.py — thêm vào class phù hợp hoặc tạo class mới

class TestMyModule(unittest.TestCase):
    def test_something(self):
        from src.my_module import my_func
        result = my_func("input")
        self.assertEqual(result, "expected")
```

**Nguyên tắc**:
- Unit tests: không có I/O thật, mock tất cả `requests`, `playwright`, `openai`
- Integration tests: chỉ test với external services thật, đánh dấu clearly
- Mỗi test độc lập — không phụ thuộc vào order hay shared state
