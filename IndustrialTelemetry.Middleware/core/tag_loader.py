"""
core/tag_loader.py
──────────────────
Quét ``TAG_FOLDER`` để tìm tất cả file CSV và dựng danh sách TagDefinition.

Cấu trúc thư mục (đúng kiểu Vinamilk):
    TAG_FOLDER/
        <Channel>/
            <Device>.csv     ← mỗi file = một device (= một máy)

NodeId OPC UA được tổng hợp tự động:
    ns=2;s=<Channel>.<Device>.<Tag Name>

Cột CSV được dùng (định dạng export chuẩn của Kepware):
    - ``Tag Name``        (bắt buộc) → phần cuối của NodeId
    - ``Data Type``       (bắt buộc) → kiểu Kepware để ép giá trị + valueType
    - ``Eng Units``       (tuỳ chọn) → đơn vị đo, "-" nghĩa là không có
    - ``TagType``         (tuỳ chọn) → ANALOG / DIGITAL / COUNTER / STRING
    - ``TagCode``         (bắt buộc nếu REQUIRE_TAG_CODE) → mã nghiệp vụ
    - ``Acquisition Class`` (tuỳ chọn) → chỉ để hướng dẫn cấu hình Kepware,
      KHÔNG đưa vào message
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from config import settings
from core.value_types import canonical_kepware_type

logger = logging.getLogger("industrial_telemetry.tag_loader")

#: Cột bắt buộc trong CSV.
_REQUIRED_COLUMNS = {"Tag Name"}

#: Các encoding có thể gặp khi export CSV từ Kepware/Excel trên Windows.
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1")

#: Giá trị "không có đơn vị" trong CSV.
_EMPTY_UNIT = {"", "-", "--", "n/a", "na", "none"}


@dataclass(frozen=True)
class TagDefinition:
    """Định nghĩa một tag OPC UA được đọc từ CSV."""

    node_id: str          # ns=2;s=<Channel>.<Device>.<TagName>
    channel: str          # Tên Channel (tên thư mục cha của CSV)
    device: str           # Tên Device (= machineId), tên file CSV không extension
    tag_name: str         # Tag Name trong Kepware
    tag_code: str         # TagCode — mã nghiệp vụ, duy nhất toàn hệ thống
    tag_type: str         # ANALOG / DIGITAL / COUNTER / STRING
    kepware_type: str     # Boolean / Int / Word / DWord / Long / Float / Double / String
    unit: str | None      # Đơn vị đo (None nếu không có)
    description: str      # Mô tả (tiếng Việt không dấu, lấy từ CSV)
    scan_rate_ms: int | None  # Scan Rate của Kepware (ms), None nếu không khai báo

    @property
    def channel_device(self) -> str:
        """Khóa map equipment: ``<Channel>.<Device>``."""
        return f"{self.channel}.{self.device}"

    @property
    def display_name(self) -> str:
        return f"{self.channel}.{self.device}.{self.tag_name}"

    @property
    def value_type(self) -> str:
        """Tên kiểu OPC UA canonical sẽ ghi ra Kafka."""
        from core.value_types import opcua_type_for

        return opcua_type_for(self.kepware_type)


def _build_node_id(channel: str, device: str, tag_name: str) -> str:
    """Tạo NodeId OPC UA theo chuẩn Kepware."""
    return f"ns=2;s={channel}.{device}.{tag_name}"


def _iter_csv_files(tag_folder: Path) -> Iterator[tuple[str, str, Path]]:
    """
    Duyệt tất cả CSV trong ``tag_folder``.
    Yields (channel, device, csv_path).
    """
    if not tag_folder.exists():
        logger.error("[TAG LOADER] TAG_FOLDER not found: %s", tag_folder)
        return
    if not tag_folder.is_dir():
        logger.error("[TAG LOADER] TAG_FOLDER is not a directory: %s", tag_folder)
        return

    for channel_dir in sorted(tag_folder.iterdir()):
        if not channel_dir.is_dir():
            continue
        channel = channel_dir.name

        csv_files = sorted(channel_dir.glob("*.csv"))
        if not csv_files:
            logger.debug("[TAG LOADER] No CSV in channel dir: %s", channel_dir)
            continue

        for csv_path in csv_files:
            yield channel, csv_path.stem, csv_path


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    """
    Đọc CSV bằng module ``csv`` chuẩn (không phụ thuộc pandas).

    Thử lần lượt các encoding cho tới khi khớp.
    """
    last_exc: Exception | None = None
    for encoding in _CSV_ENCODINGS:
        try:
            with csv_path.open("r", encoding=encoding, newline="") as fh:
                reader = csv.DictReader(fh)
                rows = []
                for raw_row in reader:
                    # Chuẩn hóa key: strip + bỏ BOM còn sót.
                    rows.append(
                        {
                            (k or "").strip().lstrip("\ufeff"): (v or "").strip()
                            for k, v in raw_row.items()
                            if k is not None
                        }
                    )
                return rows
        except UnicodeDecodeError as exc:
            last_exc = exc
    raise last_exc or UnicodeDecodeError("csv", b"", 0, 1, "no encoding matched")


def _clean_unit(raw: str | None) -> str | None:
    """Chuẩn hóa cột Eng Units: "-" → None."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text.casefold() in _EMPTY_UNIT:
        return None
    return text


