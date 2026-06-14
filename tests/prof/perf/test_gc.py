import gc

import pytest
from pytest_codspeed import BenchmarkFixture

from benchmarks.bench_gc import Point, PointClass, PointClassSlots, PointGCFalse
from unittest.mock import patch


@pytest.mark.parametrize("cls", [Point, PointClass, PointClassSlots, PointGCFalse])
@pytest.mark.memory
def test_gc_times(cls, benchmark: BenchmarkFixture):
    data = {i: cls(i, i, i) for i in range(1_000_000)}

    # benchmark() internally already calls 'gc.collect()' unless gc is disabled, so we
    # pretend it is disabled
    with patch("pytest_codspeed.plugin.gc.isenabled") as mock:
        mock.return_value = True
        benchmark(gc.collect)
