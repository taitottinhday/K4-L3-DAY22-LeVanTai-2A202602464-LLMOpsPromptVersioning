"""
Bước 4 — Guardrails AI Validators
====================================
NHIỆM VỤ:
  1. Xây dựng PIIDetector: phát hiện & redact email, số điện thoại, SSN, số thẻ tín dụng
  2. Xây dựng JSONFormatter: tự động sửa JSON lỗi
  3. Bọc mỗi validator trong Guard và test với các mẫu đầu vào
  4. Chạy demo với 6 trường hợp PII và 5 trường hợp JSON

DELIVERABLE: Tất cả test cases pass (PII bị redact, JSON được sửa thành công)

CÁC KHÁI NIỆM CHÍNH:
  - @register_validator     — khai báo custom validator class
  - Validator.validate()    — implement logic kiểm tra + sửa
  - OnFailAction.FIX        — thay thế output thay vì raise error
  - Guard().use(validator)  — gắn validator instance vào guard
  - guard.validate(text)    → ValidationOutcome
      .validation_passed    — bool
      .validated_output     — output đã được xử lý

⚠️  QUAN TRỌNG: on_fail phải truyền vào CONSTRUCTOR của VALIDATOR, KHÔNG phải Guard.use()
    SAI  : Guard().use(PIIDetector, on_fail=OnFailAction.FIX)   ← TypeError
    ĐÚNG : Guard().use(PIIDetector(on_fail=OnFailAction.FIX))   ← correct
"""

import os
import re
import json

# Guardrails emits OpenTelemetry spans in the background. Disable its optional
# exporter for this local lab demo so offline runs do not block on retries.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("GUARDRAILS_RUN_SYNC", "true")

from guardrails import Guard
from guardrails.validators import Validator, register_validator, PassResult, FailResult

try:
    from guardrails.hub import OnFailAction
except ImportError:
    from guardrails.validator_base import OnFailAction

# Keep the local demo deterministic/offline; custom validators do not need
# Guardrails' optional anonymous metrics exporter.
try:
    from guardrails.settings import settings
    settings.rc.enable_metrics = False
    settings.disable_tracing = True
except (ImportError, AttributeError):
    pass


# ── 1. PII Detector Validator ──────────────────────────────────────────────
@register_validator(name="custom/pii-detector", data_type="string")
class PIIDetector(Validator):
    """
    Phát hiện và redact Personally Identifiable Information (PII).

    Các pattern được phát hiện:
      EMAIL       : xxx@xxx.xxx
      PHONE       : (123) 456-7890 hoặc 123-456-7890
      SSN         : 123-45-6789
      CREDIT_CARD : 1234 5678 9012 3456 (hoặc dấu gạch nối)
    """

    # Regex patterns cho từng loại PII — đã được định nghĩa sẵn, bạn chỉ cần dùng
    PII_PATTERNS = {
        "EMAIL":       r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "PHONE":       r"(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}",
        "SSN":         r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    }

    def validate(self, value: str, metadata: dict):
        """
        Tìm PII trong value. Dùng FailResult(fix_value=...) để FIX thay đầu ra.

        Bước:
          1. Copy value → redacted_text
          2. Với mỗi loại PII và pattern tương ứng:
             - Tìm tất cả matches bằng re.findall(pattern, value)
             - Thay thế từng match bằng "[PII_TYPE_REDACTED]" trong redacted_text
             - Ghi lại (pii_type, match) vào found_pii
          3. Nếu found_pii không rỗng → FailResult(fix_value=redacted_text)
          4. Nếu không tìm thấy PII → PassResult()
        """
        redacted_text = value
        found_pii     = []

        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, value)

            for match in matches:
                redacted_text = redacted_text.replace(
                    match, f"[{pii_type}_REDACTED]"
                )
                found_pii.append((pii_type, match))

        if found_pii:
            print(f"  ⚠️  Đã redact {len(found_pii)} PII: {[p[0] for p in found_pii]}")
            # FIX cần FailResult(fix_value=...) để Guardrails thay output.
            return FailResult(error_message="Phát hiện PII", fix_value=redacted_text)

        return PassResult()


