"""Fast structural smoke for the full RM-147 benchmark runner."""

from scripts.benchmark_rm147_analytics import run_benchmark


def test_benchmark_reports_order_parity_limits_memory_and_artifact_sizes() -> None:
    report = run_benchmark(sizes=(0, 10), samples=2, warmups=1)

    assert report["contract"] == "rm147-analytics-benchmark-v1"
    assert report["sizes"] == (0, 10)
    results = report["results"]
    assert [item["size"] for item in results] == [0, 10]
    assert all(item["ordered_shuffled_equal"] for item in results)
    assert all(item["service_query_count"] == 0 for item in results)
    assert all(item["application_read_query_count"] == 4 for item in results)
    assert all(item["sampled"] is False for item in results)
    assert all(item["peak_traced_bytes"] >= 0 for item in results)
    assert all(item["json_bytes"] > 0 and item["csv_bytes"] > 0 for item in results)
