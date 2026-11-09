"""Share concurrent reads without caching completed results or sharing objects."""

from __future__ import annotations

import copy
import threading


def _publish_read_snapshot(flight: dict, result, waiters: int) -> None:
    try:
        if waiters:
            flight["result"] = copy.deepcopy(result)
    except BaseException as exc:
        flight["error"] = exc
        raise
    finally:
        flight["event"].set()


def coalesced_read(flights: dict, flights_lock: threading.Lock, key, func):
    """Share one identical read while it is in flight, never after it ends.

    Filesystem-backed reads remain authoritative: this is deliberately an
    in-flight fan-in only, not a completed-result cache. Each caller receives
    independent dictionaries because scope enrichment and UI serialization
    annotate the results after the read completes.

    The copy handed to a *waiting* caller exists so two callers never share
    objects.  The caller that ran the read keeps the object ``func()`` built:
    that result is private to this flight, so copying it on the way out was a
    full traversal of every row for nobody (docs/24 §D1).  When no caller
    joined the flight -- the ordinary single-request case -- nothing is copied
    at all.  When callers did join, one private snapshot is taken *before* the
    owner can annotate its result, and each waiter copies from that snapshot,
    so no two callers ever share a dictionary.

    The waiter count is exact because joining and retiring a flight happen
    under the same lock: once the owner pops the flight, nobody can join it.
    At 2,000 rows the copy this removes was ~22% of ``scopes.list_all()``.
    """
    with flights_lock:
        flight = flights.get(key)
        if flight is None:
            flight = {"event": threading.Event(), "waiters": 0}
            flights[key] = flight
            owner = True
        else:
            flight["waiters"] = flight.get("waiters", 0) + 1
            owner = False
    if owner:
        try:
            result = func()
        except BaseException as exc:
            # ``BaseException``, not ``Exception``: a KeyboardInterrupt inside
            # the read used to skip this cleanup, leaving the flight registered
            # with its event never set -- so the *next* caller for that key
            # waited forever.  Because list/search/stats/doctor coalesce on
            # fixed keys, one Ctrl-C permanently wedged that endpoint.
            with flights_lock:
                flight["error"] = exc
                flights.pop(key, None)
                flight["event"].set()
            raise
        with flights_lock:
            flights.pop(key, None)
            waiters = flight.get("waiters", 0)
        # The flight is retired, so the count cannot grow; the copy runs
        # outside the shared lock so it never stalls an unrelated flight.
        _publish_read_snapshot(flight, result, waiters)
        return result
    flight["event"].wait()
    if flight.get("error") is not None:
        raise flight["error"]
    return copy.deepcopy(flight["result"])
