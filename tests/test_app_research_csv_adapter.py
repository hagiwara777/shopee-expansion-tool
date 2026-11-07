"""The preserved research adapter remains offline and deduplicates inputs."""
import csv
from io import StringIO


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


def test_research_adapter_preserves_dedup_and_does_not_initialize_keepa(monkeypatch):
    from modules.keepa_client import KeepaExpansionClient
    from modules.research_csv_adapter import ResearchCsvInput, import_research_csvs
    def unexpected(*args, **kwargs):
        raise AssertionError('Research CSV import must not initialize Keepa')
    monkeypatch.setattr(KeepaExpansionClient, '__init__', unexpected)
    result = import_research_csvs([ResearchCsvInput('first.csv', _research_csv()),
                                   ResearchCsvInput('second.csv', _research_csv())])
    assert result.summary['input_file_count'] == 2
    assert result.summary['resolver_ready_count'] == 1
