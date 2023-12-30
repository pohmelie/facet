# Facet
Service manager for asyncio (and classic blocking code since version 0.10.0).

[![Github actions status for master branch](https://github.com/pohmelie/facet/actions/workflows/ci.yaml/badge.svg?branch=master)](https://github.com/pohmelie/facet/actions/workflows/ci.yaml)
[![Codecov coverage for master branch](https://codecov.io/gh/pohmelie/facet/branch/master/graph/badge.svg)](https://codecov.io/gh/pohmelie/facet)
[![Pypi version](https://img.shields.io/pypi/v/facet.svg)](https://pypi.org/project/facet/)
[![Pypi downloads count](https://img.shields.io/pypi/dm/facet)](https://pypi.org/project/facet/)

- [Facet](#facet)
    - [Reasons](#reasons)
        - [Asyncio](#asyncio)
        - [Blocking code](#blocking-code)
    - [Features](#features)
    - [License](#license)
    - [Requirements](#requirements)
    - [Usage](#usage)
        - [Asyncio](#asyncio-1)
        - [Blocking code](#blocking-code-1)
    - [API](#api)
        - [Asyncio](#asyncio-2)
            - [`start`](#start)
            - [`stop`](#stop)
            - [`dependencies`](#dependencies)
            - [`add_task`](#add_task)
            - [`run`](#run)
            - [`wait`](#wait)
            - [`graceful_shutdown_timeout`](#graceful_shutdown_timeout)
            - [`running`](#running)
        - [Blocking code](#blocking-code-2)
            - [`start`](#start-1)
            - [`stop`](#stop-1)
            - [`dependencies`](#dependencies-1)
            - [`running`](#running-1)

## Reasons
### Asyncio
[`mode`](https://github.com/ask/mode) tries to do too much job:
- Messy callbacks (`on_start`, `on_started`, `on_crashed`, etc.).
- Inheritance restrict naming and forces `super()` calls.
- Forced logging module and logging configuration.
### Blocking code
- [`ExitStack`](https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack) is too low-level to manage services.
- Common api for async and blocking worlds.

## Features
- Simple (`start`, `stop`, `dependencies` and `add_task`).
- Configurable via inheritance (graceful shutdown timeout).
- Mixin (no `super()` required).
- Requires no runner engine (`Worker`, `Runner`, etc.) just plain `await` or `async with`/`with`.

## License
`facet` is offered under MIT license.

## Requirements
- python 3.11+

Last version with python 3.6+ support is 0.9.1

## Usage

### Asyncio

``` python
import asyncio
from facet import AsyncioServiceMixin

class B(AsyncioServiceMixin):
    def __init__(self):
        self.value = 0

    async def start(self):
        self.value += 1
        print("b started")

    async def stop(self):
        self.value -= 1
        print("b stopped")

class A(AsyncioServiceMixin):
    def __init__(self):
        self.b = B()

    @property
    def dependencies(self):
        return [self.b]

    async def start(self):
        print("a started")

    async def stop(self):
        print("a stopped")

asyncio.run(A().run())
```
This will produce:
```
b started
a started
```
Start and stop order determined by strict rule: **dependencies must be started first and stopped last**. That is why `B` starts before `A`. Since `A` may use `B` in `start` routine.

Hit `ctrl-c` and you will see:
```
a stopped
b stopped
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
class A(AsyncioServiceMixin):
    async def task(self):
        await asyncio.sleep(1)
        print("task done")

    async def start(self):
        self.add_task(self.task())
        print("start done")

asyncio.run(A().run())
```
This will lead to background task creation and handling:
```
start done
task done
```
Any non-handled exception on background task will lead the whole service stack crashed. This is also a key feature to fall down fast and loud.

All background tasks will be cancelled and awaited on service stop.

You can manage dependencies start/stop to start sequently, parallel or mixed. Like this:
``` python
class A(AsyncioServiceMixin):
    def __init__(self):
        self.b = B()
        self.c = C()
        self.d = D()

    @property
    def dependencies(self):
        return [
            [self.b, self.c],
            self.d,
        ]
```
This leads to first `b` and `c` starts parallel, after they successfully started `d` will try to start, and then `a` itself start will be called. And on stop routine `a` stop called first, then `d` stop, then both `b` and `c` stops parallel.

The rule here is **first nesting level is sequential, second nesting level is parallel**

### Blocking code
Since version 0.10.0 `facet` can be used in blocking code with pretty same rules. **But with limited API**. For example:
``` python
from facet import BlockingServiceMixin

class B(BlockingServiceMixin):
    def __init__(self):
        self.value = 0

    def start(self):
        self.value += 1
        print("b started")

    def stop(self):
        self.value -= 1
        print("b stopped")

class A(BlockingServiceMixin):
    def __init__(self):
        self.b = B()

    @property
    def dependencies(self):
        return [self.b]

    def start(self):
        print("a started")

    def stop(self):
        print("a stopped")

with A() as a:
    assert a.b.value == 1
```
This will produce:
```
b started
a started
a stopped
b stopped
```
As you can see, there is no `wait` method. Waiting and background tasks are on user shoulders and technically can be implemented with `concurrent.futures` module. But `facet` do not provide such functionality, since there are a lot of ways to do it: `threading`/`multiprocessing` and their primitives.

Also, there are no «sequential, parallel and mixed starts/stops for dependencies» feature. So, just put dependencies in `dependencies` property as a plain `list` and they will be started/stopped sequentially.

## API
### Asyncio
Here is public methods you get on inheritance/mixin:

#### `start`
``` python
async def start(self):
    pass
```
Start routine.

#### `stop`
``` python
async def stop(self):
    pass
```
Stop routine.

#### `dependencies`
``` python
@property
def dependencies(self) -> list[AsyncioServiceMixin | list[AsyncioServiceMixin]]:
    return []
```
Should return iterable of current service dependencies instances.

#### `add_task`
``` python
def add_task(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
```
Add background task.

#### `run`
``` python
async def run(self) -> None:
```
Run service and wait until it stop.

#### `wait`
``` python
async def wait(self) -> None:
```
Wait for service stop. Service must be started. This is useful when you use service as a context manager.

#### `graceful_shutdown_timeout`
``` python
@property
def graceful_shutdown_timeout(self) -> int:
    return 10
```
How much total time in seconds wait for stop routines. This property can be overriden with subclass:
``` python
class CustomServiceMixin(AsyncioServiceMixin):
    @property
    def graceful_shutdown_timeout(self):
        return 60
```

#### `running`
``` python
@property
def running(self) -> bool:
```
Check if service is running

### Blocking code

#### `start`
``` python
def start(self):
    pass
```
Start routine.

#### `stop`
``` python
def stop(self):
    pass
```
Stop routine.

#### `dependencies`
``` python
@property
def dependencies(self) -> list[BlockingServiceMixin | list[BlockingServiceMixin]]:
    return []
```
Should return iterable of current service dependencies instances.

#### `running`
``` python
@property
def running(self) -> bool:
```
Check if service is running