def _clean_scan_rate(raw: str | None) -> int | None:
    """Chuẩn hóa cột Scan Rate sang int (ms)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _load_csv(channel: str, device: str, csv_path: Path) -> list[TagDefinition]:
    """Đọc một file CSV và trả về danh sách TagDefinition."""
    try:
        rows = _read_rows(csv_path)
    except Exception as exc:
        logger.error("[TAG LOADER] Cannot read CSV %s: %s", csv_path, exc)
        return []

    if not rows:
        logger.warning("[TAG LOADER] Empty CSV: %s", csv_path)
        return []

    headers = set(rows[0].keys())
    missing = _REQUIRED_COLUMNS - headers
    if missing:
        logger.error(
            "[TAG LOADER] CSV %s missing required columns: %s", csv_path.name, missing
        )
        return []

    tags: list[TagDefinition] = []
    skipped_empty_name = 0
    skipped_empty_code = 0

    for row in rows:
        tag_name = (row.get("Tag Name") or "").strip()
        if not tag_name:
            skipped_empty_name += 1
            continue

        tag_code = (row.get("TagCode") or "").strip()
        if not tag_code and settings.REQUIRE_TAG_CODE:
            skipped_empty_code += 1
            continue

        tags.append(
            TagDefinition(
                node_id=_build_node_id(channel, device, tag_name),
                channel=channel,
                device=device,
                tag_name=tag_name,
                tag_code=tag_code,
                tag_type=(row.get("TagType") or "").strip().upper(),
                kepware_type=canonical_kepware_type(row.get("Data Type")),
                unit=_clean_unit(row.get("Eng Units")),
                description=(row.get("Description") or "").strip(),
                scan_rate_ms=_clean_scan_rate(row.get("Scan Rate")),
            )
        )

    if skipped_empty_name:
        logger.warning(
            "[TAG LOADER] %s — skipped %d row(s) with empty Tag Name",
            csv_path.name,
            skipped_empty_name,
        )
    if skipped_empty_code:
        logger.info(
            "[TAG LOADER] %s — skipped %d row(s) with empty TagCode",
            csv_path.name,
            skipped_empty_code,
        )

    logger.info(
        "[TAG LOADER] %s/%s.csv → %d tag(s)", channel, device, len(tags)
    )
    return tags


def load_all_tags(tag_folder: Path | None = None) -> list[TagDefinition]:
    """
    Đọc toàn bộ CSV trong TAG_FOLDER.

    Returns:
        Danh sách TagDefinition đã dedup theo node_id.
    """
    folder = Path(tag_folder or settings.TAG_FOLDER)
    all_tags: list[TagDefinition] = []
    seen_node_ids: set[str] = set()
    seen_tag_codes: dict[str, str] = {}

    for channel, device, csv_path in _iter_csv_files(folder):
        for tag in _load_csv(channel, device, csv_path):
            if tag.node_id in seen_node_ids:
                logger.warning(
                    "[TAG LOADER] Duplicate NodeId skipped: %s", tag.node_id
                )
                continue
            if tag.tag_code:
                previous = seen_tag_codes.get(tag.tag_code)
                if previous is not None:
                    logger.warning(
                        "[TAG LOADER] Duplicate TagCode %s (%s vs %s)",
                        tag.tag_code,
                        previous,
                        tag.node_id,
                    )
                    continue
                seen_tag_codes[tag.tag_code] = tag.node_id
            seen_node_ids.add(tag.node_id)
            all_tags.append(tag)

    logger.info(
        "[TAG LOADER] Total %d tag(s) loaded from %s",
        len(all_tags),
        folder,
    )
    return all_tags
