from __future__ import annotations

from types import SimpleNamespace

from summary_relay_bot.services.message_extraction import extract_message_for_summary


def test_extract_plain_group_text() -> None:
    extracted = extract_message_for_summary(SimpleNamespace(text=" hello ", caption=None))

    assert extracted.message_type == "text"
    assert extracted.summary_content == "hello"
    assert extracted.file_id is None


def test_extract_document_placeholder_with_metadata_and_caption() -> None:
    message = SimpleNamespace(
        text=None,
        caption="important file",
        document=SimpleNamespace(
            file_id="file-id",
            file_unique_id="unique-id",
            file_name="report.pdf",
            mime_type="application/pdf",
            file_size=1234,
        ),
    )

    extracted = extract_message_for_summary(message)

    assert extracted.message_type == "document"
    assert extracted.summary_content == "[document: report.pdf] important file"
    assert extracted.file_id == "file-id"
    assert extracted.file_unique_id == "unique-id"
    assert extracted.file_name == "report.pdf"
    assert extracted.mime_type == "application/pdf"
    assert extracted.file_size == 1234
    assert extracted.media_metadata == {
        "file_id": "file-id",
        "file_unique_id": "unique-id",
        "file_name": "report.pdf",
        "mime_type": "application/pdf",
        "file_size": 1234,
        "message_type": "document",
        "caption": "important file",
    }


def test_extract_photo_uses_largest_photo_and_caption() -> None:
    message = SimpleNamespace(
        text=None,
        caption="scene",
        photo=[
            SimpleNamespace(file_id="small", file_unique_id="small-u", file_size=1),
            SimpleNamespace(file_id="large", file_unique_id="large-u", file_size=10),
        ],
    )

    extracted = extract_message_for_summary(message)

    assert extracted.message_type == "photo"
    assert extracted.summary_content == "[photo] scene"
    assert extracted.file_id == "large"
    assert extracted.file_unique_id == "large-u"


def test_unsupported_message_stays_debuggable_without_summary_storage() -> None:
    extracted = extract_message_for_summary(SimpleNamespace(text=None, caption="mystery"))

    assert extracted.unsupported is True
    assert extracted.message_type == "unsupported"
    assert extracted.summary_content == "[unsupported] mystery"
