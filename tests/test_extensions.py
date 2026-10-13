import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import pricing, sustainability
from missions import m2_inference_levers


def test_break_even_cache_reads():
    # 1.25 write multiplier with 90% discount (0.10 read multiplier)
    be = pricing.break_even_cache_reads(1.25, 0.10)
    assert abs(be - (1.25 / 0.90)) < 1e-6
    assert abs(be - 1.388888) < 1e-4


def test_cache_is_worth_it_threshold():
    # Below break-even (< 1.39 reads) -> False
    assert not pricing.cache_is_worth_it(avg_cache_reads=1.0, write_cost=1.25, read_discount=0.10)
    # Above break-even (> 1.39 reads) -> True
    assert pricing.cache_is_worth_it(avg_cache_reads=2.0, write_cost=1.25, read_discount=0.10)
    assert pricing.cache_is_worth_it(avg_cache_reads=10.0, write_cost=1.25, read_discount=0.10)


def test_cache_is_worth_it_model_tiers():
    # Small model ($0.20 input, $0.25 write)
    assert pricing.cache_is_worth_it(avg_cache_reads=3.0, write_cost=0.25, price_in_per_m=0.20)
    assert not pricing.cache_is_worth_it(avg_cache_reads=1.0, write_cost=0.25, price_in_per_m=0.20)

    # Large model ($3.00 input, $3.75 write)
    assert pricing.cache_is_worth_it(avg_cache_reads=2.0, write_cost=3.75, price_in_per_m=3.00)
    assert not pricing.cache_is_worth_it(avg_cache_reads=1.2, write_cost=3.75, price_in_per_m=3.00)


def test_extension_m2_outputs():
    r2 = m2_inference_levers.run(verbose=False)
    assert r2["cache_worth_it"] is True
    assert r2["avg_cache_reads"] > 1.39
    assert "reasoning_stats" in r2
    assert r2["reasoning_stats"]["traffic_pct"] > 0
    assert r2["reasoning_stats"]["wh_pct"] > r2["reasoning_stats"]["traffic_pct"]
