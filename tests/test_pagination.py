from __future__ import annotations

import pytest

from src.api.v1.schemas.common import PaginatedResponse, PaginationParams


# ---------------------------------------------------------------------------
# PaginationParams
# ---------------------------------------------------------------------------

def test_pagination_default_offset():
    p = PaginationParams()
    assert p.offset == 0


def test_pagination_offset_page_two():
    p = PaginationParams(page=2, page_size=50)
    assert p.offset == 50


def test_pagination_offset_page_five():
    p = PaginationParams(page=5, page_size=20)
    assert p.offset == 80


def test_pagination_invalid_page():
    with pytest.raises(Exception):
        PaginationParams(page=0)


def test_pagination_invalid_page_size_zero():
    with pytest.raises(Exception):
        PaginationParams(page_size=0)


def test_pagination_invalid_page_size_too_large():
    with pytest.raises(Exception):
        PaginationParams(page_size=1001)


def test_pagination_invalid_sort_order():
    with pytest.raises(Exception):
        PaginationParams(sort_order="random")


# ---------------------------------------------------------------------------
# PaginatedResponse.build
# ---------------------------------------------------------------------------

def test_build_single_page():
    r = PaginatedResponse.build(data=["a", "b", "c"], total=3, page=1, page_size=10)
    assert r.total_pages == 1
    assert r.has_next is False
    assert r.has_prev is False


def test_build_multiple_pages():
    r = PaginatedResponse.build(data=list(range(10)), total=25, page=1, page_size=10)
    assert r.total_pages == 3
    assert r.has_next is True
    assert r.has_prev is False


def test_build_last_page():
    r = PaginatedResponse.build(data=list(range(5)), total=25, page=3, page_size=10)
    assert r.has_next is False
    assert r.has_prev is True


def test_build_middle_page():
    r = PaginatedResponse.build(data=list(range(10)), total=30, page=2, page_size=10)
    assert r.has_next is True
    assert r.has_prev is True


def test_build_empty_result():
    r = PaginatedResponse.build(data=[], total=0, page=1, page_size=50)
    assert r.total == 0
    assert r.total_pages == 1
    assert r.has_next is False
    assert r.has_prev is False


def test_build_exact_page_fill():
    # 100 items, 50 per page → 2 pages exactly
    r = PaginatedResponse.build(data=list(range(50)), total=100, page=1, page_size=50)
    assert r.total_pages == 2
    assert r.has_next is True

    r2 = PaginatedResponse.build(data=list(range(50)), total=100, page=2, page_size=50)
    assert r2.has_next is False
    assert r2.has_prev is True


def test_build_preserves_data():
    items = [{"id": i} for i in range(3)]
    r = PaginatedResponse.build(data=items, total=3, page=1, page_size=10)
    assert r.data == items
