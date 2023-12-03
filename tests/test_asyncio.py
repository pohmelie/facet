import asyncio
import time

import pytest

from facet import ServiceMixin


class Simple(ServiceMixin):
    def __init__(self):
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_single_state():
    async with Simple() as service:
        assert service.started is True
        assert service.stopped is False
        assert service.running is True
    assert service.stopped is True


class StartFailed(ServiceMixin):
    def __init__(self):
        self.started = False
        self.stopped = False

    async def start(self):
        raise RuntimeError

    async def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_start_failed():
    service = StartFailed()
    assert service.running is False
    with pytest.raises(RuntimeError):
        await service.run()
    assert service.started is False
    assert service.stopped is False
    assert service.running is False


class Root(Simple):
    def __init__(self, deps):
        super().__init__()
        self.deps = deps

    @property
    def dependencies(self):
        return self.deps


@pytest.mark.asyncio
async def test_start_failed_later():
    valid = Simple()
    broken = StartFailed()
    root = Root([valid, broken])
    assert root.running is False
    with pytest.raises(RuntimeError):
        await root.run()

    assert valid.started is True
    assert valid.stopped is True
    assert valid.running is False


@pytest.mark.asyncio
async def test_start_failed_earlier():
    valid = Simple()
    broken = StartFailed()
    root = Root([broken, valid])
    assert root.running is False
    with pytest.raises(RuntimeError):
        await root.run()

    assert valid.started is False
    assert valid.stopped is False
    assert valid.running is False


class DelayedStartFailed(StartFailed):
    async def start(self):
        await asyncio.sleep(0)
        await super().start()


@pytest.mark.asyncio
async def test_start_failed_parallel_later():
    valid = Simple()
    broken = DelayedStartFailed()
    root = Root([[broken, valid]])
    assert root.running is False
    with pytest.raises(RuntimeError):
        await root.run()

    assert valid.started is True
    assert valid.stopped is True
    assert valid.running is False


class StatsService(ServiceMixin):
    def __init__(self):
        self.start_count = 0
        self.start_time = None
        self.stop_count = 0
        self.stop_time = None

    async def start(self):
        self.start_count += 1
        self.start_time = time.perf_counter()

    async def stop(self):
        self.stop_count += 1
        self.stop_time = time.perf_counter()


class C(StatsService):
    pass


class B(StatsService):
    def __init__(self, c: C):
        super().__init__()
        self.c = c

    @property
    def dependencies(self):
        return [self.c]


class A(StatsService):
    def __init__(self):
        super().__init__()
        self.c = C()
        self.b1 = B(self.c)
        self.b2 = B(self.c)

    @property
    def dependencies(self):
        return [
            self.b1,
            self.b2,
        ]


@pytest.mark.asyncio
async def test_diamond_dependencies():
    async with A() as a:
        assert a.running is True
        assert a.b1.running is True
        assert a.b2.running is True
        assert a.c.running is True
    assert a.c.start_count == 1
    assert a.c.stop_count == 1
    assert a.c.start_time < a.b1.start_time < a.b2.start_time < a.start_time
    assert a.stop_time < a.b2.stop_time < a.b1.stop_time < a.c.stop_time


@pytest.mark.asyncio
async def test_c_does_not_stops():
    async with A() as a:
        async with B(a.c):
            pass
        assert a.c.running is True
    assert a.c.running is False


class WithTask(ServiceMixin):
    def __init__(self):
        self.task_cancelled = 0

    async def task(self):
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.task_cancelled += 1
            raise

    async def start(self):
        self.add_task(self.task())


@pytest.mark.asyncio
async def test_added_task_cancelation():
    async with WithTask() as service:
        pass
    assert service.task_cancelled == 1


class WithTaskException(ServiceMixin):
    async def task(self):
        raise RuntimeError

    async def start(self):
        self.add_task(self.task())


@pytest.mark.asyncio
async def test_task_exception():
    service = WithTaskException()
    with pytest.raises(RuntimeError):
        await service.run()

    with pytest.raises(RuntimeError):
        async with service:
            await service.wait()


class StartFailB(ServiceMixin):
    def __init__(self):
        self.start_called = 0
        self.stop_called = 0

    async def start(self):
        self.start_called += 1
        raise RuntimeError

    async def stop(self):
        self.stop_called += 1


class StartFailA(ServiceMixin):
    def __init__(self):
        self.b = StartFailB()
        self.start_called = 0
        self.stop_called = 0

    @property
    def dependencies(self):
        return [
            self.b,
        ]

    async def start(self):
        self.start_called += 1

    async def stop(self):
        self.stop_called += 1


@pytest.mark.asyncio
async def test_start_exception():
    service = StartFailA()
    with pytest.raises(RuntimeError):
        async with service:
            pass

    assert service.start_called == 0
    assert service.stop_called == 0
    assert service.b.start_called == 1
    assert service.b.stop_called == 0


class Parallel(StatsService):
    def __init__(self):
        super().__init__()
        self.services = [StatsService(), StatsService(), StatsService()]

    @property
    def dependencies(self):
        return [self.services]


@pytest.mark.asyncio
async def test_start_groups():
    async with Parallel() as parallel:
        pass
    assert all(s.start_count == 1 and s.stop_count == 1 for s in parallel.services)


@pytest.mark.asyncio
async def test_empty_methods():
    async with ServiceMixin():
        pass
