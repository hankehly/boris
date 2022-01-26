from boris import Backend, Config
from boris.job import Call, Job


class TestJob:
    """Unit tests for Job class"""

    def test_chunks(self):
        """Check that Job.chunks splits job into chunks of max size chunk_size"""
        job = Job(
            config=Config.construct(backend=Backend.Aws),
            call_start_pos=0,
            call_arg_byte_ranges=[(0, 1), (1, 2), (2, 3)],
            chunk_size=2,
        )

        chunks = job.chunks()

        assert len(chunks) == 2
        assert job.n_chunks == 2

        assert chunks[0].call_start_pos == 0
        assert chunks[1].call_start_pos == 2

        assert chunks[0].call_arg_byte_ranges == job.call_arg_byte_ranges[:2]
        assert chunks[1].call_arg_byte_ranges == job.call_arg_byte_ranges[2:]

    def test_calls(self):
        """Check that Job.calls returns a list of Call objects"""
        job = Job(
            config=Config.construct(backend=Backend.Aws),
            call_start_pos=0,
            call_arg_byte_ranges=[(0, 1), (1, 2), (2, 3)],
            store_function_output=False,
            chunk_size=2,
        )

        chunk_1, chunk_2 = job.chunks()

        call1 = Call(
            id="00000",
            job_id=job.id,
            config=job.config,
            arg_byte_range=job.call_arg_byte_ranges[0],
            store_function_output=job.store_function_output,
        )

        call2 = Call(
            id="00001",
            job_id=job.id,
            config=job.config,
            arg_byte_range=job.call_arg_byte_ranges[1],
            store_function_output=job.store_function_output,
        )

        call3 = Call(
            id="00002",
            job_id=job.id,
            config=job.config,
            arg_byte_range=job.call_arg_byte_ranges[2],
            store_function_output=job.store_function_output,
        )

        chunk_1_calls = chunk_1.calls()
        chunk_2_calls = chunk_2.calls()

        assert len(chunk_1_calls) == 2
        assert chunk_1.n_calls == 2

        assert chunk_1_calls[0].json(exclude={"config"}) == call1.json(
            exclude={"config"}
        )

        assert chunk_1_calls[1].json(exclude={"config"}) == call2.json(
            exclude={"config"}
        )

        assert len(chunk_2_calls) == 1
        assert chunk_2.n_calls == 1

        assert chunk_2_calls[0].json(exclude={"config"}) == call3.json(
            exclude={"config"}
        )