# ── 2. JSON Formatter Validator ────────────────────────────────────────────
@register_validator(name="custom/json-formatter", data_type="string")
class JSONFormatter(Validator):
    """
    Validate và tự động sửa JSON lỗi.

    Các lỗi có thể sửa tự động:
      - Strip markdown code fences (``` hoặc ```json)
      - Thay single quotes → double quotes
      - Xóa trailing commas trước } hoặc ]
      - Re-serialize với json.dumps để định dạng chuẩn
    """

    @staticmethod
    def _repair(text: str) -> str:
        """
        Cố gắng sửa chuỗi JSON lỗi.

        Bước:
          1. Strip whitespace đầu/cuối
          2. Xóa markdown fences bằng re.sub
          3. Thay single quotes → double quotes
          4. Xóa trailing commas trước } hoặc ]
          5. Trả về chuỗi đã sửa (chưa re-serialize)
        """
        text = text.strip()

        # Xóa markdown fences — đã cho sẵn
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$',          '', text)
        text = text.strip()

        text = text.replace("'", '"')

        text = re.sub(r',\s*([}\]])', r'\1', text)

        return text

    def validate(self, value: str, metadata: dict):
        """
        Thử parse value thành JSON.
        Nếu thất bại, gọi _repair() rồi thử lại.

        Trả về PassResult nếu JSON hợp lệ; FailResult(fix_value=...)
        nếu sửa được hoặc phải tạo JSON dự phòng.
        """
        try:
            json.loads(value)
            return PassResult()
        except json.JSONDecodeError:
            pass

        try:
            repaired_text = self._repair(value)
            parsed = json.loads(repaired_text)
            print(f"  🔧 JSON đã được sửa thành công")
            repaired_json = json.dumps(parsed, indent=2, ensure_ascii=False)
            return FailResult(
                error_message="JSON lỗi, đã tự sửa",
                fix_value=repaired_json,
            )
        except (json.JSONDecodeError, TypeError) as e:
            fallback = json.dumps(
                {"error": "Không thể phân tích JSON", "raw": value[:200]},
                ensure_ascii=False,
            )
            return FailResult(
                error_message=f"Không thể sửa JSON: {e}",
                fix_value=fallback,
            )


# ── 3. Demo: PII Guard ─────────────────────────────────────────────────────
def demo_pii_guard():
    print("\n" + "=" * 55)
    print("  Demo: PII Detection & Redaction")
    print("=" * 55)

    guard = Guard().use(PIIDetector(on_fail=OnFailAction.FIX))
    # Guardrails 0.11 leaves this unset when no LLM/re-ask is configured.
    # Explicitly disabling re-asks keeps this validator-only demo local.
    guard._num_reasks = 0

    test_cases = [
        ("Email",        "Contact John at john.doe@example.com for details."),
        ("Phone",        "Call our support line at (555) 867-5309."),
        ("SSN",          "Patient SSN is 123-45-6789 on file."),
        ("Credit Card",  "Payment made with card 4532 1234 5678 9010."),
        ("Multi-PII",    "Email: alice@example.com, Phone: 555-123-4567"),
        ("Clean",        "No sensitive information in this text."),
    ]

    for label, text in test_cases:
        result = guard.validate(text)
        output = str(result.validated_output)
        if any(re.search(pattern, output) for pattern in PIIDetector.PII_PATTERNS.values()):
            raise AssertionError(f"PII còn sót trong ca {label}")

        print(f"\n[{label}]")
        print(f"  Input:  {text}")
        print(f"  Output: {output}")


# ── 4. Demo: JSON Guard ────────────────────────────────────────────────────
def demo_json_guard():
    print("\n" + "=" * 55)
    print("  Demo: JSON Formatting & Repair")
    print("=" * 55)

    guard = Guard().use(JSONFormatter(on_fail=OnFailAction.FIX))
    guard._num_reasks = 0

    test_cases = [
        ("Valid JSON",       '{"name": "Alice", "age": 30}'),
        ("Markdown fences",  '```json\n{"name": "Bob"}\n```'),
        ("Single quotes",    "{'name': 'Charlie', 'score': 95}"),
        ("Trailing comma",   '{"key": "value",}'),
        ("Truly invalid",    "This is not JSON at all: ??? {]"),
    ]

    for label, text in test_cases:
        result = guard.validate(text)
        output = str(result.validated_output)
        parsed = json.loads(output)
        if label == "Truly invalid" and "error" not in parsed:
            raise AssertionError("JSON lỗi phải trả về nội dung dự phòng")
        status = (
            "🛟 JSON dự phòng" if label == "Truly invalid"
            else "🔧 Đã sửa" if output != text
            else "✅ Hợp lệ"
        )
        print(f"\n[{label}] {status}")
        print(f"  Input:  {text}")
        print(f"  Output: {output}")


# ── 5. Main ────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Bước 4: Guardrails AI Validators")
    print("=" * 55)

    demo_pii_guard()
    demo_json_guard()

    print("\n✅ Bước 4 hoàn thành!")


if __name__ == "__main__":
    main()
