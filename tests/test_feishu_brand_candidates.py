import json

from app.brand_candidates import BrandCandidate
from app.configuration.feishu_base import FeishuBaseConfig, FeishuBrandCandidateWriter


def test_feishu_brand_candidate_writer_creates_review_record(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if "/tenant_access_token/internal" in request.full_url:
            return _Response({"code": 0, "tenant_access_token": "tenant-token"})
        if "/tables/candidates_table/records" in request.full_url:
            return _Response({"code": 0, "data": {"record": {"record_id": "rec1"}}})
        raise AssertionError(f"Unexpected URL: {request.full_url}")

    monkeypatch.setattr("app.configuration.feishu_base.urlopen", fake_urlopen)
    writer = FeishuBrandCandidateWriter(
        FeishuBaseConfig(
            app_id="app-id",
            app_secret="secret",
            base_token="base-token",
            brands_table_id="brands",
            categories_table_id="categories",
            detection_rules_table_id="rules",
            brand_candidates_table_id="candidates_table",
        )
    )

    writer.report(
        BrandCandidate(
            candidate_brand="德金",
            category="cat_food",
            post_title="【闲置】德金猫粮野猪45/斤，2斤包邮",
            post_url="https://www.douban.com/group/topic/323456789/",
        )
    )

    body = json.loads(requests[-1].data.decode("utf-8"))
    assert body["fields"]["candidate_brand"] == "德金"
    assert body["fields"]["category"] == "cat_food"
    assert body["fields"]["source"] == "system_auto"
    assert body["fields"]["status"] == "needs_review"
    assert "人工审核" in body["fields"]["note"]


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")
