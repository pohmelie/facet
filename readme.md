# Facet
[![Travis status for master branch](https://travis-ci.com/pohmelie/facet.svg?branch=master)](https://travis-ci.com/pohmelie/facet)
[![Codecov coverage for master branch](https://codecov.io/gh/pohmelie/facet/branch/master/graph/badge.svg)](https://codecov.io/gh/pohmelie/facet)
[![Pypi version](https://img.shields.io/pypi/v/facet.svg)](https://pypi.org/project/facet/)
[![Pypi downloads count](https://img.shields.io/pypi/dm/facet)](https://pypi.org/project/facet/)

Service manager for asyncio.

# Reason
[`mode`](https://github.com/ask/mode) tries to do too much job:
- Messy callbacks (`on_start`, `on_started`, `on_crashed`, etc.).
- Inheritance restrict naming and forces `super()` calls.
- Forced logging module and logging configuration.

# Features
- Simple (`start`, `stop`, `dependencies` and `add_task`).
- Configurable via inheritance (graceful shutdown timeout, logging).
- Mixin (no `super()` required).
- Requires no runner engine (`Worker`, `Runner`, etc.) just plain `await` or `async with`.

# License
`facet` is offered under MIT license.

# Requirements
* python 3.7+

# Usage
``` python
import asyncio
import logging

from facet import ServiceMixin


class B(ServiceMixin):

    def __init__(self):
        self.value = 0

    async def start(self):
        self.value += 1

    async def stop(self):
        self.value -= 1


class A(ServiceMixin):

    def __init__(self):
        self.b = B()

    @property
    def dependencies(self):
        return [self.b]


logging.basicConfig(level=logging.DEBUG)
asyncio.run(A().run())
```
This will produce:
```
INFO:facet:[B] - service started
INFO:facet:[A] - service started
```
Start and stop order determined by strict rule: **dependencies must be started first and stopped last**. That is why `B` starts before `A`. Since `A` may use `B` in `start` routine.

Hit `ctrl-c` and you will see:
```
INFO:facet:[A] - service stopped
INFO:facet:[B] - service stopped
Traceback (most recent call last):
  ...
KeyboardInterrupt
```
Stop order is reversed, since `A` may use `B` in `stop` routine. Any raised exception propagates to upper context. `facet` do not trying to be too smart.

Service can be used as a context manager. Instead of
``` python
asyncio.run(A().run())
```
Code can look like:
``` python
async def main():
    async with A() as a:
        assert a.b.value == 1
        await a.wait()

asyncio.run(main())
```

Another service feature is `add_task` method:
``` python
class A(ServiceMixin):

    async def task(self):
        await asyncio.sleep(1)
        logging.info("task done")

    async def start(self):
        await self.add_task(self.task())
        logging.info("start done")


logging.basicConfig(level=logging.DEBUG)
asyncio.run(A().run())
```
This will lead to background task creation and handling:
```
INFO:root:start done
INFO:facet:[A] - service started
INFO:root:task done
```
Any non-handled exception on background task will lead the whole service stack crashed. This is also a key feature to fall down fast and loud.

All background tasks will be cancelled and awaited on service stop.

# API
Here is public methods you get on inheritance/mixin:
## `wait`
``` python
async def wait(self):
```
Wait for service stop. Service must be started. This is useful when you use service as a context manager.

## `run`
``` python
async def run(self):
```
Run service and wait until it stop.

## `graceful_shutdown_timeout`
``` python
@property
def graceful_shutdown_timeout(self):
    return 10
```
How much total time in seconds wait for stop routines. This property can be overriden with subclass:
``` python
class CustomServiceMixin(ServiceMixin):
    @property
    def graceful_shutdown_timeout(self):
        return 60
```

## `dependencies`
``` python
@property
def dependencies(self):
    return []
```
Should return iterable of current service dependencies instances.

## `running`
``` python
@property
def running(self):
```
Check if service is running

## `add_task`
``` python
async def add_task(self, coro):
```
Add background task.

## `start`
``` python
async def start(self):
    pass
```
Start routine.

## `stop`
``` python
async def stop(self):
    pass
```
Stop routine.

## `log`
``` python
async def log(self, level, message, *, exc_info=None):
```
Logging routine. Should be overridden in subclass in the same way as `graceful_shutdown_timeout` to handle non-standard logging module/engine.
