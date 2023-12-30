import time

import pytest

from facet import BlockingServiceMixin


class Simple(BlockingServiceMixin):
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def test_single_state():
    with Simple() as service:
        assert service.started is True
        assert service.stopped is False
        assert service.running is True
    assert service.stopped is True


class StartFailed(BlockingServiceMixin):
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        raise RuntimeError

    def stop(self):
        self.stopped = True


def test_start_failed():
    service = StartFailed()
    assert service.running is False
    with pytest.raises(RuntimeError):
        with service:
            pass
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


def test_start_failed_later():
    valid = Simple()
    broken = StartFailed()
    root = Root([valid, broken])
    assert root.running is False
    with pytest.raises(RuntimeError):
        with root:
            pass

    assert valid.started is True
    assert valid.stopped is True
    assert valid.running is False


def test_start_failed_earlier():
    valid = Simple()
    broken = StartFailed()
    root = Root([broken, valid])
    assert root.running is False
    with pytest.raises(RuntimeError):
        with root:
            pass

    assert valid.started is False
    assert valid.stopped is False
    assert valid.running is False


class StatsService(BlockingServiceMixin):
    def __init__(self):
        self.start_count = 0
        self.start_time = None
        self.stop_count = 0
        self.stop_time = None

    def start(self):
        self.start_count += 1
        self.start_time = time.perf_counter()

    def stop(self):
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


def test_diamond_dependencies():
    with A() as a:
        assert a.running is True
        assert a.b1.running is True
        assert a.b2.running is True
        assert a.c.running is True
    assert a.c.start_count == 1
    assert a.c.stop_count == 1
    assert a.c.start_time < a.b1.start_time < a.b2.start_time < a.start_time
    assert a.stop_time < a.b2.stop_time < a.b1.stop_time < a.c.stop_time


def test_c_does_not_stops():
    with A() as a:
        with B(a.c):
            pass
        assert a.c.running is True
    assert a.c.running is False


class StartFailB(BlockingServiceMixin):
    def __init__(self):
        self.start_called = 0
        self.stop_called = 0

    def start(self):
        self.start_called += 1
        raise RuntimeError

    def stop(self):
        self.stop_called += 1


class StartFailA(BlockingServiceMixin):
    def __init__(self):
        self.b = StartFailB()
        self.start_called = 0
        self.stop_called = 0

    @property
    def dependencies(self):
        return [
            self.b,
        ]

    def start(self):
        self.start_called += 1

    def stop(self):
        self.stop_called += 1


def test_start_exception():
    service = StartFailA()
    with pytest.raises(RuntimeError):
        with service:
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


def test_start_groups():
    with Parallel() as parallel:
        pass
    assert all(s.start_count == 1 and s.stop_count == 1 for s in parallel.services)


def test_empty_methods():
    with BlockingServiceMixin():
        pass
