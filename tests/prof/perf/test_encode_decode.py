import pytest

from benchmarks.bench_encodings import Directory
from benchmarks.bench_validation import bench_msgspec
from benchmarks.generate_data import make_filesystem_data

import msgspec.json
import msgspec.msgpack
from pytest_codspeed import BenchmarkFixture


@pytest.fixture(params=[1000, 10000])
def file_system_data(request):
    return make_filesystem_data(request.param)


json_decoder = msgspec.json.Decoder(type=Directory)
json_encoder = msgspec.json.Encoder()

msgpack_decoder = msgspec.json.Decoder(type=Directory)
msgspec_encoder = msgspec.json.Encoder()



@pytest.mark.parametrize(
    "encoder",
    [
        pytest.param(json_encoder.encode, id="json"),
        pytest.param(msgspec_encoder.encode, id="msgpack"),
    ],
)
def test_encode(benchmark: BenchmarkFixture, encoder, file_system_data):
    res = benchmark.pedantic(
        encoder,
        args=(file_system_data,),
        rounds=1000,
        warmup_rounds=100,
    )

    assert isinstance(res, bytes)


@pytest.mark.parametrize(
    "encoder,decoder",
    [
        pytest.param(json_encoder.encode, json_decoder.decode, id="json"),
        pytest.param(msgspec_encoder.encode, msgpack_decoder.decode, id="msgpack"),
    ],
)
def test_decode(benchmark: BenchmarkFixture, encoder, decoder, file_system_data):
    data = encoder(file_system_data)
    res = benchmark.pedantic(
        decoder,
        args=(data,),
        rounds=1000,
        warmup_rounds=1000,
    )

    assert isinstance(res, Directory)


@pytest.mark.parametrize(
    "encoder,decoder",
    [
        pytest.param(json_encoder.encode, json_decoder.decode, id="json"),
        pytest.param(msgspec_encoder.encode, msgpack_decoder.decode, id="msgpack"),
    ],
)
def test_roundtrip(benchmark: BenchmarkFixture, encoder, decoder, file_system_data):
    def func(data):
        return decoder(encoder(data))

    res = benchmark.pedantic(
        func,
        args=(file_system_data,),
        rounds=500,
        warmup_rounds=100,
    )

    assert isinstance(res, Directory)