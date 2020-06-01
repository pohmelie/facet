from asyncio import Future, Lock, Task, create_task, gather, wait, wait_for

__all__ = ("ServiceMixin",)
__version__ = "0.1.0"
version = tuple(map(int, __version__.split(".")))


class ServiceMixin:

    __running = False
    __tasks = ()
    __start_lock = None
    __stop_lock = None
    __exit_point = None

    async def __wait_with_cancellation_on_fail(self, tasks):
        try:
            await gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await wait(tasks)

    async def __start_dependencies(self):
        self.__tasks = []
        starts = []
        for dependency in self.dependencies:
            # propagate exit point
            dependency._ServiceMixin__exit_point = self.__exit_point
            starts.append(create_task(dependency.__aenter__()))
        if starts:
            await self.__wait_with_cancellation_on_fail(starts)

    async def __stop_dependencies(self):
        stops = []
        for task in self.__tasks:
            if not task.done():
                task.cancel()
                stops.append(task)
        for dependency in self.dependencies:
            stops.append(create_task(dependency.__aexit__(None, None, None)))
        if stops:
            await self.__wait_with_cancellation_on_fail(stops)

    async def __start(self):
        if self.__exit_point is None:
            self.__exit_point = Future()
        await self.__start_dependencies()
        try:
            await self.start()
        except:  # noqa
            await self.__stop_dependencies()
            raise
        else:
            self.__running = True

    async def __stop(self):
        self.__running = False
        try:
            await self.stop()
        finally:
            await self.__stop_dependencies()
        self.__exit_point = None

    async def __aenter__(self):
        if self.__start_lock is None:
            self.__start_lock = Lock()
        async with self.__start_lock:
            if not self.__running:
                await self.__start()
        return self

    async def __aexit__(self, *exc_info):
        if self.__stop_lock is None:
            self.__stop_lock = Lock()
        async with self.__stop_lock:
            if self.__running:
                await wait_for(self.__stop(), timeout=self.graceful_shutdown_timeout)

    def __task_callback(self, task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self.__exit_point.set_exception(exc)

    async def wait(self):
        await self.__exit_point

    async def run(self):
        async with self:
            await self.wait()

    @property
    def graceful_shutdown_timeout(self):
        return 10

    @property
    def dependencies(self):
        return []

    @property
    def running(self) -> bool:
        return self.__running

    def add_task(self, coro) -> Task:
        task = create_task(coro)
        task.add_done_callback(self.__task_callback)
        self.__tasks.append(task)
        return task

    async def start(self):
        pass

    async def stop(self):
        pass
