import csv
from io import StringIO
import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules.keepa_client import KeepaExpansionClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"


def _standard_logger_warning(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


def _research_csv() -> bytes:
    output = StringIO(newline="")
    headers = ["Country", "Location", "Name", "Product URL", "Search Date"]
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        [
            {
                "Country": "PH",
                "Location": "Japan",
                "Name": "Official Store Test Product 500ml",
                "Product URL": "https://shopee.ph/product-i.1.2",
                "Search Date": "2026-07-23 15:00:00",
            },
            {
                "Country": "PH",
                "Location": "Korea",
                "Name": "Japan only in title",
                "Product URL": "https://shopee.ph/product-i.1.3",
                "Search Date": "2026-07-23 15:00:00",
            },
        ]
    )
    return output.getvalue().encode("utf-8-sig")


def test_research_csv_adapter_tab_uploads_previews_and_downloads_without_api(monkeypatch):
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)

    def unexpected_keepa_call(*args, **kwargs):
        raise AssertionError("The research CSV adapter must not initialize Keepa")

    monkeypatch.setattr(KeepaExpansionClient, "__init__", unexpected_keepa_call)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

    assert not app.exception
    assert "Shopee調査CSV取込" in [tab.label for tab in app.tabs]
    assert any(uploader.key == "research_csv_adapter_files" for uploader in app.file_uploader)
    assert any(area.label == "商品名リスト" for area in app.text_area)

    app.file_uploader(key="research_csv_adapter_files").set_value(
        [
            ("first.csv", _research_csv(), "text/csv"),
            ("second.csv", _research_csv(), "text/csv"),
        ]
    ).run()
    app.button(key="research_csv_adapter_import").click().run()

    assert not app.exception
    assert app.session_state["research_csv_adapter_result"].summary["input_file_count"] == 2
    assert app.session_state["research_csv_adapter_result"].summary["resolver_ready_count"] == 1
    assert [button.label for button in app.download_button if "ダウンロード" in button.label][-3:] == [
        "Resolver用TSVをダウンロード",
        "追跡用Manifest CSVをダウンロード",
        "保留・除外CSVをダウンロード",
    ]
    assert len(app.dataframe) >= 2
